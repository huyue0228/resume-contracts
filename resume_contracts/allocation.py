"""Canonical allocation snapshots and synthetic mock results, without external I/O."""
import hashlib
import json
from copy import deepcopy
from .models import AllocationRequest, AllocationResponse, AllocationCapabilities, allocation_tags_hash
from datetime import datetime

TOOLS = ['allocation.'+name for name in ('read_snapshot','filter_eligible','rank_demands','simulate_plan','validate_plan','submit_plan')]

def canonical_snapshot(value):
    value = deepcopy(value)
    value['members'].sort(key=lambda m:m['member_id'])
    value['demands'].sort(key=lambda d:d['demand_id'])
    for member in value['members']:
        member['tags'].sort(key=lambda t:t['code'])
        member['allowed_demand_ids'].sort()
        member['counted_demand_ids'].sort()
    for demand in value['demands']:
        demand['required_tags'].sort(); demand['preferred_tags'].sort()
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()

def snapshot_hash(value): return hashlib.sha256(canonical_snapshot(value)).hexdigest()

def allocation_capabilities(**overrides):
    data=dict(task_kinds=['pool.candidate_allocation'],execution_modes=['deterministic'],kernel_build='dev',toolset_version='allocation-tools/v1',tool_names=TOOLS)
    data.update(overrides)
    return AllocationCapabilities.model_validate(data)

def allocation_request():
    snapshot=dict(snapshot_id='snapshot-1',snapshot_at='2026-09-14T00:00:00Z',scope_ref='scope-1',entity_ref='entity-1',pool_ref='pool-1',scope_revision=1,policy_revision=1,epoch=1,next_sequence=1,window_seconds=604800,
        members=[dict(member_id=1,candidate_ref='candidate-1',application_ref='application-1',qualification_ref='qualification-1',qualification_revision=1,member_revision=1,workflow_revision=1,source_revision=1,standard_ref='standard-1',standard_hash='a'*64,tags_hash='b'*64,admitted=True,created_at='2026-09-13T00:00:00Z',tags=[dict(code='backend',status='supported',confidence_bps=9000,source='model',assertion_ref='assertion-1',verified=True)],allowed_demand_ids=[1],counted_demand_ids=[])],
        demands=[dict(demand_id=1,department_ref='department-1',revision=1,reception_state='receiving',required_tags=['backend'],preferred_tags=[],priority=1,recent_supply_count=0,last_allocation_sequence=0)])
    for member in snapshot['members']: member['tags_hash']=allocation_tags_hash(member['tags'])
    return AllocationRequest.model_validate(dict(task_id='allocation-fixture',idempotency_key='allocation-fixture-key',pin=dict(pin_id='pin-1',kernel_build='dev',toolset_version='allocation-tools/v1'),snapshot=snapshot,snapshot_hash=snapshot_hash(snapshot)))

def allocation_response(request=None,scenario='success'):
    request=request or allocation_request()
    s=request.snapshot.model_dump(mode='json'); demands={d['demand_id']:d for d in s['demands']}; seq=s['next_sequence']; decisions=[]
    for m in sorted(s['members'],key=lambda m:(datetime.fromisoformat(m['created_at'].replace('Z','+00:00')),m['member_id'])):
        tags={t['code']:t for t in m['tags'] if t['status']=='supported' and (t['source']=='manual' or t['confidence_bps']>=8000)}
        options=[]; receiving=False
        for ident in m['allowed_demand_ids']:
            d=demands[ident]
            if d['reception_state']!='receiving': continue
            receiving=True
            hits=sorted((set(d['required_tags'])|set(d['preferred_tags'])) & tags.keys())
            if not set(d['required_tags'])<=tags.keys() or not hits: continue
            order=[-len(set(d['preferred_tags']) & tags.keys()),d['priority'],d['recent_supply_count'],d['last_allocation_sequence'],ident]
            options.append((order,d,hits))
        decision=dict(member_id=m['member_id'],qualification_ref=m['qualification_ref'],action='wait',demand_id=0,department_ref='',matched_tags=[],assertion_refs=[],order=[],sequence=0,reason_code='no_active_mapping' if not m['allowed_demand_ids'] else 'required_tags_unavailable' if receiving else 'no_receiving_demand')
        if options:
            order,d,hits=min(options,key=lambda o:o[0])
            decision.update(action='assign',demand_id=d['demand_id'],department_ref=d['department_ref'],matched_tags=hits,assertion_refs=[tags[h]['assertion_ref'] for h in hits],order=order,sequence=seq,reason_code='allocated')
            if d['demand_id'] not in m['counted_demand_ids']: d['recent_supply_count']+=1
            d['last_allocation_sequence']=seq; seq+=1
        decisions.append(decision)
    value=AllocationResponse.model_validate(dict(task_id=request.task_id,idempotency_key=request.idempotency_key,pin=request.pin,snapshot_hash=request.snapshot_hash,decisions=decisions,safe_trace=dict(tool_names=TOOLS,tool_call_count=6,duration_ms=0,reused=False))).model_dump(mode='json')
    if scenario=='incomplete':value['decisions']=[]
    if scenario=='invalid_reference':value['decisions'][0]['demand_id']=999999
    if scenario=='invalid_schema':value['summary']='forbidden'
    return value
