"""Plain-language clause explanations and whole-policy summaries in English, Hindi and Marathi, for read-aloud.

Built deterministically from the clause's structured interpretation (category, scope, limits, conditions), so the
spoken summary never says anything the clause does not. The exact clause wording is always offered alongside.
"""
from __future__ import annotations

from app.models import Clause
from app.models import ClauseCategory as Cat
from app.money import fmt

BASIS_EN = {"per_day": "per day", "per_hospitalisation": "per hospitalisation", "per_eye": "per eye", "per_policy_year": "per policy year", "per_claim": "per claim"}
BASIS_HI = {"per_day": "प्रति दिन", "per_hospitalisation": "प्रति अस्पताल भर्ती", "per_eye": "प्रति आँख", "per_policy_year": "प्रति पॉलिसी वर्ष", "per_claim": "प्रति क्लेम"}
BASIS_MR = {"per_day": "प्रति दिवस", "per_hospitalisation": "प्रत्येक हॉस्पिटल दाखल्यासाठी", "per_eye": "प्रति डोळा", "per_policy_year": "प्रति पॉलिसी वर्ष", "per_claim": "प्रति क्लेम"}


def _items(c: Clause) -> str:
    return ", ".join(c.interpretation.scope_terms[:6])


def explain(c: Clause, lang: str) -> str:
    it = c.interpretation
    items = _items(c)
    lim = it.limit
    amt = f"₹{fmt(lim.amount)}" if lim and lim.amount is not None else None
    if lang == "hi":
        head = f"धारा {c.section}, {c.heading}. "
        body = {
            Cat.coverage: f"यह धारा बताती है कि ये खर्च भुगतान योग्य हैं: {items}.",
            Cat.limit: f"ये खर्च भुगतान योग्य हैं: {items}, लेकिन अधिकतम {amt} {BASIS_HI.get(lim.basis, '') if lim else ''} तक।",
            Cat.conditional_coverage: f"ये खर्च भुगतान योग्य हैं: {items}, लेकिन केवल एक शर्त पूरी होने पर।",
            Cat.exclusion: f"ये खर्च भुगतान योग्य नहीं हैं: {items}.",
            Cat.conditional_exclusion: f"ये खर्च आम तौर पर भुगतान योग्य नहीं हैं: {items}, सिवाय एक अपवाद के।",
            Cat.waiting_period: (f"इन इलाज के लिए प्रतीक्षा अवधि है: {items}। {it.waiting_months} महीने की लगातार कवरेज के बाद ही भुगतान होगा।" if it.waiting_months
                                 else f"पॉलिसी शुरू होने के पहले {it.waiting_days} दिनों में हुई बीमारी का भुगतान नहीं होगा, दुर्घटना को छोड़कर।"),
            Cat.deductible: f"हर पॉलिसी वर्ष में पहले ₹{fmt(it.amount)} आपको खुद देने होंगे, उसके बाद बीमा भुगतान शुरू होगा।" if it.amount else "इसमें डिडक्टिबल का प्रावधान है।",
            Cat.copayment: f"स्वीकृत राशि का {it.percent} प्रतिशत हिस्सा आपको खुद देना होगा।",
            Cat.time_window: f"भर्ती से {it.window_days_before} दिन पहले और छुट्टी के {it.window_days_after} दिन बाद तक के उसी बीमारी से जुड़े खर्च भुगतान योग्य हैं।",
            Cat.computation_order: "यह धारा बताती है कि गणना किस क्रम में होगी: पहले बहिष्कार, फिर सीमाएँ, फिर डिडक्टिबल, फिर को-पेमेंट।",
            Cat.definition: f"यह एक परिभाषा है: {c.heading}.",
        }.get(it.category, "इस धारा का पूरा पाठ नीचे दिया गया है।")
        cond = " ध्यान दें, एक शर्त लागू है, जिसका मूल पाठ अंग्रेज़ी में दिया गया है।" if it.condition else ""
        rep = f" यह धारा {', '.join(it.replaces)} को बदलती है।" if it.replaces else ""
        return head + body + cond + rep + " यह केवल सरल सार है; मान्य पाठ पॉलिसी का मूल शब्दांकन है।"
    if lang == "mr":
        head = f"कलम {c.section}, {c.heading}. "
        body = {
            Cat.coverage: f"हे कलम सांगते की हे खर्च देय आहेत: {items}.",
            Cat.limit: f"हे खर्च देय आहेत: {items}, पण जास्तीत जास्त {amt} {BASIS_MR.get(lim.basis, '') if lim else ''} पर्यंत.",
            Cat.conditional_coverage: f"हे खर्च देय आहेत: {items}, पण फक्त एक अट पूर्ण झाल्यावर.",
            Cat.exclusion: f"हे खर्च देय नाहीत: {items}.",
            Cat.conditional_exclusion: f"हे खर्च सहसा देय नाहीत: {items}, एका अपवादाशिवाय.",
            Cat.waiting_period: (f"या उपचारांसाठी प्रतीक्षा कालावधी आहे: {items}. {it.waiting_months} महिन्यांच्या सलग विमा संरक्षणानंतरच पैसे मिळतील." if it.waiting_months
                                 else f"पॉलिसी सुरू झाल्यापासून पहिल्या {it.waiting_days} दिवसांत झालेल्या आजारासाठी पैसे मिळणार नाहीत, अपघात वगळता."),
            Cat.deductible: f"प्रत्येक पॉलिसी वर्षात पहिले ₹{fmt(it.amount)} तुम्हाला स्वतः भरावे लागतील, त्यानंतर विमा कंपनी पैसे देईल." if it.amount else "यात डिडक्टिबलची तरतूद आहे.",
            Cat.copayment: f"मंजूर रकमेपैकी {it.percent} टक्के रक्कम तुम्हाला स्वतः भरावी लागेल.",
            Cat.time_window: f"दाखल होण्यापूर्वी {it.window_days_before} दिवस आणि डिस्चार्जनंतर {it.window_days_after} दिवसांपर्यंतचे त्याच आजाराशी संबंधित खर्च देय आहेत.",
            Cat.computation_order: "हे कलम गणनेचा क्रम ठरवते: आधी वगळलेले खर्च, मग मर्यादा, मग डिडक्टिबल, आणि शेवटी को-पेमेंट.",
            Cat.definition: f"ही एक व्याख्या आहे: {c.heading}.",
        }.get(it.category, "या कलमाचा पूर्ण मजकूर खाली दिला आहे.")
        cond = " लक्षात ठेवा, एक अट लागू आहे; तिचा मूळ मजकूर इंग्रजीत दिला आहे." if it.condition else ""
        rep = f" हे कलम {', '.join(it.replaces)} ची जागा घेते." if it.replaces else ""
        return head + body + cond + rep + " हा फक्त सोपा सारांश आहे; पॉलिसीचा मूळ मजकूरच ग्राह्य आहे."
    head = f"Clause {c.section}, {c.heading}. "
    body = {
        Cat.coverage: f"This clause says these expenses are payable: {items}.",
        Cat.limit: f"These expenses are payable: {items}, up to {amt} {BASIS_EN.get(lim.basis, '') if lim else ''}.",
        Cat.conditional_coverage: f"These expenses are payable: {items}, but only {it.condition}.",
        Cat.exclusion: f"These expenses are not payable: {items}.",
        Cat.conditional_exclusion: f"These expenses are not payable: {items}, {it.condition}.",
        Cat.waiting_period: (f"Treatment of {items} is payable only after {it.waiting_months} months of continuous cover." if it.waiting_months
                             else f"Illness in the first {it.waiting_days} days of the policy is not payable, except after an accident."),
        Cat.deductible: f"You pay the first ₹{fmt(it.amount)} each policy year before the insurer pays." if it.amount else "There is a deductible.",
        Cat.copayment: f"You pay {it.percent} percent of the admissible amount yourself.",
        Cat.time_window: f"Expenses for the same condition up to {it.window_days_before} days before admission and {it.window_days_after} days after discharge are payable.",
        Cat.computation_order: "This clause sets the order of the calculation: exclusions, then limits, then the deductible, then the co-payment.",
        Cat.definition: f"This is a definition of {c.heading}.",
    }.get(it.category, "")
    rep = f" It replaces clause {', '.join(it.replaces)}." if it.replaces else ""
    return head + body + rep + " The exact wording is: " + c.text


