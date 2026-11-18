import * as THREE from './vendor/three.module.js';

/**
 * Explanatory architecture, not a runtime client. Nothing in this module calls
 * an openSoom endpoint, a model API, or a physical device. Native resource
 * groups are deliberately distinguished from processes and logical modules.
 */
const SOURCE = {
  architecture: { path: 'docs/architecture.md', label: 'Architecture & boundaries', locator: 'Resource tree; distributed demonstration; trust' },
  core: { path: 'src/opensoom/core.py', label: 'Resource provisioning & control', locator: 'Core.bootstrap; setup_facility; request_action; verify_result' },
  registry: { path: 'config/facilities.json', label: 'Facility configuration', locator: 'food-a and learning-b entries' },
  food: { path: 'profiles/food-production.json', label: 'Food-production profile', locator: 'zones; permitted actions; simulation targets' },
  learning: { path: 'profiles/learning-space.json', label: 'Learning-space profile', locator: 'zones; permitted actions; simulation targets' },
  adapters: { path: 'src/opensoom/adapters.py', label: 'Two virtual vendor adapters', locator: 'normalize; encode_virtual; vendor-a and vendor-b branches' },
  policy: { path: 'src/opensoom/policy.py', label: 'Diagnosis & policy code', locator: 'freshness; profile-specific diagnosis' },
  store: { path: 'src/opensoom/store.py', label: 'Persistent service state', locator: 'SQLite Store' },
  api: { path: 'src/opensoom/app.py', label: 'Shared local API', locator: '/api/tools; /api/state; notifications' },
  mcp: { path: 'src/opensoom/mcp_server.py', label: 'Shared MCP tools', locator: 'stdio server; ServiceClient; scoped service calls' },
  plugin: { path: 'docs/agent-integration.md', label: 'Codex plugin instructions', locator: 'Start and connect; Tool and permission contract' },
  runner: { path: 'src/opensoom/llm_runner.py', label: 'Actual model API runner', locator: 'tool loop; MCP transport; shared budget' },
  agentEvidence: { path: 'evidence/agent/index.json', label: 'Codex & live-model evidence', locator: 'accepted captures and historical limits' },
  protocol: { path: 'evidence/runtime/cse-mqtt-tls-smoke.json', label: 'Native MQTT/TLS + HTTPS', locator: 'native_mqtt_create; https_same_resource; native_mqtt_denial' },
  topology: { path: 'scripts/cse_product_topology.py', label: 'Two-site execution script', locator: 'SITES; start API processes; native announcements; outage and replay' },
  multisite: { path: 'evidence/runtime/product-multisite-continuity.json', label: 'Actual distributed execution', locator: 'local_recovery_while_central_down; central_cannot_bypass_local_authority; fresh_central_intent_local_policy_ack_recovery' },
  mcc: { path: 'evidence/runtime/cse-multisite-smoke.json', label: 'Mcc & announcement evidence', locator: 'remote CSE registration; remote reads; announcement' },
  federation: { path: 'src/opensoom/federation.py', label: 'Intent validation & replay', locator: 'CentralIntent; FederationReceiver.receive; _validate_scope_and_time' },
  acceptance: { path: 'evidence/application/release-acceptance.json', label: 'Operational outcomes', locator: 'recovery; stale; missing; timeout; no recovery' },
  deployment: { path: 'deploy/README.md', label: 'Deployment trust limits', locator: 'single secure profile; distributed HTTP; local trust boundary' },
};

const LAYERS = {
  devices: { label: 'Virtual facility & adapters', ko: '가상 시설 · 어댑터', color: '#d6a96e' },
  resources: { label: 'Native oneM2M resources', ko: 'oneM2M 표준 리소스', color: '#a9dec8' },
  operations: { label: 'Local operations', ko: '현장 운영 · 상태', color: '#c1b5e6' },
  federation: { label: 'Cross-site resource sharing', ko: '중앙 공유 · 재연결', color: '#e1c785' },
  interfaces: { label: 'Shared agent & UI access', ko: '공통 에이전트 · 화면', color: '#a7cde8' },
};

const MODES = {
  distributed: {
    label: 'DISTRIBUTED / LOCALHOST LAB',
    en: 'Two facility APIs, two MN-CSEs and one central IN-CSE were run as separate local processes. Native Mcc, selective announcements and explicit intent replay were exercised over HTTP. Agent access is shown as the shared interface contract; its execution evidence comes from the separate single-installation profile.',
    ko: '현장 API 2개, MN-CSE 2개, 중앙 IN-CSE 1개를 별도 로컬 프로세스로 실행한 구성입니다. HTTP 기반 Mcc·선택적 공지·명시적 의도 재처리를 검증했습니다. 에이전트 연결은 공통 인터페이스를 나타내며, 실행 검증은 별도 단일 설치에서 수행했습니다.',
    evidence: ['topology', 'multisite', 'mcc', 'deployment'],
  },
  single: {
    label: 'SINGLE INSTALLATION / SECURE CSE PROFILE',
    en: 'One local service and one actual CSE serve two reusable example profiles. Adapter observations, ACKs and SDT projection updates use native oneM2M MQTT/TLS; service reads and commands use HTTPS. MCP uses stdio, and the local API and callback use loopback HTTP. No central CSE is required.',
    ko: '하나의 현장 서비스와 실제 CSE가 서로 다른 두 예시 프로필을 처리합니다. 관측·ACK·SDT 갱신은 네이티브 oneM2M MQTT/TLS, 조회·명령은 HTTPS를 사용합니다. MCP는 stdio, 로컬 API·콜백은 HTTP입니다. 중앙 CSE 없이 시작할 수 있습니다.',
    evidence: ['architecture', 'protocol', 'agentEvidence', 'deployment'],
  },
};

const nodes = [];
const edges = [];
const both = ['distributed', 'single'];
function node(id, title, ko, type, layer, shape, position, description, descriptionKo, path, sources, options = {}) {
  const entry = { id, title, ko, type, layer, shape, position, description, descriptionKo, path, sources, modes: both, ...options };
  nodes.push(entry);
  return entry;
}
function edge(id, from, to, flow, label, sources, options = {}) {
  edges.push({ id, from, to, flow, label, sources, modes: both, implementation: 'implemented', ...options });
}

const sites = [
  { key: 'food', fid: 'food-a', x: -9.2, name: 'Northworks', profile: 'food-production', vendor: 'Vendor A', port: 8091, csePort: 8181,
    zones: [['cook', 'Cooking line', '조리 구역', 'hood'], ['wash', 'Wash area', '세척 구역', 'wash'], ['pack', 'Packing area', '포장 구역', 'pack']] },
  { key: 'learning', fid: 'learning-b', x: 9.2, name: 'Westside', profile: 'learning-space', vendor: 'Vendor B', port: 8092, csePort: 8182,
    zones: [['classroom', 'Classroom', '교육실', 'room'], ['meeting', 'Meeting room', '회의실', 'room'], ['lounge', 'Shared lounge', '공용 공간', 'room']] },
];

