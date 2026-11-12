import hashlib,json,sqlite3,tempfile,unittest,zipfile
from pathlib import Path
from nacl.public import PrivateKey,SealedBox
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from import_session import unseal,install

class SessionImportTests(unittest.TestCase):
    def test_authenticated_seal_round_trip_and_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);key=PrivateKey.generate();(p/'key').write_bytes(bytes(key))
            db=sqlite3.connect(':memory:');db.execute('CREATE TABLE qa(value TEXT)');raw=db.serialize();db.close()
            cipher=SealedBox(key.public_key).encrypt(raw)
            def archive(cipher):
                manifest={'recipientSha256':hashlib.sha256(bytes(key.public_key)).hexdigest(),'cipherSha256':hashlib.sha256(cipher).hexdigest()}
                with zipfile.ZipFile(p/'a.zip','w') as z:
                    z.writestr('don-max-session.sealed',cipher);z.writestr('don-max-transfer.json',json.dumps(manifest))
            archive(cipher);self.assertEqual(unseal(p/'a.zip',p/'key'),raw)
            changed=bytearray(cipher);changed[-1]^=1;archive(bytes(changed))
            with self.assertRaises(Exception):unseal(p/'a.zip',p/'key')
    def test_public_output_destination_is_refused(self):
        with self.assertRaises(ValueError):install('never-opened','never-opened','/tmp/public/max-session.db')
