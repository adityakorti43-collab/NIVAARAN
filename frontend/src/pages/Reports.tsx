import { Download, FileJson, FileText } from "lucide-react";
import { NeedClaim } from "../components/NeedClaim";
import { Disclaimer, PageHeader, Range, Section, SyntheticBanner, Tag } from "../components/ui";
import { api } from "../lib/api";
import { inr } from "../lib/format";

const CONTENTS = ["Claim summary", "Selected policy version and why", "Itemised adjudication ledger", "Estimated payable range",
  "Potential patient responsibility", "Evidence citations with exact excerpts and pages", "Calculation trace", "Unresolved questions and review requirements",
  "Bill arithmetic checks", "Limitations and disclaimer"];

export default function Reports() {
  return (
    <div>
      <PageHeader eyebrow="Reports" title="Export the claim analysis"
        description="Reports contain only what the pipeline produced from your documents: cited clauses, the deterministic calculation and every unresolved question. Synthetic and hypothetical content is labelled." />
      <NeedClaim>{(b) => {
        const a = b.analysis;
        return (
          <>
            <SyntheticBanner show={a.synthetic} />
            <div className="grid gap-5 lg:grid-cols-[1fr_360px]">
              <Section title={b.claim.title} description={`Analysis ${a.analysis_id} · ${new Date(a.created_at).toLocaleString("en-IN")} · ${a.version.selected?.label ?? "no version"}`}>
                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="rounded-lg bg-paper p-3"><p className="eyebrow">Billed</p><p className="mt-1 font-semibold num">{inr(a.summary.total_billed)}</p></div>
                  <div className="rounded-lg bg-paper p-3"><p className="eyebrow">Est. payable</p><p className="mt-1 font-semibold num"><Range low={a.summary.payable_low} high={a.summary.payable_high} /></p></div>
                  <div className="rounded-lg bg-paper p-3"><p className="eyebrow">Out-of-pocket</p><p className="mt-1 font-semibold num"><Range low={a.summary.patient_low} high={a.summary.patient_high} /></p></div>
                </div>
                <p className="eyebrow mt-5 mb-2">Included in the report</p>
                <ul className="grid gap-1.5 text-sm sm:grid-cols-2">{CONTENTS.map((c) => <li key={c} className="flex items-center gap-2"><span className="size-1.5 rounded-full bg-accent" aria-hidden />{c}</li>)}</ul>
                <p className="mt-4 text-sm text-muted">{a.rows.filter((r) => r.manual_review).length} item(s) are flagged for manual review and are reported as unresolved, not as covered or excluded.</p>
              </Section>
              <Section title="Download">
                <div className="space-y-2">
                  <a className="btn-primary w-full" href={api.reportUrl(b.claim.claim_id, "pdf")} download data-testid="download-pdf"><FileText className="size-4" /> PDF report <Download className="ml-auto size-4" /></a>
                  <a className="btn-secondary w-full" href={api.reportUrl(b.claim.claim_id, "json")} download data-testid="download-json"><FileJson className="size-4" /> Structured JSON <Download className="ml-auto size-4" /></a>
                </div>
                <p className="mt-3 text-xs text-muted">The JSON export includes the full ledger, evidence, adjustments, trace, recorded comparisons and document fingerprints (SHA-256).</p>
                {a.synthetic && <Tag tone="conditional" className="mt-3">Report will be labelled SYNTHETIC</Tag>}
                <Disclaimer className="mt-4" />
              </Section>
            </div>
          </>
        );
      }}</NeedClaim>
    </div>
  );
}
