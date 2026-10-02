const U='https://gtxhswoogrwswlxvkvbd.supabase.co';
const K='sb_publishable_hoWqZbKUcFpPPgW0QEmR6w_laR0IYns';
const E='27andrej1976@gmail.com';
const L='Максимум';
const BUCKET='maximum-content';

const db=supabase.createClient(U,K);
const q=s=>document.querySelector(s);
const esc=(s='')=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));

async function show(session){
  q('#login').hidden=!!session;
  q('#panel').hidden=!session;
  if(session){ await load(); await loadStores(); }
}

async function load(){
  q('#content').textContent='Загрузка…';
  const {data,error}=await db.from('maximum_content').select('*').order('id');
  if(error){ q('#content').textContent='Ошибка: '+error.message; return; }
  q('#content').innerHTML='';

  for(const x of data){
    const a=document.createElement('article');
    a.className='editor';
    const image=x.image_url
      ? '<div class="photo-preview"><img src="'+esc(x.image_url)+'" alt="Фото раздела"></div>'
      : '<p class="no-photo">Фото пока не добавлено</p>';

    a.innerHTML=
      '<div class="row"><h2>'+esc(x.title)+'</h2>'+
      '<label><input type="checkbox" data-published '+(x.is_published?'checked':'')+'> Опубликован</label></div>'+
      '<label>Название<input data-title value="'+esc(x.title)+'"></label>'+
      '<label>Текст<textarea data-body>'+esc(x.body)+'</textarea></label>'+
      '<div class="photo-box"><strong>Фото раздела</strong>'+image+
      '<input type="file" data-file accept="image/jpeg,image/png,image/webp">'+
      '<div class="photo-actions"><button type="button" data-upload="'+x.id+'" data-section="'+esc(x.section)+'">Добавить / заменить фото</button>'+
      (x.image_url?'<button type="button" class="secondary" data-delete-photo="'+x.id+'" data-section="'+esc(x.section)+'">Удалить фото</button>':'')+
      '</div><small>JPEG, PNG или WebP, максимум 5 МБ.</small></div>'+
      '<button data-save="'+x.id+'">Сохранить раздел</button>';
    q('#content').appendChild(a);
  }
}

async function uploadPhoto(button){
  const a=button.closest('.editor');
  const file=a.querySelector('[data-file]').files[0];
  if(!file){ q('#saveMsg').textContent='Сначала выберите фотографию.'; return; }
  if(file.size>5*1024*1024){ q('#saveMsg').textContent='Файл больше 5 МБ.'; return; }

  q('#saveMsg').textContent='Загружаю фото…';
  const ext=(file.name.split('.').pop()||'jpg').toLowerCase();
  const path=button.dataset.section+'/photo.'+ext;

  const {error:upError}=await db.storage.from(BUCKET).upload(path,file,{
    upsert:true,
    contentType:file.type,
    cacheControl:'3600'
  });
  if(upError){ q('#saveMsg').textContent='Ошибка загрузки: '+upError.message; return; }

  const {data:urlData}=db.storage.from(BUCKET).getPublicUrl(path);
  const imageUrl=urlData.publicUrl+'?v='+Date.now();

  const {error}=await db.from('maximum_content')
    .update({image_url:imageUrl,updated_at:new Date().toISOString()})
    .eq('id',button.dataset.upload);

  q('#saveMsg').textContent=error?'Ошибка: '+error.message:'Фото сохранено';
  if(!error) await load();
}

async function deletePhoto(button){
  if(!confirm('Удалить фото из этого раздела?')) return;
  q('#saveMsg').textContent='Удаляю фото…';

  const {data:row,error:rowError}=await db.from('maximum_content')
    .select('image_url').eq('id',button.dataset.deletePhoto).single();
  if(rowError){ q('#saveMsg').textContent='Ошибка: '+rowError.message; return; }

  if(row?.image_url){
    try{
      const marker='/storage/v1/object/public/'+BUCKET+'/';
      const raw=row.image_url.split('?')[0];
      const path=decodeURIComponent(raw.split(marker)[1]||'');
      if(path) await db.storage.from(BUCKET).remove([path]);
    }catch(_){}
  }

  const {error}=await db.from('maximum_content')
    .update({image_url:null,updated_at:new Date().toISOString()})
    .eq('id',button.dataset.deletePhoto);

  q('#saveMsg').textContent=error?'Ошибка: '+error.message:'Фото удалено';
  if(!error) await load();
}

q('#loginBtn').onclick=async()=>{
  const username=q('#username').value.trim();
  const password=q('#password').value;
  if(username!==L){ q('#loginMsg').textContent='Неверный логин или пароль'; return; }
  q('#loginMsg').textContent='Вход…';
  const {data,error}=await db.auth.signInWithPassword({email:E,password});
  if(error){ q('#loginMsg').textContent='Не удалось войти: '+error.message; return; }
  q('#loginMsg').textContent='';
  await show(data.session);
};

