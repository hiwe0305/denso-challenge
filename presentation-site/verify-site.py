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
assert len(routes) == len(set(routes)) == 13, routes
assert 'resources' not in routes
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
    digest = media.get('provenance', {}).get('assetSha256')
    if digest:
        assert hashlib.sha256((DIST / media['url']).read_bytes()).hexdigest() == digest, f"Changed paper figure: {media['url']}"
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
assert story_manifest['storySha256'] == hashlib.sha256((ROOT / story_manifest['storyFile']).read_bytes()).hexdigest(), 'Stale story media content'
published_data = (DIST / 'skill-plan-data.js').read_text()
published_story = json.loads(published_data.split('const IDEA_STORY = ', 1)[1].removesuffix(';\n'))
assert published_story == story, 'Interactive story differs from media authority'
plan_dir = ROOT / 'docs/implementation-plan/skill-a1'
published_spec = json.loads(published_data.split('const SKILL_PLAN_SPEC = ', 1)[1].split(';\nconst IDEA_STORY', 1)[0])
assert published_spec == json.loads((plan_dir / 'task-spec.proposed.json').read_text())
plan_manifest = json.loads((DIST / 'data/skill-a1-plan/manifest.json').read_text())
for item in plan_manifest['files']:
    source = plan_dir / item['name']
    published = DIST / 'data/skill-a1-plan' / item['name']
    assert source.read_bytes() == published.read_bytes()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == item['sha256']
from zipfile import ZipFile
with ZipFile(DIST / 'assets/skill-a1-plan.zip') as plan_zip:
    assert plan_zip.testzip() is None
    for item in plan_manifest['files']:
        assert plan_zip.read('skill-a1/' + item['name']) == (plan_dir / item['name']).read_bytes()
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
# A valid ZIP CRC does not establish that its local document links are usable.
from urllib.parse import urlsplit, unquote
import posixpath
with ZipFile(DIST / 'assets/idea-v3.1.zip') as dossier_zip:
    names=set(dossier_zip.namelist())
    assert {'IDEA.md','deliverables/DENSO-Noi-dung-form-y-tuong.md','docs/implementation-plan/skill-a1/README.md','examples/engineering-loop/README.md'} <= names
    for name in names:
        if not name.endswith('.md'): continue
        for link in re.findall(r'\]\(([^)]+)\)',dossier_zip.read(name).decode()):
            target=urlsplit(link.strip('<>'))
            if target.scheme or not target.path: continue
            resolved=posixpath.normpath(posixpath.join(posixpath.dirname(name),unquote(target.path)))
            assert resolved in names, f'Package link missing: {name} -> {link}'
assert json.loads((DIST/'data/pitch-pages.json').read_text())==json.loads((ROOT/'presentation-site/content/pitch-pages.json').read_text()), 'Stale route summaries'
print(f'Validated {len(routes)} routes, {len(docs)} documents, 18 story scenes, 5 improvement cases and local publishing assets.')

# Approved presentation versions and original author figures are publishing inputs.
current = json.loads((DIST / 'data/current-platform.json').read_text())
assert current == json.loads((ROOT / 'presentation-site/content/current-platform.json').read_text())
assert json.loads((DIST / 'data/current-cost-model.json').read_text()) == json.loads((ROOT / 'presentation-site/content/current-cost-model.json').read_text())
sources = json.loads((DIST / 'data/presentation-sources.json').read_text())
assert len(sources['decks']) == 2 and len(sources['figures']) == 5
for deck in sources['decks']:
    assert hashlib.sha256((DIST / deck['path']).read_bytes()).hexdigest() == deck['sha256']
    assert hashlib.sha256((ROOT / 'deliverables' / deck['file']).read_bytes()).hexdigest() == deck['sha256']
    assert len(deck['slideTexts']) == deck['slideCount']
for figure in sources['figures']:
    assert hashlib.sha256((DIST / figure['path']).read_bytes()).hexdigest() == figure['sha256']
    assert hashlib.sha256((ROOT / 'presentation-site/assets/platform' / Path(figure['path']).name).read_bytes()).hexdigest() == figure['sha256']
    assert figure['sourceUrl'].startswith('https://') and figure['kind'] == 'original_author_figure'
assert sum(len(t['names']) for t in current['team']) == 5
assert all(t['status'] == 'Chờ bổ sung minh chứng' for t in current['team'])
print('Verified current pitch/workflow SHA-256, 5 original figures, cost inputs and team evidence status.')
