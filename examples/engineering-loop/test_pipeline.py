from copy import deepcopy
from pathlib import Path
import json
import numpy as np
import pytest
from run import ContractError, Policy, Scorer, World, validate_record, fit, PROFILE

RESULTS=Path(__file__).parent/'results'
@pytest.fixture
def row(): return json.loads((RESULTS/'robot-release.json').read_text())[0]

@pytest.mark.parametrize('key,value',[('split','final'),('profile','GR1_29D'),('frame','camera_mm'),('dt',.1),('rights','unknown'),('action_provenance','human_motion'),('scenario_id','final-0'),('step',-1)])
def test_training_rejects_incompatible_or_leaked_data(row,key,value):
    row[key]=value
    with pytest.raises(ContractError): validate_record(row)

def test_missing_action_is_not_zero_label(row):
    row['command']=[float('nan')]*4
    with pytest.raises(ContractError):validate_record(row)

def test_nonmonotonic_clock_prevents_training(row,tmp_path):
    with pytest.raises(ContractError,match='nonmonotonic'):fit([row,deepcopy(row)],tmp_path/'bad.json')

@pytest.mark.parametrize('timestamp',[None,float('nan'),float('inf'),True])
def test_timestamp_must_be_present_and_finite(row,timestamp):
    row['timestamp']=timestamp
    with pytest.raises(ContractError,match='timestamp'):validate_record(row)

@pytest.mark.parametrize('offset',[0,-.05,.1])
def test_increasing_steps_do_not_hide_invalid_clock(row,tmp_path,offset):
    following=deepcopy(row);following['step']+=1;following['timestamp']+=offset
    with pytest.raises(ContractError,match='time'):
        fit([row,following],tmp_path/'bad-clock.json')

def test_valid_relative_clock_with_nonzero_origin(row,tmp_path):
    row['timestamp']=1234.5
    following=deepcopy(row);following['step']+=1;following['timestamp']+=row['dt']
    _,receipt=fit([row,following],tmp_path/'valid-clock.json')
    assert receipt['rows']==2 and receipt['reload_max_error']<1e-10

def test_wrong_checkpoint_binding_not_deployed(tmp_path):
    p=tmp_path/'bad.json';p.write_text(json.dumps({'profile':'GR1','weights':np.zeros((35,4)).tolist()}))
    with pytest.raises(ContractError):Policy.load(p)

def test_reload_preserves_inference():
    r=json.loads((RESULTS/'training-receipts.json').read_text())
    assert all(v['reload_max_error']<1e-10 for v in r.values())
    p=Policy.load(RESULTS/'S.checkpoint.json');o=World([.03,-.02],[-.1,.05]).observe()
    assert p.predict(o).shape==(4,) and np.isfinite(p.predict(o)).all()

def test_unknown_is_not_pass_or_failure_attribution():
    ep=json.loads((RESULTS/'unknown.json').read_text())
    assert not ep['success'] and ep['stages']['grasp']=='unknown'
    assert ep['stages']['lift']=='not_attempted'
    assert all(t['policy_stage'] not in ['lift','transfer','place','release','retreat'] for t in ep['trace'])

def test_binding_fault_has_observable_command_difference():
    ep=json.loads((RESULTS/'binding-fault.json').read_text())
    assert not ep['success']
    assert any(abs(t['predicted_action'][0]-t['sent_command'][0])>.05 for t in ep['trace'])

def test_zero_success_does_not_fail_unreached_stages():
    ep=json.loads((RESULTS/'zero-skill.json').read_text())
    assert ep['stages']['approach']=='fail'
    assert all(v=='not_attempted' for k,v in ep['stages'].items() if k!='approach')

def test_release_action_alone_not_enough_for_task_success():
    s=Scorer();s.stage=6
    bad={'ee':[0,0,.2],'object':[.1,.1,.02],'target':[-.1,-.1,.02],'attached_sensor':False,'grip_closed':False}
    for _ in range(20):assert not s.update(bad)

def test_local_correction_gain_does_not_promote_failed_final():
    r=json.loads((RESULTS/'report.json').read_text())
    assert r['development']['C']['success']
    assert r['final']['C']['successes']<r['final']['C']['trials']
    assert not r['promotion']['reference_C']
    assert not r['promotion']['native_vla'] and not r['promotion']['real_robot']
    assert not r['usage']['valid_cost_savings_claim']

def test_synthetic_descendants_do_not_inflate_independent_roots():
    r=json.loads((RESULTS/'report.json').read_text())
    assert r['generation']['accepted']==24
    assert r['training']['S']['independent_roots']==1
    assert r['training']['C']['independent_roots']==2

def test_final_never_used_as_training_or_correction():
    for name in ['robot-release','synthetic-release','correction-release']:
        rows=json.loads((RESULTS/(name+'.json')).read_text())
        assert all(not x['scenario_id'].startswith('final-') for x in rows)
        assert all(x['split']=='train' for x in rows)

def test_actual_simulation_success_and_regression():
    r=json.loads((RESULTS/'report.json').read_text())
    assert r['final']['S']['successes']==r['final']['S']['trials']==12
    assert r['regression']['S']['success'] and r['regression']['R']['success']
    ep=json.loads((RESULTS/'after-synthetic.json').read_text())
    states=np.array([t['measured']['object'] for t in ep['trace']])
    assert states[:,2].max()>.14  # physical object lifted, no success label only
    assert np.linalg.norm(states[-1,:2]-np.array(ep['scenario']['target']))<.026

def test_invalid_runtime_command_stops_before_execution():
    w=World([-.1,0],[.1,0]);before=w.observe()
    with pytest.raises(ContractError):w.step([float('nan'),0,0,0])
    assert before==w.observe()

def test_active_attempt_is_not_a_terminal_failure():
    s=Scorer()
    o=World([-.1,0],[.1,0]).observe()
    assert not s.update(o)
    assert s.status['approach']=='in_progress'

def test_failed_executions_are_not_positive_imitation_targets(row):
    row['episode_success']=False
    with pytest.raises(ContractError,match='positive BC'):validate_record(row)

def test_generated_release_matches_executed_command_and_measured_motion():
    eps=json.loads((RESULTS/'generated-trajectories.json').read_text())
    rows=json.loads((RESULTS/'synthetic-release.json').read_text())
    lookup={e['scenario']['id']:e for e in eps}
    for r in rows:
        ep=lookup[r['scenario_id']]
        assert ep['success']
        t=ep['trace'][r['step']]
        assert np.allclose(r['command'],t['sent_command'])
        assert r['measured_response']==t['measured']
