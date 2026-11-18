#!/usr/bin/env python3
"""Render the two worker workloads for Kubernetes or an exported ETSI Sandbox scenario."""
import argparse
import base64
import json
import uuid
from pathlib import Path

ROLES = ('maintenance', 'bridge')


def settings(config, role):
    # Credentials are injected separately by the deployment, never exported in a scenario.
    allowed = {'facility_id', 'facility_path', 'assets', 'cse_url', 'cse_ca', 'origin', 'freshness_seconds',
               'settle_seconds', 'tolerance_pct', 'poll_seconds', 'listen_port', 'listen_host'}
    if role == 'bridge':
        allowed |= {'registry_url', 'mec_ca', 'allowed_service_origins', 'provider_sensor_ids', 'sensor_type',
                    'service_name', 'bridge_mode', 'provider_registration', 'sensor_test_callback'}
    extra = config.keys() - allowed
    if extra:
        raise ValueError('Unexpected configuration keys: ' + ', '.join(sorted(extra)))
    if not config['origin'] or config['origin'] == 'CAdmin' or not config['cse_url'].startswith('https://'):
        raise ValueError('Supply a scoped AE origin and an authenticated HTTPS worker gateway')
    return {**config, 'listen_port': 8080, 'listen_host': '0.0.0.0'}


def kubernetes(image, configs, namespace):
    result = []
    for role, config in configs.items():
        name = 'os-' + role
        labels = {'app': name, 'app.kubernetes.io/part-of': 'opensoom'}
        meta = {'name': name, 'namespace': namespace, 'labels': labels}
        trust = {'name': 'trust', 'mountPath': '/etc/opensoom/trust', 'readOnly': True}
        container = {'name': role, 'image': image, 'imagePullPolicy': 'IfNotPresent',
                     'ports': [{'name': 'callback', 'containerPort': 8080}],
                     'securityContext': {'allowPrivilegeEscalation': False, 'readOnlyRootFilesystem': True,
                                         'capabilities': {'drop': ['ALL']}},
                     'env': [{'name': 'OPENSOOM_WORKER_ROLE', 'value': role},
                             {'name': 'OPENSOOM_WORKER_CONFIG_JSON', 'value': json.dumps(config)},
                             {'name': 'OPENSOOM_WORKER_CSE_TOKEN', 'valueFrom': {'secretKeyRef':
                                 {'name': name + '-credentials', 'key': 'cse-token'}}}],
                     'volumeMounts': [trust], 'readinessProbe': {'httpGet': {'path': '/health', 'port': 8080}},
                     'resources': {'requests': {'cpu': '10m', 'memory': '32Mi'}, 'limits': {'memory': '160Mi'}}}
        if role == 'bridge':
            container['env'].append({'name': 'OPENSOOM_MEC_TOKEN', 'valueFrom': {'secretKeyRef':
                                    {'name': name + '-credentials', 'key': 'mec-token', 'optional': True}}})
        spec = {'automountServiceAccountToken': False, 'securityContext': {'runAsNonRoot': True,
                'runAsUser': 65532, 'seccompProfile': {'type': 'RuntimeDefault'}}, 'containers': [container],
                'volumes': [{'name': 'trust', 'configMap': {'name': 'os-worker-trust'}}]}
        result += [{'apiVersion': 'apps/v1', 'kind': 'Deployment', 'metadata': meta, 'spec': {
                       'replicas': 1, 'selector': {'matchLabels': labels},
                       'template': {'metadata': {'labels': labels}, 'spec': spec}}},
                   {'apiVersion': 'v1', 'kind': 'Service', 'metadata': meta, 'spec': {
                       'selector': labels, 'ports': [{'port': 8080, 'targetPort': 'callback'}]}}]
    return {'apiVersion': 'v1', 'kind': 'List', 'items': result}


def sandbox(image, configs, scenario, edge, mn_name):
    locations = [loc for d in scenario['deployment']['domains'] for z in d['zones']
                 for net in z['networkLocations'] for loc in (net.get('physicalLocations') or [])
                 if loc.get('type') == 'EDGE' and loc['name'] == edge]
    if len(locations) != 1:
        raise ValueError('Select exactly one EDGE hosting the intended MN-CSE')
    processes = locations[0]['processes']
    targets = [p['id'] for p in processes if p['name'] == mn_name]
    if len(targets) != 1:
        raise ValueError('The selected edge must host the named MN-CSE process')
    for role, cfg in configs.items():
        name = 'os-' + role
        if any(p['name'] == name for p in processes):
            raise ValueError('A worker with this name already exists in the exported scenario')
        encoded = base64.urlsafe_b64encode(json.dumps(cfg).encode()).decode().rstrip('=')
        app_id = str(uuid.uuid5(uuid.NAMESPACE_URL, '/'.join([scenario['name'], edge, name, cfg['facility_id']])) )
        processes.append({'id': app_id, 'name': name, 'type': 'EDGE-APP', 'image': image,
             'isExternal': False, 'dependencies': targets, 'environment': 'OPENSOOM_WORKER_ROLE=' + role +
             ',OPENSOOM_WORKER_CONFIG_B64=' + encoded, 'serviceConfig': {'name': name,
             'ports': [{'protocol': 'TCP', 'port': 8080}]}})
    return scenario


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--image', required=True)
    for role in ROLES:
        p.add_argument('--' + role, type=Path, required=True)
    p.add_argument('--namespace', default='opensoom-workers')
    p.add_argument('--scenario', type=Path, help='Exported dep-opt-c JSON with its existing topology')
    p.add_argument('--edge')
    p.add_argument('--mn-process')
    args = p.parse_args()
    cfg = {r: settings(json.loads(getattr(args, r).read_text()), r) for r in ROLES}
    if cfg['maintenance']['origin'] == cfg['bridge']['origin']:
        p.error('Use distinct provisioned AE identities')
    out = (sandbox(args.image, cfg, json.loads(args.scenario.read_text()), args.edge, args.mn_process)
           if args.scenario else kubernetes(args.image, cfg, args.namespace))
    print(json.dumps(out, indent=2))


if __name__ == '__main__':
    main()
