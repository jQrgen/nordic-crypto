(function(T){
  var spot=T.$(".nr-spot");if(!spot||T.still)return;
  var raf=0,x=0,y=0;
  addEventListener("pointermove",function(e){x=e.clientX;y=e.clientY;if(!raf)raf=requestAnimationFrame(function(){spot.style.setProperty("--mx",x+"px");spot.style.setProperty("--my",y+"px");raf=0})},{passive:true});
})(window.NCT);
