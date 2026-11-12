"""Open only the server-recipient SealedBox artifact into a private session dir.

No network, login or output of credentials. Never import into the HTTP tree.
"""
import argparse,hashlib,json,os
from pathlib import Path
import pwd,sqlite3,tempfile,zipfile
from nacl.public import PrivateKey,SealedBox


def unseal(archive,key_path):
    key=PrivateKey(Path(key_path).read_bytes())
    with zipfile.ZipFile(archive) as z:
        if set(z.namelist())!={'don-max-session.sealed','don-max-transfer.json'}:
            raise ValueError('Unexpected encrypted artifact entries')
        if any(x.file_size>64*1024*1024 for x in z.infolist()):raise ValueError('Artifact size limit')
        manifest=json.loads(z.read('don-max-transfer.json'));cipher=z.read('don-max-session.sealed')
    if (manifest.get('recipientSha256')!=hashlib.sha256(bytes(key.public_key)).hexdigest()
            or manifest.get('cipherSha256')!=hashlib.sha256(cipher).hexdigest()):raise ValueError('Recipient or transport hash mismatch')
    raw=SealedBox(key).decrypt(cipher)
    if not raw.startswith(b'SQLite format 3\x00') or len(raw)>64*1024*1024:raise ValueError('Invalid SQLite session')
    return raw


def install(archive,key_path,destination):
    dest=Path(destination).resolve()
    if dest!=Path('/var/lib/don-control/session/max-session.db'):
        raise ValueError('Private deployment destination required')
    if dest.exists():raise ValueError('Existing session requires a separately prepared refresh')
    raw=unseal(archive,key_path)
    account=pwd.getpwnam('don-control')
    fd,tmp=tempfile.mkstemp(prefix='.max-import-',dir=dest.parent)
    try:
        os.fchmod(fd,0o600);os.fchown(fd,account.pw_uid,account.pw_gid)
        with os.fdopen(fd,'wb') as out:out.write(raw)
        connection=sqlite3.connect('file:'+tmp+'?mode=ro',uri=True)
        try:
            if connection.execute('PRAGMA quick_check').fetchone()!=('ok',):raise ValueError('SQLite integrity failure')
        finally:connection.close()
        os.replace(tmp,dest)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive',required=True);p.add_argument('--private-key',required=True)
    p.add_argument('--destination',default='/var/lib/don-control/session/max-session.db');a=p.parse_args()
    try:install(a.archive,a.private_key,a.destination)
    except Exception:raise SystemExit('Private session import failed; no credential value was printed')
    print('Private MAX session imported. Account login and public feed were not changed.')
