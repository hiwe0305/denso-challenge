"""Package reviewed storyboard captures; build a captioned 72-second illustration film.

Frames come from story-export.html at 1280x720 through the browser capture tool.
Image generation is separate; this script does not generate robot performance evidence.
Requires FFmpeg only for rebuilding the film, not for serving the website.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / 'presentation-site/dist/assets/story'
CONTENT = ROOT / 'presentation-site/content'
STORY = json.loads((CONTENT / 'solution-story.json').read_text())
SECONDS = STORY['secondsPerScene']

def run(*args):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

def stamp(seconds):
    return f'{seconds // 3600:02}:{seconds // 60 % 60:02}:{seconds % 60:02}.000'

frames = [ASSETS / f'scene-visual-{i:02}.jpg' for i in range(1, 10)]
for branch in ('visual', 'contact'):
    for i in range(1, 10):
        assert (ASSETS / f'scene-{branch}-{i:02}.jpg').is_file(), (branch, i)

with TemporaryDirectory(prefix='humanoid-story-') as temp:
    folder = Path(temp)
    parts = []
    for i, frame in enumerate(frames):
        part = folder / f'{i:02}.mp4'
        run('ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-loop', '1',
            '-i', str(frame), '-t', str(SECONDS), '-r', '24',
            '-vf', f'fade=t=in:st=0:d=0.25,fade=t=out:st={SECONDS - 0.25}:d=0.25',
            '-c:v', 'libx264', '-threads', '2', '-preset', 'fast', '-crf', '22',
            '-pix_fmt', 'yuv420p', '-an', str(part))
        parts.append(part)
    listing = folder / 'concat.txt'
    listing.write_text(''.join(f"file '{p.as_posix()}'\n" for p in parts))
    run('ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-f', 'concat',
        '-safe', '0', '-i', str(listing), '-c', 'copy', '-movflags', '+faststart',
        str(ASSETS / 'solution-story.mp4'))

vtt = ['WEBVTT', '']
for i, scene in enumerate(STORY['scenes']['visual']):
    vtt += [str(i + 1), f'{stamp(i * SECONDS)} --> {stamp((i + 1) * SECONDS)}',
            scene['title'], scene['body'], '']
(ASSETS / 'solution-story.vi.vtt').write_text('\n'.join(vtt), encoding='utf-8')

readme = '''# Bộ cảnh giải thích Humanoid Skill Learning

Hai tình huống, mỗi tình huống 9 cảnh: visual (đổi ánh sáng, gắp hụt) và
contact (gắp rồi trượt). Ảnh 1280x720 có màn hình workflow và chú thích tiếng Việt.

Đây là ảnh AI và giao diện minh họa quy trình đề xuất, chưa phải kết quả huấn luyện
hay bản ghi robot thực hiện của đội. Cảnh đặt đúng mô tả kết quả kỳ vọng.
Robot trên hình là humanoid minh họa; không là ảnh hay mô hình chính xác của GR1.

Video 72 giây dùng 9 cảnh visual, chuyển cảnh nhẹ, chú thích trên hình, không lời đọc.
Nguyên bản ảnh AI, prompt và nội dung các cảnh được kèm để chỉnh sửa và tái sử dụng.
'''
with ZipFile(ASSETS / 'storyboard.zip', 'w', ZIP_DEFLATED) as bundle:
    bundle.writestr('README.md', readme)
    for branch in ('visual', 'contact'):
        for i in range(1, 10):
            p = ASSETS / f'scene-{branch}-{i:02}.jpg'
            bundle.write(p, f'{branch}/{i:02}.jpg')
    for p in sorted(ASSETS.glob('*.png')):
        bundle.write(p, f'reference-images/{p.name}')
    bundle.write(CONTENT / 'story-image-prompts.json', 'image-prompts.json')
    bundle.write(CONTENT / 'solution-story.json', 'story-content.json')
    bundle.write(ASSETS / 'solution-story.vi.vtt', 'solution-story.vi.vtt')

manifest = {
    'kind': 'Illustrated proposed workflow; not experimental robot evidence',
    'generation': 'Built-in image_gen; same canonical reference for all variants',
    'robot': 'Generic illustrated humanoid, not an exact GR1 model',
    'film': {'durationSeconds': SECONDS * 9, 'width': 1280, 'height': 720,
             'fps': 24, 'audio': False, 'captions': 'Burned-in Vietnamese scene text + VTT'},
    'promptFile': 'presentation-site/content/story-image-prompts.json',
    'storyFile': 'presentation-site/content/solution-story.json',
    'assets': [
        {'path': 'assets/story/' + p.name,
         'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'bytes': p.stat().st_size}
        for p in sorted(ASSETS.iterdir()) if p.is_file()
    ]
}
(ROOT / 'presentation-site/dist/data/story-media-manifest.json').write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
print(f'Built {SECONDS * 9}s film, 18 storyboard frames and download bundle.')
