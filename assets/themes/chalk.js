(function(T){
  var dust=[];
  T.canvas(T.$(".ck-dust"),function(c,s){
    c.clearRect(0,0,s.w,s.h);
    if(dust.length<70&&Math.random()<.5)dust.push({x:Math.random()*s.w,y:-5,v:.2+Math.random()*.5,r:.6+Math.random()*1.6,a:.15+Math.random()*.35,ph:Math.random()*6});
    dust=dust.filter(function(p){p.y+=p.v;p.ph+=.02;p.x+=Math.sin(p.ph)*.3;c.fillStyle="rgba(241,241,232,"+p.a+")";c.beginPath();c.arc(p.x,p.y,p.r,0,6.3);c.fill();return p.y<s.h});
  },30);
  // a puff of chalk where you click
  if(!T.still)document.addEventListener("click",function(e){for(var i=0;i<14;i++){var a=Math.random()*6.3,v=Math.random()*1.5;dust.push({x:e.clientX,y:e.clientY,v:Math.sin(a)*v+.3,r:1+Math.random()*1.5,a:.5,ph:a})}});
})(window.NCT);
