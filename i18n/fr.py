"""French (Français) site UI, /fr/.

Chrome strings fall back to English in i18n.t() until a translation is added to S.
This file does not translate article bodies or summaries. Nordic news sources are unchanged.
"""
S = {
"push_title": "Notifications",
"push_lead": "Un seul message à chaque publication de nouveaux sujets. Plusieurs sujets dans la même publication forment un seul message, pas un par sujet.",
"push_on": "Activer les notifications",
"push_off": "Désactiver les notifications",
"push_on_status": "Les notifications sont activées pour ce navigateur.",
"push_off_status": "Les notifications sont désactivées.",
"push_topics": "Pays",
"push_all": "Tous les pays nordiques",
"push_lang_note": "Les messages utilisent la langue de cette page. Ouvrez une autre langue et activez à nouveau les notifications pour en changer.",
"push_privacy": "Nous ne conservons que l’abonnement push de votre navigateur (l’adresse et les deux clés qui chiffrent le message), la langue de cette page et les pays que vous choisissez. Pas de nom, pas d’adresse e-mail, et aucun suivi de ce que vous lisez. Le même bouton désactive les notifications et supprime l’abonnement. Cloudflare Web Analytics compte les visites de façon agrégée, sans cookies, et nous ne vendons pas ces données.",
"push_unsupported": "Ce navigateur ne peut pas afficher de notifications.",
"push_denied": "Les notifications sont bloquées pour ce site dans les réglages du navigateur.",
"push_ios": "Sur iPhone ou iPad, ajoutez d’abord le site à l’écran d’accueil. iOS 16.4 ou plus récent peut ensuite utiliser ces notifications du navigateur. Le service push d’Apple (APNs) n’est pas utilisé.",
"push_unavailable": "Le service de notification n’est pas encore activé.",
"push_working": "Patientez …",
"push_fail": "Impossible de mettre à jour les notifications. Réessayez.",
"push_saved": "Enregistré.",
"push_noscript": "Activer les notifications nécessite JavaScript.",
}

S.update({'nav_talks': 'Exposés', 'talks_title': 'Exposés – conférences publiques sur la crypto dans les pays nordiques', 'talks_desc': 'Exposés publics sur le bitcoin, les cryptomonnaies et la blockchain tenus dans les pays nordiques, avec la vidéo et les faits indiqués par la chaîne.', 'talks_h1': 'Exposés', 'talks_lead': 'Enregistrements d’exposés publics sur le bitcoin, les cryptomonnaies et la blockchain tenus en Norvège, en Suède, au Danemark, en Finlande, en Islande, aux îles Féroé, au Groenland et aux îles Åland depuis le livre blanc du bitcoin. Les plus récents d’abord. Le lecteur ne se charge qu’après un clic sur lecture, et seulement si la plateforme autorise l’intégration.', 'talks_n': '{n} exposés', 'talks_none': 'Aucun exposé ne correspond à ces filtres.', 'talks_year': 'Année', 'talks_year_all': 'Toutes les années', 'talks_language': 'Langue', 'talks_lang_unknown': 'Langue non indiquée', 'talks_play': 'Lecture', 'talks_watch': 'Voir sur la plateforme', 'talks_speakers': 'Intervenants', 'talks_event': 'Événement', 'talks_channel': 'Chaîne', 'talks_published': 'Vidéo publiée', 'talks_duration': 'Durée', 'talks_held': 'Tenu', 'talks_source': 'Source', 'talks_calendar': 'Entrée du calendrier', 'talks_embed_note': 'Le lecteur se charge depuis la plateforme seulement après un clic sur lecture.', 'talks_not_embed': 'Cette plateforme n’a pas proposé de lecteur intégrable. Le lien mène à la vidéo.', 'past_talks': 'Les enregistrements d’exposés publics sont dans les <a href="{href}">archives des exposés</a>.', 'c_FO': 'Îles Féroé', 'c_GL': 'Groenland', 'c_AX': 'Åland'})
