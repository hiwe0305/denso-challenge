"""Export one requested handover package; source papers stay local."""
import argparse
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import re

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / 'presentation-site/dist'


def website_files():
    return [(p, str(p.relative_to(DIST))) for p in sorted(DIST.rglob('*')) if p.is_file()]


def dossier_files():
    files = [ROOT / name for name in ['README.md', 'IDEA.md', 'PROMPT.md', 'start-website.sh']]
    for pattern in ['docs/*.md', 'docs/assets/*.svg', 'docs/assets/*.png', 'docs/reviews/*',
                    'docs/information-challenge/*', 'deliverables/*.md', 'presentation-site/*.md',
                    'presentation-site/*.py', 'presentation-site/*.js', 'presentation-site/content/*.json']:
        files.extend(sorted(ROOT.glob(pattern)))
    for directory in ['idea-v3-2026-10-05', 'examples/engineering-loop',
                      'docs/implementation-plan/skill-a1', 'presentation-site/dist']:
        files.extend(sorted((ROOT / directory).rglob('*')))
    return [(p, str(p.relative_to(ROOT))) for p in sorted(set(files))
            if p.is_file() and not {'history', '__pycache__', '.pytest_cache'} & set(p.relative_to(ROOT).parts)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind', choices=['website', 'dossier', 'all'], default='website',
                        help='Default: website only. Dossier already includes the website.')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'deliverables')
    args = parser.parse_args()
    if not (DIST / 'index.html').is_file():
        parser.error('Build the website first: python presentation-site/build-content.py')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    exports = []
    if args.kind in ['website', 'all']:
        exports.append(('DENSO-Humanoid-Human-first-Website.zip', website_files(), False))
    if args.kind in ['dossier', 'all']:
        exports.append(('Human-first-Humanoid-Ho-so.zip', dossier_files(), True))
    for name, entries, is_dossier in exports:
        target = args.output_dir / name
        with ZipFile(target, 'w', ZIP_DEFLATED) as archive:
            for path, relative in entries:
                archive.write(path, relative)
            if is_dossier:
                reference = (ROOT / 'docs/references/README.md').read_text()
                reference = re.sub(r' · \[PDF\]\(papers/[^)]+\)', '', reference)
                reference = re.sub(r'\[([^\]]+)\]\(papers/[^)]+\)', r'\1', reference)
                reference += '\nPDF nguồn giữ trong repository, không đóng gói bản sao trong ZIP này.\n'
                archive.writestr('docs/references/README.md', reference)
        with ZipFile(target) as archive:
            assert archive.testzip() is None
            assert len(archive.namelist()) == len(set(archive.namelist()))
            print(target, len(archive.namelist()), 'files', target.stat().st_size, 'bytes')


if __name__ == '__main__':
    main()
