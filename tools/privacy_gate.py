#!/usr/bin/env python3
"""Personverngrind: feiler (exit 1) hvis noe i de gitte mappene ligner private data.
Skriver aldri ut selve treffet, bare fil, linje og regel."""
import os, re, sys
RULES = {
 "e-postadresse": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
 "telefonnummer": re.compile(r"(?:\+47[\s-]?)\d{2}[\s-]?\d{2}[\s-]?\d{2}[\s-]?\d{2}\b|(?<![\d.,/])\b[2-9]\d(?: \d{2}){3}\b(?![\d.,])|(?<![\d.,/])\b[2-9]\d{2} \d{2} \d{3}\b(?![\d.,])|(?<![\d.,/=-])\b[2-9]\d{7}\b(?![\d.,])"),
 "fødselsnummer": re.compile(r"\b[0-3]\d[01]\d\d{2} ?\d{5}\b"),
 "kontonummer": re.compile(r"\b\d{4}[ .]\d{2}[ .]\d{5}\b"),
 "IBAN": re.compile(r"\bNO\d{2} ?\d{4} ?\d{4} ?\d{3}\b"),
 "privatadresse/ID": re.compile(r"personnummer|fødselsdato|hjemmeadresse|bostedsadresse", re.I),
 # Organisasjonsnummer i tekst (f.eks. kildetitler): NO 9 siffer (8xx/9xx, også med mellomrom), SE NNNNNN-NNNN, DK CVR, «org.nr …».
 # URL-er fjernes før sjekken, så register-lenker (brreg/allabolag/cvr) er tillatt; selve nummeret skal ikke stå i synlig tekst.
 "organisasjonsnummer": re.compile(r"(?<![\d.,/=-])\b[89]\d{8}\b(?![\d.,])|(?<![\d.,/=-])\b[89]\d{2} \d{3} \d{3}\b(?![\d.,])|(?<![\d-])\b\d{6}-\d{4}\b(?![\d-])|\bCVR(?:-?n(?:r|ummer)\.?)?:?\s*\d{8}\b|\borg(?:anisations?|anisasjons)?\.?\s*-?n(?:r|ummer)\.?\s*:?\s*\d", re.I),
}
# Personlige søkeord (helse, økonomi o.l.) ligger i state/private_terms.json, som holdes utenfor git.
# Mangler fila, feiler grinda (fail closed).
PRIV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "state", "private_terms.json")
if not os.path.exists(PRIV): print("personverngrind: FEIL, mangler state/private_terms.json", file=sys.stderr); sys.exit(1)
import json
for k, v in json.load(open(PRIV, encoding="utf-8")).items(): RULES[k] = re.compile(v, re.I)
ALLOW_EMAIL = re.compile(r"^$")  # ingen e-postadresser publiseres (ingen er offentlige på jqrgen.github.io)
hits = 0; n = 0
for target in sys.argv[1:]:
    for dp, _, fs in os.walk(target):
        for f in fs:
            if not f.endswith((".html", ".json", ".txt", ".js", ".xml", ".css")): continue
            n += 1; p = os.path.join(dp, f)
            for i, line in enumerate(open(p, encoding="utf-8", errors="replace"), 1):
                line = re.sub(r"https?://[^\s\"'<>]+", " ", line)  # URL-er (artikkel-id-er) er ikke persondata
                for name, rx in RULES.items():
                    for m in rx.finditer(line):
                        s = m.group(0)
                        hits += 1; print(f"  {p}:{i}  regel «{name}»", file=sys.stderr)
if hits: print(f"personverngrind: FEIL, {hits} treff i {n} filer. Publiserer ikke.", file=sys.stderr); sys.exit(1)
print(f"personverngrind: OK ({n} filer, {len(RULES)} regler)")
