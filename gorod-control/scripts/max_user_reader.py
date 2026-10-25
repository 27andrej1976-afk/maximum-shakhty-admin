"""Read only allowlisted public MAX channels through a user-owned session.

Uses unofficial PyMax, never sends or marks messages read. Only the explicitly
authorized URSV channel may be joined, after validating its public identity. Session material is
never part of the returned public payload. Authentication is interactive only in
our local Windows connector, never in GitHub Actions.
"""
import asyncio,base64,json,os,re,tempfile,zlib
from datetime import datetime,timedelta,timezone
from pathlib import Path
CHANNELS=(
 {'id':'max_city','slug':'shakhtygorod','chat_id':-68696541241372,'name':'Администрация города Шахты'},
 {'id':'max_water','slug':'id6167110467_gos','chat_id':-69418948796459,'name':'ГУП РО «УРСВ»'},
 {'id':'max_power','slug':'id6163089292_biz','chat_id':-72527316071728,'name':'АО Донэнерго · отключения'},
)
SESSION='max-session.db'

def enum_value(value):return getattr(value,'value',value)

def validate_channel(chat,channel):
    if chat.id!=channel['chat_id'] or enum_value(chat.type)!='CHANNEL' or enum_value(chat.access)!='PUBLIC':
        raise ValueError('Unexpected channel identity or access')
    title=re.sub(r'[^а-яa-z0-9]+',' ',(chat.title or '').lower()).strip()
    if channel['id']=='max_city' and title!='администрация города шахты':raise ValueError('Channel title changed')
    if channel['id']=='max_water' and title!='гуп ро урсв':raise ValueError('Channel title changed')
    if channel['id']=='max_power' and not ('донэнерго' in title and 'отключения' in title):raise ValueError('Channel title changed')

def public_post(message,channel,now):
    if message.chat_id not in (None,channel['chat_id']):raise ValueError('Unexpected message channel')
    if not isinstance(message.text,str) or not message.text.strip() or len(message.text)>40000:return None
    # MAX channel posts use CHANNEL; TEXT is retained for the older payload shape.
    if enum_value(getattr(message,'type',None)) not in ('CHANNEL','TEXT'):return None
    # A forwarded message needs separate provenance review; don't publish its wrapper as original.
    if getattr(message,'link',None) is not None:return None
    try:published=datetime.fromtimestamp(message.time/1000,timezone.utc)
    except (ValueError,TypeError,OverflowError,OSError):return None
    if not -timedelta(minutes=5)<now-published<timedelta(days=16):return None
    if not isinstance(message.id,int) or message.id<=0:return None
    url='https://max.ru/'+channel['slug']
    return {'id':channel['id']+'/'+str(message.id),'publishedAt':published.isoformat(),
      'text':message.text.strip(),'url':url,'officialUrl':url,'sourceId':channel['id'],
      'source':channel['name'],'origin':'official_max','transport':'max_user_session'}

async def read_channels(client,now=None):
    now=now or datetime.now(timezone.utc);posts=[];states=[]
    for channel in CHANNELS:
        state={'id':channel['id'],'url':'https://max.ru/'+channel['slug'],'checkedAt':now.isoformat(),
          'status':'error','readStatus':'error','coverage':'partial','transport':'max_user_session','posts':0}
        try:
            chat=await client.get_chat(channel['chat_id']);validate_channel(chat,channel)
            if channel['id']=='max_water' and not getattr(chat,'join_time',0):
                chat=await client.join_channel('https://max.ru/'+channel['slug'])
                validate_channel(chat,channel)
            messages=await client.fetch_history(chat_id=chat.id,backward=100,interactive=False)
            batch=[p for m in messages if (p:=public_post(m,channel,now))]
            posts.extend(batch)
            state.update(status='ok',readStatus='ok',posts=len(messages),matchingPosts=len(batch),
              lastPostAt=max((p['publishedAt'] for p in batch),default=None),
              note='Прочитано через пользовательскую сессию MAX: до 100 последних публикаций. Полнота не гарантируется.')
        except Exception:
            state['note']='Канал MAX не прочитан. Проверьте подписку, действительность сессии и доступность MAX.'
        states.append(state)
    return posts,states

class NoInteractiveLogin:
    async def authenticate(self,app):raise RuntimeError('MAX login required on local computer')

def make_client(work_dir,qr_provider=None):
    from pymax import WebClient,ExtraConfig
    options={'work_dir':str(work_dir),'session_name':SESSION,
      'extra_config':ExtraConfig(log_level='CRITICAL',telemetry=False,reconnect=False,relogin=False,request_timeout=20)}
    if qr_provider is None:options['auth_flow']=NoInteractiveLogin()
    else:options['qr_provider']=qr_provider
    return WebClient(**options)

async def run_reader(work_dir,now=None,qr_provider=None):
    client=make_client(work_dir,qr_provider)
    try:
        await asyncio.wait_for(client.connect(),timeout=240 if qr_provider else 45)
        return await asyncio.wait_for(read_channels(client,now),timeout=100)
    finally:await client.close()

def encode_session(path):
    raw=Path(path).read_bytes()
    if len(raw)>1_000_000 or not raw.startswith(b'SQLite format 3\x00'):raise ValueError('Invalid session database')
    encoded=base64.b64encode(zlib.compress(raw,9)).decode('ascii')
    if len(encoded)>45000:raise ValueError('Session too large for a repository secret')
    return encoded

def decode_session(value):
    if len(value)>45000:raise ValueError('Session secret too large')
    packed=base64.b64decode(value,validate=True);decoder=zlib.decompressobj()
    raw=decoder.decompress(packed,1_000_001)
    if len(raw)>1_000_000 or not decoder.eof or decoder.unused_data or not raw.startswith(b'SQLite format 3\x00'):
        raise ValueError('Invalid session secret')
    return raw

def collect_session(now=None,environ=None):
    env=os.environ if environ is None else environ
    value=env.get('MAX_USER_SESSION_B64','').strip()
    if not value:return [],[]
    try:
        raw=decode_session(value)
        with tempfile.TemporaryDirectory(prefix='city-max-private-') as folder:
            target=Path(folder)/SESSION;target.write_bytes(raw);target.chmod(0o600)
            return asyncio.run(run_reader(folder,now))
    except Exception:
        return [],[{'id':c['id'],'url':'https://max.ru/'+c['slug'],'status':'error','readStatus':'error',
          'checkedAt':(now or datetime.now(timezone.utc)).isoformat(),'posts':0,'coverage':'partial',
          'transport':'max_user_session','note':'Сессия MAX недоступна или требует нового входа через коннектор.'} for c in CHANNELS]
