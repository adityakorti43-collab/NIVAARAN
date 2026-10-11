"""Generate the SYNTHETIC demonstration PDFs (policy, endorsement, itemised bill).

Run from the backend directory:  python -m demo.generate_demo
The generated PDFs are then processed by the normal ingestion pipeline — nothing downstream is hard-coded.
"""
from __future__ import annotations

from pathlib import Path

import pymupdf as fitz

from demo import content as C

OUT_DIR = Path(__file__).resolve().parent / "documents"
PAGE_W, PAGE_H = fitz.paper_size("a4")
MARGIN = 56
BODY_W = PAGE_W - 2 * MARGIN


def _wrap(text: str, font: str, size: float, width: float) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if fitz.get_text_length(trial, fontname=font, fontsize=size) <= width:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


class Writer:
    def __init__(self, doc: fitz.Document, total_pages: int, banner: str | None = None, footer: str | None = None):
        self.doc, self.total, self.page, self.y, self.n = doc, total_pages, None, 0.0, 0
        # banner=None keeps the orange SYNTHETIC banner; banner="" omits it (sample documents use a quiet footer instead)
        self.banner = C.BANNER if banner is None else banner
        self.footer = footer or "synthetic demonstration material"

    def new_page(self):
        self.n += 1
        self.page = self.doc.new_page(width=PAGE_W, height=PAGE_H)
        if self.banner:
            self.page.draw_rect(fitz.Rect(0, 0, PAGE_W, 30), color=None, fill=(0.98, 0.93, 0.85))
            self.page.insert_text((MARGIN, 20), self.banner, fontname="hebo", fontsize=8.5, color=(0.55, 0.25, 0.05))
        self.page.insert_text((MARGIN, PAGE_H - 28), f"Page {self.n} of {self.total} - {self.footer}",
                              fontname="helv", fontsize=8, color=(0.4, 0.4, 0.4))
        self.y = 60

    def line(self, text: str, font="helv", size=10.0, gap=3.0, color=(0.1, 0.1, 0.12), x=MARGIN):
        for ln in _wrap(text, font, size, BODY_W - (x - MARGIN)):
            self.page.insert_text((x, self.y + size), ln, fontname=font, fontsize=size, color=color)
            self.y += size + gap

    def space(self, h: float):
        self.y += h


def _render_clauses(path: Path, header: list[str], pages: list, title_size=14, banner: str | None = None, footer: str | None = None,
                    subject: str = "SYNTHETIC demonstration document"):
    doc = fitz.open()
    w = Writer(doc, len(pages), banner, footer)
    for i, blocks in enumerate(pages):
        w.new_page()
        if i == 0:
            w.line(header[0], font="hebo", size=title_size, gap=6)
            for h in header[1:]:
                w.line(h, size=10)
            w.space(10)
        for heading, body in blocks:
            if body is None:
                w.space(6)
                w.line(heading, font="hebo", size=12, gap=5, color=(0.05, 0.2, 0.3))
                continue
            w.line(heading, font="hebo", size=10.5, gap=3)
            w.line(body, size=10, gap=3)
            w.space(7)
    doc.set_metadata({"title": header[0], "subject": subject, "creator": "Nivaaran document generator"})
    doc.save(path)
    doc.close()


def _render_bill(path: Path):
    doc = fitz.open()
    w = Writer(doc, 1)
    w.new_page()
    w.line(C.BILL_HEADER[0], font="hebo", size=14, gap=6)
    for h in C.BILL_HEADER[1:]:
        w.line(h, size=10)
    w.space(12)
    cols = [MARGIN, MARGIN + 22, MARGIN + 238, MARGIN + 312, MARGIN + 350, MARGIN + 420]
    heads = ["No", "Description", "Date", "Qty", "Rate (INR)", "Amount (INR)"]
    for x, h in zip(cols, heads):
        w.page.insert_text((x, w.y + 10), h, fontname="hebo", fontsize=9)
    w.y += 16
    w.page.draw_line((MARGIN, w.y - 3), (PAGE_W - MARGIN, w.y - 3), color=(0.6, 0.6, 0.6), width=0.6)
    for i, (desc, dt, qty, rate, amt) in enumerate(C.BILL_ITEMS, start=1):
        vals = [str(i), desc, dt, qty, rate, amt]
        for x, v in zip(cols, vals):
            w.page.insert_text((x, w.y + 10), v, fontname="helv", fontsize=9)
        w.y += 15
    w.page.draw_line((MARGIN, w.y + 2), (PAGE_W - MARGIN, w.y + 2), color=(0.6, 0.6, 0.6), width=0.6)
    w.y += 8
    w.page.insert_text((cols[1], w.y + 10), "Total Amount", fontname="hebo", fontsize=10)
    w.page.insert_text((cols[5], w.y + 10), C.BILL_TOTAL, fontname="hebo", fontsize=10)
    w.y += 30
    w.line("All amounts are illustrative synthetic values created for demonstrating Nivaaran.", size=8.5,
           color=(0.4, 0.4, 0.4))
    doc.set_metadata({"title": C.BILL_HEADER[0], "subject": "SYNTHETIC demonstration bill", "creator": "Nivaaran demo generator"})
    doc.save(path)
    doc.close()


def generate(out_dir: Path = OUT_DIR) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "policy": out_dir / "synthetic_policy_v1.pdf",
        "endorsement": out_dir / "synthetic_endorsement_E01.pdf",
        "bill": out_dir / "synthetic_bill_appendicectomy.pdf",
        "brochure": out_dir / "synthetic_benefits_brochure.pdf",
        "undated": out_dir / "synthetic_endorsement_E02_undated.pdf",
    }
    _render_clauses(paths["policy"], C.POLICY_HEADER, C.POLICY_PAGES)
    _render_clauses(paths["endorsement"], C.ENDORSEMENT_HEADER, C.ENDORSEMENT_PAGES)
    _render_bill(paths["bill"])
    _render_clauses(paths["brochure"], C.BROCHURE_HEADER, C.BROCHURE_PAGES)
    _render_clauses(paths["undated"], C.UNDATED_HEADER, C.UNDATED_PAGES)
    return paths


if __name__ == "__main__":
    for kind, p in generate().items():
        print(f"{kind:12s} {p}")