for (const site of sites) {
  const { key, fid, x, name, profile, vendor } = site;
  const profileSource = key === 'food' ? 'food' : 'learning';
  const local = `${fid}/`;
  site.zones.forEach(([zid, title, ko, shape], i) => {
    node(`${key}-${zid}`, title, ko, 'SIMULATED PHYSICAL ZONE', 'devices', shape, [x + (i - 1) * 3.1, 0.05, 6.5],
      `${name}'s ${title.toLowerCase()} is a virtual device scenario. Airflow, fan state, particulate matter and CO₂ values have explicit timestamps and profile-specific meaning. Damper actions change the simulated response.`,
      `${name}의 ${ko}를 표현한 가상 장비 시나리오입니다. 풍량·팬 상태·미세먼지·CO₂는 시간 정보와 시설별 의미를 갖습니다. 댐퍼 명령은 가상 응답에 반영되며 물리적 환기 실험이 아닙니다.`,
      `profile:${profile} / zone:${zid}`, [profileSource, 'adapters', 'acceptance'],
      { short: zid.toUpperCase(), boundary: 'Simulated measurements and actuation. No CFD, capture-efficiency or health-effect claim.', site: key });
  });
  node(`${key}-adapter`, `${vendor} adapter`, `${vendor} 가상 어댑터`, 'LOGICAL ADAPTER MODULE', 'devices', 'adapter', [x, 0.85, 3.95],
    'Normalizes a vendor payload into common units and identities, preserves timestamps, publishes observations, reads a real CSE command and writes a separate ACK. The same diagnostic and agent code works with either adapter.',
    '제조사별 입력의 단위·식별자·시간을 공통 관측 모델로 바꿉니다. 실제 CSE의 명령을 읽고 별도 ACK를 기록합니다. 어댑터가 바뀌어도 진단과 에이전트 도구 코드는 같습니다.',
    `src/opensoom/adapters.py · ${vendor}`, ['adapters', 'core', 'protocol'],
    { short: `${vendor.toUpperCase()} / NORMALIZE`, boundary: 'Runs within the local service. Single profile: native MQTT/TLS writes. Distributed profile: HTTP CSE client.', site: key });

  node(`${key}-cse`, `${name} MN-CSE`, `${name} 현장 MN-CSE`, 'ACTUAL CSE PROCESS', 'resources', 'cse', [x, 2.7, -1.35],
    `An actual ACME MN-CSE at port ${site.csePort}. It stores ${fid}'s resources and provides native discovery, subscriptions, groups and access control. The other facility and central CSE run in different processes.`,
    `${site.csePort} 포트의 실제 ACME MN-CSE입니다. ${fid} 리소스를 저장하고 발견·구독·그룹 조회·권한 검사를 수행합니다. 다른 현장과 중앙 CSE는 별도 프로세스입니다.`,
    `http://127.0.0.1:${site.csePort}/cse-${key}`, ['topology', 'multisite', 'mcc'],
    { short: `MN-CSE / ${site.csePort}`, modes: ['distributed'], major: true, boundary: 'Local distributed test over HTTP. A coloured resource deck is not a separate process for each resource.', site: key });
  node(`${key}-ae`, 'Application identities', '애플리케이션 식별자', 'NATIVE AE RESOURCE GROUP', 'resources', 'identity', [x + 3.1, 2.7, -1.35],
    'The opensoom AE and adapter, diagnostic, operator, maintenance and observer AEs have different responsibilities. CSE-local registration supplies identities that ACPs distinguish.',
    'opensoom AE와 어댑터·진단·운영·유지보수·관찰용 AE를 등록합니다. CSE는 이 식별자를 기준으로 권한을 구분합니다. 역할 수가 독립 실행 서비스 수를 뜻하지는 않습니다.',
    `cse-${key}/{opensoom,os-adapter,os-diagnostic,os-operator,os-maintenance,os-observer}`, ['core', 'architecture'],
    { short: 'AE / SIX IDENTITIES', modes: ['distributed'], boundary: 'Distinct AE registrations; application roles are cohosted by the local prototype.', site: key });
  node(`${key}-acp`, 'Explicit access policies', '명시적 접근 제어', 'NATIVE ACP RESOURCE GROUP', 'resources', 'shield', [x - 3.1, 2.7, -1.35],
    `Four ${fid} policies protect structure, observations, commands and ACKs. Every protected container has an explicit acpi reference. An observer cannot create commands; the central actor cannot bypass local command authority.`,
    `${fid}의 구조·관측·명령·ACK를 네 ACP가 분리합니다. 보호 컨테이너마다 acpi를 지정하고, 관찰자의 명령 쓰기와 중앙의 직접 제어 우회를 막습니다.`,
    `opensoom/acp-${fid}-{structure,observations,commands,acks}`, ['core', 'multisite', 'protocol'],
    { short: 'ACP / FOUR POLICIES', boundary: 'ACP checks use distinct non-admin AE origins. The loopback lab is not physical-device identity authentication.', site: key });
  node(`${key}-facility`, `${fid} resource tree`, '시설 · 구역 컨테이너', 'NATIVE CNT RESOURCE GROUP', 'resources', 'tree', [x, 2.7, 0.55],
    `A facility container and ${site.zones.length} zone containers preserve a reusable facility/zone hierarchy. Site configuration chooses the ${profile} profile; application code does not hard-code a school kitchen.`,
    `시설 컨테이너 아래 ${site.zones.length}개 구역을 공통 구조로 관리합니다. 설정이 ${profile} 프로필을 선택하므로 학교 급식실은 여러 활용 예시 중 하나입니다.`,
    `opensoom/facilities/${fid}/{${site.zones.map(z => z[0]).join(',')}}`, ['core', 'registry', profileSource],
    { short: 'CNT / FACILITY + ZONES', boundary: 'A resource family inside a CSE, not a database or application per zone.', site: key });
  node(`${key}-observations`, 'Observations', '관측 기록', 'NATIVE CNT + CIN RESOURCE GROUP', 'resources', 'records', [x - 3.1, 2.7, 2.4],
    'Each zone has an observations container. Its content instances carry normalized readings, source/received timestamps and identity. Freshness uses time, and a repeated read of one CIN cannot count as a new recovery sample.',
    '구역별 observations 컨테이너에 정규화된 값과 관측·수신 시각을 CIN으로 저장합니다. 신선도는 시간을 검사하며, 같은 CIN을 여러 번 읽어도 새로운 회복 관측으로 세지 않습니다.',
    `opensoom/facilities/${local}{zone}/observations/{CIN}`, ['core', 'architecture', 'acceptance'],
    { short: 'CNT → CIN / OBSERVATIONS', boundary: 'Real CSE records containing simulated physical readings.', site: key });
  node(`${key}-commands`, 'Bounded commands', '범위가 제한된 명령', 'NATIVE CNT + CIN RESOURCE GROUP', 'resources', 'command', [x, 2.7, 2.4],
    'The authorized service creates a command CIN only after scope, profile, freshness, action and bounds checks. Commands carry an idempotency key, run association and expiry. A write response is not device execution.',
    '서비스가 역할·시설·프로필·신선도·허용 동작·범위를 검사한 뒤 명령 CIN을 만듭니다. 중복 방지 키, 실행 ID와 만료 시간이 포함됩니다. 저장 성공만으로 장비 동작을 판단하지 않습니다.',
    `opensoom/facilities/${local}{zone}/commands/{CIN}`, ['core', 'architecture', 'acceptance'],
    { short: 'CNT → CIN / COMMANDS', boundary: 'Simulated devices only. Physical-device onboarding requires an approved facility configuration and an adapter.', site: key });
  node(`${key}-acks`, 'Device acknowledgements', '장비 ACK', 'NATIVE CNT + CIN RESOURCE GROUP', 'resources', 'ack', [x + 3.1, 2.7, 2.4],
    'The virtual adapter reads the real command and returns a separate ACK CIN. The service correlates it to the command. Missing ACK times out; two distinct healthy observations after ACK are still required for recovery.',
    '가상 어댑터가 실제 명령을 읽은 뒤 별도 ACK CIN을 기록합니다. ACK가 없으면 시간 초과이며, ACK가 있어도 이후 서로 다른 정상 관측 두 개가 있어야 회복으로 판단합니다.',
    `opensoom/facilities/${local}{zone}/acks/{CIN}`, ['core', 'acceptance', 'protocol'],
    { short: 'CNT → CIN / ACKS', boundary: 'ACK proves a simulated device response, not measured ventilation adequacy.', site: key });
  node(`${key}-subscription`, 'Diagnostic subscriptions', '진단 구독 알림', 'NATIVE SUB RESOURCE GROUP', 'resources', 'subscription', [x + 4.35, 4.0, 0.65],
    'A native subscription watches new observation content instances. Its notification prompts the service to reread authoritative CSE data before diagnosis. One subscription exists under each zone’s observations container.',
    '각 관측 컨테이너의 네이티브 SUB가 새 CIN 생성을 알립니다. 서비스는 알림을 계기로 CSE 원본을 다시 읽은 뒤 진단하므로 콜백 내용만을 측정값으로 신뢰하지 않습니다.',
    `opensoom/facilities/${local}{zone}/observations/diagnosis`, ['core', 'api', 'architecture'],
    { short: 'SUB / NOTIFY + REREAD', boundary: 'Notification callback uses local HTTP. This is a CSE subscription, not application polling presented as one.', site: key });
  node(`${key}-group`, 'Native zone fan-out', '네이티브 구역 그룹 조회', 'NATIVE GRP + FOPT RESOURCE', 'resources', 'group', [x + 3.1, 2.7, 0.55],
    'The group contains the three zone observation containers. /fopt/la retrieves their latest content through the CSE. Native errors stay visible; separate diagnostic fallback reads are not presented as a successful aggregate.',
    'GRP에 세 구역의 관측 컨테이너를 넣고 /fopt/la로 최신 값을 조회합니다. 네이티브 오류는 보존하고, 별도 진단 조회를 성공한 그룹 응답처럼 꾸미지 않습니다.',
    `opensoom/${fid}-zone-observations/fopt/la`, ['core', 'architecture'],
    { short: 'GRP / FOPT / LA', boundary: 'Group retrieval is a CSE operation. It does not prove command acknowledgement.', site: key });
  node(`${key}-sdt`, 'Standard PM2.5 projection', '표준 PM2.5 데이터 모델', 'NATIVE SDT FLEXCONTAINER GROUP', 'resources', 'sdt', [x - 3.1, 2.7, 0.55],
    'Each zone has an airQualitySensor flexContainer using cod:aiQSr and the TS-0023 v5.6.0 model. The demonstrated standard field is integer PM2.5 in µg/m³; the original observation retains full precision.',
    '구역마다 TS-0023 v5.6.0의 airQualitySensor를 cod:aiQSr FCNT로 구현했습니다. 검증 범위는 정수형 PM2.5(µg/m³)이며 원래 정밀도는 관측 CIN에 남습니다. CO₂ ppm은 단위가 다른 표준 필드에 억지로 넣지 않습니다.',
    `opensoom/${fid}-{zone}-air · cod:aiQSr · pm25`, ['core', 'architecture'],
    { short: 'FCNT / SDT / PM2.5', boundary: 'PM2.5 mapping and discovery only; not a claim that every observation uses a standard semantic model.', site: key });

  node(`${key}-service`, `${name} operations`, `${name} 현장 서비스`, 'ACTUAL API PROCESS', 'operations', 'service', [x, 6.0, -4.7],
    `The ${site.port} API process cohosts adapter, diagnosis, operation and maintenance roles for ${fid}. Tool calls use fixed server-side authority. Local operation continues when the central CSE is stopped.`,
    `${site.port} 포트의 서비스가 ${fid}의 어댑터·진단·운영·유지보수 역할을 함께 실행합니다. 도구의 권한은 서버에서 고정하며 중앙 CSE가 중단돼도 현장 작업을 이어갑니다.`,
    `http://127.0.0.1:${site.port} · separate facility process`, ['api', 'topology', 'multisite'],
    { short: `LOCAL API / ${site.port}`, modes: ['distributed'], major: true, boundary: 'An actual separate facility process; its internal role blocks are logical modules.', site: key });
  node(`${key}-policy`, 'Profile & policy', '시설 프로필 · 판단 규칙', 'LOGICAL SERVICE MODULE', 'operations', 'policy', [x - 3.0, 6.0, -4.7],
    'Site-specific targets, freshness and allowed actions define how evidence is diagnosed and which request may proceed. A running fan is a different observation from adequate exhaust flow.',
    '시설별 목표·신선도·허용 동작을 바탕으로 진단하고 명령 가능 여부를 판단합니다. 팬의 작동 보고와 충분한 배기 풍량을 구분합니다. 모든 시설에 동일한 기준을 강제하지 않습니다.',
    `profile:${profile} · Core.request_action · policy.py`, [profileSource, 'policy', 'core'],
    { short: 'PROFILE / GUARDS', modes: ['distributed'], boundary: 'Runs within the API process. Simulation targets are not certified ventilation guidance.', site: key });
  node(`${key}-state`, 'Durable run state', '지속되는 운영 기록', 'LOCAL SQLITE DATA STORE', 'operations', 'database', [x + 3.0, 6.0, -4.7],
    'Runs, incidents, commands and events persist outside the conversation. The distributed demonstration uses a separate store for each facility. Run ownership, CSE request IDs and later observations connect decisions to outcomes.',
    '실행·사건·명령·이벤트를 채팅과 분리해 저장합니다. 분산 시연에서는 현장마다 별도 SQLite를 사용합니다. 실행 소유권·CSE 요청 ID·후속 관측이 판단과 결과를 연결합니다.',
    `${fid} service runtime / SQLite`, ['store', 'core', 'multisite'],
    { short: 'SQLITE / RUNS + EVENTS', modes: ['distributed'], boundary: 'Embedded storage, not an independent database service or a replica of CSE state.', site: key });
  node(`${key}-receiver`, 'Local intent validation', '현장 의도 검증 · 재처리', 'EXPLICITLY INVOKED LIBRARY', 'federation', 'receiver', [x, 6.1, -7.3],
    'An explicit replay test retrieves a CIN from the configured central queue. FederationReceiver checks provenance, facility, profile/version, issue time, expiry and duplicate identity before dispatch through local policy.',
    '명시적 재처리 시험이 설정된 중앙 큐에서 CIN을 읽습니다. 수신 라이브러리가 출처·시설·프로필 버전·발행 시각·만료·중복을 검사한 뒤 기존 현장 정책으로 전달합니다.',
    'FederationReceiver.receive → Core.request_action', ['federation', 'topology', 'multisite'],
    { short: 'VALIDATE / REPLAY', modes: ['distributed'], boundary: 'Library invoked by the demonstration script. No always-running federation consumer or process migration is claimed.', site: key });

  for (const [zid] of site.zones) edge(`${key}-wire-${zid}`, `${key}-${zid}`, `${key}-adapter`, 'observe', 'Virtual vendor payload → normalization', ['adapters', profileSource], { category: 'simulated_input' });
  edge(`${key}-publish`, `${key}-adapter`, `${key}-observations`, 'observe', 'Create observation CIN', ['core', 'protocol', 'topology'], { protocol: { single: 'Native oneM2M MQTT/TLS', distributed: 'oneM2M HTTP' } });
  edge(`${key}-sub`, `${key}-observations`, `${key}-subscription`, 'observe', 'Native subscription notification', ['core', 'api'], { protocol: 'Local HTTP callback' });
  edge(`${key}-project`, `${key}-adapter`, `${key}-sdt`, 'observe', 'Separately update standard PM2.5 projection', ['core'], { protocol: { single: 'Native oneM2M MQTT/TLS', distributed: 'oneM2M HTTP' } });
  edge(`${key}-fanout`, `${key}-group`, `${key}-observations`, 'observe', 'Native /fopt/la retrieval', ['core'], { category: 'native_service' });
  edge(`${key}-command-read`, `${key}-commands`, `${key}-adapter`, 'act', 'Adapter retrieves command from CSE', ['core'], { protocol: { single: 'oneM2M HTTPS', distributed: 'oneM2M HTTP' } });
  edge(`${key}-ack-write`, `${key}-adapter`, `${key}-acks`, 'act', 'Create distinct ACK CIN', ['core', 'protocol'], { protocol: { single: 'Native oneM2M MQTT/TLS', distributed: 'oneM2M HTTP' } });
  for (const resource of ['observations', 'commands', 'acks']) edge(`${key}-protect-${resource}`, `${key}-acp`, `${key}-${resource}`, 'structure', 'Explicit parent CNT acpi; CIN inherits parent policy', ['core'], { category: 'resource_reference', animated: false });
  for (const resource of ['observations', 'commands', 'acks']) edge(`${key}-contains-${resource}`, `${key}-facility`, `${key}-${resource}`, 'structure', 'Zone CNT contains resource container and CINs', ['core'], { category: 'resource_containment', animated: false });
  edge(`${key}-cse-ae`, `${key}-cse`, `${key}-ae`, 'structure', 'CSE hosts native AE registrations', ['core', 'topology'], { modes: ['distributed'], animated: false });
  edge(`${key}-ae-tree`, `${key}-ae`, `${key}-facility`, 'structure', 'opensoom AE contains facility hierarchy', ['core'], { modes: ['distributed'], animated: false });
  edge(`${key}-notify-policy`, `${key}-subscription`, `${key}-policy`, 'observe', 'Notify, then authoritative reread and diagnosis', ['core', 'api'], { modes: ['distributed'] });
  edge(`${key}-diagnosis-state`, `${key}-policy`, `${key}-state`, 'observe', 'Persist correlated incident and evidence', ['store', 'core'], { modes: ['distributed'], category: 'in_process' });
  edge(`${key}-policy-command`, `${key}-policy`, `${key}-commands`, 'act', 'Authorized bounded command creation', ['core'], { modes: ['distributed'], protocol: 'oneM2M HTTP' });
  edge(`${key}-verify-ack`, `${key}-acks`, `${key}-policy`, 'act', 'Correlate ACK; await two distinct later samples', ['core', 'acceptance'], { modes: ['distributed'] });
  edge(`${key}-service-policy`, `${key}-service`, `${key}-policy`, 'agent', 'Shared tool dispatch with fixed authority', ['api', 'core'], { modes: ['distributed'], category: 'in_process' });
  edge(`${key}-intent-policy`, `${key}-receiver`, `${key}-policy`, 'share', 'Validated intent enters local policy', ['federation', 'multisite'], { modes: ['distributed'], category: 'explicit_replay' });
  edge(`${key}-mcc`, `${key}-cse`, 'central-cse', 'share', 'Native Mcc registration and remote access', ['mcc', 'topology'], { modes: ['distributed'], protocol: 'Mcc over HTTP' });
  edge(`${key}-announce`, `${key}-observations`, 'central-announcements', 'share', 'Selective observation CNT announcement', ['topology', 'multisite'], { modes: ['distributed'], protocol: 'Native oneM2M announcement / HTTP' });
  edge(`${key}-central-intent`, 'central-intents', `${key}-receiver`, 'share', 'Read configured central queue; explicit replay', ['federation', 'multisite'], { modes: ['distributed'], protocol: 'oneM2M HTTP', category: 'explicit_replay' });
}

