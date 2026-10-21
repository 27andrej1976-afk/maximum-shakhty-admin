"""Interactive Windows setup. No credentials are printed or uploaded as artifacts."""
import asyncio,json,os,subprocess,sys,webbrowser
from pathlib import Path
from datetime import datetime,timezone
if not getattr(sys,'frozen',False):sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from max_user_reader import run_reader,encode_session,SESSION,CHANNELS
APP=Path(os.environ.get('LOCALAPPDATA',Path.home()))/'CityControlMAX'
SETTINGS='https://github.com/27andrej1976-afk/maximum-shakhty-admin/settings/secrets/actions/new'
class LocalQR:
 async def show_qr(self,url):
  from urllib.parse import urlsplit
  import base64,qrcode
  from qrcode.image.svg import SvgPathImage
  parsed=urlsplit(url)
  if parsed.scheme!='https' or parsed.hostname not in ('max.ru','web.max.ru','oneme.ru'):raise ValueError('Unexpected QR host')
  svg=qrcode.make(url,image_factory=SvgPathImage).to_string()
  page=APP/'max-login.html'
  page.write_text('<!doctype html><meta charset="utf-8"><title>Подключение MAX</title><body style="font:20px sans-serif;text-align:center"><h1>Город · подключение MAX</h1><p>Отсканируйте QR через приложение MAX на телефоне и подтвердите вход.</p><img width="420" src="data:image/svg+xml;base64,'+base64.b64encode(svg).decode()+'"><p>После входа закройте эту вкладку.</p>',encoding='utf-8')
  webbrowser.open(page.as_uri());print('QR открыт в браузере. Подтвердите вход в приложении MAX.')

def main():
 APP.mkdir(parents=True,exist_ok=True)
 print('Город под контролем — подключение двух каналов MAX\n')
 print('Сборщик сохраняет только публикации администрации Шахт и Донэнерго.')
 print('Сессия технически даёт доступ ко всему аккаунту. Для постоянной работы рекомендуется отдельный аккаунт.')
 print('Сначала подпишитесь в MAX:')
 for c in CHANNELS:print('https://max.ru/'+c['slug'])
 if input('\nНачать вход по QR? Введите ДА: ').strip().lower() not in ('да','yes'):return
 try:
  posts,states=asyncio.run(run_reader(APP,qr_provider=LocalQR()))
 finally:
  (APP/'max-login.html').unlink(missing_ok=True)
 (APP/'public-channel-check.json').write_text(json.dumps({'checkedAt':datetime.now(timezone.utc).isoformat(),'sources':states,'posts':posts},ensure_ascii=False,indent=2),encoding='utf-8')
 for s in states:print(s['id']+': '+s['status']+'; публикаций: '+str(s['posts']))
 if any(s['status']!='ok' for s in states):
  print('Оба канала пока не прочитаны. Подписка и авторизация требуют проверки. Сессия в облако не передавалась.');return
 print('\nПроверка чтения успешна. Можно подключить облачный сбор без постоянно включённого ПК.')
 print('При подтверждении сессия будет скопирована в буфер обмена для сохранения в GitHub Actions Secret.')
 print('Она НЕ должна попадать в чат, исходники или публичный файл. GitHub-сборщик получит доступ к этой сессии.')
 if input('Подготовить подключение к своему GitHub? Введите ДА: ').strip().lower() not in ('да','yes'):return
 value=encode_session(APP/SESSION)
 subprocess.run(['powershell.exe','-NoProfile','-Command','$input | Set-Clipboard'],input=value,text=True,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 webbrowser.open(SETTINGS)
 print('\nВ открывшейся странице GitHub:')
 print('1. Name: MAX_USER_SESSION_B64')
 print('2. Secret: нажмите Ctrl+V, затем Add secret.')
 print('3. Сообщите Алисе: «Секрет MAX сохранён». Сам секрет присылать НЕ нужно.')
 print('После проверки реальных сообщений будет включена их обработка в приложении.')
 print('Для отключения: удалите этот Secret и завершите сессию в настройках устройств MAX.')
 if input('\nКогда сохранили Secret, нажмите Enter — буфер будет очищен. ')=='' :
  subprocess.run(['powershell.exe','-NoProfile','-Command','Set-Clipboard -Value ""'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

if __name__=='__main__':
 if '--self-test' in sys.argv:
  from max_user_reader import make_client
  import qrcode
  from qrcode.image.svg import SvgPathImage
  c=make_client(APP)
  assert len(CHANNELS)==2
  assert b'<svg' in qrcode.make('https://max.ru/',image_factory=SvgPathImage).to_string()
  print('MAX_CONNECTOR_IMPORTS_OK');sys.exit(0)
 try:main()
 except KeyboardInterrupt:print('\nОстановлено.')
 except Exception as e:print('Подключение не завершено ('+type(e).__name__+'). Секрет не выводился. Проверьте сеть, QR и доступ к каналам.')
 finally:
  if '--self-test' not in sys.argv:input('\nНажмите Enter для закрытия. ')
