"""Render the headless ETSI Sandbox workloads for an isolated test cluster."""
import json


def workload(name, image, port, env=None, args=None):
    labels = {"app": name}
    container = {"name": name, "image": image, "ports": [{"containerPort": port}]}
    if env:
        container["env"] = [{"name": key, "value": val} for key, val in env.items()]
    if args:
        container["args"] = args
    if image.startswith("opensoom/"):
        container["imagePullPolicy"] = "Never"
    spec = {"replicas": 1, "selector": {"matchLabels": labels},
            "template": {"metadata": {"labels": labels}, "spec": {
                "automountServiceAccountToken": False, "containers": [container]}}}
    deployment = {"apiVersion": "apps/v1", "kind": "Deployment",
                  "metadata": {"name": name}, "spec": spec}
    service = {"apiVersion": "v1", "kind": "Service", "metadata": {"name": name},
               "spec": {"selector": labels, "ports": [{"port": port, "targetPort": port}]}}
    return [deployment, service]


def objects():
    items = workload("meep-redis-master", "redis:7.4.2-alpine@sha256:02419de7eddf55aa5bcf49efb74e88fa8d931b4d77c07eff8a6b2144472b6952", 6379)
    common = {"MEEP_SANDBOX_NAME": "opensoom", "MEEP_LOCATION_NAME": "mep1",
              "MEEP_PUBLIC_URL": "http://opensoom-mec-ingress.default.svc.cluster.local", "MEEP_APP_ENABLEMENT": "mep1-meep-app-enablement"}
    for number, server in enumerate(("meep-app-enablement", "meep-iot", "meep-sss"), 1):
        name = "mep1-" + server
        env = dict(common, MEEP_POD_NAME=name, MEEP_INSTANCE_ID=f"48a303e4-4ecc-4c3d-ad00-{number:012d}")
        items.extend(workload(name, "opensoom/" + server + ":8c66f08e", 80, env))
    for role in ("in", "mn", "provider"):
        dep, svc = workload(f"opensoom-{role}", "opensoom/acme:2026.5.3", 8080, {"OPENSOOM_CSE_ROLE": role})
        spec = dep["spec"]["template"]["spec"]
        spec["containers"][0]["volumeMounts"] = [{"name":"store","mountPath":"/var/lib/opensoom"}]
        spec["volumes"] = [{"name":"store","hostPath":{"path":f"/var/lib/opensoom/cse-{role}","type":"DirectoryOrCreate"}}]
        dep["spec"]["strategy"] = {"type":"Recreate"}
        items.extend([dep, svc])
    config = {"apiVersion":"v1","kind":"ConfigMap","metadata":{"name":"opensoom-ingress-routes"},
              "data":{"default.conf": """server {
    listen 80;
    location /mec_service_mgmt/ { proxy_pass http://mep1-meep-app-enablement/mec_service_mgmt/; }
    location /mec_app_support/ { proxy_pass http://mep1-meep-app-enablement/mec_app_support/; }
    location /opensoom/mep1/sens/ { proxy_pass http://mep1-meep-sss/sens/; }
    location /opensoom/mep1/iots/ { proxy_pass http://mep1-meep-iot/iots/; }
    location / { return 404; }
}"""}}
    dep, svc = workload("opensoom-mec-ingress", "nginx:1.28.0-alpine@sha256:30f1c0d78e0ad60901648be663a710bdadf19e4c10ac6782c235200619158284", 80)
    gateway = dep["spec"]["template"]["spec"]
    gateway["containers"][0]["volumeMounts"] = [{"name":"routes","mountPath":"/etc/nginx/conf.d"}]
    gateway["volumes"] = [{"name":"routes","configMap":{"name":"opensoom-ingress-routes"}}]
    items.extend([config, dep, svc])
    db, svc = workload("meep-couchdb-svc-couchdb", "couchdb:3.5.1@sha256:ccea1e8035bf7afd68336e24056a1ca9c1c46d7abe42da686322c0ac7218e5c2", 5984, {"COUCHDB_USER":"admin"})
    controller, ctrl_svc = workload("meep-sandbox-ctrl", "opensoom/meep-sandbox-ctrl:8c66f08e-private-auth", 80,
                                    {"MEEP_SANDBOX_NAME":"opensoom"})
    database_password = {"name":"COUCHDB_PASSWORD","valueFrom":{"secretKeyRef":{"name":"opensoom-couchdb","key":"password"}}}
    for resource in (db, controller):
        resource["spec"]["template"]["spec"]["containers"][0]["env"].append(database_password)
    db["spec"]["template"]["spec"]["containers"][0]["env"].append({"name":"ERL_FLAGS","value":"+S 2:2"})
    items.extend([db, svc, controller, ctrl_svc])
    items.extend(workload("meep-influxdb", "influxdb:1.8.10-alpine@sha256:2601e27d6b7eac276017d7ea48d2685d52639cea974744b5877924376283a4cd", 8086))

    mqtt_cfg = {"apiVersion":"v1", "kind":"ConfigMap","metadata":{"name":"opensoom-provider-broker"},
                "data":{"mosquitto.conf":"listener 1883\nallow_anonymous false\npassword_file /auth/passwords\npersistence false\n"}}
    broker, mqtt_service = workload("opensoom-provider-events", "eclipse-mosquitto:2.0.22@sha256:81a6193ae693942a3231cd3ac52875b02b7e3a19da671b2fb4b55cc874c5b279", 1883)
    bspec = broker["spec"]["template"]["spec"]
    bspec["volumes"] = [{"name":"auth","emptyDir":{}},{"name":"config","configMap":{"name":"opensoom-provider-broker"}}]
    bspec["initContainers"] = [{"name":"password","image":"eclipse-mosquitto:2.0.22@sha256:81a6193ae693942a3231cd3ac52875b02b7e3a19da671b2fb4b55cc874c5b279",
        "command":["sh","-ec",'mosquitto_passwd -c -b /auth/passwords transducer "$BROKER_PASSWORD"; chown 1883:1883 /auth/passwords'],
        "env":[{"name":"BROKER_PASSWORD","valueFrom":{"secretKeyRef":{"name":"opensoom-provider-mqtt","key":"password"}}}],
        "volumeMounts":[{"name":"auth","mountPath":"/auth"}]}]
    bspec["containers"][0]["volumeMounts"] = [{"name":"auth","mountPath":"/auth","readOnly":True},
        {"name":"config","mountPath":"/mosquitto/config","readOnly":True}]
    items.extend([mqtt_cfg, broker, mqtt_service])
    return items


if __name__ == "__main__":
    print(json.dumps({"apiVersion": "v1", "kind": "List", "items": objects()}))