node('central-cse', 'Central IN-CSE', '중앙 IN-CSE', 'ACTUAL CSE PROCESS', 'federation', 'central', [.9, 7.6, -7.9],
  'The actual central ACME IN-CSE connects the two MN-CSEs using native Mcc registrations. It provides central resource visibility. Stopping it in the demonstration does not transfer or remove local control authority.',
  '실제 중앙 ACME IN-CSE가 네이티브 Mcc 등록으로 두 MN-CSE를 연결합니다. 중앙은 공유 리소스를 조회합니다. 중앙 중단 시험에서도 현장 제어 권한은 현장에 남아 있습니다.',
  'http://127.0.0.1:8180/cse-central · /opensoom-central', ['mcc', 'topology', 'multisite'],
  { short: 'IN-CSE / 8180', modes: ['distributed'], major: true, boundary: 'Optional distributed profile over HTTP. This is not MEC deployment, serving-CSE handover or high availability.' });
node('central-announcements', 'Selective announcements', '선택적 리소스 공지', 'NATIVE CNTAnnc RESOURCE GROUP', 'federation', 'records', [-2.7, 6.35, -5.35],
  'Selected observation containers are announced to the central CSE. Native remote reads retrieve facility evidence. Announcements share selected resource information; they are not general replication, state transfer or failover.',
  '선택한 관측 컨테이너를 중앙에 공지하고 네이티브 원격 조회로 현장 증거를 읽습니다. 공지는 필요한 리소스 정보를 공유하는 기능이며 일반 복제·상태 이전·장애 조치를 뜻하지 않습니다.',
  'central discovery: ty=10003 · opensoom:observations', ['topology', 'multisite', 'mcc'],
  { short: 'CNTAnnc / SELECTIVE', modes: ['distributed'], boundary: 'Six observation-container announcements are recorded in the two-site evidence.' });
node('central-intents', 'Expiring intent queue', '만료되는 중앙 의도 큐', 'NATIVE CNT + CIN RESOURCE GROUP', 'federation', 'command', [2.7, 6.35, -5.35],
  'A central CNT stores structured intent CINs. Facility/profile/version, issue time, expiry and request identity travel with the request. The local receiver independently decides whether a new command is permitted.',
  '중앙 CNT가 구조화된 의도를 CIN으로 저장합니다. 시설·프로필 버전·발행 시각·만료·요청 식별자를 함께 전달하고, 실제 명령 허용 여부는 현장 수신자가 다시 판단합니다.',
  'cse-central/federation-{run-id}/{CIN}', ['federation', 'topology', 'multisite'],
  { short: 'CNT / CIN / INTENTS', modes: ['distributed'], boundary: 'A durable central request is not direct authority to write a facility command.' });
node('central-operator', 'Central operator', '중앙 운영자', 'AE + EXPLICIT DEMO DRIVER', 'federation', 'operator', [-2.5, 7.6, -7.9],
  'The central operator application identity reads shared state and writes bounded intents. The demonstration driver creates and replays requests; its ACP is denied when it tries to create local command CINs directly.',
  '중앙 운영자 식별자가 공유 상태를 읽고 제한된 의도를 기록합니다. 시연 드라이버가 요청을 만들고 재처리하며, 중앙이 현장 명령 CIN을 직접 생성하려 하면 ACP가 거부합니다.',
  'cse-central/central-operator · scripts/cse_product_topology.py', ['topology', 'multisite'],
  { short: 'AE / DEMO DRIVER', modes: ['distributed'], boundary: 'This is an application identity and explicit script, not an always-on production orchestration service.' });
node('central-registration', 'Remote CSE registrations', '원격 CSE 등록', 'NATIVE CSR RESOURCE GROUP', 'federation', 'group', [0, 5.7, -3.0],
  'The IN-CSE and MN-CSEs establish real remote CSE registrations. Native remote resource addressing connects central reads to the correct facility CSE; this does not move an AE or serving CSE.',
  'IN-CSE와 MN-CSE가 실제 원격 CSE 등록을 생성합니다. 원격 주소를 통해 올바른 현장 CSE 리소스에 접근하며, AE나 서비스 CSE를 이동시키는 기능은 아닙니다.',
  'native remoteCSE / Mcc registrations', ['mcc', 'topology'],
  { short: 'CSR / MCC', modes: ['distributed'], boundary: 'Registration and remote access, not CSE handover.' });

node('single-cse', 'Shared secure CSE', '하나의 보안 CSE', 'ACTUAL CSE PROCESS', 'resources', 'central', [0, 4.25, -2.1],
  'One actual ACME CSE hosts both example facilities. Native oneM2M MQTT/TLS publishes observations, ACKs and SDT projection updates, while HTTPS serves reads and command writes. TLS verifies the lab server; origin headers remain trusted loopback identities.',
  '실제 ACME CSE 하나가 두 예시 시설을 관리합니다. 관측·ACK·SDT 갱신은 네이티브 MQTT/TLS, 조회·명령은 HTTPS입니다. TLS로 실험 서버를 검증하지만 원점 식별자는 로컬 신뢰 경계에 있습니다.',
  'https://127.0.0.1:8443/cse-secure · MQTT/TLS :8883', ['protocol', 'core', 'deployment'],
  { short: 'CSE / HTTPS + MQTT TLS', modes: ['single'], major: true, boundary: 'No central CSE is required. TLS and ACP are real; authenticated physical devices are not demonstrated.' });
node('single-ae', 'Shared application identities', '공통 AE 식별자', 'NATIVE AE RESOURCE GROUP', 'resources', 'identity', [0, 2.85, 0.3],
  'One opensoom AE contains the facility trees. Five role AEs distinguish adapter, diagnosis, operation, maintenance and observation. Role separation is enforced by native ACP and server policy.',
  'opensoom AE 아래 시설 구조를 두고 어댑터·진단·운영·유지보수·관찰용 다섯 AE를 구분합니다. 네이티브 ACP와 서버 정책이 역할 차이를 적용합니다.',
  'cse-secure/{opensoom,os-adapter,os-diagnostic,os-operator,os-maintenance,os-observer}', ['core', 'architecture'],
  { short: 'AE / SIX IDENTITIES', modes: ['single'], boundary: 'Six resource identities, not six independent processes.' });
