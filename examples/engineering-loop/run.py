"""Executable reference pipeline; NOT FluxVLA/GR00T, NOT human-data transfer.
MuJoCo mocap Cartesian effector + proximity-triggered weld attachment.
Idealized observation adapter and scripted stage sequencer are declared explicitly.
The action target predictor is actually fit from executed demonstrations.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, platform, time
from pathlib import Path
import mujoco
import numpy as np

HERE = Path(__file__).resolve().parent
STAGES = ['approach','grasp','lift','transfer','place','release','retreat']
PROFILE = 'reference_cartesian_xyz_grip_v1'
SCOPE = 'executed_reference_pipeline_not_native_vla'
class ContractError(ValueError): pass

def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p, obj):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+'\n')

def validate_record(r, expected_split='train'):
    if r.get('episode_success') is not True: raise ContractError('failed/unverified demo cannot be a positive BC target')
    if r.get('split') != expected_split: raise ContractError('split violation')
    if r.get('profile') != PROFILE: raise ContractError('action profile mismatch')
    if r.get('action_provenance') not in ['reference_seed_executed','sim_executed','reference_correction_executed']:
        raise ContractError('no compatible executed robot-action label; human/RGB not accepted')
    if r.get('rights') != 'project_authored_reference': raise ContractError('rights unknown')
    if not r.get('root_id') or not r.get('scenario_id'): raise ContractError('missing lineage')
    if str(r['scenario_id']).startswith('final-'): raise ContractError('final scenario leaked into training')
    x,a = np.asarray(r['features']),np.asarray(r['command'])
    if x.shape != (35,) or a.shape != (4,): raise ContractError('shape mismatch')
    if not np.isfinite(x).all() or not np.isfinite(a).all(): raise ContractError('nonfinite')
    if r.get('frame') != 'world_meters' or r.get('dt') != .05: raise ContractError('frame/time mismatch')
    if not isinstance(r['step'],int) or r['step']<0: raise ContractError('bad step')
    timestamp=r.get('timestamp')
    if isinstance(timestamp,bool) or not isinstance(timestamp,(int,float)) or not np.isfinite(timestamp):
        raise ContractError('missing/nonfinite timestamp')

def features(obs, stage):
    # Declared idealized sensing. No scorer stage/goal oracle hidden in a VLA input.
    # Task target is provided by the fixed instruction binding A1.
    # Reference sequencer supplies its OWN stage, distinct from independent scorer.
    one = np.eye(7)[stage]
    coords = np.r_[obs['object'][:2], obs['target'][:2]]
    return np.r_[one, np.outer(one,coords).ravel()]

def expert_target(obs, stage):
    obj,target = np.array(obs['object']),np.array(obs['target'])
    xy = obj[:2] if stage <= 2 else target[:2]
    z = [.12,.02,.17,.17,.02,.02,.16][stage]
    close = 1. if stage in [1,2,3,4] else 0.
    return np.r_[xy,z,close]

class World:
    def __init__(self, obj, target):
        self.model=mujoco.MjModel.from_xml_path(str(HERE/'world.xml'))
        self.data=mujoco.MjData(self.model)
        self.data.qpos[:3]=[*obj,.021]
        self.data.mocap_pos[0]=[-.25,-.15,.22]
        self.target=np.array([*target,.02]); self.closed=False
        mujoco.mj_forward(self.model,self.data)
        for _ in range(30):mujoco.mj_step(self.model,self.data)
    def observe(self):
        return {'ee':self.data.mocap_pos[0].copy().tolist(), 'object':self.data.qpos[:3].copy().tolist(),
                'target':self.target.copy().tolist(),'grip_closed':self.closed,
                'attached_sensor':bool(self.data.eq_active[0])}
    def step(self, command, fault=None):
        a=np.asarray(command,float)
        if a.shape!=(4,) or not np.isfinite(a).all(): raise ContractError('invalid runtime command')
        goal=np.clip(a[:3],[-.32,-.25,.019],[.32,.25,.30])
        # Diagnostic fault ONLY; never counted as source-data gain.
        if fault=='binding': goal[0]=np.clip(goal[0]+.08,-.32,.32)
        before=self.observe()
        delta=np.clip(goal-self.data.mocap_pos[0],-.035,.035)
        self.data.mocap_pos[0]+=delta
        self.closed=bool(a[3]>.5)
        if not self.closed:self.data.eq_active[0]=0
        elif not self.data.eq_active[0] and np.linalg.norm(self.data.mocap_pos[0]-self.data.qpos[:3])<.026:
            self.data.eq_active[0]=1
        for _ in range(10):mujoco.mj_step(self.model,self.data)
        return before,self.observe(),np.r_[goal,a[3]].tolist()

class Scorer:
    """Independent outcome scorer consumes measured simulator state, never policy logits."""
    def __init__(self): self.status={s:'not_attempted' for s in STAGES};self.stage=0;self.stable=0
    def update(self, o, closed_known=True):
        s=self.stage; self.status[STAGES[s]]='in_progress'  # only timeout resolves a known active attempt to fail
        ee,obj,target=np.array(o['ee']),np.array(o['object']),np.array(o['target'])
        held=o['attached_sensor']; pose_ok=np.linalg.norm(obj[:2]-target[:2])<.026
        passed=[np.linalg.norm(ee[:2]-obj[:2])<.026 and abs(ee[2]-.12)<.012,
                held, held and obj[2]>.145,
                held and pose_ok and obj[2]>.145,
                held and pose_ok and obj[2]<.04,
                (not held) and (not o['grip_closed']) and pose_ok and obj[2]<.035,
                (not held) and pose_ok and obj[2]<.035 and ee[2]>.145][s]
        if s==1 and not closed_known:
            self.status['grasp']='unknown';return False
        if s==6:self.stable=self.stable+1 if passed else 0;passed=self.stable>=12
        if passed:
            self.status[STAGES[s]]='pass'
            if s<6:self.stage+=1
            else:return True
        return False

class Policy:
    def __init__(self,W,recipe='ridge_behavior_cloning_reference'):
        self.W=np.asarray(W); self.recipe=recipe; self.stage=0;self.dwell=0
    def predict(self,o): return features(o,self.stage)@self.W
    def advance(self,o,a):
        # Reference scripted sequencer, explicitly not an end-to-end learned VLA.
        s=self.stage; near=np.linalg.norm(np.array(o['ee'])-a[:3])<.011
        if s in [1,2,3,4]:near=near and o['attached_sensor']
        if s==5:near=near and not o['attached_sensor'] and not o['grip_closed']
        self.dwell=self.dwell+1 if near else 0
        if self.dwell>=2 and s<6:self.stage+=1;self.dwell=0
    def save(self,p): write(p,{'profile':PROFILE,'recipe':self.recipe,'weights':self.W.tolist(),'scope':SCOPE})
    @classmethod
    def load(cls,p):
        o=json.loads(Path(p).read_text())
        if o['profile']!=PROFILE:raise ContractError('checkpoint binding mismatch')
        return cls(o['weights'],o['recipe'])

class Expert(Policy):
    def __init__(self):super().__init__(np.zeros((35,4)),'reference_expert_controller')
    def predict(self,o):return expert_target(o,self.stage)

def rollout(policy,scene,limit=150,fault=None,unknown=False):
    world=World(scene['object'],scene['target']);score=Scorer();trace=[];success=False
    for i in range(limit):
        obs=world.observe();x=features(obs,policy.stage);a=policy.predict(obs)
        before,after,sent=world.step(a,fault)
        success=score.update(after,not unknown)
        trace.append({'step':i,'t':round((i+1)*.05,4),'policy_stage':STAGES[policy.stage],
          'features':x.tolist(),'predicted_action':a.tolist(),'sent_command':sent,'before':before,
          'measured':after,'scorer_grasp_sensor_known':not unknown,'reference_stage_advance_halted':bool(unknown and policy.stage>=1),'score':dict(score.status),'success':success})
        # Declared reference uncertainty gate: do not advance beyond grasp when its verifier channel is missing.
        if not (unknown and policy.stage>=1):policy.advance(after,a)
        if success:break
    if not success and score.status[STAGES[score.stage]]!='unknown':
        score.status[STAGES[score.stage]]='fail'
    trace[-1]['score']=dict(score.status)
    return {'scenario':scene,'success':success,'steps':len(trace),'timeout':not success,
            'stages':score.status,'trace':trace,'policy_recipe':policy.recipe}

class SeedReplay(Policy):
    def __init__(self, seed, scene):
        super().__init__(np.zeros((35,4)), 'seed_object_frame_transform_and_replay')
        self.templates={t['policy_stage']:np.array(t['predicted_action']) for t in reversed(seed['trace'])}
        self.seed=seed['scenario']; self.scene=scene
    def predict(self,o):
        a=self.templates[STAGES[self.stage]].copy()
        key='object' if self.stage<=2 else 'target'
        a[:2]+=np.array(self.scene[key])-np.array(self.seed[key])
        return a

def records(ep,root,provenance):
    return [{'root_id':root,'ancestor_root':root.split('/variant-')[0],'scenario_id':ep['scenario']['id'],'split':'train','profile':PROFILE,
             'action_provenance':provenance,'rights':'project_authored_reference','frame':'world_meters','dt':.05,
             'step':t['step'],'timestamp':t['t'],'features':t['features'],'command':t['sent_command'],
             'episode_success':ep['success'],'measured_response':t['measured']}
             for t in ep['trace']]

def fit(rows,path):
    for r in rows:validate_record(r)
    by_root={}
    for r in rows:
        prior=by_root.setdefault(r['root_id'],[])
        if prior:
            previous=prior[-1]
            if r['step']<=previous['step'] or r['timestamp']<=previous['timestamp']:
                raise ContractError('nonmonotonic episode time')
            expected=(r['step']-previous['step'])*r['dt']
            if not np.isclose(r['timestamp']-previous['timestamp'],expected,rtol=1e-6,atol=1e-9):
                raise ContractError('timestamp spacing inconsistent with step/dt')
        prior.append(r)
    start=time.perf_counter();X=np.array([r['features'] for r in rows]);Y=np.array([r['command'] for r in rows])
    W=np.linalg.solve(X.T@X+1e-7*np.eye(X.shape[1]),X.T@Y)
    p=Policy(W);p.save(path)
    reloaded=Policy.load(path)
    assert np.allclose(X@W,X@reloaded.W,atol=1e-10)
    return p,{'objective':'MSE on absolute xyz/grip targets; NOT flow matching',
      'rows':len(rows),'recordings':len(by_root),'independent_roots':len({r['ancestor_root'] for r in rows}),'loss':float(np.mean((X@W-Y)**2)),
      'wall_seconds':time.perf_counter()-start,'checkpoint_sha256':digest(path),'reload_max_error':float(np.max(np.abs(X@W-X@reloaded.W))),
      'trainable':'35x4 linear action-target predictor','frozen':'idealized feature adapter; scripted sequencer',
      'vlm_status':'not_integrated','human_status':'not_integrated'}

def evaluate(path,scenes):return [rollout(Policy.load(path),s) for s in scenes]
def compact(ep):return {k:v for k,v in ep.items() if k!='trace'}
def compare(eps):return {'successes':sum(x['success'] for x in eps),'trials':len(eps),'stages':[x['stages'] for x in eps]}

def run(out):
    start=time.perf_counter();out=Path(out);out.mkdir(parents=True,exist_ok=True)
    if (out/'validation.json').exists():(out/'validation.json').unlink()
    rng=np.random.default_rng(17)
    seed_scene={'id':'train-seed-0','object':[-.10,-.02],'target':[.15,.04]}
    seed=rollout(Expert(),seed_scene);assert seed['success'],'expert physics path failed'
    roots=records(seed,'seed-root-0','reference_seed_executed')
    write(out/'seed-episode.json',seed);write(out/'robot-release.json',roots)
    _,r_receipt=fit(roots,out/'R.checkpoint.json')
    # Development example picked BEFORE final; corrections use only development scenarios.
    dev={'id':'dev-shift-0','object':[.08,.10],'target':[-.14,-.06]}
    before=rollout(Policy.load(out/'R.checkpoint.json'),dev)
    write(out/'before.json',before)
    # Seed-derived object-centric waypoint transformations, each actually executed in MuJoCo.
    synthetic=[];generated=[];rejects=[]
    for i in range(24):
        scene={'id':f'train-sim-{i}','object':rng.uniform([-.18,-.13],[.16,.13]).tolist(),
               'target':rng.uniform([-.18,-.13],[.18,.13]).tolist()}
        ep=rollout(SeedReplay(seed,scene),scene);generated.append(ep)
        if ep['success']:synthetic+=records(ep,'seed-root-0/variant-'+str(i),'sim_executed')
        else:rejects.append(compact(ep))
    assert synthetic,'no accepted generated trajectories'
    write(out/'synthetic-release.json',synthetic)
    write(out/'generated-trajectories.json',generated)
    write(out/'generation-log.json',{'generator':'seed object/target frame waypoint transform and execute','attempts':[compact(ep) for ep in generated]})
    _,s_receipt=fit(roots+synthetic,out/'S.checkpoint.json')
    after_s=rollout(Policy.load(out/'S.checkpoint.json'),dev);write(out/'after-synthetic.json',after_s)
    # Expert reset/full context near failure, not original failed actions treated as positives.
    correction=rollout(Expert(),dev);assert correction['success']
    corr=records(correction,'correction-dev-0','reference_correction_executed')
    write(out/'correction-release.json',corr)
    _,c_receipt=fit(roots+corr,out/'C.checkpoint.json')
    after=rollout(Policy.load(out/'C.checkpoint.json'),dev);write(out/'after-correction.json',after)
    # Independent final is constructed/evaluated AFTER recipes/checkpoints freeze. Never used for retraining.
    frng=np.random.default_rng(911)
    final=[{'id':f'final-{i}','object':frng.uniform([-.19,-.12],[.17,.12]).tolist(),
       'target':frng.uniform([-.17,-.12],[.17,.12]).tolist()} for i in range(12)]
    final_results={k:evaluate(out/(k+'.checkpoint.json'),final) for k in ['R','S','C']}
    regression={'id':'regression-seed-disjoint','object':[-.101,-.021],'target':[.151,.041]}
    reg={k:rollout(Policy.load(out/(k+'.checkpoint.json')),regression) for k in ['R','S','C']}
    # Explicit negative scenarios: binding fault, unknown sensing, no learned skill.
    binding=rollout(Policy.load(out/'S.checkpoint.json'),dev,fault='binding');write(out/'binding-fault.json',binding)
    missing=rollout(Policy.load(out/'S.checkpoint.json'),dev,unknown=True);write(out/'unknown.json',missing)
    zero=rollout(Policy(np.zeros((35,4))),dev);write(out/'zero-skill.json',zero)
    write(out/'final-results.json',{k:[compact(ep) for ep in es] for k,es in final_results.items()})
    write(out/'training-receipts.json',{'R':r_receipt,'S':s_receipt,'C':c_receipt})
    # CPU capability audit: not evidence that a native VLA couldn't run elsewhere.
    caps={'python':platform.python_version(),'numpy':np.__version__,'mujoco':mujoco.__version__,
          'fluxvla_importable':importlib.util.find_spec('fluxvla') is not None,
          'native_checkpoint_present':any((HERE.parents[1]/'checkpoints').glob('**/*.safetensors')),'native_vla':'not_tested','native_gr1':'not_tested',
          'human_motion_bridge':'not_integrated','native_action_expert_traces':'not_tested'}
    facts={'observed':'reference R fails on shifted development task' if not before['success'] else 'reference R reaches development task',
      'binding_profile':PROFILE,'representation':'idealized measured scene coordinates; no semantic VLM claim',
      'hypothesis':'coverage gap in training; R fit from one scenario is underdetermined',
      'alternatives':['controller/binding fault','reference sequencer issue'],
      'test':'two alternatives from R: S adds executed variants; C adds expert correction with R replay; separate binding-fault rollout',
      'decision':'engineer-reviewed example plan: compare S and correction; never auto causal diagnosis',
      'source_refs':['before.json','after-synthetic.json','after-correction.json','binding-fault.json']}
    report={'schema':'engineering_reference_v3.1','scope':SCOPE,'measured_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
      'seed':17,'simulator':'MuJoCo; mocap Cartesian effector with proximity weld, not contact-accurate gripper',
      'observation_adapter':'idealized simulator-state features, NOT image VLM','sequencer':'scripted; independent from outcome scorer',
      'task':'reference pick/place part into A1; stable 0.6s; reference action 4D, NOT GR1 29D',
      'human':'not_integrated; real human data cannot enter robot BC without a validated bridge',
      'generation':{'attempts':len(generated),'accepted':len(generated)-len(rejects),'rejected':len(rejects),
                    'independent_robot_seed_roots':1,'variants_are_descendants':True},
      'development':{'R':compact(before),'S':compact(after_s),'C':compact(after)},
      'final':{k:compare(v) for k,v in final_results.items()},'regression':{k:compact(v) for k,v in reg.items()},
      'negative_cases':{'binding_fault':compact(binding),'unknown_verifier_sensor':compact(missing),'zero_skill':compact(zero)},
      'training':{'R':r_receipt,'S':s_receipt,'C':c_receipt},'capabilities':caps,'evidence_card':facts,
      'promotion':{'reference_S':after_s['success'] and reg['S']['success'] and all(e['success'] for e in final_results['S']),
                   'reference_C':after['success'] and reg['C']['success'] and all(e['success'] for e in final_results['C']),
                   'native_vla':False,'real_robot':False,'cost_saving':'not_established'},
      'usage':{'wall_seconds':time.perf_counter()-start,'cash_cost':'unknown','human_hours':'not_measured',
              'valid_cost_savings_claim':False}}
    write(out/'report.json',report)
    artifacts=[p for p in out.glob('*.json') if p.name!='manifest.json']
    write(out/'manifest.json',{'scope':SCOPE,'source_sha256':digest(HERE/'run.py'),
      'world_sha256':digest(HERE/'world.xml'),'artifacts':[{'file':p.name,'sha256':digest(p)} for p in sorted(artifacts)]})
    print(json.dumps({'scope':SCOPE,'generation':report['generation'],'final':{k:[v['successes'],v['trials']] for k,v in report['final'].items()},'promotion':report['promotion']},ensure_ascii=False))
    return report

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=HERE/'results');args=ap.parse_args();run(args.out)
