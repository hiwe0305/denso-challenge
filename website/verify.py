"""Check the static publishing artifact in website/dist without network access."""
import json
import hashlib
import re
from pathlib import Path
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / 'website'
DIST = SITE / 'dist'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

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

# Every chapter in the menu must have a page renderer, and nothing else.
app = (DIST / 'app.js').read_text()
page = (DIST / 'current-platform.js').read_text()
chapters = re.findall(r"\['([a-z]+)','[^']+'\]", app.split('const main=')[0])
routes = re.search(r'const routes=\{([^}]*)\}', page)[1]
assert sorted(chapters) == sorted(r.split(':')[0] for r in routes.split(',')), (chapters, routes)
assert len(chapters) == 12 and 'examples' not in chapters
# Five-part story: every route sits in exactly one part and has a bridge line and pager lead.
parts_src = page.split('const CP_PARTS=')[1].split('];')[0]
part_routes = [r.strip("'") for p in re.findall(r"routes:\[([^\]]*)\]", parts_src) for r in p.split(',')]
assert sorted(part_routes) == sorted(chapters), part_routes
meta = re.findall(r"^ ([a-z]+):\{answers:'[^']+',lead:'[^']+'", page, re.M)
assert sorted(meta) == sorted(chapters), meta

# Media referenced by pages exist in the catalog; local media files ship with the site.
media = json.loads((SITE / 'content/media.json').read_text())['media']
for key in set(re.findall(r"media\('([A-Za-z0-9_]+)'\)", page)):
    assert key in media, f'Missing media entry: {key}'
for item in media.values():
    for field in ('url', 'poster', 'playbackUrl'):
        url = item.get(field)
        if url and not url.startswith(('https:', 'http:')):
            assert (DIST / url).is_file(), f'Missing media file: {url}'
for name in re.findall(r"preview\('([\w-]+)'", page):
    assert (DIST / 'data' / f'{name}.json').is_file(), f'Missing data preview: {name}'
for path in re.findall(r'assets/(?:platform|team|decks)/[\w.-]+\.(?:png|jpg|pptx)', page + (DIST / 'current-platform-data.js').read_text()):
    assert (DIST / path).is_file(), f'Missing page asset: {path}'

# Approved presentation versions and original author figures are publishing inputs.
current = json.loads((DIST / 'data/current-platform.json').read_text())
assert current == json.loads((SITE / 'content/current-platform.json').read_text())
assert json.loads((DIST / 'data/current-cost-model.json').read_text()) == json.loads((SITE / 'content/current-cost-model.json').read_text())
sources = json.loads((DIST / 'data/presentation-sources.json').read_text())
assert len(sources['decks']) == 2 and len(sources['figures']) == 5
for deck in sources['decks']:
    assert sha(DIST / deck['path']) == deck['sha256']
    assert sha(ROOT / 'deliverables' / deck['file']) == deck['sha256']
    assert len(deck['slideTexts']) == deck['slideCount']
for figure in sources['figures']:
    assert sha(DIST / figure['path']) == figure['sha256']
    assert sha(SITE / 'assets/platform' / Path(figure['path']).name) == figure['sha256']
    assert figure['sourceUrl'].startswith('https://') and figure['kind'] == 'original_author_figure'
assert sum(len(t['names']) for t in current['team']) == 5
assert current['team'][0]['status'] == 'Đã có video và mã nguồn'
assert all(t['status'] == 'Chờ bổ sung minh chứng' for t in current['team'][1:])
assert len(current['teamEvidence']) == len(sources['teamEvidence']) == 2
for proof in sources['teamEvidence']:
    assert sha(DIST / proof['path']) == proof['sha256']
    assert sha(SITE / 'assets/team' / Path(proof['path']).name) == proof['sha256']
    assert proof['sourceUrl'].startswith('https://')
assert not any(p.is_symlink() for p in DIST.rglob('*')), 'Pages artifact must not contain symlinks'
print(f'Verified {len(chapters)} routes in 5 story parts, {len(media)} media entries, 2 deck SHA-256, 5 original figures, cost inputs and team evidence.')
