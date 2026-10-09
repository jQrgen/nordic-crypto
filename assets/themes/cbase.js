(function(T){
  var stars=[];
  T.canvas(T.$(".cb-stars"),function(c,s){
    if(s.resized||!stars.length){stars=[];for(var i=0;i<Math.round(s.w*s.h/2600);i++)stars.push({x:Math.random()*s.w,y:Math.random()*s.h,z:Math.random()*.9+.1})}
    c.clearRect(0,0,s.w,s.h);
    for(var i=0;i<stars.length;i++){var p=stars[i];p.x-=p.z*.6;if(p.x<0){p.x=s.w;p.y=Math.random()*s.h}
      var tw=.5+.5*Math.sin((p.x+p.y)*.05+performance.now()*.002*p.z);c.fillStyle="rgba(220,232,255,"+(p.z*.9*tw+.1)+")";c.fillRect(p.x,p.y,p.z*2,p.z*2)}
    if(Math.random()<.004)stars.push({x:s.w,y:Math.random()*s.h*.5,z:6,shoot:1});
    stars=stars.filter(function(p){if(p.shoot){p.y+=2;c.strokeStyle="rgba(255,164,88,.8)";c.beginPath();c.moveTo(p.x,p.y);c.lineTo(p.x+40,p.y-14);c.stroke();return p.x>0}return true});
  },40);
  // static starfield for reduced motion
  if(T.still){var cv=T.$(".cb-stars");if(cv){var x=cv.getContext("2d");cv.width=innerWidth;cv.height=innerHeight;for(var i=0;i<300;i++){x.fillStyle="rgba(220,232,255,"+Math.random()+")";x.fillRect(Math.random()*innerWidth,Math.random()*innerHeight,1.5,1.5)}}}
  var clk=T.$(".cb-clock"),t0=Date.now();
  function tick(){var s=Math.floor((Date.now()-t0)/1000),d=new Date();clk.textContent="T+"+String(Math.floor(s/60)).padStart(2,"0")+":"+String(s%60).padStart(2,"0")+"  UTC "+d.toISOString().slice(11,19)}
  if(clk){tick();if(!T.still)setInterval(tick,1000)}
})(window.NCT);