node('single-service', 'Local operations service', '하나의 현장 운영 서비스', 'ACTUAL API PROCESS', 'operations', 'service', [0, 7.4, -6.7],
  'A single local API cohosts the reusable operational core and virtual adapter execution. Dashboard, MCP and the real-model runner reach the same server-side tool functions. Run ownership and permissions are checked here.',
  '로컬 API 하나가 공통 운영 코어와 가상 어댑터를 실행합니다. 대시보드·MCP·실제 모델 실행기가 같은 서버 도구 함수를 사용하며 실행 소유권과 권한을 서버에서 검사합니다.',
  'http://127.0.0.1:8090 · /api/tools/{name}', ['api', 'core', 'agentEvidence'],
  { short: 'LOCAL API / 8090', modes: ['single'], major: true, boundary: 'Logical role modules share this process. Local HTTP is not presented as end-to-end TLS.' });
node('single-policy', 'Facility-specific policy', '시설별 프로필 · 정책', 'LOGICAL SERVICE MODULE', 'operations', 'policy', [-3.5, 6.9, -6.1],
  'Activated profiles keep different targets and allowed controls for food-production and learning-space facilities. The same diagnosis and action guards operate on both. Stale or missing evidence cannot authorize a command.',
  '식품 생산 시설과 교육 공간의 프로필이 각각 목표·허용 제어를 정합니다. 같은 진단·명령 검사가 두 프로필에 적용되고 오래되거나 누락된 관측은 제어를 허용하지 않습니다.',
  'profiles/*.json · policy.py · Core.request_action', ['food', 'learning', 'policy', 'core'],
  { short: 'PROFILE / GUARDS', modes: ['single'], boundary: 'Rules run in the local service. They are simulation-specific policy, not universal safety thresholds.' });
node('single-state', 'Persistent evidence', '지속되는 실행 · 증거', 'LOCAL SQLITE DATA STORE', 'operations', 'database', [3.5, 6.9, -6.1],
  'Service-owned SQLite retains incidents, runs, commands and events across restart. A new run cannot reuse another run’s successful command. Verification requires command identity, ACK and two distinct later observations.',
  'SQLite가 재시작 이후에도 사건·실행·명령·이벤트를 보존합니다. 새 실행은 과거 성공 명령을 재사용할 수 없으며, 명령 식별자·ACK·후속 관측 두 개를 연결해 확인합니다.',
  'local runtime / SQLite store', ['store', 'core', 'agentEvidence'],
  { short: 'SQLITE / EVIDENCE', modes: ['single'], boundary: 'Embedded service state, separate from the CSE resource store and conversation history.' });

node('shared-mcp', 'Shared MCP tools', '공통 MCP 도구', 'ACTUAL STDIO SERVER PROCESS', 'interfaces', 'gateway', [0, 3.4, 3.4],
  'The shared MCP tools expose prerequisite checks, setup preparation, discovery, evidence, bounded requests and verification. Codex and the standalone runner share this boundary; tools cannot grant their own role or activate a profile as an operator.',
  '공통 MCP 도구로 점검·설정 준비·발견·증거 조회·제한된 요청·결과 확인을 제공합니다. Codex와 독립 실행기가 같은 경계를 사용하고 모델은 스스로 권한을 높이거나 운영자 권한으로 프로필을 활성화할 수 없습니다.',
  'doctor · prepare_setup · apply_setup · discover · read_group · read_evidence · request_action · verify_result', ['mcp', 'api', 'agentEvidence'],
  { short: 'MCP / STDIO', major: true, boundary: 'Actual stdio transport verified in the single installation. Distributed connections are shown as a shared contract, not a separately tested agent deployment.' });
node('codex-host', 'Codex plugin', 'Codex 플러그인', 'ACTUAL HOST + PACKAGED SKILLS', 'interfaces', 'terminal', [-2.45, 0.75, 6.25],
  'Packaged skills guide installation, diagnosis and operation through the shared MCP tools. Actual Codex CLI-host evidence and clean lifecycle checks are recorded separately from model-runner evidence.',
  '패키지에 포함된 스킬이 공통 MCP 도구를 통해 설치·진단·운영을 안내합니다. 실제 Codex CLI 호스트와 설치·재시작·정리 검증을 모델 실행기 증거와 구분해 기록했습니다.',
  'plugin/ · Codex CLI host · MCP stdio', ['plugin', 'agentEvidence'],
  { short: 'CODEX / SKILLS + MCP', boundary: 'Codex CLI-host evidence; a separate desktop UI installation is not claimed.' });
node('llm-runner', 'Standalone LLM runner', '독립 LLM 실행기', 'ACTUAL RUNNER PROCESS', 'interfaces', 'terminal', [2.45, 0.75, 6.25],
  'An actual API model selects tool calls through a real MCP client. The runner preserves service run correlation, bounds model steps and retries, and shares durable request/token accounting. A fixture is a separate, clearly labelled mode.',
  '실제 API 모델이 MCP 클라이언트를 통해 도구를 선택합니다. 실행 ID를 서비스와 연결하고 단계·재시도·요청·토큰 사용을 제한합니다. 결정론적 fixture는 별도 모드로 명확히 구분합니다.',
  'src/opensoom/llm_runner.py · real MCP client', ['runner', 'mcp', 'agentEvidence'],
  { short: 'LLM RUNNER / BOUNDED', boundary: 'Executed against the single-installation CSE; a model’s success statement cannot override service evidence.' });
node('model-api', 'Hosted model API', '외부 모델 API', 'EXTERNAL INFERENCE SERVICE', 'interfaces', 'cloud', [2.45, 0.65, 8.75],
  'The tested hosted API supplies actual model-generated function calls. It receives permitted tool schemas and simulated facility evidence. Local operational tokens and CSE credentials stay outside the prompt; the diagram makes no inference calls.',
  '검증된 외부 API가 실제 모델 도구 호출을 생성합니다. 허용된 도구 스키마와 가상 시설 증거를 전달하며 운영 토큰과 CSE 자격 증명은 프롬프트에 넣지 않습니다. 이 아키텍처 화면 자체는 API를 호출하지 않습니다.',
  'Hosted Responses API · verified model recorded per run', ['runner', 'agentEvidence'],
  { short: 'MODEL API / INFERENCE', boundary: 'Provider service is external; the model is not a trusted control authority or a physical ventilation model.' });
node('dashboard', 'Operations dashboard', '시설 운영 대시보드', 'BROWSER CLIENT', 'interfaces', 'screen', [-2.45, 0.65, 8.75],
  'A browser presents service-owned observations, incidents, commands and verification state. It uses the same local service and clearly labels simulated measurements. This architecture explorer is a separate explanatory page.',
  '브라우저가 서비스에 저장된 관측·사건·명령·결과를 보여 줍니다. 같은 로컬 API를 사용하고 가상 측정임을 표시합니다. 현재 아키텍처 탐색 화면은 별도의 설명용 페이지입니다.',
  'browser → /api/state · /api/tools', ['api', 'architecture'],
  { short: 'DASHBOARD / BROWSER', boundary: 'A client of the local service, not a separate backend or a live view inside this diagram.' });

edge('central-read', 'central-operator', 'central-announcements', 'share', 'Central observation and native remote reads', ['topology', 'multisite'], { modes: ['distributed'], protocol: 'oneM2M HTTP' });
edge('central-write', 'central-operator', 'central-intents', 'share', 'Create structured expiring intent CIN', ['topology', 'federation'], { modes: ['distributed'], protocol: 'oneM2M HTTP' });
edge('central-csr', 'central-cse', 'central-registration', 'structure', 'Native remoteCSE resources', ['mcc'], { modes: ['distributed'], animated: false });
edge('central-annc-store', 'central-cse', 'central-announcements', 'structure', 'IN-CSE hosts announced resources', ['multisite'], { modes: ['distributed'], animated: false });
edge('central-queue-store', 'central-cse', 'central-intents', 'structure', 'IN-CSE stores central application queue', ['topology'], { modes: ['distributed'], animated: false });
edge('codex-mcp', 'codex-host', 'shared-mcp', 'agent', 'Packaged skill → MCP tools/call', ['plugin', 'agentEvidence'], { protocol: 'MCP stdio', testedProfile: 'single' });
edge('runner-mcp', 'llm-runner', 'shared-mcp', 'agent', 'Model-generated call → real MCP client', ['runner', 'agentEvidence'], { protocol: 'MCP stdio', testedProfile: 'single' });
edge('runner-inference', 'model-api', 'llm-runner', 'agent', 'Actual inference response and tool selection', ['runner', 'agentEvidence'], { protocol: 'HTTPS', testedProfile: 'single' });
edge('mcp-single-api', 'shared-mcp', 'single-service', 'agent', 'Same authenticated tool API; server checks authority', ['mcp', 'api'], { modes: ['single'], protocol: 'Loopback HTTP' });
edge('dashboard-single-api', 'dashboard', 'single-service', 'agent', 'Read service state; scoped tool requests', ['api'], { modes: ['single'], protocol: 'Loopback HTTP' });
edge('single-service-policy', 'single-service', 'single-policy', 'agent', 'Fixed-role shared dispatch', ['core', 'api'], { modes: ['single'], category: 'in_process' });
edge('single-policy-state', 'single-policy', 'single-state', 'observe', 'Persist incidents, commands and verified outcomes', ['core', 'store'], { modes: ['single'], category: 'in_process' });
edge('single-cse-ae', 'single-cse', 'single-ae', 'structure', 'Native CSE resources and AE identities', ['core'], { modes: ['single'], animated: false });
for (const site of sites) {
  const key = site.key;
  edge(`${key}-single-tree`, 'single-ae', `${key}-facility`, 'structure', 'Same CSE / opensoom AE contains both facility trees', ['core'], { modes: ['single'], animated: false });
  edge(`${key}-single-notification`, `${key}-subscription`, 'single-policy', 'observe', 'Notification → authoritative CSE reread → diagnosis', ['core', 'api'], { modes: ['single'], protocol: 'Local HTTP callback; HTTPS read' });
  edge(`${key}-single-command`, 'single-policy', `${key}-commands`, 'act', 'Authorized command CIN creation', ['core'], { modes: ['single'], protocol: 'oneM2M HTTPS' });
  edge(`${key}-single-verify`, `${key}-acks`, 'single-policy', 'act', 'ACK plus two fresh post-ACK observation CINs', ['core', 'acceptance'], { modes: ['single'], protocol: 'oneM2M HTTPS reads' });
  edge(`${key}-mcp-contract`, 'shared-mcp', `${key}-service`, 'agent', 'Shared service interface; not separately tested in distributed topology', ['api', 'mcp', 'agentEvidence'], { modes: ['distributed'], implementation: 'shared_contract_not_exercised_here', animated: false, dashed: true });
  edge(`${key}-dashboard-contract`, 'dashboard', `${key}-service`, 'agent', 'Same browser/API contract; distributed browser session not claimed', ['api', 'topology'], { modes: ['distributed'], implementation: 'shared_contract_not_exercised_here', animated: false, dashed: true });
}

