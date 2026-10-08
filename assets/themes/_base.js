/* Theme helpers shared by every theme: scroll reveal, a reduced-motion flag and a typewriter. */
window.NCT=(function(){
  var still=window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches;
  function $(s,r){return (r||document).querySelector(s)}
  function $$(s,r){return Array.prototype.slice.call((r||document).querySelectorAll(s))}
  function type(el,text,ms,done){
    if(!el)return;if(still){el.textContent=text;done&&done();return}
    var i=0;el.textContent="";(function step(){el.textContent=text.slice(0,++i);if(i<text.length)setTimeout(step,ms||28);else done&&done()})()
  }
  function canvas(c,draw,fps){
    if(!c||still)return;var ctx=c.getContext("2d"),dpr=Math.min(window.devicePixelRatio||1,2),last=0,step=1000/(fps||30),st={};
    function size(){c.width=innerWidth*dpr;c.height=innerHeight*dpr;c.style.width=innerWidth+"px";c.style.height=innerHeight+"px";ctx.setTransform(dpr,0,0,dpr,0,0);st.w=innerWidth;st.h=innerHeight;st.resized=true}
    size();addEventListener("resize",size);
    (function loop(t){requestAnimationFrame(loop);if(document.hidden||t-last<step)return;last=t;draw(ctx,st,t);st.resized=false})(0)
  }
  // reveal: cards and sections slide in as they come into view
  var sel="main h1,main h2,main .lead,main .card,main .mktile,main .evcard,main article,main section,main li.story,main .story,main table,main .talk,main .person,main pre";
  var els=$$(sel).filter(function(e){return !e.closest(".th-r")&&e.offsetHeight<1600});
  els.forEach(function(e,i){e.classList.add("th-r");e.style.transitionDelay=Math.min(i%8,7)*45+"ms"});
  if(!still&&"IntersectionObserver" in window){
    var io=new IntersectionObserver(function(es){es.forEach(function(x){if(x.isIntersecting){x.target.classList.add("th-in");io.unobserve(x.target)}})},{rootMargin:"0px 0px -6% 0px"});
    els.forEach(function(e){io.observe(e)});
  }else els.forEach(function(e){e.classList.add("th-in")});
  return {still:still,$:$,$$:$$,type:type,canvas:canvas};
})();
