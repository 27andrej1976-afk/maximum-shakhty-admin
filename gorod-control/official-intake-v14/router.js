/* Civic report router — sandbox pilot. No unauthorised external transmissions. */
(() => {
  "use strict";
  const authority=Object.freeze({id:"administration",name:"Администрация города Шахты",guide:"Официальный сервис подачи обращений «Госуслуги. Решаем вместе». После перехода авторизуйтесь, вставьте подготовленный текст, приложите фото и подтвердите отправку.",url:"https://www.gosuslugi.ru/10091/1",proof:"Номер регистрации, полученный через официальный сервис."});
  const categories=Object.freeze({
    water:["Нет воды","Утечка воды","Проблемы канализации"],
    power:["Нет света","Обрыв провода","Повреждение электросетей"],
    city:["Яма на дороге","Мусор и свалка","Уличное освещение","Благоустройство","Другая городская проблема"]
  });
  const routes=Object.freeze(Object.fromEntries(Object.keys(categories).map(kind=>[kind,authority])));
  const byCategory=Object.fromEntries(Object.entries(categories).flatMap(([kind,items])=>items.map(c=>[c,kind])));
  const $=s=>document.querySelector(s);
  const form=$("#reportForm"),recipient=$("#recipient"),state=$("#state"),submit=$("#send"),file=$("#photo");
  const output=$("#receipt"),help=$("#guide"),preview=$("#imagePreview");
  const description=$("#description"),address=$("#address"),category=$("#category");
  const saved=new Map();
  function esc(s){const el=document.createElement("span");el.textContent=String(s);return el.innerHTML;}
  function routeFor(c){return Object.hasOwn(byCategory,c)?authority:null;}
  function timestamp(){return new Date().toLocaleString("ru-RU",{dateStyle:"medium",timeStyle:"short"});}
  function renderRoute(){
    const route=routeFor(category.value);
    recipient.textContent=route?route.name:"Выберите тип проблемы";
    help.textContent=route?route.guide:"";
    submit.disabled=!route;
  }
  Object.values(categories).flat().forEach(value=>{
    const option=document.createElement("option");option.value=option.textContent=value;category.append(option);
  });
  category.addEventListener("change",renderRoute);
  const allowedTypes=["image/jpeg","image/png","image/webp"];
  let lastObjectURL=null;
  file.addEventListener("change",()=>{
    if(lastObjectURL){URL.revokeObjectURL(lastObjectURL);lastObjectURL=null;}
    const f=file.files?.[0];
    preview.replaceChildren();
    if(!f)return;
    if(!allowedTypes.includes(f.type)||f.size>6*1024*1024){file.value="";state.textContent="Поддерживаются JPEG, PNG, WebP до 6 МБ.";return;}
    lastObjectURL=URL.createObjectURL(f);
    const img=document.createElement("img");img.src=lastObjectURL;img.alt="Предпросмотр фотографии обращения";
    preview.append(img);
    state.textContent="Фото добавлено только для предпросмотра. Не отправлено никуда.";
  });
  function exportDraft(d){
    const copy={...d};delete copy.photoName;
    const blob=new Blob([JSON.stringify(copy,null,2)],{type:"application/json"});
    const a=document.createElement("a");const url=URL.createObjectURL(blob);
    a.href=url;a.download="obrashchenie-"+d.id+".json";a.textContent="Сохранить черновик в файл";
    a.addEventListener("click",()=>setTimeout(()=>URL.revokeObjectURL(url),1000),{once:true});
    return a;
  }
  function render(d){
    const org=authority;
    output.replaceChildren();
    const title=document.createElement("h3");title.textContent="Черновик № "+d.id;
    output.append(title);
    const badge=document.createElement("p");badge.className="pending";
    badge.textContent=d.registration?"Регистрация подтверждена заявителем (не проверено приложением)":"ОЖИДАЕТ ПОДАЧИ — НЕ ДОСТАВЛЕНО";
    output.append(badge);
    const details=document.createElement("p");details.textContent=org.name+" · "+d.createdAt+" · "+d.address;
    output.append(details);
    const explain=document.createElement("p");
    explain.textContent="Это ссылка на сервис подачи обращений, а не автоматическая отправка. Сначала скопируйте текст, затем подтвердите отправку на Госуслугах. Фото прикладывается в официальной форме отдельно.";
    output.append(explain);
    if(org.telephone){
      const a=document.createElement("a");a.href="tel:"+org.telephone;a.className="primaryLink";a.textContent="Позвонить в "+org.name;
      output.append(a);
    }else if(org.url){
      const a=document.createElement("a");a.href=org.url;a.target="_blank";a.rel="noopener noreferrer";a.className="primaryLink";a.textContent="Перейти к официальной подаче обращения";
      output.append(a);
    }
    const copy=document.createElement("button");copy.type="button";copy.className="secondary";
    copy.textContent="Скопировать текст обращения";
    copy.addEventListener("click",()=>{
      const t="Обращение № "+d.id+"\nКатегория: "+d.category+"\nАдрес: "+d.address+
       "\nСуть: "+d.description+"\nФото: "+(d.photoName||"не приложено")+
       "\nПолучатель: "+org.name;
      navigator.clipboard?.writeText(t).then(()=>state.textContent="Текст скопирован. Само обращение НЕ отправлено.").catch(()=>state.textContent="Не удалось скопировать текст.");
    });
    output.append(copy,exportDraft(d));
    const confirm=document.createElement("div");confirm.className="confirm";
    confirm.append(document.createTextNode("После фактической подачи на Госуслугах можно сохранить полученный номер:"));
    const reg=document.createElement("input");reg.placeholder="Номер, полученный от организации";reg.maxLength=80;
    const save=document.createElement("button");save.type="button";save.textContent="Сохранить номер (вручную)";
    save.addEventListener("click",()=>{
      const n=reg.value.trim();
      if(n.length<3)return;
      d.registration=n;d.registrationSelfReportedAt=timestamp();
      saved.set(d.id,d);
      badge.textContent="Номер внесён пользователем: "+n+". Организацией через API пока не подтверждён.";
      badge.className="manual";
      state.textContent="Регистрационный номер сохранён только в этом сеансе. Не проверен организацией.";
    });
    confirm.append(reg,save);output.append(confirm);
  }
  form.addEventListener("submit",event=>{
    event.preventDefault();
    const route=routeFor(category.value);
    if(!route||address.value.trim().length<5||description.value.trim().length<12)return;
    const kind=byCategory[category.value];
    if((kind==="power"&&/обрыв/i.test(category.value))||/утечка газа|пожар|дым/i.test(description.value)){
      state.textContent="Опасная ситуация: не приближайтесь к месту аварии. Срочно звоните 112 или в аварийную службу. Электронное обращение не заменяет экстренный вызов.";
    }else{
      state.textContent="Создан черновик. Никаких данных организациям не отправлено.";
    }
    const id="SH-"+Date.now().toString(36).toUpperCase();
    const d={id,kind,category:category.value,address:address.value.trim(),description:description.value.trim(),photoName:file.files?.[0]?.name||"",createdAt:timestamp(),status:"draft"};
    saved.set(d.id,d);render(d);
  });
  renderRoute();
  window.CivicReportPilot={routeFor,sourceRoutes:routes,inspect:()=>({draftCount:saved.size,latest:[...saved.values()].at(-1)?.status||null})};
})();