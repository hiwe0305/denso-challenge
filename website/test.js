/* User-facing route and document regressions; no browser/network emulation claim. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const dir=path.join(__dirname,'dist');
const element={addEventListener(){},classList:{contains(){return false;}}};
const ctx=vm.createContext({URL,AbortController,console,matchMedia:()=>({addEventListener(){}}),document:{querySelector:()=>element,addEventListener(){}},window:{addEventListener(){}},location:{hash:'#overview'}});
for(const f of ['media.js','current-platform-data.js','current-platform.js'])vm.runInContext(fs.readFileSync(path.join(dir,f),'utf8'),ctx,{filename:f});
vm.runInContext(fs.readFileSync(path.join(dir,'app.js'),'utf8').replace(/navigate\(\);\s*$/,''),ctx,{filename:'app.js'});
const run=code=>vm.runInContext(code,ctx);
const runJSON=code=>JSON.parse(run('JSON.stringify('+code+')'));// plain values across the vm realm boundary
const rendered=run('Object.fromEntries(chapters.map(([id])=>[id,renderCurrentPlatform(id)]))');
const h1s=[];
for(const [id,html] of Object.entries(rendered)){
 assert.equal((html.match(/<h1[> ]/g)||[]).length,1,id+' has one route heading');
 const heading=html.match(/<h1[^>]*>(.*?)<\/h1>/s)[1];h1s.push(heading);
 assert.ok(!html.includes('Cách làm và điều kiện kiểm chứng.'),id+' answers its own menu question');
}
assert.equal(new Set(h1s).size,12,'Distinct route questions');
for(const [id,html] of Object.entries(rendered))for(const match of html.matchAll(/(?:href|src)="([^"]+)"/g)){
 const url=match[1];if(url.startsWith('#')||/^https?:/.test(url))continue;
 assert.ok(fs.existsSync(path.join(dir,url.split(/[?#]/)[0])),id+' ships local asset '+url);
}

// Story continuity: one five-part story bar, a bridge line and a unified pager on every page.
const order=runJSON('chapters.map(([id])=>id)');
assert.deepEqual(order,['overview','product','architecture','engine','sources','learning','validation','business','roadmap','outcomes','team','research'],'Presentation order');
assert.deepEqual(runJSON('CP_PARTS.flatMap(p=>p.routes)').sort(),order.slice().sort(),'Every route sits in exactly one menu part');
for(const [i,id] of order.entries()){
 const html=rendered[id],next=i===order.length-1?'architecture':order[i+1];
 assert.equal((html.match(/class="cp-story"/g)||[]).length,1,id+' has one story bar');
 assert.match(html,/class="cp-bridge"/,id+' has a bridge line');
 assert.match(html,/Trang này trả lời:/,id+' states its question');
 assert.match(html,new RegExp('class="cp-pager-next" href="#'+next+'"'),id+' pager leads to '+next);
 if(i>0)assert.match(html,new RegExp('class="cp-pager-back" href="#'+order[i-1]+'"'),id+' has a back link');
 const part=runJSON('cpPartOf('+JSON.stringify(id)+')');
 if(!part.reference)assert.match(html,new RegExp('<a href="#'+part.routes[0]+'" class="is-current"'),id+' highlights its part');
 if(['core','plug','evidence'].includes(part.id))assert.match(html,/Nguồn: spec v10\.1 mục/,id+' cites the spec');
}
assert.match(rendered.research,/Quay về lõi/);
assert.equal(run("renderCurrentPlatform('constructor')"),null);

assert.match(rendered.overview,/DENSO Việt Nam/);
assert.match(rendered.overview,/≥ 75%/);assert.match(rendered.overview,/≥ 70%/);
assert.match(rendered.overview,/loại lỗi hệ thống trước khi tiêu tiền vào dữ liệu/);
assert.match(rendered.overview,/Pitch v10 chưa cập nhật theo spec v10\.1/);
assert.doesNotMatch(rendered.overview.split('class="cp-metrics"')[1].split('</div></div>')[0],/80%|168/,'Main metric row uses BTC targets');
assert.match(rendered.product,/data-cp-step="7"/);assert.doesNotMatch(rendered.product,/data-cp-step="8"/);
assert.match(rendered.sources,/v2d-overview.png/);assert.match(rendered.sources,/121.500/);
assert.match(rendered.sources,/Tính là demo gốc\?/);
assert.match(rendered.learning,/psi0-architecture.png/);
assert.match(rendered.learning,/g1_sonic/);assert.match(rendered.learning,/AMO/);assert.match(rendered.learning,/T4 · Chuyển sang env MP/);
for(const word of ['Mulligan','DISEIL','Thu thêm teleop','Mục tiêu, chưa đo','THIẾU VÙNG PHỦ','LỖI ĐỒNG BỘ','Không tiêu ngân sách dữ liệu','Có tiêu ngân sách dữ liệu'])assert.ok(rendered.architecture.includes(word),'architecture shows '+word);
assert.equal((rendered.architecture.match(/class="cp-mark cp-goal"/g)||[]).length,5,'Our column is marked as target, not measured');
assert.match(rendered.engine,/data-cp-fault="unknown"/);assert.match(rendered.engine,/data-cp-fault="sync"/);assert.match(rendered.engine,/data-cp-fault="coverage"/);
assert.equal((rendered.engine.match(/<li value="/g)||[]).length,12,'Twelve algorithm steps');
assert.match(rendered.engine,/Minh họa logic, chưa phải kết quả chạy/);
assert.match(rendered.engine,/n_eff/);assert.match(rendered.engine,/đối chứng/);
assert.match(rendered.validation,/G1WholebodyBendPickAndPlaceTeleop-v0/);
for(const k of ['a','a07','b','bfail','c','bplus'])assert.match(rendered.validation,new RegExp('data-cp-ab="'+k+'"'));
for(const word of ['HS','HTa','HTb','HD','≥ 50%','≥ 75%','≥ 70%','150 điều kiện','bootstrap phân cấp','Power analysis','F-ACT','D*'])assert.ok(rendered.validation.includes(word),'validation shows '+word);
assert.match(rendered.business,/1\.136,60/);assert.match(rendered.business,/968,40/);
assert.match(rendered.business,/22\.840,80/);assert.match(rendered.business,/19\.090,00/);
assert.match(rendered.business,/runpod.io\/pricing/);
assert.match(rendered.business,/\+\$168,20/);assert.match(rendered.business,/−\$31,80/);assert.match(rendered.business,/\+\$68,20/);assert.match(rendered.business,/Hòa vốn/);
assert.match(rendered.business,/Máy tính kịch bản Pitch v10/);
assert.ok(rendered.business.indexOf('Số demo người để đạt ngưỡng')<rendered.business.indexOf('500 × r_demo'),'Value metrics lead the page');
assert.match(rendered.roadmap,/Điều kiện đi tiếp/);assert.doesNotMatch(rendered.roadmap,/30 ngày|13\/10|11\/11/);
for(const gate of ['G0','G1','G2','G3','G4','G5','G6','S1','S6','Q0','ngày 5 của Sprint 1'])assert.ok(rendered.roadmap.includes(gate),'roadmap shows '+gate);
assert.match(rendered.roadmap,/Scrum Master/);
assert.match(rendered.outcomes,/L0/);assert.match(rendered.outcomes,/L4/);assert.match(rendered.outcomes,/Adapter đổi/);
assert.match(rendered.team,/Dương Đình Hiếu/);assert.match(rendered.team,/Trần Ngọc Hưng/);
assert.match(rendered.team,/Trần Trịnh Hoàng Châu/);assert.match(rendered.team,/Nguyễn Thăng Long/);assert.match(rendered.team,/Dương Tiến Thông/);
assert.match(rendered.team,/Chờ bổ sung minh chứng/);
assert.match(rendered.team,/Đã có video và mã nguồn/);
assert.match(rendered.team,/DỰ ÁN TRƯỚC ĐÂY CỦA ĐỘI/);
assert.match(rendered.team,/VAI TRONG KẾ HOẠCH 12 TUẦN/);
assert.match(rendered.team,/FOCA trên SmolVLA/);
assert.match(rendered.team,/50.000/);
assert.match(rendered.team,/github.com\/hiwe0305\/humanoid-rl/);
assert.match(rendered.team,/14t8FROExp0IGz2PeSXfVRLxv7lpOCKN7/);
assert.match(rendered.team,/chưa đối chiếu log/);
assert.doesNotMatch(rendered.team,/Website chưa gắn link/);
assert.match(rendered.research,/dreamdojo-overview.png/);assert.match(rendered.research,/Joint state ground truth/);
assert.match(rendered.research,/Policy cần state/);assert.match(rendered.research,/Action điều kiện không phải action mới/);
for(const id of ['2610.05882','2609.08123','2405.01472','2506.19121','2310.17596','1011.0686','1810.02890','2505.09603'])assert.ok(rendered.research.includes(id),'research links arXiv '+id);
assert.match(rendered.research,/Pitch v10 chưa cập nhật theo spec v10\.1/);
assert.equal(rendered.resources,undefined);assert.equal(run("renderCurrentPlatform('resources')"),null);assert.equal(run("renderCurrentPlatform('examples')"),null);
for(const [id,html] of Object.entries(rendered))if(id!=='sources'&&id!=='research')assert.doesNotMatch(html,/FluxVLA|GR00T|GR1|FLARE|5\.187,20/,id+' uses approved recipe, not the archived one');
for(const html of Object.values(rendered))assert.doesNotMatch(html,/undefined|NaN|\[object Object\]/,'No template leaks');

assert.match(rendered.sources,/cp-dataset-gallery/);
assert.match(rendered.sources,/video_to_data\/v2d_corl_tutorial/);
assert.match(rendered.sources,/video_ingestion_agent/);
assert.match(rendered.sources,/FoundationPose/);
for(const id of ['human','g1','gr1','libero','mimicgen','dreamgen']){
 const html=run('cpDatasetBody('+JSON.stringify(id)+')');
 assert.ok(html.includes('data-media='),id+' includes an inspectable example');
 assert.match(rendered.sources,new RegExp('data-cp-dataset="'+id+'"'));
 for(const match of html.matchAll(/(?:href|src)="([^"]+)"/g)){const url=match[1];if(url.startsWith('#')||/^https?:/.test(url))continue;assert.ok(fs.existsSync(path.join(dir,url.split(/[?#]/)[0])),id+' ships '+url);}
}
assert.match(run("cpDatasetBody('gr1')"),/trong mô phỏng/);
assert.match(run("cpDatasetBody('dreamgen')"),/không phải DreamDojo/);
assert.throws(()=>run("cpDatasetBody('missing')"));

const close=(v,n)=>assert.ok(Math.abs(v-n)<1e-7,`${v} != ${n}`);
const budget=run('cpEvaluateCost()');close(budget.before,1136.6);close(budget.after,968.4);close(budget.net,168.2);close(budget.initial,3750.8);close(budget.opex,1380);close(budget.steady,22840.8);close(budget.firstYear,19090);
assert.equal(budget.threshold,128);assert.equal(budget.firstThreshold,150);
close(run('cpEvaluateCost({cycles:72}).steady'),10730.4);
close(run('cpEvaluateCost({cycles:72}).firstYear'),6979.6);
close(run('cpEvaluateCost({debugAfter:20}).net'),-31.8);
close(run('cpEvaluateCost({debugAfter:20,rootsAfter:200}).net'),-181.8);
assert.equal(run('cpEvaluateCost({debugAfter:20}).threshold'),null);
assert.match(run('cpCostResults(cpEvaluateCost(),false)'),/Chưa đủ điều kiện/);
assert.doesNotMatch(run('cpCostResults(cpEvaluateCost(),false)'),/22\.840,80/);
for(const expr of ['{yield:0}','{yield:1.1}','{operator:-1}','{cycles:1.5}','{engineer:NaN}','{rootsAfter:201}'])assert.throws(()=>run('cpEvaluateCost('+expr+')'));
close(run('cpEvaluateCost({cycles:0}).steady'),-1380);
// Failure → Data decision walk-through: system faults stop before the data budget; three diagnoses spend it.
assert.match(run("cpFault('sync')"),/LỖI ĐỒNG BỘ/);assert.match(run("cpFault('sync')"),/Không tiêu ngân sách dữ liệu/);
assert.match(run("cpFault('coverage')"),/THIẾU VÙNG PHỦ/);assert.match(run("cpFault('coverage')"),/Có tiêu ngân sách dữ liệu/);
assert.match(run("cpFault('unknown')"),/Thu thêm bằng chứng/);
assert.match(run("cpFault('binding')"),/LỖI CALIBRATION/);
assert.throws(()=>run("cpFault('missing')"));assert.throws(()=>run("cpFault('constructor')"));
for(const id of runJSON('Object.keys(CP_SCENARIOS)')){const html=run('cpFault('+JSON.stringify(id)+')');assert.equal((html.match(/cp-check is-hit/g)||[]).length,1,id+' stops at exactly one check');}
assert.deepEqual(runJSON("Object.values(CP_DIAG).filter(d=>d.budget).map(d=>d.name)"),['TRẠNG THÁI ĐẦU XẤU','THIẾU VÙNG PHỦ','KỸ NĂNG YẾU']);
assert.equal(run('Object.keys(CP_DIAG).length'),11);
close(run('cpNetFormula(0.3,0.5)'),168.2);close(run('cpNetFormula(0.3,0)'),-31.8);close(run('cpNetFormula(0.5,0)'),68.2);close(run('cpNetFormula(0.3,0.25)'),68.2);close(run('cpNetFormula(181.8/500,0)'),0);
assert.match(run("cpAB('bfail')"),/HTa/);assert.throws(()=>run("cpAB('missing')"));
console.log('Passed 12 routes in a five-part story, Failure → Data decisions, cost/ROI/negative scenarios, quality gating and evidence boundaries.');