export const ARCHITECTURE_SOURCE_MAP = {
  schema_version: 1,
  purpose: 'Static explanatory architecture, traceable to implementation and captured evidence. No live network, inference or control calls.',
  renderer: { library: 'three', version: '0.187.0', local_provenance: 'pitch/vendor/provenance.json' },
  boundaries: [
    'Physical devices, measurements and actuator response are simulated.',
    'Single secure CSE and distributed HTTP topologies are alternative demonstrations, not one combined transport claim.',
    'AE identities and logical modules are not necessarily independent processes.',
    'Agent execution evidence is from the single-installation profile; dashed distributed edges are the shared interface contract.',
    'Central intent replay is explicitly invoked; no always-running federation consumer is claimed.',
    'This diagram covers the original lab profiles. The deployment choices section links the separate MEC commissioning and maintenance runs.',
  ],
  sources: SOURCE, layers: LAYERS, topologies: MODES, nodes, edges,
};

const FLOW_COLORS = { observe: 0xa9dec8, act: 0xe5bc79, share: 0xe1ce95, agent: 0xa7cde8, structure: 0x739687 };
const nodeById = new Map(nodes.map(n => [n.id, n]));
const traceDescriptions = {
  overview: {
    en: 'Read from virtual zones through native resources to local decisions. Select a component to inspect its responsibility, execution boundary and source.',
    ko: '가상 구역 → 표준 리소스 → 현장 판단 순서로 읽습니다. 구성요소를 누르면 역할·실행 경계·근거를 확인할 수 있습니다.',
  },
  observe: {
    en: 'Normalize → observation CIN → native SUB notification → authoritative reread → profile-specific diagnosis. Fan state and measured airflow remain distinct.',
    ko: '정규화 → 관측 CIN → 네이티브 SUB 알림 → 원본 재조회 → 시설별 진단. 팬의 상태와 관측 풍량을 구분합니다.',
  },
  act: {
    en: 'Local guards → expiring command CIN → adapter read → distinct ACK → two unique later healthy observations. A write or ACK alone never closes the incident.',
    ko: '현장 정책 검사 → 만료되는 명령 CIN → 어댑터 수신 → 별도 ACK → 이후 서로 다른 정상 관측 두 개. 쓰기나 ACK만으로 사건을 닫지 않습니다.',
  },
  share: {
    en: 'MN-CSEs share selected resources with the IN-CSE. A central intent returns through explicit replay and local validation. Local operation was tested while the central process was stopped.',
    ko: 'MN-CSE가 선택한 리소스를 IN-CSE와 공유합니다. 중앙 의도는 명시적 재처리와 현장 검사를 거칩니다. 중앙 프로세스 중단 중에도 현장 작동을 검증했습니다.',
  },
  agent: {
    en: 'Codex skills or an actual model runner → the same MCP tools → fixed service authority → CSE evidence and bounded actions. The service independently verifies the reported result.',
    ko: 'Codex 스킬 또는 실제 모델 실행기 → 공통 MCP 도구 → 고정된 서버 권한 → CSE 증거와 제한된 동작. 보고한 결과는 서비스가 별도로 검증합니다.',
  },
};

function traceSteps(trace, topology) {
  const policy = topology === 'single' ? 'single-policy' : 'food-policy';
  const state = topology === 'single' ? 'single-state' : 'food-state';
  const service = topology === 'single' ? 'single-service' : 'food-service';
  return {
    overview: topology === 'single' ? ['food-cook', 'food-adapter', 'single-cse', 'single-service', 'shared-mcp'] : ['food-cse', 'learning-cse', 'central-cse', 'central-intents', 'shared-mcp'],
    observe: ['food-cook', 'food-adapter', 'food-observations', 'food-subscription', policy, state],
    act: [policy, 'food-commands', 'food-adapter', 'food-acks', 'food-observations', state],
    share: ['food-observations', 'food-cse', 'central-announcements', 'central-intents', 'food-receiver', 'food-policy'],
    agent: ['codex-host', 'llm-runner', 'shared-mcp', service, policy, 'food-commands', 'food-acks'],
  }[trace];
}

