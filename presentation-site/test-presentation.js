/* User-facing route and document regressions; no browser/network emulation claim. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const dir=path.join(__dirname,'dist');
const element={addEventListener(){},classList:{contains(){return false;}}};
const ctx=vm.createContext({URL,AbortController,console,matchMedia:()=>({addEventListener(){}}),document:{querySelector:()=>element,addEventListener(){}},window:{addEventListener(){}},location:{hash:'#overview'}});
for(const f of ['dossier.js','evidence.js','data-flywheel-data.js','training-blueprint-data.js','overview-flywheel-data.js','model-engine-core-data.js','pitch-pages-data.js','engineering.js','overview-flywheel.js','model-engine-core.js','learning-core.js','training-blueprint.js','data-flywheel.js','pitch-pages.js'])vm.runInContext(fs.readFileSync(path.join(dir,f),'utf8'),ctx,{filename:f});
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
assert.match(rendered.business,/5\.187,20/);assert.match(rendered.business,/data-current-budget="pilot-sim"/);
assert.match(rendered.outcomes,/Policy A1 \+ skill bundle/);assert.match(rendered.outcomes,/Dataset release/);
assert.match(rendered.roadmap,/8–12 tuần/);assert.match(rendered.roadmap,/Nhánh tùy chọn/);
assert.match(rendered.validation,/43,6%/);assert.match(rendered.validation,/96\/100/);
assert.match(rendered.engine,/n1_5\/architecture\.svg/);assert.match(rendered.engine,/SELECTED NATIVE RUN/);
assert.match(rendered.architecture,/ACQUISITION DECISION RECEIPT/);
const linked=run(`['../IDEA.md','../docs/implementation-plan/skill-a1/README.md','../examples/engineering-loop/README.md','../docs/implementation-plan/skill-a1/02-recipes-and-data.md'].map(url=>{const html=inlineMarkdown('[open]('+url+')',ENGINEERING_DIR+'README.md');const index=Number(html.match(/data-document="(\\d+)"/)[1]);return DOSSIER[index].path;})`);
assert.deepEqual(Array.from(linked),['IDEA.md','docs/implementation-plan/skill-a1/README.md','examples/engineering-loop/README.md','docs/implementation-plan/skill-a1/02-recipes-and-data.md']);
assert.equal(run("resolveDossierPath('../../IDEA.md','docs/01-product.md')"),'IDEA.md');
assert.equal(run("resolveDossierPath('javascript:alert(1)','IDEA.md')"),null);
assert.equal(run("currentPilotBudget().total"),5187.2);
console.log('Passed 13 route summaries, current budget/deliverables/timeline, native/FOCA evidence boundaries and distinct full-path document targets.');
