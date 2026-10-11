"""Understanding questions asked in Hindi or Marathi.

Retrieval and routing work on English insurance vocabulary, so a question written in Devanagari is first mapped to
English keywords with a fixed glossary of common insurance and hospital terms (deterministic; nothing is sent
anywhere). The answer itself is still built only from the documents and the rules engine; the reply opens with a line in
the asker's language showing how the question was understood, so a misreading is visible rather than silent.
"""
from __future__ import annotations

import re

# Longer phrases first, so "प्रतीक्षा कालावधी" wins over "प्रतीक्षा".
_PHRASES: list[tuple[str, str]] = [
    ("प्रतीक्षा अवधि", "waiting period"), ("प्रतीक्षा कालावधी", "waiting period"), ("वेटिंग पीरियड", "waiting period"),
    ("गहन चिकित्सा", "intensive care"), ("पहले से मौजूद", "pre-existing"), ("आधीपासून असलेला", "pre-existing"),
    ("आहार विशेषज्ञ", "dietitian"), ("सह-भुगतान", "co-payment"), ("को-पेमेंट", "co-payment"), ("एक्स-रे", "x-ray"),
]
_WORDS: dict[str, str] = {}
for en, words in {
    "room": "कमरा कमरे कमरों रूम खोली खोलीचे खोलीचा खोलीचं खोलीसाठी",
    "rent": "किराया किराए किराये किरायों भाडे भाडं भाड्याचे भाड्याची",
    "icu": "आईसीयू आयसीयू अतिदक्षता",
    "medicines": "दवा दवाई दवाइयाँ दवाइयां दवाइयों दवाओं दवाईयों औषध औषधे औषधं",
    "vitamins": "विटामिन विटामिन्स व्हिटॅमिन व्हिटॅमिन्स जीवनसत्व जीवनसत्त्व जीवनसत्त्वे",
    "infusion": "ड्रिप सलाइन सलाईन",
    "ambulance": "एम्बुलेंस एंबुलेंस ॲम्ब्युलन्स एम्ब्युलन्स रुग्णवाहिका",
    "surgery": "ऑपरेशन शस्त्रक्रिया सर्जरी",
    "surgeon": "सर्जन",
    "doctor": "डॉक्टर डॉक्टरांची डॉक्टरची चिकित्सक",
    "consultation": "परामर्श सल्ला कंसल्टेशन",
    "fees": "फीस फी शुल्क",
    "tests": "जांच जाँच जाँचें जाँचों जांचों टेस्ट टेस्टों चाचणी चाचण्या चाचण्यांचे",
    "imaging": "स्कैन स्कॅन सोनोग्राफी",
    "gloves": "दस्ताने हातमोजे",
    "masks": "मास्क",
    "tv": "टीवी टीव्ही",
    "telephone": "फोन टेलीफोन",
    "covered": "कवर कवर्ड कव्हर कव्हर्ड शामिल समाविष्ट",
    "excluded": "बहिष्कृत वगळलेले वगळले वगळला",
    "payable": "मिलेगा मिलेगी मिलेंगे मिलता भुगतान देय मिळेल मिळतील मिळणार",
    "why": "क्यों क्यूँ कशासाठी",
    "how much": "कितना कितनी कितने किती",
    "reduced": "कटौती काटा काटे कटा कपात कापले कापलं कमी",
    "deductible": "डिडक्टिबल",
    "bill": "बिल",
    "hospital": "अस्पताल हॉस्पिटल रुग्णालय दवाखाना",
    "policy": "पॉलिसी बीमा विमा",
    "claim": "क्लेम दावा",
    "dietitian": "आहारतज्ज्ञ डाइटिशियन",
    "physiotherapy": "फिजियोथेरेपी फिजिओथेरपी",
    "nebulizer": "नेबुलाइज़र नेबुलाइजर नेब्युलायझर",
    "admission": "भर्ती दाखल",
    "full": "पूरा पूरी पूरे पूर्ण",
    "total": "कुल एकूण",
    "documents": "दस्तावेज़ दस्तावेज कागज कागदपत्र कागदपत्रे",
    "endorsement": "संशोधन",
    "pre-existing": "पूर्व-मौजूद",
    "calculated": "गणना हिशोब",
    "out of pocket": "जेब जेबसे खिसा खिशातून खिशातून",
}.items():
    for w in words.split():
        _WORDS[w] = en

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_MARATHI_MARKERS = {"माझ्या", "माझा", "माझी", "माझे", "आहे", "आहेत", "मिळेल", "मिळतील", "मिळणार", "खोली", "खोलीचे", "भाडे", "किती",
                    "कशासाठी", "तुम्ही", "नाही", "झाले", "केले", "वगळले", "दवाखाना", "विमा", "रुग्णवाहिका", "चाचणी", "शस्त्रक्रिया",
                    "औषध", "औषधे", "कापले", "का?"}