/** Public entry point; safe to import in a source/provenance check without DOM. */
export function initializeArchitectureExplorer(root = document.getElementById('architecture-explorer')) {
  if (!root || root.dataset.initialized === 'true') return;
  root.dataset.initialized = 'true';
  const $ = selector => root.querySelector(selector);
  const $$ = selector => [...root.querySelectorAll(selector)];
  const stage = $('#arch-stage');
  const labelsHost = $('.arch-labels');
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  const smallScreen = window.matchMedia('(max-width: 640px)');
  const state = { topology: 'distributed', trace: 'overview', selected: 'central-cse', paused: reduced.matches, layers: new Set(Object.keys(LAYERS)), zoom: 1, yaw: 0.12, elevation: 0.60 };
  let renderer, camera, scene, world, animationId, visible = true, dirty = true, elapsed = 0, lastFrame = 0;
  let objectRecords = new Map(), edgeRecords = [], platformRecords = [], raycastTargets = [];
  const target = new THREE.Vector3();
  const bounds = new THREE.Box3();
  const projected = new THREE.Vector3();
  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  const isActive = n => n.modes.includes(state.topology) && state.layers.has(n.layer);
  const activeNodes = () => nodes.filter(isActive);
  const graphNodes = () => nodes.filter(n => n.modes.includes(state.topology));

  function makeSelectButton(n, mobile = false) {
    const button = document.createElement('button');
    button.type = 'button';
    button.dataset.archNode = n.id;
    button.setAttribute('aria-pressed', String(n.id === state.selected));
    const label = document.createElement(mobile ? 'span' : 'b');
    label.textContent = n.title;
    const subtitle = document.createElement(mobile ? 'small' : 'span');
    subtitle.textContent = `${n.ko} · ${n.short || n.type}`;
    subtitle.lang = 'ko';
    button.append(label, subtitle);
    button.addEventListener('click', () => {
      if (!state.layers.has(n.layer)) {
        state.layers.add(n.layer);
        const control = $(`[data-arch-layer="${n.layer}"]`);
        if (control) control.checked = true;
        applyVisibility();
      }
      select(n.id);
    });
    return button;
  }

  function buildAccessibleIndex() {
    const index = $('#arch-node-index');
    const mobile = $('.arch-mobile');
    index.replaceChildren();
    mobile.replaceChildren();
    const explanation = document.createElement('p');
    explanation.textContent = 'Explore the same components in a compact view. 구성요소를 선택하면 아래에서 역할과 근거를 확인할 수 있습니다. Numbered paths show how they work together.';
    mobile.append(explanation);
    for (const [id, layer] of Object.entries(LAYERS)) {
      const groupNodes = graphNodes().filter(n => n.layer === id);
      if (!groupNodes.length) continue;
      const group = document.createElement('div');
      group.className = 'arch-index-group';
      group.dataset.archIndexLayer = id;
      const heading = document.createElement('h5');
      heading.textContent = `${layer.label} / ${layer.ko}`;
      const buttons = document.createElement('div');
      groupNodes.forEach(n => buttons.append(makeSelectButton(n)));
      group.append(heading, buttons);
      index.append(group);
      const details = document.createElement('details');
      details.dataset.archIndexLayer = id;
      details.open = id === 'resources' || id === 'federation';
      const summary = document.createElement('summary');
      summary.textContent = layer.label;
      const count = document.createElement('small');
      count.textContent = `${groupNodes.length} · ${layer.ko}`;
      summary.append(count);
      const mobileButtons = document.createElement('div');
      groupNodes.forEach(n => mobileButtons.append(makeSelectButton(n, true)));
      details.append(summary, mobileButtons);
      mobile.append(details);
    }
  }

  function select(id) {
    const n = nodeById.get(id);
    if (!n || !n.modes.includes(state.topology)) return;
    state.selected = id;
    $('#arch-node-kind').textContent = n.type;
    $('#arch-node-title').textContent = n.title;
    $('#arch-node-ko').textContent = n.ko;
    $('#arch-node-path').textContent = n.path;
    $('#arch-node-description').textContent = n.description;
    $('#arch-node-description-ko').textContent = n.descriptionKo;
    $('#arch-node-boundary').textContent = n.boundary || '';
    const sources = $('#arch-node-sources');
    sources.replaceChildren();
    n.sources.slice(0, 4).forEach(key => {
      const source = SOURCE[key];
      const li = document.createElement('li');
      const a = document.createElement('a');
      a.href = `https://github.com/openSoom/openSoom/blob/main/${source.path}`;
      a.textContent = source.label;
      a.title = `${source.path} · ${source.locator}`;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      li.append(a);
      sources.append(li);
    });
    $$('[data-arch-node]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.archNode === id)));
    applyEmphasis();
    dirty = true;
  }

  function updateTrace() {
    $$('[data-arch-trace]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.archTrace === state.trace)));
    const description = traceDescriptions[state.trace];
    $('#arch-path-description').textContent = `${description.en} ${description.ko}`;
    if (state.trace === 'agent' && state.topology === 'distributed') {
      $('#arch-path-description').append(' Dashed site links are a shared contract, not a recorded distributed agent session. 점선은 별도 검증되지 않은 분산 연결을 나타냅니다.');
    }
    const steps = $('#arch-path-steps');
    steps.replaceChildren();
    traceSteps(state.trace, state.topology).forEach((id, i) => {
      const n = nodeById.get(id);
      if (!n) return;
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = `${String(i + 1).padStart(2, '0')}  ${n.title}`;
      button.addEventListener('click', () => {
        if (!state.layers.has(n.layer)) {
          state.layers.add(n.layer);
          $(`[data-arch-layer="${n.layer}"]`).checked = true;
          applyVisibility();
        }
        select(id);
      });
      steps.append(button);
    });
    applyEmphasis();
    dirty = true;
  }

  function updateMotionButton() {
    const button = $('[data-arch-action="motion"]');
    button.textContent = state.paused ? 'Resume paths' : 'Pause paths';
    button.setAttribute('aria-pressed', String(state.paused));
    button.setAttribute('aria-label', state.paused ? 'Resume illustrative path motion' : 'Pause illustrative path motion');
  }

  function updateTopology() {
    const mode = MODES[state.topology];
    $('#arch-topology-en').textContent = mode.en;
    $('#arch-topology-ko').textContent = mode.ko;
    $('#arch-view-label').textContent = mode.label;
    $$('[data-arch-topology]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.archTopology === state.topology)));
    $('[data-arch-trace="share"]').disabled = state.topology === 'single';
    const federationControl = $('[data-arch-layer="federation"]');
    federationControl.disabled = state.topology === 'single';
    federationControl.parentElement.style.opacity = state.topology === 'single' ? '.4' : '1';
    if (state.trace === 'share' && state.topology === 'single') state.trace = 'overview';
    if (!nodeById.get(state.selected).modes.includes(state.topology)) state.selected = state.topology === 'single' ? 'single-cse' : 'central-cse';
    buildAccessibleIndex();
    state.zoom = 1;
    applyVisibility();
    select(state.selected);
    updateTrace();
  }

  function addBox(parent, w, h, d, x, y, z, material) {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), material);
    mesh.position.set(x, y, z);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    parent.add(mesh);
    return mesh;
  }
  function addCylinder(parent, r, h, x, y, z, material, segments = 24) {
    const mesh = new THREE.Mesh(new THREE.CylinderGeometry(r, r, h, segments), material);
    mesh.position.set(x, y, z);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    parent.add(mesh);
    return mesh;
  }
  function outlineBox(parent, w, h, d, position, color, opacity = .45) {
    const line = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(w, h, d)), new THREE.LineBasicMaterial({ color, transparent: true, opacity }));
    line.position.set(...position);
    parent.add(line);
    return line;
  }
  function line(parent, points, color, opacity = .45, dashed = false) {
    const geometry = new THREE.BufferGeometry().setFromPoints(points.map(p => new THREE.Vector3(...p)));
    const material = dashed ? new THREE.LineDashedMaterial({ color, transparent: true, opacity, dashSize: .13, gapSize: .12 }) : new THREE.LineBasicMaterial({ color, transparent: true, opacity });
    const mesh = new THREE.Line(geometry, material);
    if (dashed) mesh.computeLineDistances();
    parent.add(mesh);
    return mesh;
  }
  function material(color, extras = {}) {
    return new THREE.MeshStandardMaterial({ color, roughness: .72, metalness: .13, ...extras });
  }

  function makeNode(n) {
    const group = new THREE.Group();
    group.position.set(...n.position);
    group.userData.nodeId = n.id;
    const color = new THREE.Color(LAYERS[n.layer].color);
    const base = material(0x284d41);
    const dark = material(0x153a31);
    const face = material(color);
    const light = material(0xe4ebda);
    const glass = material(color, { transparent: true, opacity: .18, depthWrite: false, roughness: .2 });
    let labelHeight = 1.15;
    const w = n.shape === 'central' ? 2.65 : n.shape === 'cse' ? 2.15 : 2.05;
    const baseMesh = addBox(group, w, .2, 1.3, 0, .1, 0, base);
    outlineBox(group, w + .03, .22, 1.33, [0, .1, 0], color, .58);
    addBox(group, w * .77, .035, .055, 0, .225, .56, face);
    const halo = new THREE.Mesh(new THREE.RingGeometry(.93, 1.03, 48), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: .7, side: THREE.DoubleSide, depthWrite: false }));
    halo.rotation.x = -Math.PI / 2;
    halo.scale.set(w * .65, .8, 1);
    halo.position.y = .005;
    halo.visible = false;
    group.add(halo);

    if (['cse', 'central'].includes(n.shape)) {
      const towerWidth = n.shape === 'central' ? 1.7 : 1.45;
      addBox(group, towerWidth, 1.55, .96, 0, .99, 0, dark);
      addBox(group, towerWidth + .13, .1, 1.07, 0, 1.8, 0, face);
      for (let i = 0; i < 5; i++) {
        addBox(group, towerWidth * .68, .04, .03, -.08, .48 + i * .22, .493, base);
        addBox(group, .08, .08, .04, towerWidth * .33, .48 + i * .22, .5, face);
      }
      addBox(group, .12, 1.15, .025, -towerWidth / 2 + .04, .98, .5, face);
      outlineBox(group, towerWidth + .05, 1.6, 1.0, [0, 1, 0], color, .6);
      labelHeight = 2.27;
    } else if (n.shape === 'service') {
      addBox(group, 1.9, .85, .98, 0, .65, 0, light);
      addBox(group, 1.72, .63, .04, 0, .68, .51, dark);
      for (let i = 0; i < 3; i++) {
        addBox(group, .34, .34, .05, -.52 + i * .52, .67, .55, face);
        addBox(group, .2, .025, .04, -.52 + i * .52, .39, .57, light);
      }
      addBox(group, 1.9, .08, 1.05, 0, 1.13, 0, face);
      labelHeight = 1.55;
    } else if (n.shape === 'database') {
      for (let i = 0; i < 4; i++) {
        addCylinder(group, .61, .18, 0, .35 + i * .24, 0, i === 3 ? face : base);
        const ring = new THREE.Mesh(new THREE.TorusGeometry(.61, .025, 6, 32), face);
        ring.rotation.x = Math.PI / 2;
        ring.position.set(0, .43 + i * .24, 0);
        group.add(ring);
      }
      labelHeight = 1.5;
    } else if (n.shape === 'shield') {
      const shield = new THREE.Mesh(new THREE.CylinderGeometry(.63, .63, .17, 6), face);
      shield.rotation.x = Math.PI / 2;
      shield.position.set(0, .87, 0);
      group.add(shield);
      addBox(group, .2, .29, .19, 0, .81, .13, dark);
      const lock = new THREE.Mesh(new THREE.TorusGeometry(.15, .045, 8, 20, Math.PI), dark);
      lock.position.set(0, .96, .14);
      group.add(lock);
      labelHeight = 1.85;
    } else if (n.shape === 'subscription') {
      const ring = new THREE.Mesh(new THREE.TorusGeometry(.47, .07, 9, 32), face);
      ring.position.y = .85;
      group.add(ring);
      addCylinder(group, .16, .16, 0, .85, 0, light);
      addBox(group, .07, .5, .08, 0, .42, 0, base);
      for (const side of [-1, 1]) line(group, [[side * .65, .6, 0], [side * .78, .85, 0], [side * .65, 1.1, 0]], color, .8);
      labelHeight = 1.8;
    } else if (n.shape === 'sdt') {
      const crystal = new THREE.Mesh(new THREE.OctahedronGeometry(.55), face);
      crystal.position.y = .9;
      crystal.rotation.y = Math.PI / 4;
      group.add(crystal);
      addCylinder(group, .55, .06, 0, .3, 0, dark);
      outlineBox(group, 1.45, 1.25, 1.02, [0, .9, 0], color, .35);
      labelHeight = 1.8;
    } else if (n.shape === 'group' || n.shape === 'tree' || n.shape === 'identity') {
      const columns = n.shape === 'identity' ? 3 : 3;
      for (let i = 0; i < columns; i++) {
        const px = (i - 1) * .54;
        addBox(group, .4, n.shape === 'identity' ? .8 : .37, .54, px, n.shape === 'identity' ? .63 : .46, 0, i === 1 ? light : face);
        if (n.shape === 'identity') addBox(group, .2, .1, .04, px, .86, .29, base);
      }
      line(group, [[-.55, .28, .42], [0, .28, .42], [.55, .28, .42]], color, .95);
      if (n.shape === 'tree') {
        addBox(group, .45, .28, .5, 0, .96, -.05, light);
        line(group, [[0, .8, 0], [0, .65, 0], [-.55, .65, 0]], color);
        line(group, [[0, .65, 0], [.55, .65, 0]], color);
      }
      labelHeight = 1.5;
    } else if (['records', 'command', 'ack', 'policy', 'receiver'].includes(n.shape)) {
      for (let i = 0; i < 3; i++) {
        addBox(group, 1.28, .15, .86, i * .045, .34 + i * .24, -i * .035, i === 2 ? face : base);
        addBox(group, .15, .07, .04, -.44 + i * .045, .34 + i * .24, .45 - i * .035, light);
      }
      if (n.shape === 'command') {
        line(group, [[-.28, 1, .07], [.32, 1, .07], [.09, 1, -.16]], color, 1);
        line(group, [[.32, 1, .07], [.09, 1, .29]], color, 1);
      }
      if (n.shape === 'ack') line(group, [[-.32, 1, .1], [-.06, 1, .33], [.4, 1, -.25]], 0xe4efcf, 1);
      if (n.shape === 'policy' || n.shape === 'receiver') outlineBox(group, 1.5, .9, 1.01, [0, .66, 0], color, .75);
      labelHeight = 1.5;
    } else if (n.shape === 'gateway') {
      addBox(group, .22, 1.35, .66, -.77, .88, 0, face);
      addBox(group, .22, 1.35, .66, .77, .88, 0, face);
      addBox(group, 1.74, .22, .66, 0, 1.6, 0, face);
      addBox(group, 1.3, 1.1, .11, 0, .89, 0, glass);
      for (let i = 0; i < 4; i++) {
        addBox(group, .11, .11, .13, -.42 + i * .28, 1.29, .14, light);
        addBox(group, .11, .11, .13, -.42 + i * .28, .5, .14, light);
      }
      labelHeight = 2.0;
    } else if (['terminal', 'screen', 'operator'].includes(n.shape)) {
      addBox(group, 1.68, 1.0, .13, 0, .88, -.05, face);
      addBox(group, 1.47, .79, .025, 0, .9, .026, dark);
      if (n.shape === 'screen') {
        for (let i = 0; i < 3; i++) addBox(group, .27, .16 + i * .12, .03, -.47 + i * .45, .73 + i * .06, .046, face);
      } else {
        line(group, [[-.52, 1.05, .05], [-.35, .94, .05], [-.52, .82, .05]], 0xe3efd8, .95);
        addBox(group, .58, .035, .025, .1, .82, .05, face);
      }
      addBox(group, .17, .23, .16, 0, .32, -.05, base);
      addBox(group, 1.55, .055, .43, 0, .26, .3, light);
      labelHeight = 1.75;
    } else if (n.shape === 'cloud') {
      for (const [px, py, r] of [[-.54, .72, .36], [0, .92, .5], [.55, .73, .37]]) {
        const sphere = new THREE.Mesh(new THREE.SphereGeometry(r, 18, 12), face);
        sphere.position.set(px, py, 0);
        group.add(sphere);
      }
      addBox(group, 1.45, .3, .48, 0, .56, 0, face);
      labelHeight = 1.85;
    } else if (n.shape === 'adapter') {
      addCylinder(group, .67, .43, 0, .48, 0, face, 6);
      addCylinder(group, .36, .09, 0, .75, 0, dark, 6);
      for (let i = 0; i < 3; i++) addBox(group, .13, .1, .23, -.38 + i * .38, .42, .55, light);
      labelHeight = 1.3;
    } else {
      // Miniature virtual zones. These are architectural symbols, not CFD.
      addBox(group, 1.75, .06, 1.08, 0, .25, 0, light);
      addBox(group, 1.75, .4, .07, 0, .45, -.5, base);
      if (n.shape === 'hood') {
        addBox(group, 1.34, .36, .6, 0, .48, .04, face);
        addBox(group, 1.5, .1, .76, 0, 1.18, .02, light);
        addBox(group, .25, .37, .27, 0, 1.4, -.1, base);
        for (const px of [-.32, .32]) addCylinder(group, .17, .06, px, .71, .08, dark);
        labelHeight = 1.95;
      } else if (n.shape === 'wash') {
        addBox(group, 1.25, .37, .64, 0, .48, .04, face);
        addBox(group, .83, .04, .4, 0, .69, .04, dark);
        line(group, [[.4, .68, -.1], [.4, 1.0, -.1], [.13, 1.0, -.1]], 0xe4ebda, .9);
        labelHeight = 1.5;
      } else if (n.shape === 'pack') {
        addBox(group, 1.4, .25, .6, 0, .42, 0, face);
        for (let i = 0; i < 3; i++) addBox(group, .32, .26, .4, -.45 + i * .45, .7, 0, light);
        labelHeight = 1.5;
      } else {
        for (const px of [-.4, .4]) {
          addBox(group, .52, .08, .5, px, .62, .03, face);
          addBox(group, .07, .3, .07, px, .43, .03, base);
          addBox(group, .3, .25, .08, px, .46, .4, light);
        }
        addBox(group, .15, .15, .05, .65, .73, -.44, face);
        labelHeight = 1.35;
      }
    }
    const hitbox = new THREE.Mesh(new THREE.BoxGeometry(w + .3, labelHeight, 1.65), new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false, colorWrite: false }));
    hitbox.position.y = labelHeight / 2;
    hitbox.userData.nodeId = n.id;
    group.add(hitbox);
    raycastTargets.push(hitbox);
    const label = document.createElement('div');
    label.className = `arch-label${n.major ? ' major' : ''}`;
    const title = document.createElement('b');
    title.textContent = n.title;
    const subtitle = document.createElement('small');
    subtitle.textContent = n.short || n.type;
    label.append(title, subtitle);
    labelsHost.append(label);
    world.add(group);
    objectRecords.set(n.id, { n, group, label, labelHeight, halo, face, baseMesh, hitbox });
  }

  function makePlatform({ x, y, z, width, depth, color, title, subtitle, layer, modes = both, labelAtFront = true }) {
    const group = new THREE.Group();
    group.position.set(x, y, z);
    addBox(group, width, .16, depth, 0, -.1, 0, material(0x24483c, { roughness: .87 }));
    outlineBox(group, width, .18, depth, [0, -.1, 0], color, .4);
    const inset = .32;
    line(group, [[-width / 2 + inset, .006, -depth / 2 + inset], [width / 2 - inset, .006, -depth / 2 + inset], [width / 2 - inset, .006, depth / 2 - inset], [-width / 2 + inset, .006, depth / 2 - inset], [-width / 2 + inset, .006, -depth / 2 + inset]], color, .25, true);
    for (const side of [-1, 1]) {
      addBox(group, .09, .08, .55, side * (width / 2 - .1), .02, depth / 2 - .55, material(color));
      addBox(group, .55, .08, .09, side * (width / 2 - .34), .02, depth / 2 - .27, material(color));
    }
    // A crisp, locally generated caption stays attached to its responsibility deck.
    const canvas = document.createElement('canvas');
    canvas.width = 1024;
    canvas.height = 160;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.textAlign = 'center';
    ctx.fillStyle = new THREE.Color(color).getStyle();
    ctx.font = '500 43px Arial';
    ctx.fillText(title, 512, 65);
    ctx.fillStyle = '#9fbca9';
    ctx.font = '25px Arial';
    ctx.fillText(subtitle, 512, 115);
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    const caption = new THREE.Mesh(new THREE.PlaneGeometry(Math.min(width - 1, 7.8), 1.17), new THREE.MeshBasicMaterial({ map: texture, transparent: true, depthWrite: false, side: THREE.DoubleSide }));
    caption.rotation.x = -Math.PI / 2;
    caption.position.set(0, .035, labelAtFront ? depth / 2 - .55 : -depth / 2 + .6);
    group.add(caption);
    world.add(group);
    platformRecords.push({ group, layer, modes });
  }

  function makePlatforms() {
    for (const site of sites) {
      makePlatform({ x: site.x, y: -.08, z: 5.9, width: 10.35, depth: 5.25, color: 0xd6a96e, title: site.name.toUpperCase(), subtitle: `${site.profile} / virtual zones`, layer: 'devices' });
      makePlatform({ x: site.x, y: 2.65, z: .6, width: 10.5, depth: 6.7, color: 0xa9dec8, title: 'NATIVE oneM2M RESOURCES', subtitle: 'AE · CNT / CIN · ACP · SUB · GRP · FCNT', layer: 'resources' });
      makePlatform({ x: site.x, y: 5.95, z: -4.8, width: 9.7, depth: 3.3, color: 0xc1b5e6, title: 'LOCAL OPERATIONS', subtitle: 'one API process / logical roles / embedded SQLite', layer: 'operations', modes: ['distributed'] });
      // Uprights show layer separation without suggesting independent hosting.
      const struts = new THREE.Group();
      for (const dx of [-4.8, 4.8]) line(struts, [[site.x + dx, 0, 2.7], [site.x + dx, 2.6, 2.7]], 0x779b80, .24, true);
      world.add(struts);
      platformRecords.push({ group: struts, layer: 'resources', modes: both });
    }
    makePlatform({ x: 0, y: 7.35, z: -8.25, width: 7.8, depth: 3.8, color: 0xe1c785, title: 'CENTRAL / OPTIONAL', subtitle: 'IN-CSE + central application identity', layer: 'federation', modes: ['distributed'] });
    makePlatform({ x: 0, y: 6.65, z: -6.55, width: 11.5, depth: 4.2, color: 0xc1b5e6, title: 'ONE LOCAL SERVICE', subtitle: 'profiles and roles share the same process', layer: 'operations', modes: ['single'] });
    makePlatform({ x: 0, y: 2.64, z: -.75, width: 6.7, depth: 4.6, color: 0xa9dec8, title: 'ONE CSE / TWO PROFILES', subtitle: 'the resource families belong to this CSE', layer: 'resources', modes: ['single'] });
    makePlatform({ x: 0, y: .56, z: 7.3, width: 6.6, depth: 5.7, color: 0xa7cde8, title: 'SHARED AGENT + UI CONTRACT', subtitle: 'execution captured in the single-installation profile', layer: 'interfaces' });
  }

  function makeEdge(e, index) {
    const a = nodeById.get(e.from), b = nodeById.get(e.to);
    if (!a || !b) return;
    const start = new THREE.Vector3(...a.position).add(new THREE.Vector3(0, .4, 0));
    const end = new THREE.Vector3(...b.position).add(new THREE.Vector3(0, .4, 0));
    const difference = end.clone().sub(start);
    const middle = start.clone().lerp(end, .5);
    if (e.flow === 'structure') middle.y += .1;
    else if (e.flow === 'share') middle.y += .8;
    else if (difference.length() > 7) middle.y += .9;
    else middle.y += .45;
    if (e.flow === 'act') middle.z += .44;
    if (e.flow === 'observe') middle.z -= .25;
    if (e.implementation === 'shared_contract_not_exercised_here') middle.x += e.to.startsWith('food') ? -1 : 1;
    const curve = new THREE.CatmullRomCurve3([start, start.clone().lerp(middle, .62), middle, middle.clone().lerp(end, .4), end]);
    const color = FLOW_COLORS[e.flow];
    const geometry = new THREE.BufferGeometry().setFromPoints(curve.getPoints(40));
    const edgeMaterial = e.dashed || e.flow === 'structure'
      ? new THREE.LineDashedMaterial({ color, transparent: true, opacity: .24, dashSize: e.flow === 'structure' ? .1 : .22, gapSize: .14 })
      : new THREE.LineBasicMaterial({ color, transparent: true, opacity: .36 });
    const mesh = new THREE.Line(geometry, edgeMaterial);
    mesh.computeLineDistances();
    world.add(mesh);
    const glow = new THREE.Mesh(new THREE.TubeGeometry(curve, 36, .025, 5, false), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: .8, depthWrite: false }));
    glow.visible = false;
    world.add(glow);
    const packet = new THREE.Mesh(new THREE.SphereGeometry(.065, 8, 6), new THREE.MeshBasicMaterial({ color: new THREE.Color(color).lerp(new THREE.Color(0xffffff), .3) }));
    packet.visible = e.animated !== false;
    world.add(packet);
    edgeRecords.push({ e, mesh, glow, packet, curve, phase: (index * .137) % 1 });
  }

  function applyVisibility() {
    $('#arch-component-count').textContent = activeNodes().length;
    $$('[data-arch-index-layer]').forEach(group => { group.hidden = !state.layers.has(group.dataset.archIndexLayer); });
    for (const record of objectRecords.values()) {
      record.group.visible = isActive(record.n);
      record.label.hidden = !record.group.visible;
    }
    for (const record of platformRecords) record.group.visible = record.modes.includes(state.topology) && state.layers.has(record.layer);
    for (const record of edgeRecords) {
      record.active = record.e.modes.includes(state.topology) && isActive(nodeById.get(record.e.from)) && isActive(nodeById.get(record.e.to));
      record.mesh.visible = record.active;
    }
    if (renderer) fitCamera();
    applyEmphasis();
    dirty = true;
  }

  function applyEmphasis() {
    const stepIds = new Set(traceSteps(state.trace, state.topology));
    for (const record of objectRecords.values()) {
      const selected = record.n.id === state.selected;
      const traced = state.trace !== 'overview' && stepIds.has(record.n.id);
      record.halo.visible = selected || traced;
      record.halo.material.opacity = selected ? .95 : .38;
      record.face.emissive.set(selected ? LAYERS[record.n.layer].color : '#000000');
      record.face.emissiveIntensity = selected ? .2 : 0;
      record.label.classList.toggle('selected', selected);
      record.label.classList.toggle('trace', traced);
    }
    for (const record of edgeRecords) {
      const selected = record.e.from === state.selected || record.e.to === state.selected;
      const traced = state.trace !== 'overview' && (record.e.flow === state.trace || (state.trace === 'act' && record.e.flow === 'observe' && record.e.id.startsWith('food-')));
      const structural = record.e.flow === 'structure';
      record.mesh.material.opacity = state.trace === 'overview' ? (selected ? .85 : structural ? .13 : record.e.dashed ? .28 : .37) : traced ? .92 : selected ? .45 : .07;
      record.glow.visible = !!record.active && traced && !record.e.dashed && !structural;
      record.packet.visible = !!record.active && record.e.animated !== false && (state.trace === 'overview' ? ['observe', 'share'].includes(record.e.flow) : traced);
      record.traced = traced;
    }
    dirty = true;
    renderNow();
  }

  function fitCamera() {
    if (!renderer || !stage.clientWidth || !stage.clientHeight) return;
    const width = stage.clientWidth, height = stage.clientHeight;
    renderer.setSize(width, height, false);
    bounds.makeEmpty();
    for (const record of objectRecords.values()) {
      if (!record.group.visible) continue;
      const p = record.group.position;
      bounds.expandByPoint(p.clone().add(new THREE.Vector3(-1.45, -.2, -.85)));
      bounds.expandByPoint(p.clone().add(new THREE.Vector3(1.45, record.labelHeight + .45, .9)));
    }
    if (bounds.isEmpty()) bounds.set(new THREE.Vector3(-4, 0, -3), new THREE.Vector3(4, 4, 3));
    bounds.getCenter(target);
    const distance = 70;
    camera.position.set(target.x + Math.sin(state.yaw) * Math.cos(state.elevation) * distance, target.y + Math.sin(state.elevation) * distance, target.z + Math.cos(state.yaw) * Math.cos(state.elevation) * distance);
    camera.lookAt(target);
    camera.updateMatrixWorld();
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    // Fit occupied component volumes, not the empty corners of their combined
    // world box. This keeps a layered model substantial in a wide web viewport.
    for (const record of objectRecords.values()) {
      if (!record.group.visible) continue;
      const p = record.group.position;
      for (const x of [-1.45, 1.45]) for (const y of [-.2, record.labelHeight + .45]) for (const z of [-.85, .9]) {
        projected.set(p.x + x, p.y + y, p.z + z).applyMatrix4(camera.matrixWorldInverse);
        minX = Math.min(minX, projected.x); maxX = Math.max(maxX, projected.x);
        minY = Math.min(minY, projected.y); maxY = Math.max(maxY, projected.y);
      }
    }
    if (!Number.isFinite(minX)) { minX = -5; maxX = 5; minY = -3; maxY = 3; }
    const aspect = width / height;
    const halfWidth = Math.max((maxX - minX) / 2 / .84, (maxY - minY) / 2 / .88 * aspect) / state.zoom;
    const halfHeight = halfWidth / aspect;
    const centerX = (minX + maxX) / 2, centerY = (minY + maxY) / 2;
    camera.left = centerX - halfWidth; camera.right = centerX + halfWidth; camera.top = centerY + halfHeight; camera.bottom = centerY - halfHeight;
    camera.updateProjectionMatrix();
    dirty = true;
    renderNow();
  }

  function positionLabels() {
    if (!camera) return;
    const width = stage.clientWidth, height = stage.clientHeight;
    const candidates = [...objectRecords.values()].filter(record => record.group.visible).sort((a, b) => {
      const priority = r => (r.n.id === state.selected ? 100 : 0) + (r.n.major ? 30 : 0) + (traceSteps(state.trace, state.topology).includes(r.n.id) && state.trace !== 'overview' ? 45 : 0) + (r.n.layer === 'resources' ? 8 : 0);
      return priority(b) - priority(a);
    });
    const occupied = [];
    for (const record of candidates) {
      projected.copy(record.group.position).add(new THREE.Vector3(0, record.labelHeight + .16, 0)).project(camera);
      const x = (projected.x * .5 + .5) * width;
      const y = (-projected.y * .5 + .5) * height;
      const label = record.label;
      label.hidden = false;
      const lw = label.offsetWidth || 130, lh = label.offsetHeight || 36;
      const rect = { left: x - lw / 2, right: x + lw / 2, top: y - lh, bottom: y + 2 };
      const selected = record.n.id === state.selected;
      const offscreen = projected.z < -1 || projected.z > 1 || rect.left < 5 || rect.right > width - 5 || rect.top < 5 || rect.bottom > height - 20;
      const collision = occupied.some(r => rect.left < r.right + 3 && rect.right > r.left - 3 && rect.top < r.bottom + 3 && rect.bottom > r.top - 3);
      label.hidden = offscreen || (collision && !selected);
      if (!label.hidden) {
        label.style.left = `${x}px`;
        label.style.top = `${y}px`;
        occupied.push(rect);
      }
    }
  }

  function setupPointer() {
    let down = null;
    stage.addEventListener('pointerdown', event => {
      if (event.button !== 0 || event.target.closest('button')) return;
      down = { x: event.clientX, y: event.clientY, yaw: state.yaw, elevation: state.elevation, moved: false, id: event.pointerId };
      if (event.pointerType === 'mouse') stage.setPointerCapture(event.pointerId);
    });
    stage.addEventListener('pointermove', event => {
      if (!down) return;
      const dx = event.clientX - down.x, dy = event.clientY - down.y;
      if (Math.abs(dx) + Math.abs(dy) > 5) down.moved = true;
      if (event.pointerType !== 'mouse' && Math.abs(dy) > Math.abs(dx)) return;
      if (down.moved) {
        state.yaw = THREE.MathUtils.clamp(down.yaw + dx * .0022, -.48, .48);
        state.elevation = THREE.MathUtils.clamp(down.elevation + dy * .0015, .5, .95);
        fitCamera();
      }
    });
    stage.addEventListener('pointerup', event => {
      if (!down) return;
      if (!down.moved && renderer) {
        const rect = renderer.domElement.getBoundingClientRect();
        pointer.set((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1);
        raycaster.setFromCamera(pointer, camera);
        const hits = raycaster.intersectObjects(raycastTargets.filter(mesh => mesh.parent.visible), false);
        if (hits.length) select(hits[0].object.userData.nodeId);
      }
      down = null;
      if (stage.hasPointerCapture(event.pointerId)) stage.releasePointerCapture(event.pointerId);
    });
    stage.addEventListener('pointercancel', () => { down = null; });
  }

  function renderNow() {
    if (!renderer || !scene || !camera || !stage.clientWidth || !stage.clientHeight || root.dataset.renderer === 'fallback') return;
    for (const record of edgeRecords) {
      if (!record.packet.visible) continue;
      const speed = record.e.flow === 'share' ? .075 : .115;
      record.packet.position.copy(record.curve.getPointAt((elapsed * speed + record.phase) % 1));
      record.packet.scale.setScalar(record.traced ? 1.5 : 1);
    }
    scene.updateMatrixWorld();
    positionLabels();
    renderer.render(scene, camera);
    dirty = false;
  }

  function initializeScene() {
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'low-power' });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.65));
      renderer.setClearColor(0x102f2a, 0);
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.toneMappingExposure = 1.18;
      renderer.shadowMap.enabled = true;
      renderer.shadowMap.type = THREE.PCFShadowMap;
      renderer.domElement.setAttribute('aria-hidden', 'true');
      stage.prepend(renderer.domElement);
      root.dataset.renderer = 'three.js-0.187.0';
      scene = new THREE.Scene();
      camera = new THREE.OrthographicCamera(-20, 20, 12, -12, .1, 160);
      world = new THREE.Group();
      scene.add(world);
      scene.add(new THREE.HemisphereLight(0xf4f7e7, 0x315748, 2.65));
      const sun = new THREE.DirectionalLight(0xfff8df, 3.1);
      sun.position.set(-14, 30, 18);
      sun.castShadow = true;
      sun.shadow.mapSize.set(2048, 2048);
      Object.assign(sun.shadow.camera, { left: -24, right: 24, top: 22, bottom: -22, near: .5, far: 70 });
      sun.shadow.normalBias = .07;
      sun.shadow.bias = -.00015;
      scene.add(sun);
      const fill = new THREE.DirectionalLight(0xa0cbd3, 1.6);
      fill.position.set(12, 9, -9);
      scene.add(fill);
      const grid = new THREE.GridHelper(36, 36, 0x37644f, 0x274e40);
      grid.position.y = -.32;
      grid.position.z = -1.2;
      grid.material.transparent = true;
      grid.material.opacity = .24;
      world.add(grid);
      makePlatforms();
      nodes.forEach(makeNode);
      edges.forEach(makeEdge);
      setupPointer();
      const observer = new ResizeObserver(() => fitCamera());
      observer.observe(stage);
      const intersection = new IntersectionObserver(entries => { visible = entries[0].isIntersecting; dirty = true; }, { rootMargin: '100px' });
      intersection.observe(stage);
      renderer.domElement.addEventListener('webglcontextlost', event => { event.preventDefault(); root.dataset.renderer = 'fallback'; visible = false; });
      function animate(now) {
        animationId = requestAnimationFrame(animate);
        const dt = lastFrame ? Math.max(0, Math.min((now - lastFrame) / 1000, .05)) : 0;
        lastFrame = now;
        if (!visible || document.hidden || smallScreen.matches || root.dataset.renderer === 'fallback') return;
        const moving = !state.paused;
        if (!moving && !dirty) return;
        if (moving) elapsed += dt;
        renderNow();
      }
      animationId = requestAnimationFrame(animate);
      // Integration hook for evidence capture; carries no runtime controls.
      root.architectureExplorer = { fit: fitCamera, select, getState: () => ({ topology: state.topology, trace: state.trace, paused: state.paused, selected: state.selected, visibleNodes: activeNodes().map(n => n.id), library: THREE.REVISION }), dispose: () => { cancelAnimationFrame(animationId); observer.disconnect(); intersection.disconnect(); renderer.dispose(); } };
    } catch (error) {
      root.dataset.renderer = 'fallback';
      $('.arch-loading').textContent = 'The complete component index is available below.';
      // Failure remains visible as a readable diagram; no CDN or network fallback.
      console.info('openSoom architecture: accessible component view active.', error instanceof Error ? error.name : 'WebGL unavailable');
    }
  }

  $$('[data-arch-topology]').forEach(button => button.addEventListener('click', () => { state.topology = button.dataset.archTopology; updateTopology(); }));
  $$('[data-arch-layer]').forEach(input => input.addEventListener('change', () => { input.checked ? state.layers.add(input.dataset.archLayer) : state.layers.delete(input.dataset.archLayer); applyVisibility(); }));
  $$('[data-arch-trace]').forEach(button => button.addEventListener('click', () => { state.trace = button.dataset.archTrace; updateTrace(); }));
  $$('[data-arch-action]').forEach(button => button.addEventListener('click', () => {
    const action = button.dataset.archAction;
    if (action === 'motion') { state.paused = !state.paused; updateMotionButton(); }
    if (action === 'fit') { state.yaw = .12; state.elevation = .60; state.zoom = 1; fitCamera(); }
    if (action === 'zoom-in') { state.zoom = Math.min(1.55, state.zoom + .12); fitCamera(); }
    if (action === 'zoom-out') { state.zoom = Math.max(.7, state.zoom - .12); fitCamera(); }
    dirty = true;
  }));
  reduced.addEventListener('change', event => { if (event.matches) state.paused = true; updateMotionButton(); dirty = true; });
  smallScreen.addEventListener('change', () => { fitCamera(); dirty = true; });
  document.addEventListener('visibilitychange', () => { dirty = true; });
  initializeScene();
  updateMotionButton();
  updateTopology();
}

if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => initializeArchitectureExplorer(), { once: true });
  else initializeArchitectureExplorer();
}
