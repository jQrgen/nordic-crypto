(function(T){
  var c=T.$(".vh-ctr"),t0=Date.now();
  function tick(){var s=Math.floor((Date.now()-t0)/1000);c.textContent="SP "+Math.floor(s/3600)+":"+String(Math.floor(s/60)%60).padStart(2,"0")+":"+String(s%60).padStart(2,"0")}
  if(c){tick();if(!T.still)setInterval(tick,1000)}
})(window.NCT);
