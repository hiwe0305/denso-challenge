"""Package the executed reference and current dossier; no ML/network at publishing time."""
from pathlib import Path
import json,hashlib,shutil,re,zipfile
ROOT=Path(__file__).resolve().parent.parent
D=ROOT/'presentation-site/dist';IDEA=ROOT/'idea-v3-2026-10-05';EX=ROOT/'examples/engineering-loop'
report=json.loads((EX/'results/report.json').read_text())
example_doc=IDEA/'10-example-chay-toan-he-thong.md'
example_doc.write_text(re.sub(r'Run thực: [^*]+', 'Run thực: '+report['measured_at_utc']+'.',example_doc.read_text()))

# Canonical snapshots are generated from the engineering dossier.
canonical={
 '01-product.md':'01-idea-va-pitch.md','02-system-architecture.md':'02-kien-truc-va-cach-hoc.md',
 '03-data-core.md':'03-workflow-du-lieu.md','04-learning-core.md':'02-kien-truc-va-cach-hoc.md',
 '05-contracts.md':'11-contracts-va-logic.md','06-validation-and-roadmap.md':'05-thiet-ke-kiem-chung.md',
 '07-business-case.md':'06-chi-phi-va-kha-thi.md','08-prd.md':'08-ke-hoach-trien-khai.md',
 '10-data-collection-sop.md':'03-workflow-du-lieu.md','13-expected-outcomes.md':'18-ket-qua-ky-vong.md',
 '14-task-improvement.md':'04-bang-chung-vla-va-loi.md'}
for dest,src in canonical.items():
 body=(IDEA/src).read_text()
 body=re.sub(r'\]\(([^)]+)\)',lambda m:']('+('../idea-v3-2026-10-05/'+m.group(1) if '://' not in m.group(1) and not m.group(1).startswith('#') else m.group(1))+')',body)
 lines=body.splitlines();lines.insert(2,f'_Snapshot kỹ thuật từ [hồ sơ engineering](../idea-v3-2026-10-05/{src}); [IDEA.md](../IDEA.md) là bản trình bày gửi đánh giá, recipe mới nhất ở docs/implementation-plan/skill-a1._')
 (ROOT/'docs'/dest).write_text('\n'.join(lines)+'\n')

