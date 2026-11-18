#!/usr/bin/env python3
"""Replay three distinct setpoints on one incident in an isolated actual ACME CSE."""
import argparse
import hashlib
import json
import os
import tempfile
import threading
import time
from contextlib import ExitStack
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from capture_maintenance_order import capture
from cse_multiapp_smoke import ROOT, start_cse, stop_process
from opensoom import maintenance
from opensoom.core import Core
from opensoom.maintenance_worker import MaintenanceWorker, read_content
from opensoom.models import ActionRequest, Observation, utcnow
from opensoom.onem2m import CSEClient


def fixture():
    samples, lookups = {}, []

    class Provider(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get('Content-Length', 0)))
            self.send_response(200)
            self.send_header('X-M2M-RSC', '2000')
            self.send_header('X-M2M-RI', self.headers.get('X-M2M-RI', ''))
            self.send_header('X-M2M-RVI', '4')
            self.end_headers()

        def do_GET(self):
            url = urlsplit(self.path)
            if url.path == '/services':
                body = [{'state': 'ACTIVE', 'serName': 'fixture', 'serInstanceId': 'fixture-sss',
                         'serCategory': {'id': 'sssId'}, 'transportInfo': {'endpoint': {
                             'uris': [f'http://127.0.0.1:{self.server.server_port}/sens/v1']}}}]
            elif url.path.endswith('/sensor_discovery'):
                body = [{'sensorIdentifier': identifier} for identifier in samples]
            elif url.path.endswith('/sensor_data'):
                sensor_id = parse_qs(url.query)['sensorIdentifier'][0]
                lookups.append(sensor_id)
                body = {'sensorIdentifier': sensor_id, 'data': json.dumps(samples[sensor_id])}
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(body).encode())

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Provider)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, samples, lookups


