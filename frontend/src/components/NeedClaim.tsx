import { ArrowRight, FileUp, ReceiptText } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useApp } from "../lib/store";
import type { ClaimBundle, DocumentRecord } from "../lib/types";
import { EmptyState, ErrorNote, PageSkeleton } from "./ui";

/**
 * Renders children when an analysed claim is active. Without a claim, a page can still be useful from the policy alone
 * (`policyView`); without a policy either, an actionable empty state.
 */
export function NeedClaim({ children, policyView }: {
  children: (b: ClaimBundle & { analysis: NonNullable<ClaimBundle["analysis"]> }) => ReactNode;
  policyView?: (policy: DocumentRecord) => ReactNode;
}) {
  const { bundle, loading, activeClaimId, error, documents } = useApp();
  const policies = documents.filter((d) => d.doc_type === "policy");
  const [pid, setPid] = useState<string | null>(null);
  if (loading || (activeClaimId && !bundle && !error)) return <PageSkeleton />;
  if (error && !bundle && !policyView) return <ErrorNote error={error} />;
  if (!bundle || !bundle.analysis) {
    if (policies.length && policyView) {
      const policy = policies.find((p) => p.document_id === pid) ?? policies[0];
      return (
        <div>
          <div className="mb-5 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-[6px] border border-line bg-card px-4 py-3">
            <ReceiptText className="size-4 shrink-0 text-accent" aria-hidden />
            <p className="min-w-0 flex-1 text-[13px] text-text">
              <span className="font-semibold text-ink">Working from your policy.</span>{" "}
              <span className="text-muted">Once you analyse a hospital bill, this page also covers that claim.</span>
            </p>
            {policies.length > 1 && (
              <select className="input h-9 w-auto max-w-[280px] text-[13px]" value={policy.document_id} onChange={(e) => setPid(e.target.value)} aria-label="Policy">
                {policies.map((p) => <option key={p.document_id} value={p.document_id}>{p.metadata.title ?? p.filename}</option>)}
              </select>)}
            <Link to="/claim" className="btn-ghost h-9 px-3 text-[13px]">Analyse a bill <ArrowRight className="size-3.5" /></Link>
          </div>
          {policyView(policy)}
        </div>
      );
    }
    const hasPolicy = policies.length > 0;
    return (
      <EmptyState icon={ReceiptText} title={hasPolicy ? "No claim analysed yet" : "Start with your policy"}
        actions={hasPolicy ? <Link to="/claim" className="btn-primary">Create a claim</Link>
          : <><Link to="/documents" className="btn-primary"><FileUp className="size-4" /> Upload your policy</Link><Link to="/claim" className="btn-secondary">Create a claim</Link></>}>
        {hasPolicy ? "Create a claim with your hospital bill to see what your policy is likely to pay." : "Upload your policy wording. Every page here starts working from it straight away."}
      </EmptyState>
    );
  }
  return <>{children(bundle as ClaimBundle & { analysis: NonNullable<ClaimBundle["analysis"]> })}</>;
}
