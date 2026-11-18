"""Render least-privilege native Sandbox scenario-management workloads."""
import json
from workloads import workload

TARGET = "opensoom-workers"
ACCOUNT = "opensoom-virt-engine"


def objects():
    platform, platform_service = workload("meep-platform-ctrl", "opensoom/meep-platform-ctrl:8c66f08e-private", 80)
    controller, ctrl_service = workload("opensoom-placement-ctrl", "opensoom/meep-sandbox-ctrl:8c66f08e-private-auth", 80,
                                    {"MEEP_SANDBOX_NAME":TARGET, "MEEP_NW_SIMULATOR_TYPE":"ADVANTEDGE"})
    secret = {"name":"COUCHDB_PASSWORD","valueFrom":{"secretKeyRef":{"name":"opensoom-couchdb","key":"password"}}}
    for dep in [platform,controller]:
        dep["spec"]["template"]["spec"]["containers"][0].setdefault("env",[]).append(secret)
    engine, _ = workload("meep-virt-engine","opensoom/meep-virt-engine:8c66f08e-private",9000,
        {"MEEP_SANDBOX_PODS":"opensoom-placement-ctrl","MEEP_HOST_URL":"http://opensoom-mec-ingress.default.svc.cluster.local",
         "MEEP_USER_SWAGGER":"false","MEEP_CODECOV":"false","HELM_DRIVER":"configmap"})
    spec=engine["spec"]["template"]["spec"]
    spec.update({"serviceAccountName":ACCOUNT,"automountServiceAccountToken":True,"volumes":[
        {"name":"templates","emptyDir":{}},{"name":"charts","emptyDir":{}},
        {"name":"mn-chart","configMap":{"name":"opensoom-managed-mn-chart","items":[
        {"key":"chart","path":"Chart.yaml"},{"key":"cse","path":"templates/cse.json"},
        {"key":"north","path":"north.yaml"},{"key":"south","path":"south.yaml"}]}},
        {"name":"user-chart","configMap":{"name":"opensoom-managed-chart","items":[
            {"key":"chart","path":"Chart.yaml"},{"key":"worker","path":"templates/worker.json"},
            {"key":"north","path":"north.yaml"},{"key":"south","path":"south.yaml"}]}}]})
    spec["containers"][0]["volumeMounts"]=[{"name":"templates","mountPath":"/templates/sandbox"},
        {"name":"charts","mountPath":"/charts"},{"name":"user-chart","mountPath":"/data/user-charts/maintenance","readOnly":True},
        {"name":"mn-chart","mountPath":"/data/user-charts/site-mn","readOnly":True}]
    # Helm uses ConfigMaps instead of Secrets for release records. Only the
    # existing test application's namespace is in the engine's RBAC scope.
    account = {"apiVersion":"v1","kind":"ServiceAccount","metadata":{"name":ACCOUNT,"namespace":"default"}}
    auth = "rbac.authorization.k8s.io/v1"
    verbs=["get","list","watch","create","patch","update","delete"]
    role = {"apiVersion":auth,"kind":"Role","metadata":{"name":ACCOUNT,"namespace":TARGET},"rules":[
        {"apiGroups":[""],"resources":["configmaps"],"verbs":verbs},
        {"apiGroups":["apps"],"resources":["deployments"],"verbs":verbs}]}
    binding={"apiVersion":auth,"kind":"RoleBinding","metadata":{"name":ACCOUNT,"namespace":TARGET},
        "roleRef":{"apiGroup":"rbac.authorization.k8s.io","kind":"Role","name":ACCOUNT},
        "subjects":[{"kind":"ServiceAccount","name":ACCOUNT,"namespace":"default"}]}
    return [account,role,binding,platform,platform_service,controller,ctrl_service,engine]


if __name__=="__main__":
    print(json.dumps({"apiVersion":"v1","kind":"List","items":objects()}))
