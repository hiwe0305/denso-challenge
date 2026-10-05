/* Deterministic engineering cost model. Quantities are editable planning assumptions. */
function costDefaults(model){return Object.fromEntries(model.inputs.map(x=>[x.key,x.value]));}
function calculateIndustrialCost(x){
 const positive=['yield','robotYears','robotHoursMonth','reuseSkills','baseDemos','trials'];
 if(Object.values(x).some(v=>!Number.isFinite(v)||v<0)||positive.some(k=>!(x[k]>0))||x.yield>100||x.benefits>=100)throw Error('Đầu vào cần là số hợp lệ; yield 1–100%, benefits dưới 100%, lifetime/capacity/skills dương.');
 const op=x.operatorWage/(1-x.benefits/100),eng=x.engineerWage/(1-x.benefits/100);
 const capitalHour=x.robotCapex/(x.robotYears*12*x.robotHoursMonth);
 const robotHour=capitalHour+x.maintenanceMonth/x.robotHoursMonth+x.powerKw*x.electricRate;
 const trialHours=x.trials*x.trialMin/60;
 const a=x.baseDemos/(x.yield/100),b=x.candidateDemos/(x.yield/100);
 const capture=attempts=>attempts*(x.recordMin+x.resetMin)/60;
 const ca=capture(a),cb=capture(b);
 const humanHours=x.humanClips*x.humanRecordMin/60;
 const curatingHours=(x.humanClips*x.humanQaMin+x.internetClips*x.internetQaMin)/60;
 const line=(label,quantityA,quantityB,unit,rate,kind='recurring')=>({label,quantityA,quantityB,unit,rate,baseline:quantityA*rate,candidate:quantityB*rate,kind});
 const lines=[
 line('Thu robot: ghi + setup/reset, gồm failed attempts',ca,cb,'giờ vận hành',op),
 line('QA robot, gồm mọi attempt bị reject',a*x.qaMin/60,b*x.qaMin/60,'giờ kỹ sư',eng),
 line('Sử dụng robot trong collection',ca,cb,'robot-giờ',robotHour),
 line('Task/scorer/calibration',x.taskHours,x.taskHours,'giờ kỹ sư',eng),
 line('Debug/correction review',x.debugHours,x.debugHours+x.extraDebug,'giờ kỹ sư',eng),
 line('Thu human clips',0,humanHours,'giờ vận hành',op),
 line('Human tracking/stage + internet rights/relevance QA',0,curatingHours,'giờ kỹ sư',eng),
 line('Phí quyền dữ liệu',0,x.licenseCost,'USD',1),
 line('Generation, gồm sinh lại và reject',0,x.genHours,'GPU-giờ H100',x.genRate),
 line('QA synthetic',0,x.syntheticQaHours,'giờ kỹ sư',eng),
 line('Target post-train, gồm retry reserve',x.baseTrain*(1+x.retry/100),x.candidateTrain*(1+x.retry/100),'GPU-giờ A100',x.trainRate),
 line('Bridge, gồm retry reserve',0,x.bridgeHours*(1+x.retry/100),'GPU-giờ A100',x.trainRate),
 line('GPU preprocessing bổ sung',0,x.preprocessHours,'GPU-giờ A100',x.trainRate),
 line('Sim / development evaluation',x.evalHours,x.evalHours,'GPU-giờ RTX4090',x.evalRate),
 line('Real acceptance trials: execute/reset',trialHours,trialHours,'giờ vận hành',op),
 line('Review acceptance trials',x.trials*x.scoreMin/60,x.trials*x.scoreMin/60,'giờ kỹ sư',eng),
 line('Robot trong acceptance trials',trialHours,trialHours,'robot-giờ',robotHour),
 line('Storage trong pilot',x.baseGb*x.months,x.candidateGb*x.months,'GB-tháng',x.storageRate),
 line('Chi phí còn thiếu / augmentation đối chứng',x.baseOther,x.candidateOther,'USD',1),
 line('Tích hợp nền chung, một lần',x.sharedIntegration,x.sharedIntegration,'giờ kỹ sư',eng,'oneoff'),
 line('Source adapters / heads / QA mới, một lần',0,x.extraIntegration,'giờ kỹ sư',eng,'oneoff')];
 const sum=(key,kind)=>lines.filter(l=>l.kind===kind).reduce((s,l)=>s+l[key],0);
 const baselineRecurring=sum('baseline','recurring'),candidateRecurring=sum('candidate','recurring');
 const baselineOneoff=sum('baseline','oneoff'),candidateOneoff=sum('candidate','oneoff');
 const baseline=baselineRecurring+baselineOneoff/x.reuseSkills,candidate=candidateRecurring+candidateOneoff/x.reuseSkills;
 const marginalSaving=baselineRecurring-candidateRecurring,extraOneoff=candidateOneoff-baselineOneoff;
 const breakEvenSkills=marginalSaving>0?Math.max(1,Math.ceil(extraOneoff/marginalSaving)):null;
 const perRobotDemo=((x.recordMin+x.resetMin)/60*(op+robotHour)+x.qaMin/60*eng)/(x.yield/100);
 const extraRecurring=candidateRecurring-baselineRecurring+(x.baseDemos-x.candidateDemos)*perRobotDemo;
 const neededDemoReduction=perRobotDemo>0?(extraRecurring+extraOneoff/x.reuseSkills)/perRobotDemo:null;
 const ops=[['GPU dedicated, tính cả idle',x.inferGpuCount*x.inferHours*x.evalRate],['Monitoring / model maintenance',x.monitorHours*eng],['Robot capital phân bổ tháng',x.robotCapex/(x.robotYears*12)],['Cell maintenance cố định',x.maintenanceMonth],['Cell electricity khi hoạt động',x.deploymentHours*x.powerKw*x.electricRate],['Storage + backup',x.opsStorage*x.storageRate],['OPEX chưa mô hình hóa',x.opsOther]];
 const monthly=ops.reduce((s,l)=>s+l[1],0);
 const baselineDevCapital=(ca+trialHours)*capitalHour*x.reuseSkills,candidateDevCapital=(cb+trialHours)*capitalHour*x.reuseSkills;
 const annualOpsCash=12*(monthly-x.robotCapex/(x.robotYears*12));
 return {lines,op,eng,robotHour,capitalHour,attemptsA:a,attemptsB:b,baselineRecurring,candidateRecurring,baselineOneoff,candidateOneoff,baseline,candidate,saving:baseline-candidate,marginalSaving,breakEvenSkills,perRobotDemo,neededDemoReduction,ops,monthly,
 baselineYearCash:x.robotCapex+baselineOneoff+baselineRecurring*x.reuseSkills-baselineDevCapital+annualOpsCash,
 candidateYearCash:x.robotCapex+candidateOneoff+candidateRecurring*x.reuseSkills-candidateDevCapital+annualOpsCash};
}