# --------------------------------------------------------------------------------------- whole-policy summary
_SUM = {
    "en": {"intro": "Summary of {title}. Nivaaran read {n} clauses from this document.",
           "heads": ["What is covered", "Limits on what is paid", "What you pay yourself", "Waiting periods", "What is not covered"],
           "ref": "clause", "cond": "with a condition", "except": "except in some cases", "months": "months",
           "limit": "{items}: up to {amt} {basis}", "initial": "Illness in the first {d} days of the policy, except after an accident",
           "outro": "This is a simplified summary. The policy wording is what counts, so check the exact clause before relying on it."},
    "hi": {"intro": "{title} का सार। Nivaaran ने इस दस्तावेज़ से {n} धाराएँ पढ़ीं।",
           "heads": ["क्या कवर है", "भुगतान की सीमाएँ", "आपको खुद क्या देना होगा", "प्रतीक्षा अवधि", "क्या कवर नहीं है"],
           "ref": "धारा", "cond": "शर्त के साथ", "except": "कुछ अपवादों को छोड़कर", "months": "महीने",
           "limit": "{items}: अधिकतम {amt} {basis} तक", "initial": "पॉलिसी के पहले {d} दिनों में हुई बीमारी, दुर्घटना को छोड़कर",
           "outro": "यह केवल सरल सार है। मान्य वही है जो पॉलिसी के मूल शब्दों में लिखा है, इसलिए भरोसा करने से पहले मूल धारा देखें।"},
    "mr": {"intro": "{title} चा सारांश. Nivaaran ने या दस्तऐवजातील {n} कलमे वाचली.",
           "heads": ["काय कव्हर आहे", "देय रकमेच्या मर्यादा", "तुम्हाला स्वतः काय भरावे लागेल", "प्रतीक्षा कालावधी", "काय कव्हर नाही"],
           "ref": "कलम", "cond": "अटीसह", "except": "काही अपवाद वगळता", "months": "महिने",
           "limit": "{items}: जास्तीत जास्त {amt} {basis} पर्यंत", "initial": "पॉलिसीच्या पहिल्या {d} दिवसांतील आजार, अपघात वगळता",
           "outro": "हा फक्त सोपा सारांश आहे. पॉलिसीच्या मूळ शब्दांत जे लिहिले आहे तेच ग्राह्य आहे, त्यामुळे विसंबून राहण्यापूर्वी मूळ कलम तपासा."},
}
_BASIS = {"en": BASIS_EN, "hi": BASIS_HI, "mr": BASIS_MR}
_TAILS = (" The exact wording", " यह केवल", " हा फक्त", " ध्यान दें", " लक्षात ठेवा")


