import { ReceiptText } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useApp } from "../lib/store";
import type { ClaimBundle } from "../lib/types";
import { EmptyState, ErrorNote, PageSkeleton, Spinner } from "./ui";

export function LoadDemoButton({ className = "btn-primary", label = "Load synthetic demo" }: { className?: string; label?: string }) {
  const { refresh, setActiveClaimId } = useApp();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  return (
    <>
      <button className={className} disabled={busy} data-testid="load-demo" onClick={async () => {
        setBusy(true); setErr(null);
        try {
          const r = await api.loadDemo();  // adds the synthetic case to your own workspace
          setActiveClaimId(r.claim_id);
          await refresh();
        } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
      }}>{busy ? <Spinner label="Processing demo documents…" /> : label}</button>
      {err && <ErrorNote error={err} className="mt-3 w-full" />}
    </>
  );
}

/** Renders children only when an analysed claim is active; otherwise an actionable empty state. */
export function NeedClaim({ children }: { children: (b: ClaimBundle & { analysis: NonNullable<ClaimBundle["analysis"]> }) => ReactNode }) {
  const { bundle, loading, activeClaimId, error } = useApp();
  if (loading || (activeClaimId && !bundle && !error)) return <PageSkeleton />;
  if (error && !bundle) return <ErrorNote error={error} />;
  if (!bundle || !bundle.analysis) {
    return (
      <EmptyState icon={ReceiptText} title="No claim analysed yet"
        actions={<><LoadDemoButton /><Link to="/claim" className="btn-secondary">Create a claim</Link></>}>
        Upload a policy and an itemised bill in the claim workspace, or load the clearly labelled synthetic demo.
      </EmptyState>
    );
  }
  return <>{children(bundle as ClaimBundle & { analysis: NonNullable<ClaimBundle["analysis"]> })}</>;
}
