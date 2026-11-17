#!/usr/bin/env python3
"""Exercise fixed operator/admin setup identities against the virtual service."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import httpx

ROOT=Path(__file__).resolve().parents[1]

def main():
    keys=json.loads((ROOT/'.runtime/service-credentials.json').read_text())
    rows=[]
    with httpx.Client(base_url='http://127.0.0.1:8090',trust_env=False,timeout=20) as client:
        for role,tool,args,expected in [
          ('operator','prepare_setup',{'profile_id':'learning-space'},200),
          ('operator','apply_setup',{'profile_id':'learning-space'},403),
          ('admin','apply_setup',{'profile_id':'not-configured'},404),
          ('admin','apply_setup',{'profile_id':'learning-space'},200),
          ('admin','apply_setup',{'profile_id':'learning-space'},200)]:
            response=client.post('/api/tools/'+tool,json={'arguments':args},headers={'Authorization':'Bearer '+keys[role+'_token']})
            assert response.status_code==expected, (role,tool,response.status_code)
            data=response.json()
            if role=='admin' and expected==200:
                assert data['profile_id']=='learning-space' and data['activated_facilities']==['learning-b']
                assert data['runtime']['status']=='ready'
            rows.append({'fixed_role':role,'tool':tool,'arguments':args,'http_status':response.status_code,'response':data})
    evidence={'captured_at':datetime.now(timezone.utc).isoformat(),'outcome':'PASS_AUTHORIZED_SETUP','physical_devices':'simulated','scope':'Administrator bootstrap is a separate configured identity. The operator/model does not self-escalate. Existing virtual registry/profile activation is idempotent; no physical onboarding claimed.','checks':rows,'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'src/opensoom/core.py',ROOT/'src/opensoom/app.py',ROOT/'config/facilities.json',Path(__file__)]}}
    path=ROOT/'evidence/agent/setup-acceptance.json';path.write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps({'outcome':evidence['outcome'],'checks':len(rows)}))

if __name__=='__main__':main()
