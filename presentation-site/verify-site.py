"""Check the static publishing artifact and generated dossier without network access."""
import json
import hashlib
import re
from pathlib import Path
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / 'presentation-site/dist'

class References(HTMLParser):
    def __init__(self):
        super().__init__()
        self.local = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name not in {'src', 'href'} or not value:
                continue
            if value.startswith(('#', 'https:', 'http:', 'data:')):
                continue
            assert not value.startswith('/'), f'Root-relative URL breaks project Pages: {value}'
            self.local.append(value.split('?')[0].split('#')[0])

refs = References()
refs.feed((DIST / 'index.html').read_text())
for ref in refs.local:
    assert (DIST / ref).is_file(), f'Missing entry asset: {ref}'

app = (DIST / 'app.js').read_text()
routes = re.findall(r"\['([a-z]+)','[^']+'\]", app.split('const main=')[0])
assert len(routes) == len(set(routes)) == 12, routes
for route in routes:
    assert f'function {route}()' in app, f'Missing route: {route}'
for name in re.findall(r"(?:diagramViewer\('|assets/)([\w.-]+\.(?:svg|png))", app):
    assert (DIST / 'assets' / name).is_file(), f'Missing diagram: {name}'

raw = (DIST / 'dossier.js').read_text().split('const DOSSIER = ', 1)[1].split(';\nconst SCORE_MODEL', 1)[0]
docs = json.loads(raw)
for doc in docs:
    assert doc['markdown'] == (ROOT / doc['path']).read_text(), f'Stale dossier: {doc["path"]}'

manifest = json.loads((DIST / 'data/source-manifest.json').read_text())
for media in manifest['media'].values():
    for field in ('url', 'poster', 'playbackUrl'):
        url = media.get(field)
        if url and not url.startswith(('https:', 'http:')):
            assert not url.startswith('/'), f'Root-relative media URL: {url}'
            assert (DIST / url).is_file(), f'Missing media: {url}'
    for field, hash_field in (('playbackUrl', 'playbackSha256'), ('poster', 'posterSha256')):
        digest = media.get('provenance', {}).get(hash_field)
        if digest:
            assert hashlib.sha256((DIST / media[field]).read_bytes()).hexdigest() == digest, f'Stale media: {media[field]}'
assert not any(p.is_symlink() for p in DIST.rglob('*')), 'Pages artifact must not contain symlinks'
print(f'Validated {len(routes)} routes, {len(docs)} documents and local publishing assets.')
