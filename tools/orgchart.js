(function(){
/* Who's who (org-chart/). Reads script#orgdata and window.FLAGS/CNAME/T/GRP/ROOT/LANG (build.py build_org).
   The chart is one collapsed row per country; a row's cards are only built while it is open. A country chip, a search
   (two letters or more), a #<id> link or a [data-go] link opens the rows it needs, so every entry stays reachable.
   The full list is built when its <details> opens; the industry map's country view is built on first use. */
var D=JSON.parse(document.getElementById('orgdata').textContent),E=D.entities,R=D.relations||[],by={},PP={},TX={},G={},GK=[],
 FL=window.FLAGS||{},CN=window.CNAME||{},T=window.T||{},GRP=window.GRP||{},ROOT=window.ROOT||'../',LG=window.LANG||'en';
var chart=document.getElementById('chart'),det=document.getElementById('detail'),q=document.getElementById('osearch'),stat=document.getElementById('ostat'),
 lbox=document.getElementById('olistbox'),tb=document.querySelector('#olist tbody'),im=document.getElementById('imap'),
 chips=document.querySelectorAll('.cchip'),segb=document.querySelectorAll('#secseg button'),seg='both',qv='',open={},shut={},cur=null,mapBuilt=0;
var ORDER=['NO','SE','DK','FI','IS','NORDIC','EU'],SECN={'private':tr('private'),'public':tr('public')};
var RM=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;
function tr(k,v){var s=T[k]||k;if(v)for(var x in v)s=s.split('{'+x+'}').join(v[x]);return s}
function gn(g){return GRP[g]||g}
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function fl(c){return c?(FL[c]||'<span class="cc">'+esc(c)+'</span>'):''}
/* a flag next to the country's name: hidden from screen readers, which read the name */
function fd(c){var f=FL[c];return f&&f.indexOf('<svg')===0?f.replace(/ role="img" aria-label="[^"]*"/,' aria-hidden="true"').replace(/<title>[\s\S]*?<\/title>/,''):''}
function cn(c){return c==='_'?tr('speakers'):(CN[c]||c||'')}
function ini(n){return n.split(/[\s-]+/).filter(Boolean).slice(0,2).map(function(w){return w[0]}).join('').toUpperCase()}
function lg(e,big){if(e.logo&&e.logo.file)return '<img class="logo'+(big?' big':'')+'" src="'+ROOT+esc(e.logo.file)+'" alt="'+(big?esc(tr('logo_alt',{name:e.name})):'')+'" loading="lazy" decoding="async" width="'+(big?64:24)+'" height="'+(big?64:24)+'">';return '<span class="av org" aria-hidden="true">'+esc(ini(e.name))+'</span>'}
function av(e,big){if(e.type!=='person')return lg(e,big);var c='av'+(big?' big':'');if(e.image&&e.image.file)return '<img class="'+c+'" src="'+ROOT+esc(e.image.file)+'" alt="'+(big?esc(e.name):'')+'" loading="lazy" decoding="async" width="'+(big?96:30)+'" height="'+(big?96:30)+'">';return '<span class="'+c+'" aria-hidden="true">'+esc(ini(e.name))+'</span>'}
function pend(e){return e.status&&e.status!=='published'?' <span class="tag pend">'+esc(tr('pending'))+'</span>':''}
function rel(id){return R.filter(function(r){return r.from===id||r.to===id})}
/* where an entry is shown: a person with an organisation sits on that organisation's card */
function host(e){return e.type==='person'&&e.org&&by[e.org]?by[e.org]:e}
function gk(e){return host(e).country||'_'}
function sec(e){return host(e).sector}
function rank(g){var i=ORDER.indexOf(g);return g==='_'?999:i<0?100:i}
E.forEach(function(e){by[e.id]=e;PP[e.id]=[]});
E.forEach(function(e){var o=e.org&&by[e.org];if(e.type==='person'&&o)PP[o.id].push(e);
 TX[e.id]=(e.name+' '+(e.role||'')+' '+(o?o.name:'')+' '+(e.description||'')+' '+(e.group?e.group+' '+gn(e.group):'')+' '+cn(e.country)).toLowerCase();
 var g=gk(e);if(!G[g]){G[g]={orgs:[],loose:[],n:0};GK.push(g)}G[g].n++;
 if(e.type!=='person')G[g].orgs.push(e);else if(host(e)===e)G[g].loose.push(e)});
GK.sort(function(a,b){return rank(a)-rank(b)||cn(a).localeCompare(cn(b),LG)});
function byName(a,b){return a.name.localeCompare(b.name,LG)}
GK.forEach(function(g){G[g].orgs.sort(byName);G[g].loose.sort(byName)});
for(var id in PP)PP[id].sort(byName);
function selC(){return [].slice.call(chips).filter(function(b){return b.getAttribute('aria-pressed')==='true'}).map(function(b){return b.dataset.c})}
function cOk(e){var c=selC();return !c.length||c.indexOf(gk(e))>=0}
function sOk(e){return seg==='both'||sec(e)===seg}
function m(e){return !qv||TX[e.id].indexOf(qv)>=0}
/* shown in the chart under the current search: an organisation when it or one of its people matches */
function hit(e){var h=host(e);if(h!==e)return m(h)||m(e);return e.type==='person'?m(e):m(e)||PP[e.id].some(m)}
function stats(g){var o=0,p=0,n=0;G[g].orgs.forEach(function(e){if(!sOk(e))return;if(!qv){o++;p+=PP[e.id].length}else n+=(m(e)?1:0)+PP[e.id].filter(m).length});
 G[g].loose.forEach(function(e){if(!sOk(e))return;if(!qv)p++;else if(m(e))n++});return {o:o,p:p,n:n}}
function plural(n,one,many){return n===1?tr(one):tr(many,{n:n})}
function count(s){if(qv)return plural(s.n,'n_match1','n_match');var a=[];if(s.o)a.push(plural(s.o,'n_org1','n_orgs'));if(s.p)a.push(plural(s.p,'n_person1','n_people'));return a.join(' · ')}
function pchip(p){return '<button type="button" class="person" data-id="'+esc(p.id)+'">'+av(p)+'<span class="pt"><b>'+esc(p.name)+'</b>'+esc(p.role||'')+'</span></button>'}
function xs(e){var s={};rel(e.id).forEach(function(r){var o=by[r.from===e.id?r.to:r.from];if(o&&o.sector!==e.sector)s[o.sector]=1});
 return Object.keys(s).map(function(k){return '<span class="xl '+(k==='public'?'pub':'priv')+'" title="'+esc(tr('link_to',{s:tr('x_'+k)}))+'">↔ '+esc(tr('x_'+k))+'</span>'}).join('')}
function card(o){var pp=PP[o.id].filter(function(p){return !qv||m(o)||m(p)}).map(pchip).join('');
 return '<li class="card" data-id="'+esc(o.id)+'"><button type="button" class="nm">'+lg(o)+'<span>'+esc(o.name)+'</span></button>'+xs(o)+pend(o)+(o.description?'<p class="ds" lang="en">'+esc(o.description)+'</p>':'')+(pp?'<div class="people">'+pp+'</div>':'')+'</li>'}
function body(g){var cols=seg==='both'?['private','public']:[seg],out=[];
 cols.forEach(function(s){var gr={},h='';G[g].orgs.forEach(function(o){if(o.sector===s&&hit(o)){var k=o.group?gn(o.group):tr('other');(gr[k]=gr[k]||[]).push(o)}});
  Object.keys(gr).sort(function(a,b){return a.localeCompare(b,LG)}).forEach(function(k){h+='<h5>'+esc(k)+'</h5><ul class="cards">'+gr[k].map(card).join('')+'</ul>'});
  var lo=G[g].loose.filter(function(p){return p.sector===s&&m(p)});
  if(lo.length)h+=(g==='_'?'':'<h5>'+esc(tr('people'))+'</h5>')+'<div class="people">'+lo.map(pchip).join('')+'</div>';
  if(h)out.push('<div class="col col-'+s+'"><h4>'+esc(SECN[s])+'</h4>'+h+'</div>')});
 return out.length?'<div class="cols'+(out.length>1?' two':'')+'">'+out.join('')+'</div>':'<p class="empty">'+esc(tr('nothing'))+'</p>'}
function isOpen(g){return qv?!shut[g]:!!open[g]}
function render(){var c=selC(),h='',tot=0;
 GK.forEach(function(g){if(c.length&&c.indexOf(g)<0)return;var s=stats(g);if(qv?!s.n:!(s.o||s.p))return;tot+=s.n;var o=isOpen(g),id='g-'+esc(g);
  h+='<section class="cgrp" data-c="'+esc(g)+'"><h3><button type="button" class="gh" aria-expanded="'+o+'" aria-controls="'+id+'" data-g="'+esc(g)+'">'+fd(g)+'<span class="gt"><span class="gn">'+esc(cn(g))+'</span><span class="gc">'+esc(count(s))+'</span></span></button></h3><div class="gb" id="'+id+'"'+(o?'':' hidden')+'>'+(o?body(g):'')+'</div></section>'});
 chart.innerHTML=h||'<p class="empty">'+esc(tr(qv?'no_match':'nothing'))+'</p>';
 stat.textContent=qv?plural(tot,'n_match1','n_match'):'';
 if(lbox&&lbox.open)list();if(cur)hl(cur)}
function toggle(g){var sct=chart.querySelector('.cgrp[data-c="'+g+'"]');if(!sct)return;var o=!isOpen(g);if(qv)shut[g]=!o;else open[g]=o;
 var b=sct.querySelector('.gh'),bd=sct.querySelector('.gb');b.setAttribute('aria-expanded',o);bd.hidden=!o;bd.innerHTML=o?body(g):'';if(o&&cur)hl(cur)}
function hl(id){var e=by[id],ids={};if(!e)return;ids[id]=1;rel(id).forEach(function(r){ids[r.from]=1;ids[r.to]=1});if(e.org)ids[e.org]=1;PP[id].forEach(function(p){ids[p.id]=1});
 [].forEach.call(chart.querySelectorAll('[data-id]'),function(n){n.classList.toggle('hl',!!ids[n.dataset.id])})}
function srcs(list){return '<ul>'+list.map(function(s){return '<li><a href="'+esc(s.url)+'" target="_blank" rel="noopener">'+esc(s.title||s.url)+'</a> <span class="meta">('+esc(s.source_name||'')+(s.date?', '+esc(s.date):'')+')</span></li>'}).join('')+'</ul>'}
function show(id){var e=by[id];if(!e)return;cur=id;hl(id);var rs=rel(id);
 var img=e.image&&e.image.file?'<div>'+av(e,1)+'<div class="credit">'+esc(tr('photo'))+': '+esc(e.image.author||'')+(e.image.license?', '+(e.image.license_url?'<a href="'+esc(e.image.license_url)+'" rel="noopener license" target="_blank">'+esc(e.image.license)+'</a>':esc(e.image.license)):'')+', <a href="'+esc(e.image.source_page)+'" rel="noopener" target="_blank">'+esc(tr('source'))+'</a></div></div>':(e.type==='person'?'<div>'+av(e,1)+'</div>':(e.logo&&e.logo.file?'<div>'+lg(e,1)+'<div class="credit">'+esc(tr('logo'))+': <a href="'+esc(e.logo.source_url)+'" rel="noopener" target="_blank">'+esc(tr('source'))+'</a></div></div>':''));
 var pf=(e.profiles||[]).map(function(p){return '<a href="'+esc(p.url)+'" rel="noopener nofollow" target="_blank">'+esc(p.label||p.kind)+'</a>'+(p.status!=='published'?' <span class="tag pend">'+esc(tr('pending'))+'</span>':'')}).join(' · ');
 var rl=rs.map(function(r){var o=by[r.from===id?r.to:r.from];return '<li><b lang="en">'+esc(r.label||r.type)+'</b>: <a href="#'+esc(o.id)+'" data-go="'+esc(o.id)+'">'+esc(o.name)+'</a> '+fl(o.country)+(o.sector!==e.sector?' <span class="xl '+(o.sector==='public'?'pub':'priv')+'">↔ '+esc(tr('x_'+o.sector))+'</span>':'')+' – '+esc(tr('source'))+': '+(r.sources||[]).map(function(s){return '<a href="'+esc(s.url)+'" target="_blank" rel="noopener">'+esc(s.source_name||tr('link'))+'</a>'}).join(', ')+'</li>'}).join('');
 var org=e.org&&by[e.org]?'<p>'+esc(e.role||'')+', <a href="#'+esc(e.org)+'" data-go="'+esc(e.org)+'">'+esc(by[e.org].name)+'</a></p>':(e.role?'<p>'+esc(e.role)+'</p>':'');
 var aff=(e.affiliations||[]).map(function(a){var role=a.role?esc(a.role)+', ':'';var when=a.date?' <span class="meta">('+esc(a.date)+')</span>':'';var src=a.source_url?' <span class="meta"><a href="'+esc(a.source_url)+'" rel="noopener" target="_blank">'+esc(a.source_name||tr('source'))+'</a></span>':'';return '<li>'+role+esc(a.organisation||'')+when+src+'</li>'}).join('');
 var tks=(e.talks||[]).map(function(tk){var ev=tk.event_id?' · <a href="'+ROOT+'calendar/'+esc(tk.event_id)+'/">'+esc(tr('event'))+'</a>':'';return '<li><a href="'+ROOT+'talks/#'+esc(tk.id)+'">'+esc(tk.title||tk.id)+'</a>'+ev+'</li>'}).join('');
 var where=e.country?fl(e.country)+' '+esc(cn(e.country))+' · ':'';
 det.innerHTML='<button class="close" type="button" aria-label="'+esc(tr('close'))+'">×</button><div class="row">'+img+'<div><h3>'+esc(e.name)+pend(e)+'</h3><div class="meta">'+where+(e.type==='person'?esc(tr('person')):esc(e.group?gn(e.group):tr('org')))+' · '+esc(SECN[e.sector]||'')+(e.url?' · <a href="'+esc(e.url)+'" target="_blank" rel="noopener">'+esc(tr('website'))+'</a>':'')+'</div>'+org+(e.description?'<p lang="en">'+esc(e.description)+'</p>':'')+(aff?'<h4>'+esc(tr('affiliation'))+'</h4><ul>'+aff+'</ul>':'')+(tks?'<h4>'+esc(tr('talks'))+'</h4><ul>'+tks+'</ul>':'')+(pf?'<p class="meta">'+esc(tr('profiles'))+': '+pf+'</p>':'')+'</div></div>'+(rl?'<h4>'+esc(tr('links'))+'</h4><ul>'+rl+'</ul>':'')+'<h4>'+esc(tr('sources'))+'</h4>'+srcs(e.sources||[]);
 det.hidden=false;try{history.replaceState(null,'','#'+encodeURIComponent(id))}catch(x){}}
function close(){det.hidden=true;cur=null;[].forEach.call(chart.querySelectorAll('.hl'),function(n){n.classList.remove('hl')});try{history.replaceState(null,'',location.pathname+location.search)}catch(x){}}
function setSeg(v){seg=v;[].forEach.call(segb,function(x){x.setAttribute('aria-pressed',x.dataset.v===v?'true':'false')})}
/* open everything needed to see one entry, then show it */
function reveal(id,instant){var x=by[id];if(!x)return;
 if(!cOk(x)){[].forEach.call(chips,function(b){b.setAttribute('aria-pressed','false')});regf();mapf()}
 if(!sOk(x))setSeg('both');
 if(qv&&!hit(x)){q.value='';qv=''}
 open[gk(x)]=1;shut={};render();show(id);
 var n=chart.querySelector('[data-id="'+(window.CSS&&CSS.escape?CSS.escape(id):id)+'"]');if(n)n.scrollIntoView({block:'center',behavior:instant||RM?'auto':'smooth'})}
function go(ev){var a=ev.target.closest('[data-go]');if(!a)return;ev.preventDefault();reveal(a.dataset.go)}
chart.addEventListener('click',function(ev){var b=ev.target.closest('.gh');if(b){toggle(b.dataset.g);return}if(ev.target.closest('a'))return;var n=ev.target.closest('[data-id]');if(n)show(n.dataset.id)});
det.addEventListener('click',function(ev){if(ev.target.closest('.close')){close();return}go(ev)});
document.addEventListener('keydown',function(ev){if(ev.key==='Escape'&&!det.hidden)close()});
[].forEach.call(segb,function(b){b.addEventListener('click',function(){setSeg(b.dataset.v);render()})});
function regf(){var c=selC();[].forEach.call(document.querySelectorAll('.reg article[data-c]'),function(a){a.hidden=!!(c.length&&c.indexOf(a.dataset.c)<0)})}
function mapf(){var c=selC();if(!im)return;[].forEach.call(im.querySelectorAll('.tile[data-c]'),function(t){t.hidden=!!(c.length&&c.indexOf(t.dataset.c)<0)});[].forEach.call(im.querySelectorAll('.imap-cat'),function(s){s.hidden=!s.querySelector('.tile:not([hidden])')})}
[].forEach.call(chips,function(b){var g=G[b.dataset.c];if(g)b.insertAdjacentHTML('beforeend','<span class="n">'+g.n+'</span>');
 b.addEventListener('click',function(){var on=b.getAttribute('aria-pressed')!=='true';b.setAttribute('aria-pressed',on?'true':'false');if(on)open[b.dataset.c]=1;regf();render();mapf()})});
var qt;q.addEventListener('input',function(){clearTimeout(qt);qt=setTimeout(function(){var v=q.value.trim().toLowerCase();v=v.length>1?v:'';if(v!==qv){qv=v;shut={};render()}},150)});
/* industry map: the country view is built from the category view's tiles the first time it is asked for */
function mapByCountry(){var g={},cs=[];[].forEach.call(im.querySelectorAll('.imap-bycat .tile'),function(t){var c=t.dataset.c;if(!g[c]){g[c]=[];cs.push(c)}g[c].push(t)});
 cs.sort(function(a,b){return rank(a)-rank(b)||cn(a).localeCompare(cn(b),LG)});var w=document.createElement('div');w.className='imap-cats imap-bycountry';
 w.innerHTML=cs.map(function(c){return '<section class="imap-cat" data-c="'+esc(c)+'"><h3>'+fd(c)+esc(cn(c))+' <span class="n">'+g[c].length+'</span></h3><div class="tiles"></div></section>'}).join('');
 cs.forEach(function(c,i){var d=w.children[i].lastChild;g[c].forEach(function(t){d.appendChild(t.cloneNode(true))})});im.appendChild(w);mapBuilt=1}
if(im){var vb=document.querySelectorAll('button[data-view]');[].forEach.call(vb,function(b){b.addEventListener('click',function(){if(b.dataset.view==='country'&&!mapBuilt){mapByCountry();mapf()}
 [].forEach.call(vb,function(x){x.setAttribute('aria-pressed',x===b?'true':'false')});im.setAttribute('data-view',b.dataset.view)})});
 im.addEventListener('click',go)}
function list(){tb.innerHTML=E.slice().sort(function(a,b){return rank(a.country||'_')-rank(b.country||'_')||a.name.localeCompare(b.name,LG)}).filter(function(e){return cOk(e)&&sOk(e)&&m(e)}).map(function(e){var o=e.org&&by[e.org]?by[e.org].name:'';
 return '<tr><td><a href="#'+esc(e.id)+'" data-go="'+esc(e.id)+'">'+esc(e.name)+'</a>'+pend(e)+'</td><td>'+(e.country?fd(e.country)+' '+esc(cn(e.country)):'')+'</td><td>'+(e.type==='person'?esc(tr('person')):esc(e.group?gn(e.group):tr('org')))+'</td><td>'+esc(e.sector==='public'?tr('pub'):tr('priv'))+'</td><td lang="en">'+esc(e.type==='person'?(e.role||'')+(o?', '+o:''):(e.description||''))+'</td><td>'+(e.sources||[]).map(function(s,i){return '<a href="'+esc(s.url)+'" target="_blank" rel="noopener">'+esc(s.source_name||tr('source_n',{n:i+1}))+'</a>'}).join(', ')+'</td></tr>'}).join('')}
if(lbox){lbox.addEventListener('toggle',function(){if(lbox.open)list();else tb.innerHTML=''});document.getElementById('olist').addEventListener('click',go)}
var h=decodeURIComponent(location.hash.slice(1));
if(h.indexOf('country=')===0){h.slice(8).split(',').forEach(function(x){[].forEach.call(chips,function(b){if(b.dataset.c===x){b.setAttribute('aria-pressed','true');open[x]=1}})});h='';regf()}
render();mapf();if(h&&by[h])reveal(h,1);
window.addEventListener('hashchange',function(){var x=decodeURIComponent(location.hash.slice(1));if(by[x]&&x!==cur)reveal(x)});
})();