def run():
    with ExitStack() as stack:
        root = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix='opensoom-followup-')))
        processes = []
        stack.callback(lambda: [stop_process(p) for p in processes])
        url, _, version = start_cse(root, processes)
        server, samples, lookups = fixture()
        stack.callback(server.server_close)
        stack.callback(server.shutdown)
        provider = f'http://127.0.0.1:{server.server_port}'
        os.environ.update(OPENSOOM_CSE_BASE='cse-multiapp', OPENSOOM_NOTIFY_URL=provider + '/notify',
                          OPENSOOM_FACILITY_IDS='food-a,learning-b')
        core = Core(runtime=root / 'operations', cse=stack.enter_context(CSEClient(url)))
        core.bootstrap()
        fid, zid = 'food-a', 'cook'
        actor = {'role': 'operator', 'facilities': [fid]}
        run_id = core.start_demo(fid, 'no_recovery', False, actor)['run_id']
        facility = core.facility(fid)
        cfg = core.registry[fid]['maintenance']
        asset = cfg['assets'][zid]
        def worker(role, provider_id=None):
            conf = {**cfg, 'origin': core.identities[role + ':' + fid], 'facility_path': facility['path'],
                    'facility_id': fid, 'cse_url': url, 'bridge_mode': 'mec046', 'registry_url': provider + '/services',
                    'provider_sensor_ids': {asset['sensor_id']: provider_id}}
            w = MaintenanceWorker(role, conf)
            stack.callback(w.close)
            return w
        def command(pct):
            req = ActionRequest(facility_id=fid, zone_id=zid, action='set_damper', value=pct,
                                reason='Virtual equipment follow-up', request_id=run_id + '-' + str(pct))
            item = core.request_action(req, actor, run_id)
            core.acknowledge_pending(facility, only_command_id=item['id'])
            return core.store.get('commands', item['id'])
        def airflow(recovered=False):
            core.publish(Observation(facility_id=fid, zone_id=zid, observed_at=utcnow(), adapter=facility['adapter'],
                         pm25=12, co2=610, airflow=1035 if recovered else 360, fan_running=True, damper_pct=100))
            maintenance.flush_outbox(core)
        def sample(opaque_id, value, command):
            elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(command['ack_at'])).total_seconds()
            time.sleep(max(0, cfg['settle_seconds'] - elapsed + .015))
            samples[opaque_id] = {'facility_id': fid, 'zone_id': zid, **asset, 'source': 'independent_position_sensor',
                                  'simulated': True, 'unit': '%', 'value': value, 'observed_at': utcnow()}
        def view():
            maintenance.refresh_work_orders(core)
            rows = [o for o in core.state(actor)['work_orders'] if o['run_id'] == run_id]
            if len(rows) != 1:
                raise AssertionError('Expected one logical work order')
            return rows[0]
        def records(stream):
            return [(cin['ri'], read_content(cin)) for cin in (maint.cin(path) for path in maint.children(stream))]

        maint = worker('maintenance')
        bridge = worker('bridge', 'provider-encoder-a')
        first = command(80)
        airflow()
        airflow()
        maint.scan()
        sample('provider-encoder-a', 35, first)
        bridge.scan()
        maint.scan()
        mismatch = view()
        assert mismatch['command_id'] == first['id'] and mismatch['priority'] == 'inspect_actuator_feedback'
        assert mismatch['sample']['value'] == 35 and mismatch['provider_receipt']['provider_sensor_id'] == 'provider-encoder-a'
        first_snapshot = core.store.get('commands', first['id'])

        second = command(90)
        waiting = view()
        assert waiting['command_id'] == second['id'] and waiting['evidence_status'] == 'awaiting_current_command_followup'
        assert 'sample' not in waiting and waiting['historical_work_order_ri'] == mismatch['resource_id']
        airflow()
        airflow()
        maint.scan()
        sample('provider-encoder-a', 90, second)
        bridge.scan()  # Response is now retained while the maintenance app is offline.
        second_request = next(row for _, row in records('sensor_requests') if row['command_id'] == second['id'])
        delayed_ri = next(ri for ri, row in records('sensor_responses') if row['request_id'] == second_request['request_id'] and row['status'] == 'measured')
        airflow(recovered=True)
        assert core.store.get('incidents', fid + ':' + zid)['recovery_count'] == 1
        second_snapshot = core.store.get('commands', second['id'])

        third = command(100)
        maint.close()
        maint = worker('maintenance')  # Replays retained outcomes and the earlier bridge reply.
        maint.scan()
        assert maint.health['superseded_responses'] >= 1
        assert not any(row['revision'] == 4 and row['command_id'] == second['id'] for _, row in records('work_orders'))
        assert view()['command_id'] == third['id'] and 'sample' not in view()
        airflow(recovered=True)
        assert core.store.get('incidents', fid + ':' + zid)['recovery_count'] == 1
        assert core.store.get('commands', third['id'])['status'] != 'verified'
        airflow()
        airflow()
        maint.scan()
        bridge.close()
        bridge = worker('bridge', 'replacement-encoder-b')  # Only the external identifier changes.
        sample('replacement-encoder-b', 100, third)
        bridge.scan()
        maint.scan()
        match = view()
        assert match['work_order_id'] == mismatch['work_order_id'] and match['command_id'] == third['id']
        assert match['priority'] == 'inspect_airflow_path' and match['sample']['value'] == 100
        assert match['provider_receipt']['provider_sensor_id'] == 'replacement-encoder-b'
        assert core.store.get('incidents', fid + ':' + zid)['status'] == 'open'
        assert dict(records('work_orders'))[mismatch['resource_id']]['sample']['value'] == 35
        airflow(recovered=True)
        airflow(recovered=True)
        latest = core.store.get('commands', third['id'])
        assert latest['status'] == 'verified' and latest['observed_result'] == 'recovered'
        assert core.store.get('commands', first['id']) == first_snapshot
        assert core.store.get('commands', second['id']) == second_snapshot
        snapshots = [capture(maint.config, maint.cse, run_id, command_id=cmd['id']) for cmd in (first, third)]
        return {'status': 'passed', 'acme_version': version, 'run_id': run_id, 'scope':
                'Actual isolated ACME HTTP / facility ACPs, two virtual encoder IDs on an HTTP MEC service fixture. '
                'This regression exercises rebinding and delayed delivery. Real MEC service evidence is in the separate cloud capture.',
                'mismatch': mismatch, 'after_next_ack': waiting, 'delayed_response_ri': delayed_ri,
                'delayed_command_id': second['id'], 'delayed_accepted_order_revisions': 0,
                'matched': match, 'same_work_order': True,
                'scoped_snapshot_rereads': [item['work_order']['read_rqi'] for item in snapshots], 'historical_commands_unchanged': [first['id'], second['id']],
                'current_command_after_airflow_recovery': latest, 'provider_lookup_ids': lookups,
                'changed_binding': {asset['sensor_id']: ['provider-encoder-a', 'replacement-encoder-b']},
                'source_sha256': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in
                    ('src/opensoom/core.py', 'src/opensoom/maintenance.py', 'src/opensoom/maintenance_worker.py', 'src/opensoom/mec_sensor.py')}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = run()
    if args.output:
        args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'status': result['status'], 'run_id': result['run_id'], 'work_order': result['matched']['work_order_id']}))