validation=json.loads((EX/'results/validation.json').read_text())
assert validation['exit_code']==0
assert validation['source_sha256']==hashlib.sha256((EX/'run.py').read_bytes()).hexdigest()
assert validation['tests_sha256']==hashlib.sha256((EX/'test_pipeline.py').read_bytes()).hexdigest()
assert validation['report_sha256']==hashlib.sha256((EX/'results/report.json').read_bytes()).hexdigest()
manifest=json.loads((EX/'results/manifest.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert manifest['source_sha256']==sha(EX/'run.py'),'Rerun reference after source edits'
assert manifest['world_sha256']==sha(EX/'world.xml')
for a in manifest['artifacts']:assert sha(EX/'results'/a['file'])==a['sha256']
# Keep one source/results directory; add its portable copy only inside the ZIP.
files=[p.name for p in (EX/'results').glob('*.json')]
for name in files:
 dest=D/'data/engineering'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy(EX/'results'/name,dest)
write=lambda p,o:p.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n')
flywheel=json.loads((ROOT/'presentation-site/content/data-flywheel.json').read_text())
(D/'data-flywheel-data.js').write_text('const FLYWHEEL_DATA = '+json.dumps(flywheel,ensure_ascii=False)+';\n')
write(D/'data/data-flywheel.json',flywheel)
blueprint=json.loads((ROOT/'presentation-site/content/training-blueprint.json').read_text())
(D/'training-blueprint-data.js').write_text('const TRAINING_BLUEPRINT = '+json.dumps(blueprint,ensure_ascii=False)+';\n')
write(D/'data/training-blueprint.json',blueprint)
overview=json.loads((ROOT/'presentation-site/content/overview-flywheel.json').read_text())
(D/'overview-flywheel-data.js').write_text('const OVERVIEW_FLYWHEEL = '+json.dumps(overview,ensure_ascii=False)+';\n')
write(D/'data/overview-flywheel.json',overview)
pitch=json.loads((ROOT/'presentation-site/content/pitch-pages.json').read_text())
(D/'pitch-pages-data.js').write_text('const PITCH_PAGES = '+json.dumps(pitch,ensure_ascii=False)+';\n')
write(D/'data/pitch-pages.json',pitch)
engine=json.loads((ROOT/'presentation-site/content/model-engine-core.json').read_text())
(D/'model-engine-core-data.js').write_text('const MODEL_ENGINE_CORE = '+json.dumps(engine,ensure_ascii=False)+';\n')
write(D/'data/model-engine-core.json',engine)
shutil.copy(ROOT/'deliverables/DENSO-Noi-dung-form-y-tuong.md',D/'data/denso-form-draft.md')
# Publish the approved proposal separately from measured reference artifacts.
plan=ROOT/'docs/implementation-plan/skill-a1'
story=json.loads((ROOT/'presentation-site/content/solution-story.json').read_text())
spec=json.loads((plan/'task-spec.proposed.json').read_text())
(D/'skill-plan-data.js').write_text('const SKILL_PLAN_SPEC = '+json.dumps(spec,ensure_ascii=False)+';\nconst IDEA_STORY = '+json.dumps(story,ensure_ascii=False)+';\n')
plan_dest=D/'data/skill-a1-plan';plan_dest.mkdir(parents=True,exist_ok=True)
plan_files=sorted(p for p in plan.iterdir() if p.is_file())
for p in plan_files:shutil.copy(p,plan_dest/p.name)
write(plan_dest/'manifest.json',{'status':'proposal_not_native_results','files':[{'name':p.name,'sha256':sha(p)} for p in plan_files]})
with zipfile.ZipFile(D/'assets/skill-a1-plan.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(plan_dest.iterdir()):z.write(p,'skill-a1/'+p.name)
write(D/'data/engineering/project-spec.json',json.loads((IDEA/'project-spec.json').read_text()))
for name in ['kien-truc-v3.svg','kien-truc-v3.png']:shutil.copy(IDEA/'assets'/name,D/'assets'/name)
# Readable dossier always starts with current v3.1 documents, then source/reference docs.
raw=(D/'dossier.js').read_text();old=json.loads(raw.split('const DOSSIER = ',1)[1].split(';\nconst SCORE_MODEL',1)[0])
current_paths=[ROOT/'IDEA.md',ROOT/'deliverables/DENSO-Noi-dung-form-y-tuong.md',IDEA/'README.md',*sorted(IDEA.glob('[0-9][0-9]-*.md')),*sorted(plan.glob('*.md')),EX/'README.md']
current=[{'path':str(p.relative_to(ROOT)),'title':p.read_text().splitlines()[0].removeprefix('# '),'markdown':p.read_text()} for p in current_paths]
(D/'dossier.js').write_text('const DOSSIER = '+json.dumps(current+[dict(o,markdown=(ROOT/o['path']).read_text(),title=(ROOT/o['path']).read_text().splitlines()[0].removeprefix('# ')) for o in old if o['path'] not in {str(p.relative_to(ROOT)) for p in current_paths} and not o['path'].startswith('idea-v3-')],ensure_ascii=False)+';\nconst SCORE_MODEL'+raw.split(';\nconst SCORE_MODEL',1)[1])
# Ship original relative paths, including all local Markdown dependencies.
package_files={ROOT/'IDEA.md',ROOT/'deliverables/DENSO-Noi-dung-form-y-tuong.md'}
for directory in [IDEA,EX,plan]:
 for p in directory.rglob('*'):
  if p.is_file() and not any(part in p.relative_to(directory).parts for part in ['history','example','__pycache__','.pytest_cache']):
   package_files.add(p)
from urllib.parse import unquote, urlsplit
pending=list(package_files)
while pending:
 p=pending.pop()
 if p.suffix!='.md':continue
 for link in re.findall(r'\]\(([^)]+)\)',p.read_text()):
  target=urlsplit(link.strip('<>'))
  if target.scheme or not target.path:continue
  dependency=(p.parent/unquote(target.path)).resolve()
  if not dependency.is_relative_to(ROOT):raise ValueError(f'Package link outside project: {p}: {link}')
  if not dependency.is_file():raise FileNotFoundError(f'Broken dossier link: {p.relative_to(ROOT)}: {link}')
  if dependency not in package_files:
   package_files.add(dependency);pending.append(dependency)
with zipfile.ZipFile(D/'assets/idea-v3.1.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(package_files):z.write(p,str(p.relative_to(ROOT)))
package_paths=[str(p.relative_to(ROOT)) for p in sorted(package_files)]
write(D/'data/dossier-package-manifest.json',{'scope':'current_dossier_A1_form_reference_and_local_dependencies','files':package_paths})
with (D/'pitch-pages-data.js').open('a') as f:
 f.write('const DOSSIER_PACKAGE_FILES = '+json.dumps(package_paths,ensure_ascii=False)+';\n')
print('Published dossier, A1 proposal, form and reference with complete local link dependencies.')
