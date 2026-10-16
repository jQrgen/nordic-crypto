import subprocess,base64,io
T="#1E3A45";G="#D9A034"
try:
    import qrcode
    b=io.BytesIO();qrcode.make("tdpp://nordiccrypto.no/sendto?chain=nexa&amt0=EXAMPLE&addr0=nexa%3A...&cookie=EXAMPLE&sig=...").save(b);QR='<img src="data:image/png;base64,'+base64.b64encode(b.getvalue()).decode()+'" style="width:190px">'
except Exception: QR='<div style="width:190px;height:190px;background:repeating-conic-gradient(#000 0 25%,#fff 0 50%) 0 0/24px 24px;margin:auto"></div>'
CSS=f"""body{{margin:0;font-family:Inter,Arial,sans-serif;background:#F4F1EA;color:{T}}}
.nav{{background:{T};color:#fff;padding:16px 32px;display:flex;justify-content:space-between;align-items:center}}
.logo{{font-weight:800;font-size:22px}}.logo b{{color:{G}}}
.btn{{background:{G};color:{T};border:0;border-radius:8px;padding:12px 18px;font-weight:700;display:inline-block}}
.btn2{{border:2px solid {T};border-radius:8px;padding:10px 16px;font-weight:700;display:inline-block}}
.card{{background:#fff;border-radius:14px;padding:22px;box-shadow:0 2px 10px #0002}}
.note{{background:#FFF4DC;border-left:4px solid {G};padding:8px 12px;font-size:13px}}
.ex{{font-size:12px;color:#7a6a3a}}
.phone{{width:330px;height:660px;border:12px solid #111;border-radius:40px;background:#fff;overflow:hidden;position:relative;box-shadow:0 6px 20px #0004}}
.wbar{{background:#2b6cb0;color:#fff;padding:14px;font-weight:700;font-size:16px}}
.sec{{text-align:center;font-weight:700;margin:14px 8px 2px;font-size:15px;color:#333}}
.val{{text-align:center;font-size:14px;color:#111}}
.wbtns{{position:absolute;bottom:0;left:0;right:0;display:flex;gap:8px;padding:14px;background:#fff;border-top:1px solid #ddd}}
.wbtns div{{flex:1;text-align:center;padding:12px;border-radius:24px;font-weight:700}}
.lbl{{font-size:13px;font-weight:700;letter-spacing:1px;color:#666;text-transform:uppercase;margin:8px 0}}
.wrap{{display:flex;gap:40px;padding:30px;align-items:flex-start}}
"""
NAV='<div class="nav"><div class="logo">Nordic <b>Crypto</b></div><div>News · Analysis · Newsletter · <span class="btn" style="padding:6px 12px">Sponsor</span></div></div>'
def page(name,body,w=1400,h=900):
    open(name+".html","w").write(f"<html><head><style>{CSS}</style></head><body>{body}</body></html>")
    subprocess.run(["google-chrome","--headless=new","--no-sandbox","--disable-gpu","--hide-scrollbars",f"--window-size={w},{h}",f"--screenshot=/workspace/mock/{name}.png",f"file:///workspace/mock/{name}.html"],capture_output=True)
def wally(title,inner,btns=None):
    b=f'<div class="wbtns"><div style="background:#2b6cb0;color:#fff">{btns[0]}</div><div style="border:2px solid #2b6cb0;color:#2b6cb0">{btns[1]}</div></div>' if btns else ''
    return f'<div><div class="lbl">Wally Wallet (phone)</div><div class="phone"><div class="wbar">← {title}</div>{inner}{b}</div><div class="ex" style="width:330px;margin-top:6px">Approximation of Wally layout; labels quoted from Wally i18n strings (see issue for file refs).</div></div>'
def web(inner,w=900):
    return f'<div><div class="lbl">nordiccrypto.no (browser)</div><div style="width:{w}px;background:#F4F1EA;border-radius:10px;overflow:hidden;box-shadow:0 6px 20px #0003">{NAV}<div style="padding:24px">{inner}</div></div></div>'
