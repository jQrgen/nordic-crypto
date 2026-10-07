"""Chinese (Mandarin) (中文) site UI, /zh/.

Chrome strings fall back to English in i18n.t() until a translation is added to S.
This file does not translate article bodies or summaries. Nordic news sources are unchanged.
"""
S = {
"push_title": "通知",
"push_lead": "每次发布新报道时收到一条消息。同一次发布里的多篇报道合成一条，而不是每篇一条。",
"push_on": "打开通知",
"push_off": "关闭通知",
"push_on_status": "此浏览器已打开通知。",
"push_off_status": "通知已关闭。",
"push_topics": "国家",
"push_all": "所有北欧国家",
"push_lang_note": "消息使用本页的语言。要更换语言，请打开另一种语言的页面并再次打开通知。",
"push_privacy": "我们只保存浏览器给出的推送订阅（地址和用来加密消息的两把密钥）、本页语言以及你选择的国家。不保存姓名、电子邮箱，也不跟踪你读了什么。同一个按钮可以关闭通知并删除订阅。Cloudflare Web Analytics 汇总统计访问，不使用 cookie，我们不出售这些数据。",
"push_unsupported": "此浏览器无法显示通知。",
"push_denied": "浏览器设置已禁止本站发送通知。",
"push_ios": "在 iPhone 或 iPad 上，请先把本站添加到主屏幕。iOS 16.4 或更新版本才能使用这些浏览器通知。不使用 Apple 自己的推送服务（APNs）。",
"push_unavailable": "通知服务尚未开启。",
"push_working": "正在处理…",
"push_fail": "未能更新通知。请再试一次。",
"push_saved": "已保存。",
"push_noscript": "打开通知需要 JavaScript。",
}

S.update({'nav_talks': '演讲', 'talks_title': '演讲 – 北欧的公开加密货币演讲', 'talks_desc': '在北欧国家举行的关于比特币、加密货币和区块链的公开演讲，附视频以及上传者写明的信息。', 'talks_h1': '演讲', 'talks_lead': '自比特币白皮书以来，在挪威、瑞典、丹麦、芬兰、冰岛、法罗群岛、格陵兰和奥兰举行的关于比特币、加密货币和区块链的公开演讲录像。最新的在前。只有在你点击播放、且该平台允许嵌入时，播放器才会加载。', 'talks_n': '{n} 场演讲', 'talks_none': '没有符合这些筛选条件的演讲。', 'talks_year': '年份', 'talks_year_all': '全部年份', 'talks_language': '语言', 'talks_lang_unknown': '未注明语言', 'talks_play': '播放', 'talks_watch': '在平台上观看', 'talks_speakers': '演讲者', 'talks_event': '活动', 'talks_channel': '频道', 'talks_published': '视频发布', 'talks_duration': '时长', 'talks_held': '举行日期', 'talks_source': '来源', 'talks_calendar': '日历条目', 'talks_embed_note': '只有在你点击播放之后，播放器才会从该平台加载。', 'talks_not_embed': '该平台没有提供可嵌入的播放器。链接指向视频。', 'past_talks': '公开演讲的录像在<a href="{href}">演讲存档</a>。', 'c_FO': '法罗群岛', 'c_GL': '格陵兰', 'c_AX': '奥兰'})

# Shared shoutbox. One room; these strings are the UI only.
S.update({
"nav_chat": "聊天",
"chat_title": "聊天",
"chat_desc": "Nordic Crypto 上的一个公共喊话板。读者留言，不是编辑内容。",
"chat_h1": "聊天",
"chat_lead": "Nordic Crypto 的所有语言共用一个房间。留言保持原样，不会被翻译。",
"chat_shared": "所有人看到的是同一批留言。本页不翻译它们。",
"chat_user": "这些留言由读者撰写，不是 Nordic Crypto 的编辑内容。",
"chat_rules": "<a href=\"{ethics}\">规则</a>：禁止骚扰、人肉搜索、推销理财建议，以及诈骗或推荐链接。管理员可以删除留言。",
"chat_nick": "昵称",
"chat_message": "留言",
"chat_send": "发送",
"chat_report": "举报",
"chat_reported": "已举报。管理员可以复查。",
"chat_ph_nick": "名字",
"chat_ph_msg": "写一条留言",
"chat_privacy": "喊话板保存昵称、留言，以及每天更换的 IP 地址哈希，仅用于防止滥用。不保存原始 IP 地址。昵称只放在本浏览器的本地存储里，不是 cookie。Cloudflare Web Analytics 汇总统计访问，不使用 cookie，我们不出售这些数据。",
"chat_full": "打开完整聊天",
"chat_toggle_show": "显示聊天",
"chat_toggle_hide": "隐藏聊天",
"chat_empty": "还没有留言。",
"chat_sending": "正在发送…",
"chat_sent": "已发送。",
"chat_fail": "发送失败。请再试一次。",
"chat_rate": "短时间内留言太多。请稍等。",
"chat_spam": "这条留言被拦截了。",
"chat_turnstile": "请完成验证后再发送。",
"chat_nick_err": "昵称须为 2–24 个字符。",
"chat_msg_err": "留言须为 1–280 个字符。",
"chat_banned": "你现在不能发言。",
"chat_older": "更早的留言",
"chat_time_now": "刚刚",
"chat_time_m": "{n} 分钟前",
"chat_time_h": "{n} 小时前",
"chat_time_d": "{n} 天前",
"chat_noscript": "聊天需要 JavaScript。",
})
