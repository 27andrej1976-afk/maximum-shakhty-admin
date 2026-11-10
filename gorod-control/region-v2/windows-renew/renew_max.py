"""Local Windows QR renewal; never uploads the session automatically."""
import asyncio
import base64
from datetime import datetime
import logging
import os
from pathlib import Path
import subprocess
import sys
import uuid
import webbrowser

from qr_display import QRWindow, open_html

if not Path(__file__).with_name('max_user_reader.py').is_file():
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from max_user_reader import CHANNELS, SESSION, make_client, encode_session, validate_channel

SETTINGS = 'https://github.com/27andrej1976-afk/maximum-shakhty-admin/settings/secrets/actions'


class LocalQR:
    def __init__(self, folder):
        self.folder = folder
        self.window = None
    async def show_qr(self, url):
        from urllib.parse import urlsplit
        import qrcode
        from qrcode.image.svg import SvgPathImage
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or parsed.hostname not in {'max.ru','web.max.ru','oneme.ru'}:
            raise ValueError('Unexpected QR origin')
        svg = qrcode.make(url, image_factory=SvgPathImage).to_string()
        page = self.folder / 'login.html'
        page.write_text('<!doctype html><meta charset="utf-8"><title>Дон · вход в MAX</title>'
            '<body style="font:20px sans-serif;text-align:center;padding:30px">'
            '<h1>Дон под контролем · MAX</h1><p>Отсканируй QR в MAX на телефоне и подтверди вход.</p>'
            '<img width="380" src="data:image/svg+xml;base64,'+base64.b64encode(svg).decode()+'">'
            '<p>Не отправляй QR или файл сессии в переписку. После входа вернись в окно программы.</p>', encoding='utf-8')
        print('QR сохранён на этом компьютере. Если окно не видно, открой этот адрес через Ctrl+L в браузере:', flush=True)
        print(page.as_uri(), flush=True)
        print('Локальный файл QR:', str(page), flush=True)
        try:
            self.window = QRWindow(url, page)
            print('Создано отдельное окно «Дон под контролем — QR для MAX · версия 2». Сканируй код в нём.', flush=True)
        except Exception:
            requested = open_html(page)
            print('Отдельное окно QR недоступно. ' + ('Ссылка передана браузеру; показ QR нужно проверить.' if requested else 'Браузер не принял ссылку.'), flush=True)
            print('Если открылся поисковик: нажми Ctrl+L, вставь адрес file:/// выше и нажми Enter.', flush=True)

    def close(self):
        if self.window is not None:
            self.window.close()
            self.window = None



def new_session_folder(base):
    folder = Path(base) / ('session-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8])
    folder.mkdir(parents=True, exist_ok=False)
    return folder


async def login(folder, factory=make_client):
    qr = LocalQR(folder)
    client = None
    states = []
    try:
        client = factory(folder, qr_provider=qr)
        await asyncio.wait_for(client.connect(), timeout=240)
        qr.close()
        (folder / 'login.html').unlink(missing_ok=True)
        print('Вход в MAX подтверждён. Проверяем публичные каналы…', flush=True)
        for source in CHANNELS:
            ok = False
            try:
                chat = await asyncio.wait_for(client.get_chat(source['chat_id']), timeout=20)
                validate_channel(chat, source)
                messages = await asyncio.wait_for(client.fetch_history(
                    chat_id=source['chat_id'], backward=20, interactive=False), timeout=20)
                ok = isinstance(messages, list)
            except Exception:
                pass
            states.append((source['name'], ok))
    finally:
        if client is not None:
            try:
                await asyncio.wait_for(client.close(), timeout=10)
            except Exception:
                pass
        qr.close()
        (folder / 'login.html').unlink(missing_ok=True)
    return states


def clipboard(value, *, clear=False):
    command = ("$expected=[Console]::In.ReadToEnd(); if ((Get-Clipboard -Raw).Trim() -eq $expected.Trim()) { Set-Clipboard -Value '' }"
               if clear else "$value=[Console]::In.ReadToEnd(); Set-Clipboard -Value $value")
    subprocess.run(['powershell.exe','-NoProfile','-Command',command],input=value,text=True,
                   check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)


def self_test():
    import tempfile
    from pymax import WebClient
    from qrcode.image.svg import SvgPathImage
    import qrcode
    with tempfile.TemporaryDirectory() as base:
        first, second = new_session_folder(base), new_session_folder(base)
        assert first != second and not (first / SESSION).exists()
        make_client(first, qr_provider=LocalQR(first))
    assert len(CHANNELS) == 3
    assert b'<svg' in qrcode.make('https://max.ru/', image_factory=SvgPathImage).to_string()
    print('Windows renewal offline self-test OK; no MAX connection or clipboard access')


def main():
    if os.name != 'nt':
        print('Этот запуск предназначен для Windows 10/11.')
        return
    logging.disable(logging.CRITICAL)
    print('ДОН ПОД КОНТРОЛЕМ — ПОВТОРНЫЙ ВХОД В MAX · ВЕРСИЯ 2\n',flush=True)
    print('Создаётся новая отдельная сессия. Старый коннектор и его файлы не изменяются.')
    print('Считываются только три ранее настроенных публичных канала; подписки и сообщения не отправляются.')
    print('Если MAX запросит пароль 2FA, вводи его только здесь. Символы пароля не отображаются — это нормально.')
    print('Сессия технически даёт доступ к аккаунту; её нельзя отправлять в чат или публичный файл.\n')
    input('Нажми Enter, чтобы показать QR в отдельном окне: ')
    base = Path(os.environ['LOCALAPPDATA']) / 'DonControlMAX'
    folder = new_session_folder(base)
    states = asyncio.run(login(folder))
    for title, ok in states:
        print(title+(': чтение проверено' if ok else ': чтение пока не подтверждено; проверь подписку в MAX'))
    value = encode_session(folder / SESSION)
    print('\nВход выполнен. Новая сессия пока хранится только на этом компьютере.')
    print('Далее откроется твой GitHub. Нужно обновить СУЩЕСТВУЮЩИЙ секрет MAX_USER_SESSION_B64.')
    print('Не создавай новый секрет: найди строку MAX_USER_SESSION_B64 и нажми значок карандаша.')
    print('В поле Value нажми Ctrl+V, затем Update secret. Значение нигде не выводится на экран.')
    print('Сессия будет передана GitHub только после твоего нажатия Update secret.')
    input('Нажми Enter, чтобы скопировать сессию в буфер и открыть GitHub: ')
    clipboard(value)
    try:
        webbrowser.open(SETTINGS)
        input('\nПосле Update secret вернись сюда и нажми Enter — секрет будет убран из буфера: ')
    finally:
        clipboard(value, clear=True)
    print('Готово. Сообщи Алисе: «Секрет MAX обновил». Само значение не присылай.')


if __name__ == '__main__':
    if '--self-test' in sys.argv:
        self_test()
    else:
        try:
            main()
        except KeyboardInterrupt:
            print('\nОстановлено. Сессия автоматически не передавалась.')
        except Exception:
            print('\nВход не завершён. Секреты не выводились. Сообщи Алисе, на каком шаге остановилось окно.')
        finally:
            input('\nНажми Enter для закрытия окна. ')