q('#logoutBtn').onclick=async()=>{ await db.auth.signOut(); await show(null); };

q('#content').onclick=async e=>{
  if(e.target.dataset.upload){ await uploadPhoto(e.target); return; }
  if(e.target.dataset.deletePhoto){ await deletePhoto(e.target); return; }

  const id=e.target.dataset.save;
  if(!id) return;
  const a=e.target.closest('.editor');
  q('#saveMsg').textContent='Сохраняю…';
  const {error}=await db.from('maximum_content').update({
    title:a.querySelector('[data-title]').value.trim(),
    body:a.querySelector('[data-body]').value.trim(),
    is_published:a.querySelector('[data-published]').checked,
    updated_at:new Date().toISOString()
  }).eq('id',id);
  q('#saveMsg').textContent=error?'Ошибка: '+error.message:'Сохранено';
  if(!error) await load();
};

db.auth.getSession().then(({data})=>show(data.session));


async function loadStores(){
  const box=q('#stores');
  if(!box) return;
  box.textContent='Загрузка магазинов…';
  const {data:stores,error}=await db.from('maximum_stores')
    .select('id,name,category,description,working_hours,website_url,image_url,is_published,floor_id,maximum_floors!inner(floor_number,title,sort_order)')
    .order('sort_order',{ascending:true});
  if(error){ box.textContent='Ошибка загрузки магазинов: '+error.message; return; }
  box.innerHTML='';
  const floors={};
  for(const s of stores){
    const key=String(s.floor_id);
    if(!floors[key]) floors[key]={floor:s.maximum_floors,stores:[]};
    floors[key].stores.push(s);
  }
  for(const group of Object.values(floors).sort((a,b)=>a.floor.sort_order-b.floor.sort_order)){
    const section=document.createElement('section');
    section.className='floor-editor';
    section.innerHTML='<h2>'+esc(group.floor.title)+'</h2>';
    for(const s of group.stores){
      const a=document.createElement('article');
      a.className='editor store-editor';
      a.innerHTML=
        '<div class="row"><h3>'+esc(s.name)+'</h3>'+
        '<label><input type="checkbox" data-store-published '+(s.is_published?'checked':'')+'> Опубликован</label></div>'+
        '<label>Название<input data-store-name value="'+esc(s.name)+'"></label>'+
        '<label>Категория<input data-store-category value="'+esc(s.category)+'"></label>'+
        '<label>Описание<textarea data-store-description>'+esc(s.description)+'</textarea></label>'+
        '<label>Режим работы<input data-store-hours value="'+esc(s.working_hours)+'" placeholder="Например: 08:00–22:00"></label>'+ '<label>Официальный сайт<input data-store-website type="url" value="'+esc(s.website_url||'')+'" placeholder="https://..."></label>'+
        '<div class="photo-box"><strong>Фото / логотип магазина</strong>'+
        (s.image_url?'<div class="photo-preview"><img src="'+esc(s.image_url)+'" alt="Фото магазина"></div>':'<p class="no-photo">Фото пока не добавлено</p>')+
        '<input type="file" data-store-file accept="image/jpeg,image/png,image/webp">'+
        '<div class="photo-actions"><button type="button" data-store-upload="'+s.id+'">Добавить / заменить фото</button>'+
        (s.image_url?'<button type="button" class="secondary" data-store-delete="'+s.id+'">Удалить фото</button>':'')+
        '</div><small>JPEG, PNG или WebP, максимум 5 МБ.</small></div>'+
        '<button type="button" data-store-save="'+s.id+'">Сохранить магазин</button>';
      section.appendChild(a);
    }
    box.appendChild(section);
  }
}

q('#stores').onclick=async e=>{
  const id=e.target.dataset.storeSave;
  if(!id) return;
  const a=e.target.closest('.store-editor');
  q('#saveMsg').textContent='Сохраняю магазин…';
  const {error}=await db.from('maximum_stores').update({
    name:a.querySelector('[data-store-name]').value.trim(),
    category:a.querySelector('[data-store-category]').value.trim(),
    description:a.querySelector('[data-store-description]').value.trim(),
    working_hours:a.querySelector('[data-store-hours]').value.trim(),
    website_url:a.querySelector('[data-store-website]').value.trim(),
    is_published:a.querySelector('[data-store-published]').checked,
    updated_at:new Date().toISOString()
  }).eq('id',id);
  q('#saveMsg').textContent=error?'Ошибка: '+error.message:'Магазин сохранён';
  if(!error) await loadStores();
};
