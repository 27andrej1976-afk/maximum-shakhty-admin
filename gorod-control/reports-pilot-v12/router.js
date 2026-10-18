/* Civic report router — sandbox pilot. No unauthorised external transmissions. */
(() => {
  "use strict";
  const routes=Object.freeze({
    water:{id:"ursv",name:"Шахтинский филиал ГУП РО «УРСВ»",telephone:"+78632855777",guide:"Аварийная диспетчерская. После звонка запишите номер зарегистрированной заявки и имя диспетчера, если их сообщили.",proof:"Регистрационный номер и/или ответ диспетчерской.",categories:["Нет воды","Утечка воды","Проблемы канализации"]},
    power:{id:"donenergo",name:"АО «Донэнерго»",telephone:"+78002220550",guide:"Горячая линия электросетей. Номер зарегистрированной заявки нужно подтвердить у оператора.",proof:"Регистрационный номер обращения или ответ оператора.",categories:["Нет света","Обрыв провода","Повреждение электросетей"]},
    city:{id:"administration",name:"Администрация города Шахты",guide:"Официальная платформа «Госуслуги. Решаем вместе». Перенесите адрес, описание и фото в официальную форму; сохраните номер из Госуслуг.",url:"https://www.gosuslugi.ru/",proof:"Номер обращения в личном кабинете Госуслуг.",categories:["Яма на дороге","Мусор и свалка","Уличное освещение","Благоустройство","Другая городская проблема"]}
  });
  const byCategory=Object.fromEntries(Object.entries(routes).flatMap(([kind,route])=>route.categories.map(c=>[c,kind])));
  const $=s=>document.querySelector(s);
  const form=$("#reportForm"),recipient=$("#recipient"),state=$("#state"),submit=$("#send"),file=$("#photo");
  const output=$("#receipt"),help=$("#guide"),preview=$("#imagePreview");
  const description=$("#description"),address=$("#address"),category=$("#category");
  const saved=new Map();
  function esc(s){const el=document.createElement("span");el.textContent=String(s);return el.innerHTML;}
  function routeFor(c){return routes[byCategory[c]]||null;}
  function timestamp(){return new Date().toLocaleString("ru-RU",{dateStyle:"medium",timeStyle:"short"});}
  function renderRoute(){
    const route=routeFor(category.value);
    recipient.textContent=route?route.name:"Выберите тип проблемы";
    help.textContent=route?route.guide:"";
    submit.disabled=!route;
  }
  Object.values(routes).flatMap(r=>r.categories).forEach(value=>{
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
    const org=routes[d.kind];
    output.replaceChildren();
    const title=document.createElement("h3");title.textContent="Черновик № "+d.id;
    output.append(title);
    const badge=document.createElement("p");badge.className="pending";
    badge.textContent=d.registration?"Регистрация подтверждена заявителем (не проверено приложением)":"ОЖИДАЕТ ПОДАЧИ — НЕ ДОСТАВЛЕНО";
    output.append(badge);
    const details=document.createElement("p");details.textContent=org.name+" · "+d.createdAt+" · "+d.address;
    output.append(details);
    const explain=document.createElement("p");
    explain.textContent="Нажатие телефона/ссылки только открывает официальный канал. Оно НЕ отправляет текст, фото и НЕ подтверждает получение.";
    output.append(explain);
    if(org.telephone){
      const a=document.createElement("a");a.href="tel:"+org.telephone;a.className="primaryLink";a.textContent="Позвонить в "+org.name;
      output.append(a);
    }else if(org.url){
      const a=document.createElement("a");a.href=org.url;a.target="_blank";a.rel="noopener noreferrer";a.className="primaryLink";a.textContent="Открыть Госуслуги";
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
    confirm.append(document.createTextNode("После фактической подачи в официальном канале можно сохранить номер:"));
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
    if(kind==="power"&&/обрыв/i.test(category.value)){
      state.textContent="Не приближайтесь к проводам. При угрозе людям звоните 112 и в аварийную службу.";
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