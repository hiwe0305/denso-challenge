/* Budget scopes share canonical rates, without inventing quality or measured costs. */
function calculateStudyBudget(plan,rates){
 const keys=['engineerHours','trainRuns','bridgeRuns','generationBatches','evaluationJobs','storageMonths'];
 if(keys.some(k=>!Number.isFinite(plan[k])||plan[k]<0)||['trainRuns','bridgeRuns','generationBatches','evaluationJobs'].some(k=>!Number.isInteger(plan[k]))||plan.bridgeRuns>plan.trainRuns)throw Error('Giờ/tháng phải không âm; số jobs phải nguyên; bridge jobs không vượt train jobs.');
 const loaded=calculateIndustrialCost(rates);
 const lines=[
  {label:'Engineering toàn study (gồm QA/selection/analysis)',amount:plan.engineerHours*loaded.eng},
  {label:'Target training + retry reserve',amount:plan.trainRuns*rates.baseTrain*(1+rates.retry/100)*rates.trainRate},
  {label:'Auxiliary bridge + retry reserve',amount:plan.bridgeRuns*rates.bridgeHours*(1+rates.retry/100)*rates.trainRate},
  {label:'Generation batches, gồm reject',amount:plan.generationBatches*rates.genHours*rates.genRate},
  {label:'Evaluation jobs',amount:plan.evaluationJobs*rates.evalHours*rates.evalRate},
  {label:'Storage study',amount:plan.storageMonths*rates.candidateGb*rates.storageRate}
 ];
 return {lines,subtotal:lines.reduce((s,l)=>s+l.amount,0),scope:'R&D-sim-partial',status:'planning_not_measured'};
}
function calculateAcquisitionLedger(entry,rates,cap){
 const keys=['engineerHours','operatorHours','gpuHours','otherCost'];
 if(!Number.isFinite(cap)||cap<0)throw Error('Cap phải là số không âm.');
 if(keys.some(k=>entry[k]!==null&&(!Number.isFinite(entry[k])||entry[k]<0)))throw Error('Chi phí/giờ phải không âm; để trống khi chưa biết.');
 const unknown=keys.filter(k=>entry[k]===null),loaded=calculateIndustrialCost(rates);
 const ratesByKey={engineerHours:loaded.eng,operatorHours:loaded.op,gpuHours:rates.trainRate,otherCost:1};
 const knownSubtotal=keys.reduce((s,k)=>s+(entry[k]===null?0:entry[k]*ratesByKey[k]),0);
 return {knownSubtotal,total:unknown.length?null:knownSubtotal,unknown,status:unknown.length?'incomplete':entry.measured?'measured':'estimated',capExceeded:knownSubtotal>cap,scope:'acquisition_only',quality:'not_evaluated'};
}
function pilotBudgetWorkbench(){
 const fields=[['engineerHours','Giờ kỹ sư toàn study'],['trainRuns','Target train jobs'],['bridgeRuns','Bridge jobs'],['generationBatches','Generation batches'],['evaluationJobs','Eval jobs'],['storageMonths','Tháng storage']];
 return `<section class="panel"><span class="tag">1 · R&D mô phỏng · planning subtotal</span><h2>Ngân sách PoC 12 tuần</h2><p>E0/D0 và useful R0 trước E4; core conditional 6 baseline +9 T/F/A =15 training runs. Diagnostic probes/verifier và bootstrap thêm jobs phải replan; extension có gate tối đa12. Jobs/giờ bên dưới là giả định; số bridge có thể giảm khi branch không cần. Đơn giá dùng chung với bảng skill bên dưới.</p><div class="cost-inputs">${fields.map(([k,label])=>`<label for="study-${k}">${label}<input id="study-${k}" data-study="${k}" type="number" min="0" step="${k.endsWith('Hours')||k==='storageMonths'?'any':'1'}" value="${PILOT_BUDGET.study[k]}"></label>`).join('')}</div><p id="study-error" role="alert"></p><div id="study-result" aria-live="polite"></div><p class="source-note">${esc(PILOT_BUDGET.studyNotes.engineerHours)} ${esc(PILOT_BUDGET.studyNotes.stageHours)}</p><p>${esc(PILOT_BUDGET.studyNotes.scope)}</p></section><section class="panel spaced"><span class="tag">2 · Acquisition ledger · chưa có receipts</span><h2>Tính gói T / F / A trước khi chọn</h2><p>Tính cả engineer selection/QA/planning, operator/reset, allocated A100 GPU-giờ. Robot-use, generation GPU khác đơn giá, quyền dữ liệu và các khoản khác nhập ở “Chi phí khác”. Để trống nếu chưa biết; số 0 chỉ nhập khi khoản đó đã được xác nhận không phát sinh. Training/eval và tích hợp sau acquisition ghi riêng ở total incremental ledger.</p><label for="acquisition-cap">Cost cap acquisition / arm (USD)<input id="acquisition-cap" type="number" min="0" step="any" value="${PILOT_BUDGET.acquisitionCap}"></label><p class="small">${esc(PILOT_BUDGET.capNote)}</p><div class="cards">${PILOT_BUDGET.arms.map(a=>`<section class="panel"><h3>${a.id} · ${esc(a.name)}</h3><p>${esc(a.description)}</p>${[['engineerHours','Giờ kỹ sư, gồm selection/QA'],['operatorHours','Giờ operator, gồm reset'],['gpuHours','A100 GPU-giờ acquisition'],['otherCost','Chi phí khác (USD)']].map(([k,label])=>`<label for="ledger-${a.id}-${k}">${label}<input id="ledger-${a.id}-${k}" data-ledger="${a.id}" data-field="${k}" type="number" min="0" step="any" placeholder="Chưa biết"></label>`).join('')}<label><input id="ledger-${a.id}-measured" data-measured="${a.id}" type="checkbox"> Các khoản đã đo đủ và có receipts</label></section>`).join('')}</div><p id="ledger-error" role="alert"></p><div id="ledger-result" aria-live="polite"></div><p class="source-note">Cap đủ chưa chứng minh cùng quality. Không chọn “thắng” từ chi phí hoặc số demo; evaluator và total incremental ledger còn phải xác nhận quality/uncertainty và train/eval/analysis costs.</p></section>`;
}
function initPilotBudgets(signal){
 const money=x=>x.toLocaleString('vi-VN',{style:'currency',currency:'USD',maximumFractionDigits:2});
 function rates(){if([...main.querySelectorAll('[data-cost]')].some(i=>!i.checkValidity()))throw Error('Sửa đầu vào đơn giá/phạm vi skill trước khi tính ledger.');return Object.fromEntries([...main.querySelectorAll('[data-cost]')].map(i=>[i.dataset.cost,Number(i.value)]));}
 function update(){
  try{
   const rateInputs=[...main.querySelectorAll('[data-cost]')];if(rateInputs.some(i=>!i.checkValidity()))throw Error('Sửa đầu vào đơn giá/phạm vi skill bên dưới trước khi tính study.');
   const p=Object.fromEntries([...main.querySelectorAll('[data-study]')].map(i=>[i.dataset.study,i.value.trim()===''?NaN:Number(i.value)])),c=calculateStudyBudget(p,rates());
   main.querySelector('#study-error').textContent='';main.querySelector('#study-result').innerHTML=table(['R&D scope','USD theo giả định'],c.lines.map(l=>[l.label,money(l.amount)]).concat([['Subtotal chưa gồm acquisition chưa quote',`<strong>${money(c.subtotal)}</strong>`]]));
  }catch(e){main.querySelector('#study-error').textContent=e.message;main.querySelector('#study-result').textContent='Chưa có subtotal hợp lệ.';}
  try{
   const capValue=main.querySelector('#acquisition-cap').value;const cap=capValue.trim()===''?NaN:Number(capValue);
   const rows=PILOT_BUDGET.arms.map(a=>{const e={measured:main.querySelector(`[data-measured="${a.id}"]`).checked};main.querySelectorAll(`[data-ledger="${a.id}"]`).forEach(i=>e[i.dataset.field]=i.value.trim()===''?null:Number(i.value));const c=calculateAcquisitionLedger(e,rates(),cap);return [a.id+' · '+esc(a.name),money(c.knownSubtotal)+'<br>Subtotal đã nhập',c.total===null?'Chưa đủ cost':money(c.total),c.status==='incomplete'?'Còn '+c.unknown.length+' khoản chưa biết':c.status==='measured'?'Đã đo theo receipts người nhập xác nhận':'Dự toán',c.capExceeded?'Vượt cap':c.total===null?'Chưa kết luận cap':'Trong cap'];});
   main.querySelector('#ledger-error').textContent='';main.querySelector('#ledger-result').innerHTML=table(['Arm','Phần đã nhập','Tổng acquisition','Trạng thái','Cap'],rows);
  }catch(e){main.querySelector('#ledger-error').textContent=e.message;main.querySelector('#ledger-result').textContent='Chưa có ledger hợp lệ.';}
 }
 [...main.querySelectorAll('[data-study],[data-ledger],[data-measured],#acquisition-cap,[data-cost]')].forEach(i=>i.addEventListener('input',update,{signal}));
 main.querySelector('#cost-scenario').addEventListener('change',update,{signal});main.querySelector('#cost-reset').addEventListener('click',update,{signal});update();
}
function pilotBudgetSnapshot(rates){
 const number=i=>i.value.trim()===''?null:Number(i.value),studyInputs=Object.fromEntries([...main.querySelectorAll('[data-study]')].map(i=>[i.dataset.study,number(i)]));
 let study;try{study={inputs:studyInputs,result:calculateStudyBudget(studyInputs,rates),notes:PILOT_BUDGET.studyNotes};}catch(e){study={inputs:studyInputs,result:null,status:'invalid',error:e.message};}
 const cap=number(main.querySelector('#acquisition-cap'));
 const arms=PILOT_BUDGET.arms.map(a=>{const entry={measured:main.querySelector(`[data-measured="${a.id}"]`).checked};main.querySelectorAll(`[data-ledger="${a.id}"]`).forEach(i=>entry[i.dataset.field]=number(i));try{return {id:a.id,inputs:entry,result:calculateAcquisitionLedger(entry,rates,cap)};}catch(e){return {id:a.id,inputs:entry,result:null,status:'invalid',error:e.message};}});
 return {revision:PILOT_BUDGET.revision,study,acquisition:{cap,arms,quality:PILOT_BUDGET.qualityBoundary},allocation:'Separate scopes; engineering activity already within study hours is not added again from acquisition. Total incremental training/evaluation/analysis is separate, not measured here.'};
}
