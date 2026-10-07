"""Swahili (Kiswahili) site UI, /sw/.

Chrome strings fall back to English in i18n.t() until a translation is added to S.
This file does not translate article bodies or summaries. Nordic news sources are unchanged.
"""
S = {
"push_title": "Arifa",
"push_lead": "Ujumbe mmoja kila habari mpya zinapochapishwa. Habari kadhaa katika uchapishaji mmoja ni ujumbe mmoja, si ujumbe kwa kila habari.",
"push_on": "Washa arifa",
"push_off": "Zima arifa",
"push_on_status": "Arifa zimewashwa kwenye kivinjari hiki.",
"push_off_status": "Arifa zimezimwa.",
"push_topics": "Nchi",
"push_all": "Nchi zote za Nordic",
"push_lang_note": "Ujumbe unatumia lugha ya ukurasa huu. Fungua lugha nyingine na uwashe arifa tena ili kuibadilisha.",
"push_privacy": "Tunahifadhi usajili wa push wa kivinjari chako tu (anwani na funguo mbili zinazoficha ujumbe), lugha ya ukurasa huu, na nchi unazochagua. Hakuna jina, hakuna barua pepe, na hatufuatilii unachosoma. Kitufe hicho hicho huzima arifa na kufuta usajili. Cloudflare Web Analytics huhesabu ziara kwa jumla, bila vidakuzi, na hatuuzi data hiyo.",
"push_unsupported": "Kivinjari hiki hakiwezi kuonyesha arifa.",
"push_denied": "Arifa za tovuti hii zimezuiwa katika mipangilio ya kivinjari.",
"push_ios": "Kwenye iPhone au iPad, ongeza tovuti kwenye skrini ya nyumbani kwanza. iOS 16.4 au mpya zaidi inaweza kisha kutumia arifa hizi za kivinjari. Huduma ya push ya Apple (APNs) haitumiki.",
"push_unavailable": "Huduma ya arifa bado haijawashwa.",
"push_working": "Inafanya kazi…",
"push_fail": "Imeshindwa kusasisha arifa. Jaribu tena.",
"push_saved": "Imehifadhiwa.",
"push_noscript": "Kuwasha arifa kunahitaji JavaScript.",
}

S.update({'nav_talks': 'Hotuba', 'talks_title': 'Hotuba – hotuba za umma kuhusu crypto katika nchi za Nordic', 'talks_desc': 'Hotuba za umma kuhusu bitcoin, sarafu za crypto na blockchain zilizofanyika katika nchi za Nordic, pamoja na video na ukweli uliotajwa na mchapishaji.', 'talks_h1': 'Hotuba', 'talks_lead': 'Rekodi za hotuba za umma kuhusu bitcoin, sarafu za crypto na blockchain zilizofanyika Norway, Sweden, Denmark, Finland, Iceland, Visiwa vya Faroe, Greenland na Åland tangu waraka mweupe wa bitcoin. Mpya kwanza. Kichezaji kinapakia tu baada ya kubonyeza cheza, na tu ikiwa jukwaa linaruhusu kupachika.', 'talks_n': 'Hotuba {n}', 'talks_none': 'Hakuna hotuba zinazolingana na vichujio hivi.', 'talks_year': 'Mwaka', 'talks_year_all': 'Miaka yote', 'talks_language': 'Lugha', 'talks_lang_unknown': 'Lugha haijatajwa', 'talks_play': 'Cheza', 'talks_watch': 'Tazama kwenye jukwaa', 'talks_speakers': 'Wasemaji', 'talks_event': 'Tukio', 'talks_channel': 'Kituo', 'talks_published': 'Video ilichapishwa', 'talks_duration': 'Urefu', 'talks_held': 'Ilifanyika', 'talks_source': 'Chanzo', 'talks_calendar': 'Ingizo la kalenda', 'talks_embed_note': 'Kichezaji kinapakia kutoka jukwaani tu baada ya kubonyeza cheza.', 'talks_not_embed': 'Jukwaa hili halikutoa kichezaji kinachoweza kupachikwa. Kiungo kinaelekea kwenye video.', 'past_talks': 'Rekodi za hotuba za umma ziko katika <a href="{href}">hifadhi ya hotuba</a>.', 'c_FO': 'Visiwa vya Faroe', 'c_GL': 'Greenland', 'c_AX': 'Åland'})

# Shared shoutbox. One room; these strings are the UI only.
S.update({
"nav_chat": "Gumzo",
"chat_title": "Gumzo",
"chat_desc": "Bodi moja ya pamoja kwenye Nordic Crypto. Ujumbe wa wasomaji, si maudhui ya wahariri.",
"chat_h1": "Gumzo",
"chat_lead": "Chumba kimoja kwa kila lugha ya Nordic Crypto. Ujumbe unabaki kama ulivyoandikwa.",
"chat_shared": "Kila mtu anaona ujumbe ule ule. Ukurasa huu hauutafsiri.",
"chat_user": "Ujumbe huu umeandikwa na wasomaji. Si maudhui ya wahariri wa Nordic Crypto.",
"chat_rules": "<a href=\"{ethics}\">Kanuni</a>: hakuna unyanyasaji, hakuna kufichua taarifa binafsi, hakuna kutangaza ushauri wa kifedha, na hakuna ulaghai au viungo vya rufaa. Wasimamizi wanaweza kuondoa machapisho.",
"chat_nick": "Jina la utani",
"chat_message": "Ujumbe",
"chat_send": "Tuma",
"chat_report": "Ripoti",
"chat_reported": "Imeripotiwa. Wasimamizi wanaweza kuikagua.",
"chat_ph_nick": "Jina",
"chat_ph_msg": "Andika ujumbe",
"chat_privacy": "Bodi huhifadhi jina la utani, ujumbe, na hash ya anwani ya IP inayobadilika kila siku, ili kuzuia matumizi mabaya tu. Anwani ya IP yenyewe haihifadhiwi. Jina la utani linabaki kwenye hifadhi ya ndani ya kivinjari hiki tu, si kwenye kidakuzi. Cloudflare Web Analytics huhesabu ziara kwa jumla, bila vidakuzi, na hatuuzi data hiyo.",
"chat_full": "Fungua gumzo lote",
"chat_toggle_show": "Onyesha gumzo",
"chat_toggle_hide": "Ficha gumzo",
"chat_empty": "Bado hakuna ujumbe.",
"chat_sending": "Inatuma…",
"chat_sent": "Imetumwa.",
"chat_fail": "Imeshindwa kutuma. Jaribu tena.",
"chat_rate": "Ujumbe mwingi kwa muda mfupi. Subiri.",
"chat_spam": "Ujumbe huo umezuiwa.",
"chat_turnstile": "Kamilisha ukaguzi, kisha tuma tena.",
"chat_nick_err": "Jina la utani liwe herufi 2–24.",
"chat_msg_err": "Ujumbe uwe herufi 1–280.",
"chat_banned": "Huwezi kuandika sasa.",
"chat_older": "Ujumbe wa awali",
"chat_time_now": "sasa hivi",
"chat_time_m": "dak {n} zilizopita",
"chat_time_h": "saa {n} zilizopita",
"chat_time_d": "siku {n} zilizopita",
"chat_noscript": "Gumzo linahitaji JavaScript.",
})
