import { CheckCircle2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ErrorNote, PageHeader, Section } from "../components/ui";
import { api } from "../lib/api";
import { isNativeApp } from "../lib/native";
import { useApp } from "../lib/store";

export default function Settings() {
  const { user, setUser, signOut } = useApp();
  const nav = useNavigate();
  const [params, setParams] = useSearchParams();
  const [name, setName] = useState(user?.name ?? "");
  const [msg, setMsg] = useState<string | null>(null), [err, setErr] = useState<string | null>(null);
  const [confirm, setConfirm] = useState("");

  // Returning from Google's consent screen after "Link Google".
  useEffect(() => {
    if (params.get("linked") === "google") {
      api.me().then((r) => { setUser(r.user); setMsg("Google account linked. Use it to sign in from now on."); }).catch(() => {});
      setParams({}, { replace: true });
    }
  }, [params, setParams, setUser]);

  if (!user) return null;
  return (
    <div>
      <PageHeader eyebrow="Settings" title="Your account" description="Your profile, the ways you sign in, and your data." />
      {msg && <p role="status" className="mb-4 flex items-center gap-2 rounded-xl border border-covered/25 bg-covered-bg px-3 py-2.5 text-sm text-covered"><CheckCircle2 className="size-4" />{msg}</p>}
      <ErrorNote error={err} className="mb-4" />
      <div className="grid gap-5 lg:grid-cols-2">
        <Section title="Profile" description="Optional. Used only to greet you.">
          <form className="space-y-3" onSubmit={async (e) => { e.preventDefault(); setErr(null); setMsg(null); try { setUser((await api.updateProfile(name.trim() || null)).user); setMsg("Profile saved."); } catch (x) { setErr((x as Error).message); } }}>
            <label className="block"><span className="label">Name</span><input className="input" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} placeholder="Add your name" data-testid="profile-name" /></label>
            {user.email && <label className="block"><span className="label">Email {user.email_verified ? "(verified by Google)" : ""}</span><input className="input" value={user.email} disabled /></label>}
            <button className="btn-primary">Save profile</button>
          </form>
        </Section>

        <Section title="Sign-in" description="You sign in with your Google account.">
          <div className="flex items-center justify-between gap-3" data-testid="method-google">
            <div><p className="text-sm font-medium text-ink">Google</p><p className="text-xs text-muted">{user.google_linked ? (user.email ?? "Linked") : "Not linked yet: link it so you can sign in again later."}</p></div>
            {!user.google_linked && (isNativeApp()
              ? <span className="max-w-[200px] text-right text-[12px] text-muted">Link Google from the Nivaaran website (Settings), then sign in here with it.</span>
              : <a className="btn-primary" href={api.googleStartUrl("/settings", true)}>Link Google</a>)}
          </div>
        </Section>

        <Section title="Session">
          <p className="text-sm text-muted">Signing out ends this session on the server; the cookie stops working immediately.</p>
          <button className="btn-secondary mt-3" onClick={async () => { await signOut(); nav("/"); }}>Sign out</button>
        </Section>
        <Section title="Delete account" description="Deletes your account, documents, claims, analyses, chats, scenarios and report records. This cannot be undone.">
          <label className="block"><span className="label">Type DELETE to confirm</span><input className="input" value={confirm} onChange={(e) => setConfirm(e.target.value)} /></label>
          <button className="btn mt-3 border border-conflict/40 text-conflict hover:bg-conflict-bg" disabled={confirm !== "DELETE"}
            onClick={async () => { try { await api.deleteAccount(); setUser(null); nav("/"); } catch (x) { setErr((x as Error).message); } }}>Delete my account</button>
        </Section>
      </div>
    </div>
  );
}
