(function(){
  let museumSrc=null;
  const ready=fetch('../assets/museum_card.b64')
    .then(r=>r.ok?r.text():'')
    .then(t=>{ if(t) museumSrc='data:image/jpeg;base64,'+t.trim(); })
    .catch(()=>{});

  const base=window.museumPage;
  if(typeof base!=='function') return;

  window.museumPage=function(){
    base();
    const add=()=>{
      if(!museumSrc) return;
      const box=document.querySelector('.storeBody');
      if(!box || box.querySelector('.museumHero')) return;
      const im=document.createElement('img');
      im.className='museumHero';
      im.src=museumSrc;
      im.alt='Museum';
      im.style.cssText='width:100%;border-radius:18px;margin-bottom:18px;display:block';
      box.insertBefore(im,box.firstChild);
    };
    if(museumSrc) add(); else ready.then(add);
  };
})();