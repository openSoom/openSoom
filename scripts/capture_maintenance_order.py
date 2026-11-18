#!/usr/bin/env python3
"""Reread a completed virtual ventilation incident using the maintenance AE identity."""
import argparse
import base64
import json
import os
from pathlib import Path

from opensoom.maintenance_worker import read_content, safe_rn
from opensoom.onem2m import CSEClient


def capture(config, client, run_id, commission_id=None):
    base = config['facility_path'].strip('/')
    facility = config['facility_id']

    def records(stream):
        parent = base + '/' + stream
        listing = client.discover(parent, {'ty': 4, 'lvl': 1, 'drt': 1})
        result = []
        for uri in listing['body']['m2m:uril']:
            name = safe_rn(uri.rsplit('/', 1)[-1])
            fetched = client.retrieve(parent + '/' + name)
            cin = fetched['body']['m2m:cin']
            value = read_content(cin)
            if value.get('facility_id') == facility:
                result.append({'ri': cin['ri'], 'read_rqi': fetched['rqi'], 'data': value})
        return result

    def one(matches, description):
        rows = list(matches)
        if len(rows) != 1:
            raise ValueError(f'Expected one {description}, found {len(rows)}')
        return rows[0]

    orders = [r for r in records('work_orders') if r['data'].get('run_id') == run_id]
    final = one((r for r in orders if r['data']['revision'] == 4), 'accepted independent-sample revision')
    value = final['data']
    opening = one((r for r in orders if r['data']['revision'] == 1), 'original work order')
    pending = one((r for r in orders if r['data']['revision'] == 2), 'unresolved follow-up')
    if any(r['data']['work_order_id'] != value['work_order_id'] for r in (opening, pending)):
        raise ValueError('Revisions belong to different work orders')
    outcome = one((r for r in records('outcomes') if r['ri'] == value['outcome_ri']), 'source outcome')
    req = one((r for r in records('sensor_requests') if r['ri'] == value['request_ri']), 'sensor request')
    reply = one((r for r in records('sensor_responses') if r['ri'] == value['response_ri']), 'sensor response')
    source_path = outcome['data']['source_cin_path'].strip('/')
    prefix = base + '/' + safe_rn(value['zone_id']) + '/observations/'
    if not source_path.startswith(prefix) or safe_rn(source_path[len(prefix):]) in ('la', 'ol'):
        raise ValueError('Expected the immutable observation inside the selected zone')
    source = client.retrieve(source_path)
    cin = source['body']['m2m:cin']
    measurement = read_content(cin)
    if (outcome['data']['kind'] != 'command.unresolved_after_ack' or
            any(outcome['data'][k] != req['data'][k] or req['data'][k] != value[k]
                for k in ('run_id', 'zone_id', 'incident_id', 'asset_id', 'command_id', 'source_cin_ri')) or
            reply['data']['request_ri'] != req['ri'] or req['data']['request_id'] != value['request_id'] or
            reply['data']['request_id'] != value['request_id'] or cin['ri'] != value['source_cin_ri'] or
            measurement['airflow'] != value['airflow'] or reply['data']['sample'] != value['sample'] or
            reply['data']['provider_receipt'] != value['provider_receipt'] or value['status'] != 'open'):
        raise ValueError('The source, request, response and work order do not identify the same decision')
    report = {'facility_id': facility, 'run_id': run_id, 'reader_ae': config['origin'],
              'original_observation': {'ri': cin['ri'], 'read_rqi': source['rqi'], 'data': measurement},
              'opened': opening, 'unresolved': pending, 'outcome': outcome, 'request': req,
              'response': reply, 'work_order': final}
    if commission_id:
        commissioned = one((r for r in records('provider_responses') if
                            r['data'].get('request_id') == commission_id), 'provider result')
        registration = value['provider_receipt'].get('provider_registration', {})
        enrollment = commissioned['data'].get('provider_receipt', {})
        if (commissioned['data']['status'] not in ('enabled', 'already_enabled') or
                not registration.get('enabled') or not enrollment.get('enabled') or
                registration['service_id'] != enrollment['service_id'] or
                registration['platform_id'] != enrollment['platform_id'] or
                value['provider_receipt'].get('service_id') == registration['service_id']):
            raise ValueError('Independent sensor response does not match the commissioned provider')
        report['commissioning'] = commissioned
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--commission-id', help='Also require the specified admission and two distinct MEC services')
    parser.add_argument('--config', type=Path, help='Maintenance configuration, or use the running worker environment')
    args = parser.parse_args()
    if args.config:
        config = json.loads(args.config.read_text())
    elif os.getenv('OPENSOOM_WORKER_CONFIG_JSON'):
        config = json.loads(os.environ['OPENSOOM_WORKER_CONFIG_JSON'])
    else:
        encoded = os.environ['OPENSOOM_WORKER_CONFIG_B64']
        config = json.loads(base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)))
    if config['origin'] == 'CAdmin' or not config['cse_url'].startswith('https://'):
        parser.error('Use a facility-scoped maintenance AE and its authenticated HTTPS gateway')
    token = os.environ['OPENSOOM_WORKER_CSE_TOKEN']
    with CSEClient(config['cse_url'], config['origin'], config.get('cse_ca'), bearer_token=token) as client:
        report = capture(config, client, args.run_id, args.commission_id)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
