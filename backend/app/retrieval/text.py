"""Tokenisation, light stemming, and the bill-description normalisation lexicon.

The lexicon is a small, inspectable domain dictionary (abbreviations, spelling variants, and bill
categories). It is used for bill normalisation and as an optional query-expansion step; the evaluation
reports retrieval with and without it so its effect is measured rather than assumed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

STOPWORDS = set("""a an the of and or for to in on at by with from as is are be been was were this that these
those it its into per any all such up than then which who whom whose under over during within without
including include includes not no nor only after before i ii iii iv v""".split())

# Generic words that should not by themselves establish that a clause is about a bill item.
GENERIC = set("""charge fee expense item cost service amount bill hospital hospitalization patient insured
company policy payable treatment care day total other medical medic""".split())

ABBREVIATIONS = {
    "inj": "injection", "tab": "tablet", "lap": "laparoscopic", "usg": "ultrasonography",
    "cbc": "complete blood count", "lft": "liver function test", "rft": "renal function test",
    "kft": "kidney function test", "ot": "operation theatre", "icu": "icu intensive care unit",
    "mvi": "multivitamin infusion", "tv": "television", "ecg": "electrocardiogram", "iv": "intravenous",
    "xray": "x-ray", "rmo": "resident medical officer", "ns": "normal saline", "opd": "outpatient",
    "appendectomy": "appendicectomy", "nebuliser": "nebulizer", "anesthetist": "anaesthetist",
    "anesthesia": "anaesthesia", "physio": "physiotherapy", "dietician": "dietitian",
}


@dataclass
class Category:
    key: str
    label: str
    keywords: list[str]
    hypernyms: str


# Ordered: the first matching category wins (specific before generic).
CATEGORIES = [
    Category("allied_health", "Allied health services", ["dietitian", "physiotherapy", "counselling", "counseling"], "allied health service"),
    Category("icu", "Intensive care", ["icu", "intensive care", "iccu", "nicu"], "icu intensive care unit"),
    Category("room", "Room & boarding", ["room", "ward", "bed charge", "accommodation", "boarding"], "room rent boarding nursing"),
    Category("surgeon_fee", "Surgeon fees", ["surgeon"], "surgeon fees professional fees"),
    Category("anaesthesia_fee", "Anaesthesia fees", ["anaesthetist", "anaesthesia"], "anaesthetist professional fees"),
    Category("operation_theatre", "Operation theatre", ["operation theatre", "theatre"], "operation theatre"),
    Category("vitamins", "Vitamins & supplements", ["multivitamin", "vitamin", "supplement", "tonic"], "vitamin medicines"),
    Category("respiratory", "Respiratory therapy", ["nebulizer", "nebulisation", "nebulization", "oxygen"], "respiratory therapy"),
    Category("implant", "Implants & devices", ["implant", "stent", "mesh"], "surgically implanted devices"),
    Category("consumables", "Consumables", ["glove", "mask", "syringe", "needle", "gauze", "cotton", "disposable"], "consumables"),
    Category("non_medical", "Non-medical items", ["toiletr", "admission kit", "soap", "toothpaste"], "non-medical items"),
    Category("comfort", "Comfort & personal", ["television", "telephone", "laundry", "attendant"], "comfort personal charges"),
    Category("ambulance", "Ambulance", ["ambulance"], "road ambulance"),
    # Bare "blood" is deliberately not a keyword: blood bank / transfusion charges are not laboratory investigations.
    Category("laboratory", "Laboratory", ["blood count", "blood culture", "blood test", "blood sugar", "function test", "urine",
                                          "culture", "pathology", "lab", "test"], "laboratory investigations pathology tests"),
    Category("imaging", "Imaging", ["ultrasonography", "ultrasound", "x-ray", "ct scan", "mri", "scan", "electrocardiogram"], "imaging"),
    Category("medicine", "Medicines & drugs", ["injection", "tablet", "capsule", "syrup", "drug", "medicine", "antibiotic", "intravenous", "saline", "infusion"], "medicines drugs"),
    Category("consultation", "Consultation", ["consultation", "visit", "physician", "doctor"], "consulting doctors"),
    Category("surgery", "Surgery", ["surgery", "surgical", "procedure", "appendicectomy", "cholecystectomy"], "surgical procedures"),
]
CATEGORY_LABELS = {c.key: c.label for c in CATEGORIES} | {"other": "Other hospital services"}

_WORD = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def _variants(w: str) -> str:
    w = w.replace("-", "")
    w = re.sub(r"isation", "ization", w)
    w = re.sub(r"iser$", "izer", w)
    w = re.sub(r"ise$", "ize", w)
    w = w.replace("anaes", "anes").replace("haem", "hem").replace("paed", "ped")
    w = re.sub(r"tre$", "ter", w)
    return w


def stem(w: str) -> str:
    w = _variants(w.lower())
    if len(w) > 4 and w.endswith("ies"):
        w = w[:-3] + "y"
    elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        w = w[:-1]
    for suf in ("ation", "ing", "er", "ed", "al"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            w = w[: -len(suf)]
            break
    return w


def tokens(text: str, drop_stop: bool = True) -> list[str]:
    out = []
    for raw in _WORD.findall(text.lower()):
        if drop_stop and raw in STOPWORDS:
            continue
        out.append(stem(raw))
    return out


def content_tokens(text: str) -> list[str]:
    return [t for t in tokens(text) if t not in GENERIC and not t.isdigit()]


def expand_abbreviations(text: str) -> str:
    def rep(m: re.Match) -> str:
        w = m.group(0)
        exp = ABBREVIATIONS.get(w.lower().replace("-", "").rstrip("."))
        return exp if exp else w
    return re.sub(r"[A-Za-z][A-Za-z-]*\.?", lambda m: rep(m) + (" " if m.group(0).endswith(".") else ""), text)


def classify(normalized: str, hint: str | None = None) -> Category | None:
    if hint:
        for c in CATEGORIES:
            if c.key == hint:
                return c
    low = normalized.lower()
    for c in CATEGORIES:
        if any(re.search(r"\b" + re.escape(k), low) for k in c.keywords):
            return c
    return None


@dataclass
class NormalizedItem:
    original: str
    normalized: str
    category: str
    category_label: str
    direct_tokens: set[str] = field(default_factory=set)
    general_tokens: set[str] = field(default_factory=set)

    @property
    def query(self) -> str:
        return f"{self.normalized} ({self.category_label})" if self.category != "other" else self.normalized


def normalize_item(description: str, hint: str | None = None) -> NormalizedItem:
    expanded = re.sub(r"\s+", " ", expand_abbreviations(description).replace("&", " and ")).strip()
    expanded = re.sub(r"\s*-\s+", " - ", expanded)
    cat = classify(expanded, hint)
    direct = set(tokens(description)) | set(tokens(expanded))
    general = set(tokens(cat.hypernyms)) if cat else set()
    return NormalizedItem(original=description, normalized=expanded, category=cat.key if cat else "other",
                          category_label=cat.label if cat else CATEGORY_LABELS["other"],
                          direct_tokens=direct, general_tokens=general - direct)


def term_match(term: str, item: NormalizedItem) -> str | None:
    """Return 'direct' when the item itself names the clause term, 'general' when only its category does.

    Every content word of the term must be present; a shared single word (e.g. 'kit') is not enough.
    """
    t = content_tokens(term)
    if not t:
        return None
    d = item.direct_tokens
    g = item.general_tokens | d
    if all(x in d for x in t):
        return "direct"
    if all(x in g for x in t):
        return "general"
    return None