def is_indic(q: str) -> bool:
    return bool(_DEVANAGARI.search(q))


def language(q: str) -> str:
    toks = set(re.findall(r"[ऀ-ॿ]+\??", q))
    return "mr" if toks & _MARATHI_MARKERS or q.strip().endswith("का?") else "hi"


_SUFFIXES = ("साठी", "मध्ये", "कडे", "ांचे", "ांची", "ांचा", "ांना", "ांत", "ाचे", "ाची", "ाचा", "ेचे", "ेची", "ीचे", "ीची", "चे", "चा", "ची", "चं",
             "ला", "ना", "ने", "ात", "ेत", "ों", "ें")


def _lookup(tok: str) -> str | None:
    """Exact word, then without a Hindi/Marathi case ending, then the oblique form turned back into the direct one."""
    if tok in _WORDS:
        return _WORDS[tok]
    for suf in _SUFFIXES:
        if tok.endswith(suf) and len(tok) > len(suf) + 1:
            stem = tok[: -len(suf)]
            for cand in (stem, stem + "ा", stem[:-1] + "ा" if stem.endswith("े") else None, stem[:-1] if stem.endswith("े") else None):
                if cand and cand in _WORDS:
                    return _WORDS[cand]
    if tok.endswith("े") and tok[:-1] + "ा" in _WORDS:
        return _WORDS[tok[:-1] + "ा"]
    return None


def to_english(q: str) -> str:
    """Map the insurance terms in a Hindi/Marathi question to English keywords; Latin-script words are kept."""
    text = q
    found: list[str] = []
    for phrase, en in _PHRASES:
        if phrase in text:
            found.append(en)
            text = text.replace(phrase, " ")
    for tok in re.findall(r"[ऀ-ॿ]+|[A-Za-z0-9][A-Za-z0-9.\-]*", text):
        if _DEVANAGARI.search(tok):
            en = _lookup(tok)
            if en:
                found.append(en)
        else:
            found.append(tok.lower())
    words: list[str] = []
    for w in found:            # keep order, drop repeats
        if w not in words:
            words.append(w)
    # Questions about a charge read most naturally to the router as "why ... reduced" / "is ... covered".
    if "why" in words:
        words = ["why"] + [w for w in words if w != "why"]
    elif "how much" in words:
        words = ["how much"] + [w for w in words if w != "how much"]
    elif words and words[0] not in ("how much", "is") and not any(w in words for w in ("reduced", "calculated", "total")):
        words = ["is"] + words
    return " ".join(words)


LEAD = {
    "hi": "आपका सवाल इस तरह समझा गया: “{en}”। नीचे का उत्तर आपके दस्तावेज़ों से है; हर राशि और धारा वहीं से ली गई है।",
    "mr": "तुमचा प्रश्न असा समजला: “{en}”. खालील उत्तर तुमच्या कागदपत्रांवर आधारित आहे; प्रत्येक रक्कम आणि कलम तिथूनच घेतले आहे.",
}
NOT_UNDERSTOOD = {
    "hi": "माफ़ कीजिए, यह सवाल समझ नहीं आया। कृपया शुल्क या सेवा का नाम लिखें, जैसे “कमरे का किराया”, “ICU” या “दवाइयाँ”।",
    "mr": "माफ करा, हा प्रश्न समजला नाही. कृपया खर्चाचे किंवा सेवेचे नाव लिहा, उदा. “खोलीचे भाडे”, “ICU” किंवा “औषधे”.",
}
