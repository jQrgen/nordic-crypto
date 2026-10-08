(function(T){
  var glyphs="アイウエオカキクケコサシスセソタチツテトナニヌネノ0123456789₿ΞÐ$€£¥ᚠᚢᚦᚨᚱ<>/*+=".split("");
  var cols=[],fs=16;
  T.canvas(T.$(".mx-rain"),function(c,s){
    if(s.resized||!cols.length){var n=Math.ceil(s.w/fs);cols=[];for(var i=0;i<n;i++)cols.push(Math.random()*s.h/fs|0)}
    c.fillStyle="rgba(0,0,0,0.09)";c.fillRect(0,0,s.w,s.h);c.font=fs+"px monospace";
    for(var i=0;i<cols.length;i++){
      var ch=glyphs[Math.random()*glyphs.length|0],y=cols[i]*fs;
      c.fillStyle=Math.random()<.04?"#E8FFE8":"#39FF14";c.fillText(ch,i*fs,y);
      if(y>s.h&&Math.random()>.975)cols[i]=0;else cols[i]++;
    }
  },22);
  // glitch the headings
  T.$$("main h1,main h2").forEach(function(h){if(h.children.length)return;var t=h.textContent;h.innerHTML="";var s=document.createElement("span");s.className="mx-glitch";s.setAttribute("data-text",t);s.textContent=t;h.appendChild(s)});
  // booting terminal: lists the events on the page
  var log=T.$(".mx-log");if(!log)return;
  var names=T.$$("main .evcard h3, main .evcard a, main td a").map(function(a){return a.textContent.trim()}).filter(Boolean).slice(0,40);
  var lines=["> boot nordic-node --region=NO,SE,DK,FI,IS","> sync calendar ......... ok","> peers: 5 countries online"];
  names.forEach(function(n){lines.push("> event found: "+n.slice(0,38))});
  lines.push("> watching for new blocks ...");
  var buf=[],i=0;
  function next(){if(i>=lines.length){i=3}var l=lines[i++];var cur="",k=0;
    (function ch(){cur=l.slice(0,++k);log.textContent=buf.concat([cur]).slice(-8).join("\n");if(k<l.length&&!T.still)setTimeout(ch,18);else{buf.push(l);buf=buf.slice(-8);setTimeout(next,T.still?0:600)}})()}
  if(T.still){log.textContent=lines.slice(0,8).join("\n")}else next();
})(window.NCT);
