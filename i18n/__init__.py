"""Nordic Crypto site languages (UI and chrome, not news-source languages).

English is the default (site root); every other code lives under /<code>/.
Strings: i18n/<code>.py -> S = {key: text}. Missing keys fall back to English (and build.py warns).
The languages added beyond the Nordic set ship as English stubs until a real translation is written.
Do not machine-translate article bodies into those files.

Editor workflow: our own text (story summaries, event notes, changelog entries) gets per-language variants in
queue/approved.json (items[].summary_i18n, events.notes_i18n) and changelog.json (entries[].i18n). Story headlines
are translated the same way (items[].title_i18n, or data/title_i18n.json): the card shows that headline in the page
language, and the source headline underneath when the languages differ. Quotes and other source text stay as written.

The IP country → language guess lives in tools/langselect.js (BY_COUNTRY) and is published as
/api/v1/geo-language.json. It is a default only. The nc_lang cookie from the language switcher wins.
"""
import importlib, os
# Nordic first (en at the root, then nn nb sv da fi is), then the other site languages in
# approximate number of speakers: Mandarin, Hindi, Spanish, French, Arabic, Bengali, Portuguese,
# Russian, Urdu, Indonesian, German, Japanese, Swahili, Marathi. English is already first.
ALL_LANGS = [
    "en", "nn", "nb", "sv", "da", "fi", "is",
    "zh", "hi", "es", "fr", "ar", "bn", "pt", "ru", "ur", "id", "de", "ja", "sw", "mr",
]
LANGS = [l for l in (os.environ.get("NC_LANGS") or ",".join(ALL_LANGS)).split(",") if l in ALL_LANGS]  # NC_LANGS: test builds only
# Switcher label: the name readers see, in that language.
NATIVE = {
    "en": "English", "nn": "Nynorsk", "nb": "Bokmål", "sv": "Svenska", "da": "Dansk", "fi": "Suomi", "is": "Íslenska",
    "zh": "中文", "hi": "हिन्दी", "es": "Español", "fr": "Français", "ar": "العربية", "bn": "বাংলা",
    "pt": "Português", "ru": "Русский", "ur": "اردو", "id": "Bahasa Indonesia", "de": "Deutsch",
    "ja": "日本語", "sw": "Kiswahili", "mr": "मराठी",
}
ENGLISH = {
    "en": "English", "nn": "Norwegian Nynorsk", "nb": "Norwegian Bokmål", "sv": "Swedish", "da": "Danish",
    "fi": "Finnish", "is": "Icelandic",
    "zh": "Chinese (Mandarin)", "hi": "Hindi", "es": "Spanish", "fr": "French", "ar": "Arabic", "bn": "Bengali",
    "pt": "Portuguese", "ru": "Russian", "ur": "Urdu", "id": "Indonesian", "de": "German", "ja": "Japanese",
    "sw": "Swahili", "mr": "Marathi",
}
NAME = NATIVE
HTML_LANG = {code: code for code in ALL_LANGS}
OG_LOCALE = {
    "en": "en_GB", "nn": "nn_NO", "nb": "nb_NO", "sv": "sv_SE", "da": "da_DK", "fi": "fi_FI", "is": "is_IS",
    "zh": "zh_CN", "hi": "hi_IN", "es": "es_ES", "fr": "fr_FR", "ar": "ar_SA", "bn": "bn_BD",
    "pt": "pt_BR", "ru": "ru_RU", "ur": "ur_PK", "id": "id_ID", "de": "de_DE", "ja": "ja_JP",
    "sw": "sw_KE", "mr": "mr_IN",
}
# Right-to-left UI. Arabic and Urdu in this set; add a code here when another RTL language is added.
RTL = {code: code in ("ar", "ur") for code in ALL_LANGS}
def rtl(lang): return bool(RTL.get(lang))
# quick second choice shown next to the switcher (Norway: nynorsk <-> bokmål; Finland: Swedish)
QUICK = {"nn": "nb", "nb": "nn", "fi": "sv"}
# source-language value in data (news items) -> ISO code. Not the site-language list.
SRC_LANG = {"Norwegian": "no", "Swedish": "sv", "Danish": "da", "Finnish": "fi", "Icelandic": "is", "English": "en"}
# Page language -> the news-item language name that counts as "the same language" (so we do not mark it foreign).
SAME_LANG = {
    "nn": "Norwegian", "nb": "Norwegian", "sv": "Swedish", "da": "Danish", "fi": "Finnish", "is": "Icelandic", "en": "English",
    "zh": "Chinese", "hi": "Hindi", "es": "Spanish", "fr": "French", "ar": "Arabic", "bn": "Bengali",
    "pt": "Portuguese", "ru": "Russian", "ur": "Urdu", "id": "Indonesian", "de": "German", "ja": "Japanese",
    "sw": "Swahili", "mr": "Marathi",
}
_missing = [f"{table}.{code}" for table, data in (
    ("NATIVE", NATIVE), ("ENGLISH", ENGLISH), ("HTML_LANG", HTML_LANG), ("OG_LOCALE", OG_LOCALE),
    ("RTL", RTL), ("SAME_LANG", SAME_LANG)) for code in ALL_LANGS if code not in data]
