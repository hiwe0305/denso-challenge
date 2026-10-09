/* User-facing route and document regressions; no browser/network emulation claim. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const dir=path.join(__dirname,'dist');
const element={addEventListener(){},classList:{contains(){return false;}}};
const ctx=vm.createContext({URL,AbortController,console,matchMedia:()=>({addEventListener(){}}),document:{querySelector:()=>element,addEventListener(){}},window:{addEventListener(){}},location:{hash:'#overview'}});
for(const f of ['dossier.js','evidence.js','data-flywheel-data.js','training-blueprint-data.js','overview-flywheel-data.js','model-engine-core-data.js','pitch-pages-data.js','engineering.js','overview-flywheel.js','model-engine-core.js','learning-core.js','training-blueprint.js','data-flywheel.js','pitch-pages.js','current-platform-data.js','current-platform.js'])vm.runInContext(fs.readFileSync(path.join(dir,f),'utf8'),ctx,{filename:f});
vm.runInContext(fs.readFileSync(path.join(dir,'app.js'),'utf8').replace(/navigate\(\);\s*$/,''),ctx,{filename:'app.js'});
// Text cleanup uses real DOM in the app; route regression checks need only strings.
vm.runInContext('projectDisplayHTML=html=>projectDisplayText(html)',ctx);
const run=code=>vm.runInContext(code,ctx);
const rendered=run('Object.fromEntries(chapters.map(([id])=>[id,renderEngineeringPage(id)]))');
const h1s=[];
for(const [id,html] of Object.entries(rendered)){
 assert.equal((html.match(/<h1[> ]/g)||[]).length,1,id+' has one route heading');
 const heading=html.match(/<h1[^>]*>(.*?)<\/h1>/s)[1];h1s.push(heading);
 assert.ok(!html.includes('Cách làm và điều kiện kiểm chứng.'),id+' answers its own menu question');
 assert.ok(!html.includes('data-document="-1"'),id+' links only to catalogued documents');
}
assert.equal(new Set(h1s).size,13,'Distinct route questions');
for(const [id,html] of Object.entries(rendered))for(const match of html.matchAll(/(?:href|src)="([^"]+)"/g)){
 const url=match[1];if(url.startsWith('#')||/^https?:/.test(url))continue;
 assert.ok(fs.existsSync(path.join(dir,url.split(/[?#]/)[0])),id+' ships local asset '+url);
}

assert.match(rendered.overview,/DENSO Việt Nam/);
assert.match(rendered.product,/data-cp-step="5"/);
assert.match(rendered.sources,/v2d-overview.png/);assert.match(rendered.sources,/121.500/);
assert.match(rendered.learning,/psi0-architecture.png/);
assert.match(rendered.engine,/dreamdojo-overview.png/);assert.match(rendered.engine,/Joint state ground truth/);
assert.match(rendered.architecture,/data-cp-fault="unknown"/);
assert.match(rendered.validation,/G1WholebodyBendPickAndPlaceTeleop-v0/);
assert.match(rendered.validation,/data-cp-ab="b"/);
assert.match(rendered.business,/1\.136,60/);assert.match(rendered.business,/968,40/);
assert.match(rendered.business,/22\.840,80/);assert.match(rendered.business,/19\.090,00/);
assert.match(rendered.business,/runpod.io\/pricing/);
assert.match(rendered.roadmap,/Điều kiện đi tiếp/);assert.doesNotMatch(rendered.roadmap,/30 ngày|13\/10|11\/11|12 tuần/);
assert.match(rendered.team,/Dương Đình Hiếu/);assert.match(rendered.team,/Trần Ngọc Hưng/);
assert.match(rendered.team,/Trần Trịnh Hoàng Châu/);assert.match(rendered.team,/Nguyễn Thăng Long/);assert.match(rendered.team,/Dương Tiến Thông/);
assert.match(rendered.team,/Chờ bổ sung minh chứng/);
assert.equal(rendered.resources,undefined);assert.equal(run("Object.hasOwn(pages,'resources')"),false);
for(const [id,html] of Object.entries(rendered))if(!['sources','examples'].includes(id))assert.doesNotMatch(html,/FluxVLA|GR00T|GR1|FLARE|5\.187,20/,id+' uses approved recipe, not the archived one');

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
assert.match(rendered.engine,/Policy cần state/);
assert.match(rendered.engine,/Action điều kiện không phải action mới/);
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
assert.match(run("cpFault('binding')"),/Sửa hệ thống trước/);
assert.match(run("cpFault('unknown')"),/Thu thêm bằng chứng/);
const linked=run(`['../IDEA.md','../docs/implementation-plan/skill-a1/README.md','../examples/engineering-loop/README.md','../docs/implementation-plan/skill-a1/02-recipes-and-data.md'].map(url=>{const html=inlineMarkdown('[open]('+url+')',ENGINEERING_DIR+'README.md');const index=Number(html.match(/data-document="(\\d+)"/)[1]);return DOSSIER[index].path;})`);
assert.deepEqual(Array.from(linked),['IDEA.md','docs/implementation-plan/skill-a1/README.md','examples/engineering-loop/README.md','docs/implementation-plan/skill-a1/02-recipes-and-data.md']);
assert.equal(run("resolveDossierPath('../../IDEA.md','docs/01-product.md')"),'IDEA.md');
assert.equal(run("resolveDossierPath('javascript:alert(1)','IDEA.md')"),null);
assert.equal(run("currentPilotBudget().total"),5187.2);
console.log('Passed 13 approved routes, cost/ROI/negative scenarios, quality gating, evidence boundaries and document link security.');
