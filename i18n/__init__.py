"""Crypto Nordic site languages. English is the default (site root); the others live under /<code>/.
Strings: i18n/<code>.py -> S = {key: text}. Missing keys fall back to English (and build.py warns).
Editor workflow: our own text (story summaries, event notes, changelog entries) gets per-language variants in
queue/approved.json (items[].summary_i18n, events.notes_i18n) and changelog.json (entries[].i18n). External headlines,
event titles, quotes and data from sources stay as in the source."""
import importlib, os
ALL_LANGS = ["en", "nn", "nb", "sv", "da", "fi", "is"]
LANGS = [l for l in (os.environ.get("NC_LANGS") or ",".join(ALL_LANGS)).split(",") if l in ALL_LANGS]  # NC_LANGS: test builds only
NAME = {"en": "English", "nn": "Nynorsk", "nb": "Bokmål", "sv": "Svenska", "da": "Dansk", "fi": "Suomi", "is": "Íslenska"}
HTML_LANG = {"en": "en", "nn": "nn", "nb": "nb", "sv": "sv", "da": "da", "fi": "fi", "is": "is"}
OG_LOCALE = {"en": "en_GB", "nn": "nn_NO", "nb": "nb_NO", "sv": "sv_SE", "da": "da_DK", "fi": "fi_FI", "is": "is_IS"}
# quick second choice shown next to the switcher (Norway: nynorsk <-> bokmål; Finland: Swedish)
QUICK = {"nn": "nb", "nb": "nn", "fi": "sv"}
# source-language value in data (news items) -> ISO code
SRC_LANG = {"Norwegian": "no", "Swedish": "sv", "Danish": "da", "Finnish": "fi", "Icelandic": "is", "English": "en"}
SAME_LANG = {"nn": "Norwegian", "nb": "Norwegian", "sv": "Swedish", "da": "Danish", "fi": "Finnish", "is": "Icelandic", "en": "English"}
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
def wd_head(lang): return [w.rstrip(".") for w in WD[lang]]
def short_date(lang, d):
    if lang == "en": return f"{d.day} {MON['en'][d.month-1]} {d.year}"
    if lang == "fi": return f"{d.day}.{d.month}.{d.year}"
    if lang == "sv": return f"{d.day} {MON['sv'][d.month-1]} {d.year}"
    return f"{d.day}. {MON[lang][d.month-1]} {d.year}"
def short_dm(lang, d):
    if lang == "en": return f"{d.day} {MON['en'][d.month-1]}"
    if lang == "fi": return f"{d.day}.{d.month}."
    if lang == "sv": return f"{d.day} {MON['sv'][d.month-1]}"
    return f"{d.day}. {MON[lang][d.month-1]}"
def long_date(lang, d):
    if lang == "en": return f"{d.day} {MONTH['en'][d.month-1]} {d.year}"
    if lang == "fi": return f"{d.day}. {MONTH_FI_PART[d.month-1]} {d.year}"
    if lang == "sv": return f"{d.day} {MONTH['sv'][d.month-1]} {d.year}"
    return f"{d.day}. {MONTH[lang][d.month-1]} {d.year}"
def month_caption(lang, y, m):
    n = MONTH[lang][m-1]; return f"{n[0].upper()}{n[1:]} {y}"
def hm(lang, t):
    """t: datetime/time -> clock time in local convention."""
    if lang == "en": return f"{t:%H:%M}"
    if lang == "is": return f"kl. {t:%H:%M}"
    if lang == "fi": return f"klo {t:%H.%M}"
    return f"kl. {t:%H.%M}"
def hm_end(lang, t): return f"{t:%H:%M}" if lang in ("en", "is") else f"{t:%H.%M}"
