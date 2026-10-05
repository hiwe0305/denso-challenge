"""Package the current website and canonical product dossier, without bulky papers or stale exports."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import re
ROOT=Path(__file__).resolve().parent.parent
DIST=ROOT/'presentation-site/dist'
website=ROOT/'deliverables/DENSO-Humanoid-Human-first-Website.zip'
bundle=ROOT/'deliverables/Human-first-Humanoid-Ho-so.zip'
with ZipFile(website,'w',ZIP_DEFLATED) as z:
    for p in sorted(DIST.rglob('*')):
        if p.is_file(): z.write(p,str(p.relative_to(DIST)))
files=[ROOT/'README.md',ROOT/'PROMPT.md',website]
for pattern in ['docs/*.md','docs/assets/*.svg','docs/assets/*.png','docs/reviews/*','docs/information-challenge/*','deliverables/*.md','presentation-site/*.md','presentation-site/*.py','presentation-site/content/*.json']:
    files.extend(sorted(ROOT.glob(pattern)))
files.extend(sorted(p for p in DIST.rglob('*') if p.is_file()))
reference=(ROOT/'docs/references/README.md').read_text()
reference=re.sub(r' · \[PDF\]\(papers/[^)]+\)','',reference)
reference=re.sub(r'\[([^\]]+)\]\(papers/[^)]+\)',r'\1',reference)
reference+='\nPDF nguồn giữ trong repository, không đóng gói bản sao trong ZIP này.\n'
with ZipFile(bundle,'w',ZIP_DEFLATED) as z:
    for p in files:
        if p==ROOT/'README.md':
            z.writestr('README.md',p.read_text().replace('[Tài liệu sản phẩm](deliverables/Human-first-Humanoid-Ho-so.zip)','Tài liệu sản phẩm đang mở'))
        elif p.is_file(): z.write(p,str(p.relative_to(ROOT)))
    z.writestr('docs/references/README.md',reference)
for p in [website,bundle]:
    with ZipFile(p) as z:
        assert z.testzip() is None
        assert not any('09-team-and-risks' in n or 'noi-dung-bieu-mau' in n or 'VERIFICATION.md' in n for n in z.namelist())
        print(p.name,len(z.namelist()),'files',p.stat().st_size,'bytes')
