const U='https://gtxhswoogrwswlxvkvbd.supabase.co';
const K='sb_publishable_hoWqZbKUcFpPPgW0QEmR6w_laR0IYns';
const E='27andrej1976@gmail.com';
const L='Максимум';

const db=supabase.createClient(U,K);
const q=s=>document.querySelector(s);

const esc=(s='')=>s.replace(/[&<>"']/g,c=>({
  '&':'&amp;',
  '<':'&lt;',
  '>':'&gt;',
  '"':'&quot;',
  "'":'&#039;'
}[c]));

async function show(session){
  q('#login').hidden=!!session;
  q('#panel').hidden=!session;
  if(session) await load();
}

async function load(){
  q('#content').textContent='Загрузка…';

  const {data,error}=await db
    .from('maximum_content')
    .select('*')
    .order('id');

  if(error){
    q('#content').textContent='Ошибка: '+error.message;
    return;
  }

  q('#content').innerHTML='';

  for(const x of data){
    const a=document.createElement('article');
    a.className='editor';

    a.innerHTML=
      '<div class="row"><h2>'+esc(x.title)+'</h2>'+
      '<label><input type="checkbox" data-published '+
      (x.is_published?'checked':'')+
      '> Опубликован</label></div>'+
      '<label>Название<input data-title value="'+esc(x.title)+'"></label>'+
      '<label>Текст<textarea data-body>'+esc(x.body)+'</textarea></label>'+
      '<button data-save="'+x.id+'">Сохранить раздел</button>';

    q('#content').appendChild(a);
  }
}

q('#loginBtn').onclick=async()=>{
  const username=q('#username').value.trim();
  const password=q('#password').value;

  if(username!==L){
    q('#loginMsg').textContent='Неверный логин или пароль';
    return;
  }

  q('#loginMsg').textContent='Вход…';

  const {data,error}=await db.auth.signInWithPassword({
    email:E,
    password:password
  });

  if(error){
    q('#loginMsg').textContent='Не удалось войти: '+error.message;
    return;
  }

  q('#loginMsg').textContent='';
  await show(data.session);
};

q('#logoutBtn').onclick=async()=>{
  await db.auth.signOut();
  await show(null);
};

q('#content').onclick=async e=>{
  const id=e.target.dataset.save;
  if(!id) return;

  const a=e.target.closest('.editor');

  q('#saveMsg').textContent='Сохраняю…';

  const {error}=await db
    .from('maximum_content')
    .update({
      title:a.querySelector('[data-title]').value.trim(),
      body:a.querySelector('[data-body]').value,
      is_published:a.querySelector('[data-published]').checked,
      updated_at:new Date().toISOString()
    })
    .eq('id',id);

  q('#saveMsg').textContent=
    error ? 'Ошибка: '+error.message : 'Сохранено';

  if(!error) await load();
};

db.auth.getSession().then(({data})=>show(data.session));
