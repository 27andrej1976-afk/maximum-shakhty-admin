import asyncio
import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

FOLDER=Path(__file__).parent/'windows-renew'
sys.path.insert(0,str(FOLDER))
from renew_max import LocalQR


class QRDisplayTests(unittest.TestCase):
    def test_native_qr_does_not_depend_on_browser_opening(self):
        with tempfile.TemporaryDirectory() as folder:
            output=io.StringIO()
            with patch('renew_max.QRWindow') as window, patch('renew_max.open_html') as browser, contextlib.redirect_stdout(output):
                provider=LocalQR(Path(folder))
                asyncio.run(provider.show_qr('https://max.ru/'))
                self.assertTrue((Path(folder)/'login.html').is_file())
                window.assert_called_once()
                browser.assert_not_called()
                self.assertIn('file:///',output.getvalue())
                self.assertNotIn('QR открыт в браузере',output.getvalue())
                provider.close()
                window.return_value.close.assert_called_once()
    def test_browser_failure_still_provides_manual_qr_file(self):
        with tempfile.TemporaryDirectory() as folder:
            output=io.StringIO()
            with patch('renew_max.QRWindow',side_effect=ImportError()), patch('renew_max.open_html',return_value=False), contextlib.redirect_stdout(output):
                provider=LocalQR(Path(folder))
                asyncio.run(provider.show_qr('https://max.ru/'))
                self.assertTrue((Path(folder)/'login.html').is_file())
                self.assertIn('Браузер не принял ссылку',output.getvalue())
                self.assertIn('Ctrl+L',output.getvalue())
    def test_unexpected_qr_host_is_not_opened(self):
        with tempfile.TemporaryDirectory() as folder,patch('renew_max.QRWindow') as window:
            with self.assertRaises(ValueError):
                asyncio.run(LocalQR(Path(folder)).show_qr('https://example.invalid/'))
            window.assert_not_called()
            self.assertFalse((Path(folder)/'login.html').exists())


if __name__=='__main__':
    unittest.main()