def _sentence(c: Clause, lang: str) -> str:
    """The explanation sentence without the 'Clause x, heading.' prefix and without the closing caveat."""
    body = explain(c, lang).split(". ", 1)[-1]
    for cut in _TAILS:
        body = body.split(cut)[0]
    return body.strip()


def summarise(clauses: list[Clause], title: str, lang: str) -> dict:
    """Group a policy's interpreted clauses into five plain-language sections. Every point cites its clause."""
    L = _SUM[lang]
    sections: list[list[dict]] = [[], [], [], [], []]
    for c in clauses:
        it = c.interpretation
        items = _items(c) or c.heading
        cat = it.category
        if cat == Cat.coverage:
            sections[0].append({"text": items, "clause": c.section})
        elif cat == Cat.time_window:
            sections[0].append({"text": _sentence(c, lang), "clause": c.section})
        elif cat == Cat.conditional_coverage:
            sections[0].append({"text": f"{items} ({L['cond']})", "clause": c.section})
        elif cat == Cat.limit and it.limit and it.limit.amount is not None:
            sections[1].append({"text": L["limit"].format(items=items, amt=f"₹{fmt(it.limit.amount)}", basis=_BASIS[lang].get(it.limit.basis, "")).strip(),
                                "clause": c.section})
        elif cat in (Cat.deductible, Cat.copayment):
            sections[2].append({"text": _sentence(c, lang), "clause": c.section})
        elif cat == Cat.waiting_period:
            sections[3].append({"text": f"{items}: {it.waiting_months} {L['months']}" if it.waiting_months else L["initial"].format(d=it.waiting_days),
                                "clause": c.section})
        elif cat == Cat.exclusion:
            sections[4].append({"text": items, "clause": c.section})
        elif cat == Cat.conditional_exclusion:
            sections[4].append({"text": f"{items} ({L['except']})", "clause": c.section})
    out = [{"heading": h, "items": s} for h, s in zip(L["heads"], sections) if s]
    speech = [L["intro"].format(title=title, n=len(clauses))]
    for sec in out:
        speech.append(sec["heading"] + ". " + "; ".join(f"{i['text']} ({L['ref']} {i['clause']})" for i in sec["items"]) + ".")
    speech.append(L["outro"])
    return {"lang": lang, "title": title, "intro": speech[0], "sections": out, "outro": L["outro"], "text": " ".join(speech),
            "source": "structured reading of the policy's clauses (deterministic); the exact wording governs"}
