import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from opensoom.maintenance_worker import MaintenanceWorker
from opensoom.mec_sensor import EvidenceError, SensorService, provider_sample


REQUEST = {'facility_id': 'food-a', 'zone_id': 'cook', 'asset_id': 'damper-a', 'sensor_id': 'shaft-a'}


def sample(at):
    return {**REQUEST, 'observed_at': at.isoformat(), 'value': 35, 'unit': '%',
            'source': 'independent_position_sensor'}


def flextype(sample_payload, provider_id='provider-fcnt-ri'):
    return {'sensorIdentifier': provider_id, 'data': json.dumps([{
        'CharacteristicName': 'sample', 'CharacteristicValue': json.dumps(sample_payload)}])}


def test_sandbox_service_contract_and_opaque_id():
    now = datetime.now(timezone.utc)
    urls = []
    def provider(request):
        urls.append(request.url)
        if request.url.path == '/services':
            data = [{'state': 'ACTIVE', 'serInstanceId': 'svc-1', 'serName': 'mep-sss',
                     'serCategory': {'id': 'sssId'}, 'transportInfo': {'endpoint': {
                         'uris': ['http://edge/tenant/sens/v1/']}}}]
        elif request.url.path.endswith('/sensor_discovery'):
            assert dict(request.url.params) == {'type': 'FLX', 'sensorPropertyList': 'saref:any'}
            data = [{'sensorIdentifier': 'provider-fcnt-ri', 'sensorType': 'FLX'}]
        else:
            assert request.url.path == '/tenant/sens/v1/queries/sensor_data'
            assert request.url.params['sensorIdentifier'] == 'provider-fcnt-ri'
            data = flextype(sample(now))
        return httpx.Response(200, json=data)
    svc = SensorService({'registry_url': 'http://edge/services', 'provider_sensor_ids': {'shaft-a': 'provider-fcnt-ri'}})
    svc.client.close()
    with httpx.Client(transport=httpx.MockTransport(provider)) as client:
        svc.client = client
        reading, receipt = svc.read(REQUEST)
    assert len(urls) == 3 and reading['sensor_id'] == REQUEST['sensor_id'] and reading['value'] == 35
    assert receipt['provider_sensor_id'] == 'provider-fcnt-ri' and receipt['service_id'] == 'svc-1'
    assert receipt['lookup_status'] == 200 and len(receipt['lookup_sha256']) == 64


@pytest.mark.parametrize('override', [dict(sensor_id='wrong-sensor'),dict(asset_id='other'),dict(zone_id='other'),
                                      dict(unit='rpm'),dict(observed_at=None),dict(value=True),dict(value=float('nan')),
                                      dict(source='command_echo')])
def test_rejects_unusable_provider_characteristics(override):
    raw = flextype({**sample(datetime.now(timezone.utc)), **override})
    with pytest.raises(EvidenceError):
        provider_sample(raw, REQUEST, 'provider-fcnt-ri')


def test_rejects_unapproved_registry_endpoint_before_sensor_request():
    svc = SensorService({'registry_url':'https://registry.example/services'}, 'synthetic-test-only')
    svc.client.close()
    def registry(req):
        assert req.url.host == 'registry.example'
        return httpx.Response(200,json=[{'state':'ACTIVE','serCategory':{'id':'sssId'},'serInstanceId':'x',
                 'transportInfo':{'endpoint':{'uris':['https://other.example/unapproved']}}}])
    with httpx.Client(transport=httpx.MockTransport(registry)) as client:
        svc.client = client
        with pytest.raises(EvidenceError, match='unapproved_service_endpoint'):
            svc.read(REQUEST)


def test_standard_scalar_uses_provider_time_and_comparison_windows():
    # Whole-second test keeps both the native and the serialized time exact.
    now = datetime.now(timezone.utc).replace(microsecond=0)
    response = {'sensorIdentifier':'shaft-a','data':'35','dataUnitOfMeasure':'%',
                'dataTimestamp':{'seconds':int(now.timestamp()),'nanoSeconds':0}}
    reading = provider_sample(response, REQUEST)
    assert reading['observed_at'] == now.isoformat()
    worker = MaintenanceWorker('maintenance', {'origin':'Ctest', 'facility_id':'food-a', 'facility_path':'in/site',
        'cse_url':'http://127.0.0.1', 'settle_seconds':3, 'freshness_seconds':45})
    try:
        req = {**REQUEST,'ack_at':(now - timedelta(seconds=4)).isoformat()}
        assert worker.check_sample(req,reading,now) == 35
        for age in (-1, 46):
            with pytest.raises(EvidenceError, match='outside_freshness_window'):
                worker.check_sample(req,reading,now + timedelta(seconds=age))
        with pytest.raises(EvidenceError, match='before_actuator_settled'):
            worker.check_sample({**req,'ack_at':now.isoformat()},reading,now)
    finally:
        worker.close()


def test_commissioning_creates_only_installed_provider_and_rereads_before_sensor_use():
    entry = {'iotPlatformId': 'shaft-provider', 'enabled': True,
             'userTransportInfo': [{'id':'events','name':'Events','protocol':'MQTT','type':'MB_TOPIC_BASED',
                                    'version':'3.1.1','endpoint':{'addresses':[{'host':'events','port':1883}]}}],
             'customServicesTransportInfo': [{'id':'position','name':'Position','protocol':'REST_HTTP',
                                    'type':'REST_HTTP','version':'4','endpoint':{'addresses':[{'host':'sensors','port':8080}]}}]}
    calls = []
    state = {}
    def api(req):
        calls.append((req.method, req.url.path))
        if req.url.path == '/services':
            return httpx.Response(200,json=[{'state':'ACTIVE','serName':'iot','serCategory':{'id':'iotId'},
                'serInstanceId':'svc033','transportInfo':{'endpoint':{'uris':['http://edge/iots/v1']}}}])
        if req.method == 'POST':
            assert json.loads(req.content) == entry
            state.update(entry)
            return httpx.Response(201,json=state)
        return httpx.Response(200,json=state) if state else httpx.Response(404)
    svc = SensorService({'registry_url':'http://edge/services','provider_registration':{'profile':'encoder','record':entry}})
    svc.client.close()
    with httpx.Client(transport=httpx.MockTransport(api)) as client:
        svc.client = client
        with pytest.raises(EvidenceError,match='provider_unregistered'):
            svc.read(REQUEST)
        status, receipt = svc.registration(commission=True)
        assert status == 'enabled' and receipt['before_status'] == 404 and receipt['write_status'] == 201
        assert receipt['readback_status'] == 200 and receipt['service_id'] == 'svc033'
        assert svc.registration(commission=True)[0] == 'already_enabled'
        assert [x[0] for x in calls].count('POST') == 1
        state['enabled'] = False
        with pytest.raises(EvidenceError,match='provider_disabled'):
            svc.read(REQUEST)
        state['enabled'] = True
        state['customServicesTransportInfo'] = []
        with pytest.raises(EvidenceError,match='provider_transport_mismatch'):
            svc.registration(commission=True)
        assert not any('/queries/' in url for _,url in calls)
