import os
import sys
import tempfile
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
os.environ["NIVAARAN_DATA_DIR"] = tempfile.mkdtemp(prefix="nivaaran-test-")
os.environ["NIVAARAN_NO_DOTENV"] = "1"     # never pick up the operator's real credentials in tests
os.environ["NIVAARAN_ENABLE_DEMO"] = "1"   # the synthetic demo seeding is test-only; it is off in production

from demo import content as C  # noqa: E402
from demo.generate_demo import OUT_DIR, _render_clauses, generate  # noqa: E402

from app.bills.parse import build_bill, parse_bill_bytes  # noqa: E402
from app.ingestion.documents import process_policy_document  # noqa: E402
from app.models import Claim, DocType  # noqa: E402


@pytest.fixture(scope="session")
def demo_paths():
    if not (OUT_DIR / "synthetic_policy_v1.pdf").exists():
        generate()
    return {"policy": OUT_DIR / "synthetic_policy_v1.pdf", "endorsement": OUT_DIR / "synthetic_endorsement_E01.pdf",
            "bill": OUT_DIR / "synthetic_bill_appendicectomy.pdf"}


@pytest.fixture(scope="session")
def policy(demo_paths):
    return process_policy_document(demo_paths["policy"].read_bytes(), "policy.pdf", DocType.policy, True)


@pytest.fixture(scope="session")
def endorsement(demo_paths):
    return process_policy_document(demo_paths["endorsement"].read_bytes(), "e01.pdf", DocType.endorsement, True)


@pytest.fixture(scope="session")
def bill(demo_paths):
    return build_bill(parse_bill_bytes(demo_paths["bill"].read_bytes(), "pdf"), synthetic=True)


@pytest.fixture()
def make_claim(policy, endorsement, bill):
    def _make(with_endorsement=True, **kw):
        args = dict(claim_id="t1", title="Laparoscopic appendicectomy", policy_document_id=policy.document_id,
                    endorsement_ids=[endorsement.document_id] if with_endorsement else [], bill=bill,
                    admission_date=bill.admission_date, discharge_date=bill.discharge_date, diagnosis=bill.diagnosis)
        args.update(kw)
        return Claim(**args), {policy.document_id: policy, endorsement.document_id: endorsement}
    return _make


def make_pdf(tmp_path: Path, name: str, header: list[str], pages: list) -> bytes:
    p = tmp_path / name
    _render_clauses(p, header, pages)
    return p.read_bytes()


def endorsement_pdf(tmp_path, name, number="E-09", policy_no="SYN-HP-2025-000123", effective="01-Dec-2025",
                    applies="Hospitalisations commencing on or after 01-Dec-2025", clauses=None):
    header = [f"Endorsement No. {number} to Policy {policy_no}", f"Policy Number: {policy_no}",
              "Endorsement Issue Date: 20-Nov-2025"]
    if effective:
        header.append(f"Endorsement Effective Date: {effective}")
    if applies:
        header.append(f"Applies To: {applies}")
    clauses = clauses or [("X1.1 Revised Co-payment", "This endorsement replaces clause 5.2. A co-payment of 20% applies to the admissible claim amount after the deductible.")]
    return make_pdf(tmp_path, name, header, [[("Endorsement Provisions", None)] + clauses])
