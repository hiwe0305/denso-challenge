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

# The visual explanation must ship with both branches and its downloadable film.
story_manifest = json.loads((DIST / 'data/story-media-manifest.json').read_text())
for asset in story_manifest['assets']:
    path = DIST / asset['path']
    assert path.is_file(), f'Missing story asset: {asset["path"]}'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == asset['sha256'], f'Stale story asset: {path.name}'
story = json.loads((ROOT / story_manifest['storyFile']).read_text())
assert set(story['scenes']) == {'visual', 'contact'}
assert all(len(scenes) == 9 for scenes in story['scenes'].values())
assert story_manifest['film']['durationSeconds'] == story['secondsPerScene'] * 9 == 72
for branch in story['scenes']:
    for i in range(1, 10):
        assert (DIST / f'assets/story/scene-{branch}-{i:02}.jpg').is_file()
for asset in ('solution-story.mp4', 'solution-story.vi.vtt', 'storyboard.zip'):
    assert (DIST / 'assets/story' / asset).is_file()
export_refs = References()
export_refs.feed((DIST / 'story-export.html').read_text())
assert all((DIST / ref).is_file() for ref in export_refs.local), 'Missing storyboard export dependency'
three = json.loads((DIST / 'vendor/three-manifest.json').read_text())
assert hashlib.sha256((DIST / 'vendor/three.module.min.js').read_bytes()).hexdigest() == three['moduleSha256']
assert (DIST / 'vendor/three-LICENSE.txt').is_file(), 'Missing 3D renderer license'
# Improvement examples and the canonical specification must be shipped together.
improvement = json.loads((DIST / 'data/task-improvement.json').read_text())
assert improvement == json.loads((ROOT / 'presentation-site/content/task-improvement.json').read_text()), 'Stale task improvement examples'
assert improvement['status'] == 'declared_examples_not_robot_measurements'
assert {c['id'] for c in improvement['cases']} == {'grasp','upstream','zero_task','bootstrap','unknown'}
assert any(d['path'] == 'docs/14-task-improvement.md' for d in docs)
assert any(d['path'] == 'docs/reviews/full-idea-audit-2026-10-05.md' for d in docs)
assert (DIST / 'assets/task-improvement.svg').read_bytes() == (ROOT / 'docs/assets/task-improvement.svg').read_bytes()
audit = json.loads((ROOT / 'docs/reviews/full-idea-audit-2026-10-05.json').read_text())
node_ids = {n['id'] for n in audit['nodes']}
assert all(set(f['targets']) <= node_ids and f['reasoning']['premises'] for f in audit['findings'])
assert all(e['from'] in node_ids and e['to'] in node_ids for e in audit['edges'])
assert not any(p.is_symlink() for p in DIST.rglob('*')), 'Pages artifact must not contain symlinks'
print(f'Validated {len(routes)} routes, {len(docs)} documents, 18 story scenes, 5 improvement cases and local publishing assets.')
