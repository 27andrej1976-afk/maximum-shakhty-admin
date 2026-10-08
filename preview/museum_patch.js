(function(){
  let museumSrc='../assets/museum_card.jpg';
  const ready=Promise.resolve();

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