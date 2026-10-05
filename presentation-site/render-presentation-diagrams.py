"""Readable explanatory views; the canonical Mermaid diagrams remain available separately."""
from pathlib import Path
from html import escape

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'presentation-site/dist/assets'
PALETTE={'blue':('#edf4ff','#285ea6'), 'red':('#fff0f2','#bd2235'), 'gold':('#fff7e7','#926323'), 'green':('#edf7f0','#36744e')}

def render(name,title,subtitle,boxes,edges,bands=()):
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="1040" height="720" viewBox="0 0 1040 720" role="img" aria-labelledby="title desc"><title id="title">{escape(title)}</title><desc id="desc">{escape(subtitle)}</desc>',
      '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10" fill="#60768c"/></marker></defs>',
      '<rect width="1040" height="720" fill="#ffffff"/>',
      f'<text x="32" y="46" font-family="Arial,sans-serif" font-size="30" font-weight="700" fill="#243244">{escape(title)}</text>',
      f'<text x="32" y="80" font-family="Arial,sans-serif" font-size="20" fill="#596b80">{escape(subtitle)}</text>']
    for x,y,w,h,label in bands:
        parts += [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="#f4f7fb"/>',f'<text x="{x+18}" y="{y+28}" font-family="Arial,sans-serif" font-size="18" font-weight="700" fill="#596b80">{escape(label)}</text>']
    for path,label,x,y in edges:
        parts.append(f'<path d="{path}" fill="none" stroke="#60768c" stroke-width="3" marker-end="url(#arrow)"/>')
        if label:parts.append(f'<text x="{x}" y="{y}" font-family="Arial,sans-serif" font-size="18" fill="#596b80">{escape(label)}</text>')
    for x,y,w,h,color,kicker,label,lines in boxes:
        bg,ink=PALETTE[color]
        parts += [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{bg}" stroke="{ink}" stroke-width="{3 if color=="red" else 2}"/>',f'<text x="{x+18}" y="{y+29}" font-family="Arial,sans-serif" font-size="17" font-weight="700" fill="{ink}">{escape(kicker)}</text>',f'<text x="{x+18}" y="{y+64}" font-family="Arial,sans-serif" font-size="25" font-weight="700" fill="#243244">{escape(label)}</text>']
        for i,line in enumerate(lines):parts.append(f'<text x="{x+18}" y="{y+96+i*27}" font-family="Arial,sans-serif" font-size="20" fill="#465a70">{escape(line)}</text>')
    parts += ['<text x="32" y="698" font-family="Arial,sans-serif" font-size="17" fill="#596b80">Sơ đồ giải thích thiết kế · Các mô-đun riêng của đề xuất cần xây và kiểm chứng.</text>','</svg>']
    text='\n'.join(parts)
    (OUT/f'{name}.svg').write_text(text)
    (ROOT/'docs/assets'/f'{name}.svg').write_text(text)

render('system-explained','Health → baseline → chọn can thiệp tiếp theo',
 'Điểm nhấn: quyết định bổ sung có đối chứng, cùng chất lượng và tổng chi phí.',[
 (32,125,285,180,'blue','01 · DATA CORE','Giữ đúng tín hiệu',['Human · Internet · Synthetic','Teleop robot thật','QA, quyền, roots và masks']),
 (377,125,285,180,'blue','02 · FLUXVLA','Học & thích nghi',['Pretrained VLA + action head','Human/video sau gate','Target-robot adaptation']),
 (722,125,285,180,'green','03 · EXECUTION','Robot làm được gì?',['Controller đã kiểm','Scorer độc lập','ID/OOD + lỗi + chi phí']),
 (180,410,680,210,'red','ĐÓNG GÓP CẦN CHỨNG MINH','Chọn gói dữ liệu cho điều kiện còn yếu',['Kiểm camera / mapping / reachability trước','Engineer duyệt giả thuyết → bổ sung một nguồn phù hợp','T / F / A từ R0: cùng quality và hai cost caps'])],
 [('M317 214H372','',0,0),('M662 214H717','',0,0),('M865 305V365H750V405','Báo cáo development',680,348),('M180 515H80V310','Thu / QA thêm',32,385)])

render('data-explained','Một recording, nhiều views — một lineage',
 'Điểm nhấn: chọn objective theo tín hiệu; derivative giữ split của recording gốc.',[
 (32,120,290,150,'blue','01 · RAW','Nguồn & bằng chứng',['Files, timestamps, rights','Measured / inferred / generated']),
 (375,120,290,150,'gold','02 · QA GATE','Hợp lệ để học?',['Timing, geometry, confidence','Reject hoặc quarantine có log']),
 (718,120,290,150,'red','03 · ROOT SPLIT','Chia trước biến đổi',['Recording + parents cùng split','Final holdout khóa riêng']),
 (32,355,290,170,'blue','VIEW A · HUMAN / INTERNET','Kiến thức thao tác',['RGB → stage / temporal order','Wrist motion chỉ khi valid','Không giả robot-action labels']),
 (375,355,290,170,'blue','VIEW B · TARGET ROBOT','Học điều khiển',['Images + state + action','Units / joints / normalization','Train và calibration đúng roles']),
 (718,355,290,170,'blue','VIEW C · SYNTHETIC','Biến thể có kiểm',['Appearance giữ semantics','Physics actions nếu đã thực thi','Không đổi nghĩa nhãn nguồn']),
 (260,570,520,100,'green','ĐẦU RA DÙNG LẠI','Release bất biến + QA/cost receipt',[])],
 [('M322 195H370','',0,0),('M665 195H713','',0,0),('M860 270V310H180V350','Views chỉ từ training roots',352,304),('M520 310V350','',0,0),('M860 310V350','',0,0),('M180 525V550H350V565','',0,0),('M520 525V565','',0,0),('M860 525V550H690V565','',0,0)])

render('validation-explained','Chứng minh từng lợi ích, rồi khóa bài thi cuối',
 'Điểm nhấn: so công bằng; final test không tham gia chọn nguồn hoặc tuning.',[
 (32,125,285,155,'gold','E0 · KHÓA NỀN TẢNG','Chạy được đường học',['Task / robot / scorer / splits','Loss → gradient → reload','Closed-loop, chưa success']),
 (377,125,285,155,'blue','E1 · ROBOT BASELINE','R0: 6 runs core',['2 budgets × 3 seeds','Đo công tới acceptance','Health fail: sửa rồi pin lại']),
 (722,125,285,155,'blue','EXTENSIONS · CÓ GATE','Source / compute / SDG',['Human/internet sau E0','Basic trước Cosmos','Contrast và cost riêng']),
 (130,370,780,165,'red','E4 · KHÁC BIỆT SẢN PHẨM','T / F / A: 9 runs core từ parent R0',['Expert teleop / fixed mixture / condition-cost · catalog / caps','Chỉ chọn từ development probes; báo no-gain nếu không hơn']),
 (180,580,680,90,'green','FINAL FREEZE · INDEPENDENT TEST','Chất lượng + demos + full cost + uncertainty',[])],
 [('M317 205H372','',0,0),('M662 205H717','',0,0),('M865 280V330H520V365','Development, chưa final',450,320),('M520 535V575','Khóa checkpoint và recipe',548,564)])

print('Rendered three explanatory diagrams, preserving separate canonical views.')
