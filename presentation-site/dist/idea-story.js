/* A proposed workflow told through one consistent task. No simulated measurements. */
const IDEA_ASSETS = 'assets/story/';
const IDEA_PHASES = [
 ['data','Dữ liệu phù hợp','Mẫu robot + tín hiệu bổ sung',1],
 ['learn','Huấn luyện kỹ năng','Tận dụng mô hình có sẵn',6],
 ['execute','Robot thực hiện','Camera + trạng thái + lệnh',2],
 ['evaluate','Đánh giá kết quả','Thành công, lỗi và tổng công',7],
 ['improve','Chọn cách cải thiện','Kỹ sư kiểm tra và quyết định',5]
];
const IDEA_CONDITIONS = {
 visual: {label:'Đổi ánh sáng · gắp hụt',image:'visual-failure.png',failure:'Bộ gắp đóng nhưng không lấy được linh kiện',observation:'Quan sát: bộ gắp tiếp cận lệch, vật vẫn ở trên bàn.',hypothesis:'Giả thuyết cần kiểm: quan sát trong ánh sáng mới chưa đủ tốt.',checks:['Camera và thời điểm ảnh','Hiệu chuẩn tọa độ','Vùng thao tác và điều khiển'],choice:'Thử biến đổi hình ảnh cơ bản',reason:'Sau khi kiểm hệ thống, thử một gói nhỏ thay đổi ánh sáng trên dữ liệu học hợp lệ.',package:'Biến thể ánh sáng',signal:'Giữ nhãn hành động chỉ khi vật, hình học và ý nghĩa thao tác không đổi.',alternatives:['Tái dùng dữ liệu liên quan','Thu mẫu robot có chủ đích','Video bổ sung nếu đủ tín hiệu'],comparison:'So với parent policy và thu mẫu robot có chủ đích; ghi toàn bộ công của augmentation và training.'},
 contact: {label:'Gắp rồi trượt · rơi vật',image:'contact-failure.png',failure:'Linh kiện tuột khỏi bộ gắp trước khi tới khay',observation:'Quan sát: robot đã nâng vật, nhưng vật rơi trong lúc chuyển.',hypothesis:'Giả thuyết cần kiểm: cách gắp hoặc điều khiển tiếp xúc chưa phù hợp.',checks:['Bộ gắp và phản hồi robot','Thời điểm đóng / mở bộ gắp','Điều khiển và cấu hình vật'],choice:'Thu mẫu robot sửa lỗi có chủ đích',reason:'Nếu hệ thống đã được kiểm, ưu tiên mẫu robot đích về giữ vật và chuyển vật.',package:'Mẫu giữ vật / sửa lỗi',signal:'Camera, trạng thái và hành động đúng robot đích; kiểm kết quả từng lượt.',alternatives:['Sửa điều khiển nếu có lỗi','Tái dùng mẫu robot phù hợp','Biến thể vật lý nếu đủ độ tin cậy'],comparison:'So cùng chất lượng yêu cầu và ngân sách; tính cả thu mẫu, đặt lại vật và kiểm dữ liệu.'}
};
function ideaSteps(condition){return IDEA_STORY.scenes[condition];}
function ideaArchitecture(){return `<div class="idea-architecture" aria-label="Kiến trúc giải pháp đề xuất"><div class="idea-architecture-head"><h2>Solution trong một hình</h2><span>Nhấn một khối để xem ví dụ</span></div><div class="idea-flow">${IDEA_PHASES.map(([id,title,sub,step],i)=>`<button type="button" class="idea-node" data-idea-phase="${id}" data-idea-step="${step}" aria-pressed="false"><span class="idea-node-index">0${i+1}</span><strong>${title}</strong><small>${sub}</small></button>`).join('')}</div><div class="idea-loop"><span aria-hidden="true">↶</span><span>Đánh giá điều kiện còn yếu → kiểm hệ thống → chọn can thiệp phù hợp → học và đo lại</span></div><p class="idea-architecture-note">Mẫu robot dạy hành động · Video bổ sung tín hiệu thao tác · Vòng cải thiện do kỹ sư duyệt</p></div>`;}
function renderIdeaOverview(){return `<div class="idea-overview">
 ${openingIntro()}
 ${openingArchitecture()}
 <section class="panel spaced"><span class="opening-kicker">DATA CORE · DATA FLYWHEEL</span><h2>Trải nghiệm mới định hướng lần học tiếp theo.</h2><p>Chạy → kiểm giả thuyết → chọn can thiệp/data → QA release → học với dữ liệu tốt cũ → kiểm toàn task và chọn phiên bản. Lỗi integration đi sang repair; candidate no-gain được giữ lại như evidence, chưa thay policy đang dùng.</p><a class="button" href="#architecture">Khám phá data flywheel →</a></section>
 ${openingTaskContract()}
 ${openingCase()}
 ${openingEvidence()}
 ${openingNativeBaseline()}
 ${openingSourceRecipes()}
 <details class="opening-more"><summary>Thử thêm các tình huống cải thiện<span>Fixture minh họa riêng; không phải kết quả native hoặc scorer A1.</span></summary>${taskImprovementMarkup()}</details>
 <details class="opening-more"><summary>Khám phá đầy đủ: 9 cảnh từ giao việc đến bàn giao<span>Ảnh từng bước, trình phát câu chuyện và hai tình huống lỗi</span></summary>
 <section class="idea-story" id="idea-story" aria-labelledby="idea-story-title"><header class="idea-story-header"><div><span class="idea-eyebrow">MỘT NHIỆM VỤ · TOÀN BỘ VÒNG CẢI THIỆN</span><h2 id="idea-story-title">“Đặt linh kiện màu vàng vào ô A1.”</h2></div><span class="idea-status">Minh họa thiết kế</span></header>
 <fieldset class="idea-scenarios"><legend>Khám phá tình huống lỗi</legend>${['contact','visual'].map(id=>[id,IDEA_CONDITIONS[id]]).map(([id,c])=>`<button type="button" data-idea-condition="${id}" aria-pressed="${id==='contact'}">${c.label}</button>`).join('')}</fieldset>
 <div class="idea-stage" id="idea-stage"></div>
 <div class="idea-player"><div class="idea-player-buttons"><button type="button" id="idea-prev" aria-label="Cảnh trước">←</button><button type="button" id="idea-play">▶ Xem toàn bộ câu chuyện</button><button type="button" id="idea-next" aria-label="Cảnh tiếp theo">→</button></div><span id="idea-position">Cảnh 1 / 9</span></div>
 <div class="idea-step-list" aria-label="Chọn cảnh trong câu chuyện">${ideaSteps('contact').map((s,i)=>`<button type="button" data-idea-step="${i}" aria-pressed="${i===0}"><span>${String(i+1).padStart(2,'0')}</span>${s.label}</button>`).join('')}</div>
 <p class="idea-disclosure">Bộ ảnh AI và màn hình minh họa giải thích quy trình đề xuất; demo 3D có chuyển động được dựng. Thử nghiệm VLA trên GR1 chưa thực hiện. Chuyển cảnh không biểu diễn thời gian huấn luyện thực.</p></section>
 <section class="idea-full-story" aria-labelledby="idea-gallery-title"><div class="section-head"><h2 id="idea-gallery-title">Xem nhanh toàn bộ câu chuyện</h2><p>Cùng một robot, nhiệm vụ và vòng cải thiện. Nhấn ảnh để xem từng bước.</p></div><div class="idea-gallery" id="idea-gallery"></div></section>
 </details>
 ${openingQualityCost()}
 <section class="idea-video-section"><div><span class="idea-eyebrow">BẢN KỂ CHUYỆN BẰNG VIDEO</span><h2>Nhập môn solution trong 72 giây</h2><p>Chín cảnh đã đồng bộ với bản triển khai A1: baseline → lỗi → phép kiểm → can thiệp có điều kiện → đo chất lượng và tổng công. Đây là video giải thích; chưa là bản ghi native VLA / GR1.</p></div><video id="idea-film" controls playsinline preload="none" poster="assets/story/task-start.png" aria-label="Video minh họa chín bước phát triển kỹ năng humanoid"><source src="assets/story/solution-story.mp4" type="video/mp4"><track kind="captions" src="assets/story/solution-story.vi.vtt" srclang="vi" label="Tiếng Việt"><a href="assets/story/solution-story.mp4">Mở video minh họa</a></video><p class="idea-film-status" role="status"></p><a class="idea-download" href="assets/story/solution-story.mp4" download>Tải video minh họa ↓</a><a class="idea-download" href="assets/story/storyboard.zip" download>Tải bộ cảnh A1 đã cập nhật ↓</a></section>
 ${next('product','Sản phẩm và phần đội đóng góp')}
 </div>`;}