if _missing:
    raise RuntimeError("i18n registry incomplete: " + ", ".join(_missing))
_S = {}
def strings(lang):
    if lang not in _S: _S[lang] = importlib.import_module(f"i18n.{lang}").S
    return _S[lang]
MISSING = set()
def t(lang, key, **kw):
    s = strings(lang).get(key)
    if s is None:
        MISSING.add((lang, key)); s = strings("en")[key]
    return s.format(**kw) if kw else s
def has(lang, key): return key in strings(lang)

# ---- dates (Europe/Oslo already applied by the caller) ----
MON = {"en": "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(),
       "nn": "jan. feb. mars apr. mai juni juli aug. sep. okt. nov. des.".split(),
       "nb": "jan. feb. mars apr. mai juni juli aug. sep. okt. nov. des.".split(),
       "sv": "jan. feb. mars apr. maj juni juli aug. sep. okt. nov. dec.".split(),
       "da": "jan. feb. mar. apr. maj jun. jul. aug. sep. okt. nov. dec.".split(),
       "fi": None,
       "is": "jan. feb. mar. apr. maí jún. júl. ágú. sep. okt. nóv. des.".split()}
MONTH = {"en": "January February March April May June July August September October November December".split(),
         "nn": "januar februar mars april mai juni juli august september oktober november desember".split(),
         "nb": "januar februar mars april mai juni juli august september oktober november desember".split(),
         "sv": "januari februari mars april maj juni juli augusti september oktober november december".split(),
         "da": "januar februar marts april maj juni juli august september oktober november december".split(),
         "fi": "tammikuu helmikuu maaliskuu huhtikuu toukokuu kesäkuu heinäkuu elokuu syyskuu lokakuu marraskuu joulukuu".split(),
         "is": "janúar febrúar mars apríl maí júní júlí ágúst september október nóvember desember".split()}
# Finnish long dates use the partitive month: "3. lokakuuta 2026"
MONTH_FI_PART = "tammikuuta helmikuuta maaliskuuta huhtikuuta toukokuuta kesäkuuta heinäkuuta elokuuta syyskuuta lokakuuta marraskuuta joulukuuta".split()
WD = {"en": "Mon Tue Wed Thu Fri Sat Sun".split(),
      "nn": "mån. tys. ons. tor. fre. lau. sun.".split(),
      "nb": "man. tir. ons. tor. fre. lør. søn.".split(),
      "sv": "mån tis ons tors fre lör sön".split(),
      "da": "man. tir. ons. tor. fre. lør. søn.".split(),
      "fi": "ma ti ke to pe la su".split(),
      "is": "mán. þri. mið. fim. fös. lau. sun.".split()}
# Nordic languages have their own date forms. Other site languages use the English forms until translated.
def _dl(lang): return lang if lang in MON else "en"
def wd_head(lang): return [w.rstrip(".") for w in WD[_dl(lang)]]
def short_date(lang, d):
    lang = _dl(lang)
    if lang == "en": return f"{d.day} {MON['en'][d.month-1]} {d.year}"
    if lang == "fi": return f"{d.day}.{d.month}.{d.year}"
    if lang == "sv": return f"{d.day} {MON['sv'][d.month-1]} {d.year}"
    return f"{d.day}. {MON[lang][d.month-1]} {d.year}"
def short_dm(lang, d):
    lang = _dl(lang)
    if lang == "en": return f"{d.day} {MON['en'][d.month-1]}"
    if lang == "fi": return f"{d.day}.{d.month}."
    if lang == "sv": return f"{d.day} {MON['sv'][d.month-1]}"
    return f"{d.day}. {MON[lang][d.month-1]}"
def long_date(lang, d):
    lang = _dl(lang)
    if lang == "en": return f"{d.day} {MONTH['en'][d.month-1]} {d.year}"
    if lang == "fi": return f"{d.day}. {MONTH_FI_PART[d.month-1]} {d.year}"
    if lang == "sv": return f"{d.day} {MONTH['sv'][d.month-1]} {d.year}"
    return f"{d.day}. {MONTH[lang][d.month-1]} {d.year}"
def month_caption(lang, y, m):
    n = MONTH[_dl(lang)][m-1]; return f"{n[0].upper()}{n[1:]} {y}"
def hm(lang, t):
    """t: datetime/time -> clock time in local convention."""
    lang = _dl(lang)
    if lang == "en": return f"{t:%H:%M}"
    if lang == "is": return f"kl. {t:%H:%M}"
    if lang == "fi": return f"klo {t:%H.%M}"
    return f"kl. {t:%H.%M}"
def hm_end(lang, t):
    lang = _dl(lang)
    return f"{t:%H:%M}" if lang in ("en", "is") else f"{t:%H.%M}"
