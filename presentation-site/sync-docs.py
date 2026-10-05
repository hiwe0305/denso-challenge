"""Render canonical diagrams and rebuild the complete website dossier."""
from pathlib import Path
import shutil,subprocess,sys
ROOT=Path(__file__).resolve().parent.parent
SITE=ROOT/'presentation-site';ASSETS=SITE/'dist/assets'
subprocess.run([sys.executable,str(SITE/'render-diagrams.py')],check=True)
for name in ['system-architecture','data-flow','runtime','improvement-loop','evaluation']:
 shutil.copy2(ROOT/'docs/assets'/f'{name}.svg',ASSETS/f'{name}.svg')
shutil.copy2(ROOT/'docs/reviews/idea-score.json',SITE/'dist/data/idea-score.json')
subprocess.run([sys.executable,str(SITE/'render-presentation-diagrams.py')],check=True)
for name in ['task-example.svg','fluxvla-paper-figure-1.png']:
 shutil.copy2(ROOT/'docs/assets'/name,ASSETS/name)
subprocess.run([sys.executable,str(SITE/'build-content.py')],check=True)
print('Synced five source diagrams and the complete dossier.')
