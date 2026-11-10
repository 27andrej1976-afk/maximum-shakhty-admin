"""Show a local login QR directly; browser opening is only a fallback.

The live login link is never logged or uploaded. This module handles display,
not confirmation: only MAX can confirm authentication.
"""
import asyncio
import os
from pathlib import Path
import webbrowser


def qr_matrix(url):
    import qrcode
    qr = qrcode.QRCode(border=4, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(url)
    qr.make(fit=True)
    return qr.get_matrix()


def open_html(page):
    page = Path(page).resolve()
    try:
        if os.name == 'nt':
            os.startfile(str(page))
            return True
        return bool(webbrowser.open(page.as_uri()))
    except Exception:
        return False


class QRWindow:
    def __init__(self, url, page):
        self.root = None
        self.task = None
        try:
            import tkinter as tk
            matrix = qr_matrix(url)
            self.root = tk.Tk()
            self.root.title('Дон под контролем — QR для MAX · версия 2')
            self.root.configure(bg='white')
            self.root.resizable(False, False)
            tk.Label(self.root, text='Вход в MAX', font=('Segoe UI', 18, 'bold'), bg='white').pack(pady=(18, 5))
            tk.Label(self.root, text='Открой сканер QR в MAX на телефоне\nи подтверди вход. Код временный.',
                     font=('Segoe UI', 11), bg='white').pack(padx=22, pady=7)
            cell = max(3, min(8, 420 // len(matrix)))
            size = len(matrix) * cell
            canvas = tk.Canvas(self.root, width=size, height=size, bg='white',
                               highlightthickness=0)
            canvas.pack(padx=25, pady=10)
            # Draw square modules directly: no Pillow or external image viewer.
            for y, row in enumerate(matrix):
                for x, dark in enumerate(row):
                    if dark:
                        canvas.create_rectangle(x*cell, y*cell, (x+1)*cell, (y+1)*cell,
                                                fill='black', outline='black', width=0)
            tk.Button(self.root, text='Открыть QR в браузере', command=lambda: open_html(page),
                      font=('Segoe UI', 10)).pack(pady=(6, 9))
            tk.Label(self.root, text='После подтверждения вернись в чёрное окно программы.\nQR и секрет сессии в переписку не отправляй.',
                     font=('Segoe UI', 9), bg='white', fg='#556677').pack(padx=20, pady=(0, 18))
            self.root.protocol('WM_DELETE_WINDOW', self.close)
            self.root.update()
            self.root.lift()
            self.task = asyncio.create_task(self._pump())
        except Exception:
            self.close()
            raise

    async def _pump(self):
        try:
            while self.root is not None:
                self.root.update()
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            pass
        except Exception:
            self.close()

    def close(self):
        root, self.root = self.root, None
        if root is not None:
            try:
                root.destroy()
            except Exception:
                pass
        if self.task is not None and not self.task.done():
            self.task.cancel()