tier=lambda n,p,d,f=False:f'<div class="card" style="flex:1;{"border:3px solid "+G if f else ""}"><h3 style="margin:0">{n}</h3><div style="font-size:28px;font-weight:800;margin:10px 0">{p}</div><div class="ex">EXAMPLE PRICE ONLY</div><p style="font-size:14px">{d}</p><span class="btn">Sponsor with Nexa</span></div>'
# 01
page("01-sponsor-page",NAV+f'''<div style="padding:40px 80px"><h1 style="margin:0">Sponsor Nordic Crypto</h1><p>Support independent Nordic crypto journalism. Pay directly from your Nexa wallet with Wally (TDPP). Funds go straight to our self-custodial Nexa address.</p>
<div style="display:flex;gap:24px;margin:24px 0">{tier("Supporter","X NEXA","One-off sponsorship. Optional name on the sponsor wall.")}{tier("Monthly Sponsor","Y NEXA / month","Recurring via Wally TDPP registration + monthly request. Name on wall + newsletter mention.",True)}{tier("Partner","Z NEXA / month","Logo on sponsor wall + newsletter acknowledgement (terms TBD).")}</div>
<label><input type="checkbox" checked> Show my name publicly on the sponsor wall</label> &nbsp; <input placeholder="Display name (optional)" style="padding:8px;width:260px">
<p class="note">Prices are placeholders for design only. Sponsorship terms, receipts and VAT handling to be confirmed (see issue: open questions).</p></div>''',1400,820)
# 02
modal=f'''<div class="card" style="text-align:center;max-width:520px;margin:auto"><h2 style="margin-top:0">Pay with Wally Wallet</h2><div>Monthly Sponsor · <b>Y NEXA</b> <span class="ex">(example)</span></div>
<p style="font-size:14px">Step 1 of 2: approve <b>nordiccrypto.no</b> as a service in Wally (one time). Then approve the payment.</p>{QR}
<p style="font-size:13px">Scan with Wally, or on mobile:</p><span class="btn">Open in Wally</span>
<p style="font-size:12px;word-break:break-all;color:#555">tdpp://nordiccrypto.no/reg?addr=nexa:…&amp;topic=sponsor&amp;uoa=NEX&amp;maxper=…&amp;sig=…</p><div class="btn2">Cancel</div></div>'''
reg=wally("Trickle Pay",f'''<div class="sec">Accept or reject Service</div><div class="val">nordiccrypto.no:sponsor</div>
<div class="sec">Allow Limited Automatic Approval</div><div class="val" style="font-size:13px">Maximum per request: … NEXA<br>Maximum per month: … NEXA</div><div class="ex" style="text-align:center;padding:6px">(values suggested by site, editable by user)</div>''',("accept","deny"))
page("02-qr-modal-and-wally-registration",'<div class="wrap">'+web(modal)+reg+'</div>',1400,900)
# 03
wait=f'''<div class="card" style="text-align:center;max-width:520px;margin:auto"><h2 style="margin-top:0">Approve payment in Wally</h2><div>Monthly Sponsor · <b>Y NEXA</b> <span class="ex">(example)</span></div>{QR}
<p style="font-size:12px;word-break:break-all;color:#555">tdpp://nordiccrypto.no/sendto?chain=nexa&amp;addr0=nexa:…&amp;amt0=…&amp;topic=sponsor&amp;reason=Nordic+Crypto+monthly+sponsor&amp;cookie=…&amp;sig=…</p>
<p>⏳ Waiting for Wally… (the site also checks the chain via Rostrum)</p><div class="btn2">Cancel</div></div>'''
pay=wally("Trickle Pay",'''<div style="margin:12px;padding:8px;border:1px solid #ccc;border-radius:20px;text-align:center;font-size:13px">[account pill] My Nexa account</div>
<div class="sec">Payment Requested By</div><div class="val">nordiccrypto.no:sponsor</div><div class="sec">Using Account</div><div class="val">My Nexa account (NEXA)</div>
<div class="sec">Spends</div><div class="val"><b>Y NEXA</b> (example)</div><div class="val" style="font-size:13px;margin-top:4px">Nordic Crypto monthly sponsor</div>
<div class="sec">Will Not Automatically Sign Because</div><div class="val" style="font-size:13px">Exceeds per request maximum</div>''',("accept","deny"))
page("03-payment-request-web-and-wally",'<div class="wrap">'+web(wait)+pay+'</div>',1400,900)
# 04
ok=f'''<div class="card" style="text-align:center;max-width:560px;margin:auto"><div style="font-size:56px;color:{G}">✓</div><h2>Thank you for sponsoring Nordic Crypto!</h2><p>Payment received: <b>Y NEXA</b> <span class="ex">(example)</span><br><span style="font-size:13px">tx: 3f9a…c21e · seen on-chain</span></p>
<p style="font-size:14px">Your name “Ola N.” will appear on the sponsor wall.</p><span class="btn">See sponsor wall</span> <span class="btn2">Back to news</span><p class="note" style="text-align:left;margin-top:16px">Receipt/invoice: TBD pending tax review.</p></div>'''
done=wally("Home",'''<div style="margin:60px 16px 0;background:#2e7d32;color:#fff;padding:14px;border-radius:8px;text-align:center;font-weight:700">Payment accepted</div>
<div class="sec" style="margin-top:30px">Recent activity</div><div class="val" style="font-size:13px;padding:0 12px">−Y NEXA · Trickle Pay nordiccrypto.no:sponsor. Nordic Crypto monthly sponsor</div>
<div class="ex" style="padding:16px;text-align:center">Wally POSTs {resultCode:200, txid, txidem, tx} to https://nordiccrypto.no/sendto?cookie=…</div>''')
page("04-success-web-and-wally",'<div class="wrap">'+web(ok)+done+'</div>',1400,900)
# 05
names=["Ola N.","Kari B.","Anonymous ×12","Fjord Labs AS (logo)","Sven K.","Mette L.","Aurora DAO (logo)","Jonas P."]
cells="".join(f'<div class="card" style="text-align:center;font-weight:700">{n}<div class="ex">{"Partner" if "logo" in n else "Monthly" if i%2 else "Supporter"}</div></div>' for i,n in enumerate(names))
page("05-sponsor-wall",NAV+f'<div style="padding:40px 80px"><h1>Our sponsors</h1><p>Thanks to everyone who keeps Nordic Crypto independent. Names shown only with opt-in consent. <span class="ex">(Sample names — fictional placeholders)</span></p><div style="display:grid;grid-template-columns:repeat(4,1fr);gap:18px">{cells}</div><p style="margin-top:30px"><span class="btn">Become a sponsor</span></p></div>',1400,700)
