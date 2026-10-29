// Render data/progress.json, written by scripts/repo/daily_report.py when the Pages site is built.
(function () {
  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const table = (head, rows) => rows.length
    ? `<div class="table"><table><thead><tr>${head.map((h) => `<th class="${h.num ? 'num' : ''}">${esc(h.label)}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`
    : '<p class="muted">Chưa có dữ liệu.</p>';
  const fmtTime = (iso) => new Date(iso).toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh', dateStyle: 'short', timeStyle: 'short' });

  function render(data) {
    document.getElementById('meta').textContent = `Báo cáo sinh lúc ${fmtTime(data.generated_at)} (giờ Việt Nam)${data.repo ? ' · ' + data.repo : ''}.`;
    const parts = [];

    parts.push('<h2>Rule kích hoạt</h2>');
    parts.push(data.rules.length
      ? `<div class="rules">${data.rules.map((r) => `<div class="rule"><b>${esc(r.rule)}</b>${esc(r.text)}</div>`).join('')}</div>`
      : '<p class="ok">Không có rule nào kích hoạt.</p>');

    const people = Object.entries(data.yesterday || {});
    parts.push('<h2>Hôm qua theo người</h2>');
    parts.push(table(
      [{ label: 'Người' }, { label: 'Nhiệm vụ con' }, { label: 'Giờ', num: true }],
      people.map(([owner, v]) => `<tr><td>${esc(owner)}</td><td><ul>${v.subtasks.map((s) => `<li>${esc(s)}</li>`).join('')}</ul></td><td class="num">${v.hours}</td></tr>`)
    ));

    const k = Object.entries(data.k || {});
    parts.push('<h2>Hệ số k, 7 ngày</h2>');
    parts.push(table(
      [{ label: 'Người' }, { label: 'Giờ thực', num: true }, { label: 'Giờ ước kiếm được', num: true }, { label: 'k', num: true }],
      k.map(([owner, v]) => `<tr><td>${esc(owner)}</td><td class="num">${v.hours}</td><td class="num">${v.earned.toFixed(1)}</td><td class="num">${v.k == null ? '—' : v.k.toFixed(2)}</td></tr>`)
    ));

    if (data.prs) {
      parts.push('<h2>PR đang mở</h2>');
      parts.push(table(
        [{ label: 'PR' }, { label: 'Tác giả' }, { label: 'Tuổi (ngày làm việc)', num: true }, { label: 'Review' }, { label: 'Dòng', num: true }],
        data.prs.map((p) => `<tr><td>${data.repo ? `<a href="https://github.com/${esc(data.repo)}/pull/${p.number}">#${p.number}</a>` : '#' + p.number} ${esc(p.title)}${p.draft ? ' (nháp)' : ''}</td><td>${esc(p.author)}</td><td class="num">${p.age_days}</td><td>${p.reviewed ? 'có' : 'chưa'}</td><td class="num">${p.size}</td></tr>`)
      ));
    }

    if (data.ci) {
      parts.push('<h2>CI trên master</h2>');
      parts.push(table(
        [{ label: 'Workflow' }, { label: 'Kết quả' }],
        data.ci.map((c) => `<tr><td><a href="${esc(c.url)}">${esc(c.workflow)}</a></td><td>${esc(c.conclusion)}</td></tr>`)
      ));
    }

    if (data.issues) {
      const causes = Object.entries(data.issues.causes_7d);
      parts.push('<h2>Lỗi 7 ngày theo nguyên nhân</h2>');
      parts.push(table([{ label: 'Nguyên nhân' }, { label: 'Số issue', num: true }],
        causes.map(([cause, n]) => `<tr><td>${esc(cause)}</td><td class="num">${n}</td></tr>`)));
    }

    parts.push('<h2>Tiến độ story</h2>');
    parts.push(table(
      [{ label: 'Story' }, { label: 'Người làm' }, { label: 'Xong', num: true }, { label: '' }],
      (data.stories || []).map((s) => {
        const pct = s.total ? Math.round((100 * s.done) / s.total) : 0;
        return `<tr><td>${esc(s.id)}</td><td>${esc(s.owner)}</td><td class="num">${s.done}/${s.total}</td><td><div class="bar"><span style="width:${pct}%"></span></div></td></tr>`;
      })
    ));

    if (data.errors && data.errors.length) {
      parts.push('<h2>Nguồn không đọc được</h2>');
      parts.push(`<ul class="muted">${data.errors.map((e) => `<li>${esc(e)}</li>`).join('')}</ul>`);
    }
    document.getElementById('report').innerHTML = parts.join('');
  }

  fetch('data/progress.json?t=' + Date.now())
    .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(render)
    .catch(() => {
      document.getElementById('meta').innerHTML = 'Chưa có báo cáo. Dữ liệu được sinh khi build GitHub Pages; tại máy, chạy <code>python3 scripts/repo/daily_report.py --json website/dist/data/progress.json</code>.';
    });
})();
