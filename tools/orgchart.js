(function(){
var D=JSON.parse(document.getElementById('orgdata').textContent),E=D.entities,R=D.relations,by={},FL=window.FLAGS||{},CN=window.CNAME||{};E.forEach(function(e){by[e.id]=e});
var chart=document.getElementById('chart'),det=document.getElementById('detail'),q=document.getElementById('osearch'),tb=document.querySelector('#olist tbody'),seg='both';
var ORDER=['NO','SE','FI','IS','FO','NORDIC','EU'],SECN={'private':'Private sector','public':'Public sector'};
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function fl(c){return FL[c]||'<span class="cc">'+esc(c||'')+'</span>'}
function cn(c){return CN[c]||c||''}
function ini(n){return n.split(/[\s-]+/).filter(Boolean).slice(0,2).map(function(w){return w[0]}).join('').toUpperCase()}
function av(e,big){var c='av'+(big?' big':'');if(e.image&&e.image.file)return '<img class="'+c+'" src="../'+esc(e.image.file)+'" alt="'+esc(e.name)+'" loading="lazy" width="'+(big?96:34)+'" height="'+(big?96:34)+'">';return '<span class="'+c+'" aria-hidden="true">'+esc(ini(e.name))+'</span>'}
function pend(e){return e.status&&e.status!=='published'?' <span class="tag pend">Pending editor review</span>':''}
function rel(id){return R.filter(function(r){return r.from===id||r.to===id})}
function xs(e){var s={};rel(e.id).forEach(function(r){var o=by[r.from===e.id?r.to:r.from];if(o&&o.sector!==e.sector)s[o.sector]=1});
 if(e.type==='person'&&e.org&&by[e.org]&&by[e.org].sector!==e.sector)s[by[e.org].sector]=1;
 return Object.keys(s).map(function(k){return '<span class="xl '+(k==='public'?'pub':'priv')+'" title="Link to the '+k+' sector">↔ '+k+'</span>'}).join('')}
function people(o){return E.filter(function(p){return p.type==='person'&&p.org===o.id})}
function selC(){return [].slice.call(document.querySelectorAll('.cchip[aria-pressed=true]')).map(function(b){return b.dataset.c})}
function cOk(e){var c=selC();return !c.length||c.indexOf(e.country)>=0}
function pchip(p){return '<span class="person" role="button" tabindex="0" data-id="'+esc(p.id)+'">'+av(p)+'<span><b>'+esc(p.name)+'</b><br>'+esc(p.role||'')+'</span></span>'}
function render(){var h='';['private','public'].forEach(function(sec){
 h+='<div class="col col-'+sec+'"><h2>'+SECN[sec]+'</h2>';var any=0;
 ORDER.concat(Object.keys(CN).filter(function(c){return ORDER.indexOf(c)<0})).forEach(function(c){
  var orgs=E.filter(function(e){return e.sector===sec&&e.type!=='person'&&e.country===c&&cOk(e)}),loose=E.filter(function(p){return p.type==='person'&&p.sector===sec&&p.country===c&&!(p.org&&by[p.org])&&cOk(p)});
  if(!orgs.length&&!loose.length)return;any=1;var groups={};orgs.forEach(function(o){(groups[o.group||'Other']=groups[o.group||'Other']||[]).push(o)});
  h+='<section class="cgrp" data-c="'+esc(c)+'"><h3>'+fl(c)+esc(cn(c))+' <span class="meta">('+orgs.length+')</span></h3>';
  Object.keys(groups).sort().forEach(function(g){h+='<div class="grp"><h4>'+esc(g)+'</h4>';groups[g].sort(function(a,b){return a.name.localeCompare(b.name,'en')}).forEach(function(o){
   var pp=people(o).map(pchip).join('');
   h+='<div class="card" role="button" tabindex="0" data-id="'+esc(o.id)+'"><div class="nm">'+esc(o.name)+xs(o)+pend(o)+'</div><div class="ds">'+esc(o.description||'')+'</div>'+(pp?'<div class="people">'+pp+'</div>':'')+'</div>'});h+='</div>'});
  if(loose.length)h+='<div class="grp"><h4>People</h4><div class="people">'+loose.map(pchip).join('')+'</div></div>';
  h+='</section>'});
 if(!any)h+='<p class="empty">Nothing in this sector for the selected countries.</p>';
 h+='</div>'});chart.innerHTML=h;chart.className='cols'+(seg==='both'?'':' only-'+seg);list()}
function srcs(list){return '<ul>'+list.map(function(s){return '<li><a href="'+esc(s.url)+'" target="_blank" rel="noopener">'+esc(s.title||s.url)+'</a> <span class="meta">('+esc(s.source_name||'')+(s.date?', '+esc(s.date):'')+')</span></li>'}).join('')+'</ul>'}
function show(id){var e=by[id];if(!e)return;var rs=rel(id),ids={};ids[id]=1;rs.forEach(function(r){ids[r.from]=1;ids[r.to]=1});if(e.org)ids[e.org]=1;people(e).forEach(function(p){ids[p.id]=1});
 [].forEach.call(chart.querySelectorAll('[data-id]'),function(n){n.classList.toggle('hl',!!ids[n.dataset.id])});
 var img=e.image&&e.image.file?'<div>'+av(e,1)+'<div class="credit">Photo: '+esc(e.image.author||'')+', <a href="'+esc(e.image.license_url||'#')+'" rel="noopener license" target="_blank">'+esc(e.image.license)+'</a>, <a href="'+esc(e.image.source_page)+'" rel="noopener" target="_blank">source</a></div></div>':(e.type==='person'?'<div>'+av(e,1)+'</div>':'');
 var rl=rs.map(function(r){var o=by[r.from===id?r.to:r.from];return '<li><b>'+esc(r.label||r.type)+'</b>: <a href="#" data-go="'+esc(o.id)+'">'+esc(o.name)+'</a> '+fl(o.country)+(o.sector!==e.sector?' <span class="xl '+(o.sector==='public'?'pub':'priv')+'">↔ '+o.sector+'</span>':'')+' – source: '+r.sources.map(function(s){return '<a href="'+esc(s.url)+'" target="_blank" rel="noopener">'+esc(s.source_name||'link')+'</a>'}).join(', ')+'</li>'}).join('');
 var org=e.org&&by[e.org]?'<p>'+esc(e.role||'')+', <a href="#" data-go="'+esc(e.org)+'">'+esc(by[e.org].name)+'</a></p>':(e.role?'<p>'+esc(e.role)+'</p>':'');
 det.innerHTML='<button class="close" type="button" aria-label="Close">×</button><div class="row">'+img+'<div><h3>'+esc(e.name)+pend(e)+'</h3><div class="meta">'+fl(e.country)+' '+esc(cn(e.country))+' · '+(e.type==='person'?'Person':esc(e.group||'Organisation'))+' · '+SECN[e.sector]+(e.url?' · <a href="'+esc(e.url)+'" target="_blank" rel="noopener">website</a>':'')+'</div>'+org+(e.description?'<p>'+esc(e.description)+'</p>':'')+'</div></div>'+(rl?'<b>Links</b><ul>'+rl+'</ul>':'')+'<b>Sources</b>'+srcs(e.sources);
 det.hidden=false;history.replaceState(null,'','#'+encodeURIComponent(id))}
chart.addEventListener('click',function(ev){var n=ev.target.closest('[data-id]');if(n){ev.stopPropagation();show(n.dataset.id)}});
chart.addEventListener('keydown',function(ev){if(ev.key==='Enter'||ev.key===' '){var n=ev.target.closest('[data-id]');if(n){ev.preventDefault();show(n.dataset.id)}}});
function go(ev){var g=ev.target.closest('[data-go]');if(g){ev.preventDefault();var x=by[g.dataset.go];if(x&&!cOk(x)){[].forEach.call(document.querySelectorAll('.cchip'),function(b){b.setAttribute('aria-pressed','false')});render()}show(g.dataset.go);var c=chart.querySelector('[data-id="'+g.dataset.go+'"]');if(c)c.scrollIntoView({block:'center',behavior:'smooth'})}}
det.addEventListener('click',function(ev){go(ev);if(ev.target.closest('.close')){det.hidden=true;[].forEach.call(chart.querySelectorAll('.hl'),function(n){n.classList.remove('hl')});history.replaceState(null,'',location.pathname)}});
[].forEach.call(document.querySelectorAll('.seg button'),function(b){b.addEventListener('click',function(){[].forEach.call(document.querySelectorAll('.seg button'),function(x){x.setAttribute('aria-pressed',x===b)});seg=b.dataset.v;render()})});
[].forEach.call(document.querySelectorAll('.cchip'),function(b){b.addEventListener('click',function(){b.setAttribute('aria-pressed',b.getAttribute('aria-pressed')==='true'?'false':'true');
 var c=selC();[].forEach.call(document.querySelectorAll('.reg article[data-c]'),function(a){a.hidden=c.length&&c.indexOf(a.dataset.c)<0});render()})});
function list(){var t=(q.value||'').toLowerCase();tb.innerHTML=E.slice().sort(function(a,b){return ORDER.indexOf(a.country)-ORDER.indexOf(b.country)||a.name.localeCompare(b.name,'en')}).filter(function(e){var o=e.org&&by[e.org]?by[e.org].name:'';
 return cOk(e)&&(seg==='both'||e.sector===seg)&&(!t||(e.name+' '+(e.role||'')+' '+o+' '+(e.description||'')+' '+(e.group||'')+' '+cn(e.country)).toLowerCase().indexOf(t)>=0)}).map(function(e){var o=e.org&&by[e.org]?by[e.org].name:'';
 return '<tr><td><a href="#" data-go="'+esc(e.id)+'">'+esc(e.name)+'</a>'+pend(e)+'</td><td>'+fl(e.country)+' '+esc(cn(e.country))+'</td><td>'+(e.type==='person'?'Person':esc(e.group||'Organisation'))+'</td><td>'+(e.sector==='public'?'Public':'Private')+'</td><td>'+esc(e.type==='person'?(e.role||'')+(o?', '+o:''):(e.description||''))+'</td><td>'+e.sources.map(function(s,i){return '<a href="'+esc(s.url)+'" target="_blank" rel="noopener">'+esc(s.source_name||('source '+(i+1)))+'</a>'}).join(', ')+'</td></tr>'}).join('');
 [].forEach.call(chart.querySelectorAll('[data-id]'),function(n){var e=by[n.dataset.id],o=e.org&&by[e.org]?by[e.org].name:'';n.classList.toggle('dim',!!t&&(e.name+' '+(e.role||'')+' '+o+' '+(e.description||'')).toLowerCase().indexOf(t)<0&&!n.querySelector('.person:not(.dim)'))})}
document.getElementById('olist').addEventListener('click',go);
var h=decodeURIComponent(location.hash.slice(1));if(h.indexOf('country=')===0){h.slice(8).split(',').forEach(function(x){[].forEach.call(document.querySelectorAll('.cchip'),function(b){if(b.dataset.c===x)b.setAttribute('aria-pressed','true')})});h=''}
q.addEventListener('input',list);render();if(h&&by[h])show(h);
})();
