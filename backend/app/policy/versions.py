"""Policy-version registry: which policy wording + endorsements apply on a treatment date.

Rules (all derived from documents, never from upload order):
- The base version starts at the policy effective date and ends at the policy period end.
- Each endorsement with a parseable effective date inside the policy period starts a new cumulative version.
- Endorsements are applied prospectively only when the documents say so (an endorsement "applies to
  hospitalisations on or after" statement, or a policy applicability clause). Otherwise the case is
  flagged for review instead of guessing.
- Missing dates, policy-number mismatches, overlapping replacements and out-of-period dates are reported
  as conflicts.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from app.models import NOT_FOUND, Clause, ClauseCategory, DocumentRecord, PolicyVersion, VersionSelection


def _d(v: str | None) -> Optional[date]:
    if not v or v == NOT_FOUND:
        return None
    try:
        return date.fromisoformat(v)
    except ValueError:
        return None


def _policy_applicability_clause(policy: DocumentRecord) -> Optional[Clause]:
    return next((c for c in policy.clauses if c.interpretation.category == ClauseCategory.applicability), None)


def build_versions(policy: DocumentRecord, endorsements: list[DocumentRecord]) -> tuple[list[PolicyVersion], list[str]]:
    conflicts: list[str] = []
    pm = policy.metadata
    p_from = _d(pm.get("effective_date")) or _d(pm.get("policy_period_from"))
    p_to = _d(pm.get("policy_period_to"))
    if not p_from:
        conflicts.append("Policy effective date not found in the provided documents; version applicability cannot be dated.")
    applic = _policy_applicability_clause(policy)
    by_section = {c.section: c for c in policy.clauses}

    usable: list[tuple[date, DocumentRecord]] = []
    for e in endorsements:
        em = e.metadata
        num = em.get("endorsement_number", e.filename)
        if em.get("policy_number") not in (None, NOT_FOUND) and pm.get("policy_number") not in (None, NOT_FOUND) \
                and em["policy_number"] != pm["policy_number"]:
            conflicts.append(f"Endorsement {num} refers to policy {em['policy_number']}, not {pm['policy_number']}; it was not applied.")
            continue
        eff = _d(em.get("effective_date"))
        if not eff:
            conflicts.append(f"Endorsement {num} has no effective date in the provided documents; its applicability cannot be determined.")
            continue
        if (p_from and eff < p_from) or (p_to and eff > p_to):
            conflicts.append(f"Endorsement {num} effective date {eff} falls outside the policy period; it was not applied.")
            continue
        retro = em.get("retrospective", "unclear")
        if retro == "yes":
            conflicts.append(f"Endorsement {num} appears to claim retrospective effect; precedence requires manual review.")
        elif retro == "unclear" and not applic:
            conflicts.append(f"Endorsement {num} does not state whether it applies retrospectively and the policy has no applicability clause.")
        usable.append((eff, e))
    usable.sort(key=lambda t: (t[0], t[1].metadata.get("issue_date", "")))

    # Overlapping replacements of the same section on the same effective date are a genuine conflict.
    seen: dict[tuple[date, str], str] = {}
    for eff, e in usable:
        for c in e.clauses:
            for sec in c.interpretation.replaces:
                key = (eff, sec)
                if key in seen and seen[key] != e.document_id:
                    conflicts.append(f"Two endorsements effective {eff} both replace clause {sec}; precedence is unresolved.")
                seen[key] = e.document_id

    versions: list[PolicyVersion] = []
    starts = [p_from] + [eff for eff, _ in usable]
    applied: list[DocumentRecord] = []
    superseded: dict[str, str] = {}
    for i, start in enumerate(starts):
        notes = []
        if i > 0:
            eff, e = usable[i - 1]
            applied = applied + [e]
            for c in e.clauses:
                for sec in c.interpretation.replaces:
                    old = by_section.get(sec)
                    if old:
                        # A later endorsement replacing the same section also supersedes the earlier replacement.
                        prev = superseded.get(old.clause_id)
                        if prev:
                            superseded[prev] = c.clause_id
                        superseded[old.clause_id] = c.clause_id
                        notes.append(f"Clause {sec} replaced by {c.section} ({e.metadata.get('endorsement_number', '')}).")
                    else:
                        notes.append(f"{c.section} says it replaces clause {sec}, which was not found in the policy wording.")
            basis = (f"endorsement states it applies to '{e.metadata.get('applies_to')}'"
                     if e.metadata.get("retrospective") == "no" else
                     f"policy clause {applic.section} states endorsements are not retrospective" if applic else
                     "applicability unclear")
            notes.append(f"Starts on endorsement effective date {eff} ({basis}).")
        end = (starts[i + 1] - timedelta(days=1)) if i + 1 < len(starts) and starts[i + 1] else p_to
        label = "Base policy wording" if i == 0 else "Policy + " + " + ".join(
            d.metadata.get("endorsement_number", d.filename) for d in applied)
        versions.append(PolicyVersion(
            version_id=f"{policy.document_id}:v{i + 1}", label=label, policy_document_id=policy.document_id,
            endorsement_ids=[d.document_id for d in applied], effective_from=start, effective_to=end,
            superseded_sections=dict(superseded), notes=notes))
    return versions, conflicts


def select_version(treatment_date: Optional[date], versions: list[PolicyVersion], conflicts: list[str],
                   override_id: Optional[str] = None) -> VersionSelection:
    if override_id:
        chosen = next((v for v in versions if v.version_id == override_id), None)
        if not chosen:
            raise ValueError(f"Unknown policy version {override_id}")
        return VersionSelection(treatment_date=treatment_date, selected=chosen,
                                alternatives=[v for v in versions if v.version_id != override_id],
                                reasons=[f"HYPOTHETICAL: version '{chosen.label}' was selected manually in the What-If Lab, "
                                         "not by the treatment date."],
                                conflicts=conflicts, review_required=bool(conflicts), overridden=True)
    if not treatment_date:
        return VersionSelection(treatment_date=None, selected=None, alternatives=versions,
                                reasons=["Treatment date not provided; the applicable version cannot be determined."],
                                conflicts=conflicts, review_required=True)
    matches = [v for v in versions if v.effective_from and v.effective_from <= treatment_date
               and (v.effective_to is None or treatment_date <= v.effective_to)]
    if not matches and versions and all(v.effective_from is None for v in versions):
        # Nothing in the documents dates the policy (common for schedules, extracts and scans). Apply the base
        # wording rather than refusing every item, and say clearly that the dates are unconfirmed.
        base = versions[0]
        return VersionSelection(treatment_date=treatment_date, selected=base, alternatives=versions[1:],
                                reasons=[f"The documents do not state when this policy is in force, so the base wording '{base.label}' "
                                         f"is applied. Confirm the policy covered {treatment_date} before relying on this estimate."],
                                conflicts=conflicts, review_required=True)
    if not matches:
        return VersionSelection(treatment_date=treatment_date, selected=None, alternatives=versions,
                                reasons=[f"Treatment date {treatment_date} is outside every documented policy version period."],
                                conflicts=conflicts, review_required=True)
    chosen = matches[-1]
    reasons = [f"Treatment (admission) date {treatment_date} falls within '{chosen.label}' "
               f"({chosen.effective_from} to {chosen.effective_to or 'open'})."]
    reasons += chosen.notes
    later = [v for v in versions if v.effective_from and v.effective_from > treatment_date]
    if later:
        reasons.append("Later version(s) " + ", ".join(f"'{v.label}' from {v.effective_from}" for v in later)
                       + " do not apply because they start after the treatment date.")
    return VersionSelection(treatment_date=treatment_date, selected=chosen,
                            alternatives=[v for v in versions if v is not chosen], reasons=reasons,
                            conflicts=conflicts, review_required=bool(conflicts))


def active_clauses(version: PolicyVersion, docs: dict[str, DocumentRecord]) -> list[Clause]:
    policy = docs[version.policy_document_id]
    out = [c for c in policy.clauses if c.clause_id not in version.superseded_sections]
    for eid in version.endorsement_ids:
        out += [c for c in docs[eid].clauses
                if c.clause_id not in version.superseded_sections]
    return out
