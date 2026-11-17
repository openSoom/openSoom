#!/usr/bin/env python3
"""Fetch the pinned MIT-licensed Three.js browser modules for offline serving."""
from pathlib import Path
import base64
import hashlib
import io
import json
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
VERSION = '0.187.0'
URL = f'https://registry.npmjs.org/three/-/three-{VERSION}.tgz'
INTEGRITY = 'Qiu7R+Cmh8CstZsY1uJOSWnVlfo7ZtNLV7mF8Jltk3LB3AtDu9cRZlcnRKkAk8Y4z6KKw35z7Y7Urd7jWY8etA=='

def main():
    payload = urllib.request.urlopen(URL, timeout=45).read()
    if base64.b64encode(hashlib.sha512(payload).digest()).decode() != INTEGRITY:
        raise SystemExit('Three.js package integrity mismatch')
    destination = ROOT / 'pitch/vendor'
    destination.mkdir(parents=True, exist_ok=True)
    files = {}
    with tarfile.open(fileobj=io.BytesIO(payload), mode='r:gz') as archive:
        for name in ('build/three.module.js', 'build/three.core.js', 'LICENSE'):
            content = archive.extractfile('package/' + name).read()
            output = destination / Path(name).name
            output.write_bytes(content)
            files[output.name] = hashlib.sha256(content).hexdigest()
    (destination / 'provenance.json').write_text(json.dumps({'name':'three','version':VERSION,'source':URL,'license':'MIT','npm_sha512':INTEGRITY,'files':files},indent=2)+'\n')
    print(json.dumps({'version':VERSION,'files':list(files),'integrity_verified':True}))

if __name__ == '__main__':
    main()
