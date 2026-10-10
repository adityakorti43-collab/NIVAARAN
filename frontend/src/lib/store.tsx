import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, authEvents } from "./api";
import type { AuthUser, ClaimBundle, ClaimListEntry, DocumentRecord } from "./types";

interface AppState {
  user: AuthUser | null;
  authLoading: boolean;
  setUser: (u: AuthUser | null) => void;
  signOut: () => Promise<void>;
  claims: ClaimListEntry[];
  documents: DocumentRecord[];
  activeClaimId: string | null;
  bundle: ClaimBundle | null;
  loading: boolean;
  error: string | null;
  setActiveClaimId: (id: string | null) => void;
  refresh: () => Promise<void>;
  refreshClaim: () => Promise<void>;
  selection: Record<string, string>;
  setSelection: (s: Record<string, string>) => void;
  copilotOpen: boolean;
  setCopilotOpen: (v: boolean) => void;
  askCopilot: (q: string) => void;
  pendingQuestion: string | null;
  clearPending: () => void;
}

const Ctx = createContext<AppState | null>(null);
const KEY = "nivaaran.activeClaim";
const readKey = (): string | null => { try { return localStorage.getItem(KEY); } catch { return null; } };

export function AppProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [claims, setClaims] = useState<ClaimListEntry[]>([]);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [activeClaimId, setActive] = useState<string | null>(readKey);
  const [bundle, setBundle] = useState<ClaimBundle | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selection, setSelection] = useState<Record<string, string>>({});
  const [copilotOpen, setCopilotOpen] = useState(false);
  const [pendingQuestion, setPending] = useState<string | null>(null);
  const askCopilot = useCallback((q: string) => { setPending(q); setCopilotOpen(true); }, []);
  const clearPending = useCallback(() => setPending(null), []);

  const setActiveClaimId = useCallback((id: string | null) => {
    setActive(id);
    try { id ? localStorage.setItem(KEY, id) : localStorage.removeItem(KEY); } catch { /* storage unavailable */ }
  }, []);

  // Session is resolved by the server from an HttpOnly cookie; the browser never sees the token.
  useEffect(() => {
    api.me().then((r) => setUser(r.user)).catch(() => setUser(null)).finally(() => setAuthLoading(false));
    const onUnauth = () => { setUser(null); setClaims([]); setDocuments([]); setBundle(null); };
    authEvents.addEventListener("unauthorized", onUnauth);
    return () => authEvents.removeEventListener("unauthorized", onUnauth);
  }, []);

  const refresh = useCallback(async () => {
    if (!user) { setLoading(false); return; }
    try {
      const [c, d] = await Promise.all([api.claims(), api.documents()]);
      setClaims(c);
      setDocuments(d);
      setError(null);
      if (c.length && (!activeClaimId || !c.some((x) => x.claim_id === activeClaimId))) setActiveClaimId(c[c.length - 1].claim_id);
      if (!c.length) setActiveClaimId(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [user, activeClaimId, setActiveClaimId]);

  const refreshClaim = useCallback(async () => {
    if (!user || !activeClaimId) { setBundle(null); return; }
    try { setBundle(await api.claim(activeClaimId)); } catch (e) { setBundle(null); setError((e as Error).message); }
  }, [user, activeClaimId]);

  const signOut = useCallback(async () => {
    try { await api.logout(); } finally {
      setUser(null); setClaims([]); setDocuments([]); setBundle(null); setActiveClaimId(null);
    }
  }, [setActiveClaimId]);

  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => { refreshClaim(); }, [refreshClaim]);

  return (
    <Ctx.Provider value={{ user, authLoading, setUser, signOut, claims, documents, activeClaimId, bundle, loading, error, setActiveClaimId,
      refresh, refreshClaim, selection, setSelection, copilotOpen, setCopilotOpen, askCopilot, pendingQuestion, clearPending }}>
      {children}
    </Ctx.Provider>
  );
}

export function useApp() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useApp outside provider");
  return v;
}
