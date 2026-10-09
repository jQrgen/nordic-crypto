(function(T){
  // HP bar on every coin tile, filled from the 24h change: +5 % or better is full, -5 % or worse is a sliver.
  function hp(){T.$$(".mktile:not(.px-done)").forEach(function(tile){tile.classList.add("px-done");
    var chg=tile.querySelector(".chg"),pct=0;
    if(chg){var m=chg.textContent.replace(",",".").match(/[-−+]?\d+(\.\d+)?/);if(m)pct=parseFloat(m[0].replace("−","-"))}
    var v=Math.max(6,Math.min(100,50+pct*10));
    var bar=document.createElement("div");bar.className="px-hp";bar.setAttribute("aria-hidden","true");
    bar.innerHTML="<b>HP</b><span><i></i></span>";tile.appendChild(bar);
    var i=bar.querySelector("i");if(v<25)i.className="low";else if(v<50)i.className="mid";
    setTimeout(function(){i.style.width=v+"%"},T.still?0:400);
  })}
  hp();var m=T.$("main");if(m&&"MutationObserver" in window)new MutationObserver(hp).observe(m,{childList:true,subtree:true});
  var h=T.$("main h1"),box=T.$(".px-type");
  if(h&&box)setTimeout(function(){T.type(box,"▶ "+h.textContent.trim()+"!",45)},T.still?0:900);
})(window.NCT);
