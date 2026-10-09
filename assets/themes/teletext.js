(function(T){
  var clk=T.$(".tt-clock"),sub=T.$(".tt-sub"),pg=T.$(".tt-pg"),n=1,p=100;
  function tick(){var d=new Date();clk.textContent=d.toTimeString().slice(0,8)}
  if(clk){tick();if(!T.still){setInterval(tick,1000);setInterval(function(){n=n%4+1;sub.textContent=n+"/4"},6000)}}
  // the page counter searches up to P101 like an old TV
  if(pg&&!T.still){var iv=setInterval(function(){p++;pg.textContent="P"+p;if(p>=101)clearInterval(iv)},700);pg.textContent="P100"}
})(window.NCT);
