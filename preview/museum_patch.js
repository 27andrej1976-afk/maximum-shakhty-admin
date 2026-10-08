(async function(){
  let museumData = null;
  try {
    const r = await fetch('../assets/museum_card.b64?v=21b616e', {cache:'no-store'});
    if (r.ok) museumData = 'data:image/jpeg;base64,' + (await r.text()).trim();
  } catch (_) {}
  if (!museumData) return;

  function applyMuseumImage(){
    document.querySelectorAll('img[alt="Музей"]').forEach(function(img){
      img.src = museumData;
      img.onerror = null;
    });

    const app = document.getElementById('app');
    if (!app) return;
    const isMuseum = app.textContent && app.textContent.indexOf('Выездная экспозиция Шахтинского краеведческого музея') !== -1;
    if (isMuseum && !document.getElementById('museumHeroImage')) {
      const hero = document.createElement('div');
      hero.id = 'museumHeroImage';
      hero.className = 'card';
      hero.style.cssText = 'padding:0;overflow:hidden;margin-bottom:14px';
      const img = document.createElement('img');
      img.src = museumData;
      img.alt = 'Музей';
      img.style.cssText = 'display:block;width:100%;height:auto;aspect-ratio:3/2;object-fit:cover';
      hero.appendChild(img);
      const actions = app.querySelector('.actions');
      if (actions) app.insertBefore(hero, actions);
      else app.appendChild(hero);
    }
  }

  if (typeof window.openSection === 'function') {
    const originalOpenSection = window.openSection;
    window.openSection = function(){
      const out = originalOpenSection.apply(this, arguments);
      setTimeout(applyMuseumImage, 0);
      return out;
    };
  }

  if (typeof window.museumPage === 'function') {
    const originalMuseumPage = window.museumPage;
    window.museumPage = function(){
      const out = originalMuseumPage.apply(this, arguments);
      setTimeout(applyMuseumImage, 0);
      return out;
    };
  }

  applyMuseumImage();
})();