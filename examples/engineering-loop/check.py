"""Run the reference and record the actual test outcome tied to artifacts/source."""
import re, subprocess, sys
from pathlib import Path
from run import run, write, digest, HERE
out=HERE/'results';run(out)
p=subprocess.run([sys.executable,'-m','pytest','-q',str(HERE/'test_pipeline.py')],capture_output=True,text=True)
print(p.stdout)
if p.stderr:print(p.stderr)
m=re.search(r'(\d+) passed',p.stdout)
receipt={'scope':'reference_contract_scoring_and_pipeline_tests_not_native_vla','exit_code':p.returncode,
 'passed':int(m.group(1)) if m else 0,'source_sha256':digest(HERE/'run.py'),'tests_sha256':digest(HERE/'test_pipeline.py'),
 'report_sha256':digest(out/'report.json'),'output':p.stdout.strip()}
write(out/'validation.json',receipt)
import json
manifest=json.loads((out/'manifest.json').read_text())
manifest['artifacts'].append({'file':'validation.json','sha256':digest(out/'validation.json')})
write(out/'manifest.json',manifest)
raise SystemExit(p.returncode)