function ideaMiniFlow(items){return `<div class="idea-mini-flow">${items.map((s,i)=>`<div><span>0${i+1}</span><strong>${s}</strong></div>`).join('')}</div>`;}
function ideaScreen(view,c){switch(view){
 case 'mission':return `<div class="idea-command"><span>LỆNH NHIỆM VỤ</span><strong>Đặt linh kiện vàng<br>vào ô A1</strong></div><div class="idea-tray" aria-label="Ô A1 là ô đích phía trước bên trái">${['B1','B2','B3','A1','A2','A3'].map(x=>`<span class="${x==='A1'?'target':''}">${x}${x==='A1'?'<i>Ô đích</i>':''}</span>`).join('')}</div><p class="idea-screen-note">Đúng vật · đúng ô · đã nhả · vật ổn định</p>`;
 case 'data':return `<div class="idea-source-role"><strong>Human egocentric</strong><span>RGB + wrist poses → common motion pilot có gate</span></div><div class="idea-source-role robot"><strong>Robot đích</strong><span>Expert actions · calibration · correction</span></div><div class="idea-source-role optional"><strong>Synthetic</strong><span>Quỹ đạo thực thi / QA → robot action targets; video sinh giữ provenance riêng</span></div><p class="idea-screen-note">Roots / splits trước biến thể. Final không vào training. Common wrist bridge là candidate, cần kiểm transfer.</p>`;
 case 'execute':return `${ideaMiniFlow(['Ảnh + lệnh → VLM features','Action Expert + state → action chunk','Binding / controller → command','Response đo → scorer độc lập'])}<p class="idea-screen-note">Học trong mô phỏng trước; robot thật cần cấu hình và nghiệm thu riêng.</p>`;
 case 'failure':return `<div class="idea-event"><span>TÌNH HUỐNG ĐƯỢC DỰNG</span><strong>${c.label}</strong><p>${c.observation}</p></div><div class="idea-open-question"><strong>Cần kiểm nguyên nhân</strong><span>Một hình lỗi chưa đủ kết luận robot thiếu dữ liệu.</span></div>`;
 case 'health':return `<ul class="idea-checks">${c.checks.map(s=>`<li><span aria-hidden="true">○</span>${s}<small>Cần kiểm</small></li>`).join('')}</ul><div class="idea-branch"><strong>Có lỗi hệ thống?</strong><span>Sửa và lập lại baseline</span></div><div class="idea-branch"><strong>Có giả thuyết dữ liệu?</strong><span>Xét gói phù hợp và chi phí</span></div>`;
 case 'choice':return `<div class="idea-selected-package"><span>PHƯƠNG ÁN MINH HỌA · KỸ SƯ DUYỆT</span><strong>${c.choice}</strong></div><ul class="idea-alternatives">${c.alternatives.map(s=>`<li>${s}</li>`).join('')}</ul><p class="idea-screen-note">Đủ tín hiệu · đủ quyền · trong ngân sách. Chưa đủ cơ sở thì hoãn.</p>`;
 case 'learn':return `${ideaMiniFlow([c.package,'Release có QA / roots / split','Recipe: loss + modules train / freeze','Checkpoint + gradient / reload checks'])}<div class="idea-training-track" aria-hidden="true"><span></span></div><p class="idea-screen-note">Hoạt ảnh minh họa quá trình; không là tiến độ công việc thực.</p>`;
 case 'evaluate':return `<div class="idea-result-pair"><div><span>Phiên bản ban đầu</span><strong>Đối chứng</strong></div><div><span>Phiên bản bổ sung</span><strong>Cần đo</strong></div></div><ul class="idea-measures"><li>Chất lượng trên các lượt giữ riêng</li><li>Số mẫu robot và thời gian thực hiện</li><li>Công thu, kiểm, học và thử lại</li></ul><div class="idea-result-note">Kết quả: cải thiện / không cải thiện / chưa đủ kết luận</div>`;
 case 'deliver':return `<div class="idea-bundle"><span>GÓI KỸ NĂNG SAU NGHIỆM THU</span><strong>Checkpoint + preprocessing / binding</strong><strong>Dataset release + recipe + receipts</strong><strong>Rollouts + báo cáo chất lượng / tổng công</strong></div><p class="idea-screen-note">Thử tác vụ thứ hai để đo công tái sử dụng.</p>`;
 default:return '';
}}
function ideaStageMarkup(s,c,index){return `<div class="idea-scene-image"><img src="${IDEA_ASSETS+s.image}" alt="${esc(s.alt)}" width="1672" height="941" decoding="sync"><span class="idea-image-label">Ảnh minh họa AI · Không phải bản ghi thử nghiệm</span>${s.view==='mission'?'<span class="idea-task-callout">Linh kiện vàng → Ô A1</span>':''}</div><div class="idea-system"><div class="idea-system-heading"><span>WORKFLOW ĐỀ XUẤT</span><span>0${index+1} / 09</span></div>${ideaScreen(s.view,c)}</div><div class="idea-scene-caption" aria-live="polite"><span class="idea-caption-step">CẢNH 0${index+1} · ${s.label.toLocaleUpperCase('vi')}</span><h3>${s.title}</h3><p>${s.body}</p><small>${s.note}</small></div>`;}
function initIdeaStory(signal){const root=document.querySelector('.idea-overview');if(!root)return;
 let condition='contact',index=0,playing=false,timer=null;
 const stage=root.querySelector('#idea-stage'),gallery=root.querySelector('#idea-gallery'),play=root.querySelector('#idea-play');
 function stop(){playing=false;clearTimeout(timer);timer=null;play.textContent='▶ Xem toàn bộ câu chuyện';play.setAttribute('aria-pressed','false');}
 function render(){const steps=ideaSteps(condition),s=steps[index],c=IDEA_CONDITIONS[condition];
  stage.innerHTML=ideaStageMarkup(s,c,index);
  root.querySelector('#idea-position').textContent=`Cảnh ${index+1} / 9`;
  root.querySelector('#idea-prev').disabled=index===0;root.querySelector('#idea-next').disabled=index===8;
  root.querySelectorAll('[data-idea-step]').forEach(b=>b.setAttribute('aria-pressed',String(Number(b.dataset.ideaStep)===index)));
  root.querySelectorAll('[data-idea-phase]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.ideaPhase===s.phase)));
  root.querySelectorAll('[data-idea-condition]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.ideaCondition===condition)));
  stage.querySelector('img').addEventListener('error',e=>{e.target.hidden=true;stage.querySelector('.idea-image-label').textContent='Ảnh chưa tải được. Nội dung cảnh vẫn xem ở bên dưới.';},{signal});
 }
 function renderGallery(){gallery.innerHTML=ideaSteps(condition).map((s,i)=>`<button type="button" class="idea-gallery-item" data-idea-gallery="${i}" aria-label="Xem cảnh ${i+1}: ${esc(s.title)}"><div class="idea-gallery-image"><img src="${IDEA_ASSETS}scene-${condition}-${String(i+1).padStart(2,'0')}.jpg" alt="" loading="lazy" width="1280" height="720"><span>${String(i+1).padStart(2,'0')}</span></div><strong>${s.label}</strong><small>${s.title}</small></button>`).join('');}
 function tick(){if(!playing||signal.aborted)return;if(index===8){stop();return;}index++;render();timer=setTimeout(tick,8000);}
 root.addEventListener('click',e=>{const b=e.target.closest('button');if(!b||!root.contains(b))return;
  if(b.dataset.ideaCondition){stop();condition=b.dataset.ideaCondition;index=3;renderGallery();render();return;}
  if(b.dataset.ideaStep!==undefined||b.dataset.ideaGallery!==undefined){stop();index=Number(b.dataset.ideaStep??b.dataset.ideaGallery);render();if(b.dataset.ideaGallery!==undefined||b.classList.contains('idea-node')){root.querySelector('#idea-story').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'start'});}return;}
  if(b.id==='idea-prev'||b.id==='idea-next'){stop();index=Math.max(0,Math.min(8,index+(b.id==='idea-next'?1:-1)));render();return;}
  if(b.id==='idea-play'){if(playing){stop();return;}index=0;playing=true;render();play.textContent='Ⅱ Tạm dừng câu chuyện';play.setAttribute('aria-pressed','true');timer=setTimeout(tick,8000);}
 },{signal});
 document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();},{signal});
 const film=root.querySelector('#idea-film');film.addEventListener('play',stop,{signal});film.addEventListener('error',()=>{root.querySelector('.idea-film-status').textContent='Video chưa phát được. Bạn có thể xem đủ 9 cảnh ở phần tương tác phía trên.';},{signal});
 signal.addEventListener('abort',()=>{stop();film.pause();film.removeAttribute('src');film.querySelectorAll('source').forEach(s=>s.removeAttribute('src'));film.load();},{once:true});
 renderGallery();render();
}
