#!/usr/bin/env python3
"""Actual local service/CSE checks for independent-review findings. No model calls."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import time
import uuid
import httpx

ROOT=Path(__file__).resolve().parents[1]

def hashes():
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'src/opensoom/core.py',ROOT/'src/opensoom/app.py',Path(__file__)]}

def main():
    credentials=json.loads((ROOT/'.runtime/service-credentials.json').read_text())
    evidence={'started_at':datetime.now(timezone.utc).isoformat(),'kind':'actual_CSE_review_regression','physical_devices':'simulated','live_model_calls':0,'source_sha256_before':hashes(),'setpoints':[]}
    client=httpx.Client(base_url='http://127.0.0.1:8090',timeout=12,trust_env=False)
    def request(method,path,body=None,role='operator',run=None,expected=200):
        headers={'Authorization':'Bearer '+credentials[role+'_token']}
        if run:headers['X-OpenSoom-Run-ID']=run
        response=client.request(method,path,json=body,headers=headers)
        assert response.status_code==expected, (path,response.status_code,response.json())
        return response.json()
    def tool(name,args,**kwargs):return request('POST','/api/tools/'+name,{'arguments':args},**kwargs)
    deadline=time.monotonic()+25
    while time.monotonic()<deadline:
        try:
            if tool('doctor',{})['status']=='ready':break
        except httpx.HTTPError:pass
        time.sleep(.3)
    for value in (0,50,100):
        run=request('POST','/api/demo/start',{'facility_id':'food-a','scenario':'exhaust_fault','autorun':False})['run_id']
        command=tool('request_action',{'facility_id':'food-a','zone_id':'cook','action':'set_damper','value':value,'reason':'Review regression: preserve the requested virtual setpoint','request_id':run+':setpoint'},run=run)
        deadline=time.monotonic()+18
        while time.monotonic()<deadline:
            result=tool('verify_result',{'facility_id':'food-a','command_id':command['id']},run=run)
            if result['ack'] and result['outcome'] in ('recovered','unresolved'):break
            time.sleep(.3)
        assert result['ack'] and result['observations']['damper_pct']['value']==value, result
        assert result['outcome']==('recovered' if value==100 else 'unresolved'),result
        assert bool(result['complete'])==(value==100),result
        evidence['setpoints'].append({'requested_value':value,'run_id':run,'command_id':command['id'],'result':result})
    owner_run='owner-'+uuid.uuid4().hex[:12]
    request('POST','/api/agent-runs',{'id':owner_run,'facility_id':'food-a','mode':'fixture'})
    before=request('GET','/api/runs/'+owner_run)
    patch=request('PATCH','/api/agent-runs/'+owner_run,{'summary':'unauthorized change','outcome':'FAIL'},role='observer',expected=403)
    append=tool('doctor',{},role='observer',run=owner_run,expected=403)
    after=request('GET','/api/runs/'+owner_run)
    assert before==after,'Unauthorized write changed a run or its tool log'
    owner=request('PATCH','/api/agent-runs/'+owner_run,{'summary':'Owner update accepted','outcome':'RUNNING'})
    assert owner['summary']=='Owner update accepted'
    evidence['ownership']={'run_id':owner_run,'observer_patch':patch,'observer_tool_append':append,'target_state_unchanged':True,'owner_update_allowed':True}
    evidence['source_sha256_after']=hashes()
    assert evidence['source_sha256_after']==evidence['source_sha256_before']
    evidence['outcome']='PASS_REVIEW_REGRESSIONS'
    output=ROOT/'evidence/release/review-regressions.json';output.write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps({'outcome':evidence['outcome'],'setpoints':[r['requested_value'] for r in evidence['setpoints']],'owner_scope_checked':True,'evidence':str(output.relative_to(ROOT))}))
    client.close()

if __name__=='__main__':main()
