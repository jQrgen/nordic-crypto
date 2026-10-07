"""Japanese (日本語) site UI, /ja/.

Chrome strings fall back to English in i18n.t() until a translation is added to S.
This file does not translate article bodies or summaries. Nordic news sources are unchanged.
"""
S = {
"push_title": "通知",
"push_lead": "新しい記事が公開されるたびに、通知は1件だけ届きます。同じ公開に複数の記事があっても、記事ごとの通知にはしません。",
"push_on": "通知をオンにする",
"push_off": "通知をオフにする",
"push_on_status": "このブラウザでは通知がオンです。",
"push_off_status": "通知はオフです。",
"push_topics": "国",
"push_all": "北欧のすべての国",
"push_lang_note": "通知はこのページの言語です。変えるには別の言語のページを開き、通知をオンにし直してください。",
"push_privacy": "保存するのはブラウザのプッシュ購読（宛先と、メッセージを暗号化するための鍵2つ）、このページの言語、選んだ国だけです。氏名もメールアドレスも、何を読んだかの追跡もありません。同じボタンで通知をオフにすると、購読は削除されます。Cloudflare Web Analytics は訪問を集計し、Cookie は使わず、そのデータは販売しません。",
"push_unsupported": "このブラウザは通知を表示できません。",
"push_denied": "ブラウザの設定で、このサイトの通知がブロックされています。",
"push_ios": "iPhone または iPad では、先にこのサイトをホーム画面に追加してください。iOS 16.4 以降で、このブラウザ通知を使えます。Apple 独自のプッシュ（APNs）は使いません。",
"push_unavailable": "通知サービスはまだオンになっていません。",
"push_working": "処理しています…",
"push_fail": "通知を更新できませんでした。もう一度試してください。",
"push_saved": "保存しました。",
"push_noscript": "通知をオンにするには JavaScript が必要です。",
}

S.update({'nav_talks': '講演', 'talks_title': '講演 – 北欧の公開クリプト講演', 'talks_desc': '北欧諸国で行われたビットコイン、暗号資産、ブロックチェーンについての公開講演。動画と、投稿者が記した事実を載せています。', 'talks_h1': '講演', 'talks_lead': 'ビットコイン白書以降、ノルウェー、スウェーデン、デンマーク、フィンランド、アイスランド、フェロー諸島、グリーンランド、オーランドで行われた、ビットコイン、暗号資産、ブロックチェーンについての公開講演の録画です。新しい順です。プレーヤーは再生を押したあと、そのプラットフォームが埋め込みを許可している場合にだけ読み込まれます。', 'talks_n': '{n} 件の講演', 'talks_none': 'この条件に合う講演はありません。', 'talks_year': '年', 'talks_year_all': 'すべての年', 'talks_language': '言語', 'talks_lang_unknown': '言語の記載なし', 'talks_play': '再生', 'talks_watch': 'プラットフォームで見る', 'talks_speakers': '講演者', 'talks_event': 'イベント', 'talks_channel': 'チャンネル', 'talks_published': '動画の公開', 'talks_duration': '長さ', 'talks_held': '開催', 'talks_source': '出典', 'talks_calendar': 'カレンダーの項目', 'talks_embed_note': 'プレーヤーは、再生を押したあとでプラットフォームから読み込まれます。', 'talks_not_embed': 'このプラットフォームは埋め込み用プレーヤーを提供していません。リンク先が動画です。', 'past_talks': '公開講演の録画は<a href="{href}">講演アーカイブ</a>にあります。', 'c_FO': 'フェロー諸島', 'c_GL': 'グリーンランド', 'c_AX': 'オーランド'})
