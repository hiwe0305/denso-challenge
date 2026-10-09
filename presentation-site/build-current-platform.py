"""Publish the two approved decks and their credited figures without network calls."""
from pathlib import Path
import hashlib, json, shutil, re
from zipfile import ZipFile
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / 'presentation-site'
DIST = SITE / 'dist'
data = json.loads((SITE / 'content/current-platform.json').read_text())
cost = json.loads((SITE / 'content/current-cost-model.json').read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
manifest = {'updated': data['updated'], 'priority': 'Current pitch supersedes older recipes, budgets and durations', 'decks': [], 'figures': [], 'teamEvidence': []}
for deck in data['decks']:
    source = ROOT / 'deliverables' / deck['file']
    target = DIST / 'assets/decks' / source.name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(source, target)
    # A text snapshot lets reviewers trace the website to its precise PPT version.
    with ZipFile(source) as archive:
        slides = sorted((n for n in archive.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml', n)), key=lambda n: int(re.search(r'slide(\d+)', n)[1]))
        texts = [' '.join(t.text or '' for t in ET.fromstring(archive.read(n)).iter('{http://schemas.openxmlformats.org/drawingml/2006/main}t')) for n in slides]
    manifest['decks'].append({**deck, 'path': 'assets/decks/' + source.name, 'sha256': sha(source), 'slideCount': len(slides), 'slideTexts': texts})
figure_sources = json.loads((SITE / 'assets/platform/sources.json').read_text())
for item in figure_sources['assets']:
    source = SITE / 'assets/platform' / item['file']
    target = DIST / 'assets/platform' / item['file']
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(source, target)
    manifest['figures'].append({'path': 'assets/platform/' + source.name, 'sha256': sha(source), 'sourceUrl': item['url'], 'kind': 'original_author_figure'})
for item in data.get('teamEvidence', []):
    source = SITE / 'assets/team' / item['image']
    target = DIST / 'assets/team' / source.name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(source, target)
    manifest['teamEvidence'].append({'path': 'assets/team/' + source.name, 'sha256': sha(source), 'sourceUrl': item['sourceUrl'], 'kind': item['kind']})
for filename, obj in [('current-platform.json', data), ('current-cost-model.json', cost), ('presentation-sources.json', manifest)]:
    (DIST / 'data' / filename).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
(DIST / 'current-platform-data.js').write_text('const CURRENT_PLATFORM = ' + json.dumps(data, ensure_ascii=False) + ';\nconst CURRENT_COST_MODEL = ' + json.dumps(cost, ensure_ascii=False) + ';\nconst PRESENTATION_SOURCES = ' + json.dumps(manifest, ensure_ascii=False) + ';\n')
print('Published current pitch + technical workflow, cost model, 5 original figures and team evidence with source hashes.')
