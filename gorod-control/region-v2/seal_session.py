"""Encrypt the already-authorized session to the existing server's public key.

SealedBox provides authenticated encryption. Only the server's private key can
open the artifact. No plaintext session, token or private key is an output.
"""
import argparse,hashlib,json,os,sys
from datetime import datetime,timezone
from pathlib import Path
from nacl.public import PublicKey,SealedBox
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from max_user_reader import decode_session

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--recipient',required=True);p.add_argument('--output',required=True);p.add_argument('--manifest',required=True)
    a=p.parse_args()
    try:
        recipient=bytes.fromhex(Path(a.recipient).read_text().strip())
        if len(recipient)!=32:raise ValueError('Invalid recipient')
        raw=decode_session(os.environ.get('MAX_USER_SESSION_B64',''))
        sealed=SealedBox(PublicKey(recipient)).encrypt(raw)
        output=Path(a.output);output.write_bytes(sealed);output.chmod(0o600)
        manifest={'createdAt':datetime.now(timezone.utc).isoformat(),'format':'libsodium-sealedbox',
            'recipientSha256':hashlib.sha256(recipient).hexdigest(),
            'cipherSha256':hashlib.sha256(sealed).hexdigest(),'plaintextExported':False}
        Path(a.manifest).write_text(json.dumps(manifest,indent=2))
        print(json.dumps(manifest))
    except Exception:
        raise SystemExit('Session encryption failed; verify the existing secret and pinned public recipient')
