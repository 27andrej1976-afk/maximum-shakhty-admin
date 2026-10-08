(async function(){
  const files=[
    '../assets/museum_card_1.txt?v=final2',
    '../assets/museum_card_2.txt?v=final2',
    '../assets/museum_card_3.txt?v=final2',
    '../assets/museum_card_4a.txt?v=final2',
    '../assets/museum_card_4b.txt?v=final2',
    '../assets/museum_card_5a.txt?v=final2',
    '../assets/museum_card_5b.txt?v=final2',
    '../assets/museum_card_6a.txt?v=final2',
    '../assets/museum_card_6b.txt?v=final2'
  ];
  let museumData=null;
  try{
    const responses=await Promise.all(files.map(p=>fetch(p,{cache:'no-store'})));
    if(responses.some(r=>!r.ok)) return;
    const parts=await Promise.all(responses.map(r=>r.text()));
    const b64=parts.join('').replace(/\s+/g,'');
    if(b64.length!==43200) return;
    museumData='data:image/jpeg;base64,'+b64;
  }catch(_){ return; }

  function applyMuseumImage(){
    document.querySelectorAll('img[alt="Музей"]').forEach(img=>{
      img.src=museumData;
      img.onerror=null;
    });

    const app=document.getElementById('app');
    if(!app) return;
    const isMuseum=app.textContent && app.textContent.includes('Выездная экспозиция Шахтинского краеведческого музея');
    const body=app.querySelector('.storeBody');
    if(isMuseum && body && !document.getElementById('museumHeroImage')){
      const img=document.createElement('img');
      img.id='museumHeroImage';
      img.alt='Музей';
      img.src=museumData;
      img.style.cssText='display:block;width:100%;height:auto;aspect-ratio:2/3;object-fit:cover;border-radius:18px;margin-bottom:18px';
      body.insertBefore(img,body.firstChild);
    }
  }

  if(typeof window.home==='function'){
    const originalHome=window.home;
    window.home=function(){
      const out=originalHome.apply(this,arguments);
      setTimeout(applyMuseumImage,0);
      return out;
    };
  }

  if(typeof window.museumPage==='function'){
    const originalMuseumPage=window.museumPage;
    window.museumPage=function(){
      const out=originalMuseumPage.apply(this,arguments);
      setTimeout(applyMuseumImage,0);
      return out;
    };
  }

  if(typeof window.openSection==='function'){
    const originalOpenSection=window.openSection;
    window.openSection=function(){
      const out=originalOpenSection.apply(this,arguments);
      setTimeout(applyMuseumImage,0);
      return out;
    };
  }

  applyMuseumImage();
})();