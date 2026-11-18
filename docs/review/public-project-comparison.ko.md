# openSoom이 어느 부분에서 경쟁할 수 있는가

2026년 11월 19일 02:50 KST 기준 주최 측 평가 일정표에서 예시 행을 제외하고 이름이 있는 프로젝트는 7개였다. 그중 3개가 Hackster URL을 기재했다. 공개 글과 작성팀의 공개 저장소를 대조했다. 아래 수치는 각 팀이 보고한 결과다. 다른 팀의 실험을 재현하거나 심사 점수를 산정하지 않았다. [심사 일정표](https://docs.google.com/spreadsheets/d/1x1husd3She4ixkpxVvUy4LZJ75F2QFRDIpocEdst7p8/edit?gid=0) · [주최 측의 대회 목적](https://estimed.etsi.org/news/estimed_hackathon2/)

| 경쟁작 | 공개 자료에서 확인한 강점 | openSoom에 주는 시사점 |
| --- | --- | --- |
| **EdgeGuard** | 작업자와 지게차의 충돌을 예측한다. 저장소의 같은 가상 1,000회 실험에서 넓은 근접경보와 자체 정책 모두 충돌 0건이었다. 작업 처리량은 각각 48.3%와 97.2%였다. 브라우저 데모, 공개 기사, 영상, 다중 CSE 구현까지 연결된다. | 비교한 세 팀 중 가장 강하다. 어떤 사람이 어떤 판단을 바꾸는지와 기존 방식과의 비교를 누구나 첫 화면에서 이해할 수 있다. [Hackster](https://www.hackster.io/ahind012/edgeguard-stop-forklift-accidents-before-they-happen-e07309) · [검토한 실험과 재현 자료](https://github.com/ljw22112/Edgeguard/blob/cc49460cc02d90a0e02f7087f455efd5fd7c056d/README.md#key-results) |
| **HexaGuard** | 항공과 상수도에 같은 로컬 판단 엔진을 적용한다. 실제 ACME와 연동하고 수격작용 모델을 별도 해석기와 대조했다. 작성팀은 테스트 215개와 라이브 ETSI MEC Sandbox 검증이 남았음을 명시한다. | 범용성은 서로 다른 입력·기준을 가진 사례로 증명해야 한다. openSoom의 기회는 두 시설에서 같은 정비 로직이 실행되고 실제 MEC 서비스의 응답이 작업을 바꾼 기록이다. [Hackster](https://www.hackster.io/eslamabdelmogood/hexaguard-intelligent-edge-protection-84a745) · [검토한 원본 저장소](https://github.com/nahedabdelrahmanahmed-ux/HEXA-TPU-RT-/blob/9f49e8bdf89fdbff042257d91edfc129dfff21c7/README.md) |
| **UNIMORE Industrial IoT Anomaly Detection** | 모터 온도·진동·전류로 이상을 검출한다. 합성 검증 데이터에서 탐지율 100%, 오탐률 약 2.38%를 보고했다. Sandbox 앱 준비 확인과 서비스 발견을 수행했고, 추론 프로세스의 실제 MEC 호스팅은 별도라고 명시했다. | 모델 평가의 명료성이 강점이다. openSoom은 이상 판정 이후 어느 작업을 남기고 누가 무엇을 먼저 점검하는지까지 보여줄 수 있다. [Hackster](https://www.hackster.io/unimore-inginf-mantova/industrial-iot-anomaly-detection-with-onem2m-and-etsi-mec-00d531) · [검토한 검증 범위](https://github.com/STEFANIAGT/INDUSTRIAL-IOT-ANOMALY-DETECTION/blob/e8221d3836325fcce7317453858346a503f816e6/README.md) |

SafeZone, 다중 로봇 바닥 이상 탐지, 도로 결빙 감지, FireRoute는 당시 일정표의 Hackster 칸이 비어 있었다. 프로젝트 제목만으로 진척이나 순위를 추정할 수 없다. Hackster 직접 열람이 제한된 HexaGuard와 UNIMORE의 기술 수치는 위에 고정한 작성팀 원본을 근거로 삼았다.

## 심사위원이 재현할 수 있는 차이

HSE는 후드별 시운전 성능을 이후 검사의 기준으로 삼도록 안내한다. OSHA 배기설비 점검표에는 저풍량의 여러 원인이 나온다. 그래서 openSoom은 같은 저풍량에서도 구동축이 실제로 움직였는지에 따라 첫 점검을 달리한다. 운영자가 회복 여부를 판단하고, 정비사는 해당 작업 판본에 점검 상태를 기록한다. [HSE 시운전 지침](https://www.hse.gov.uk/lev/commissioning.htm) · [OSHA 산업환기 기술 매뉴얼 부록 III:3-4](https://www.osha.gov/otm/section-3-health-hazards/chapter-3)

- 보존 작업실의 비교 시험에서 두 명령은 95% 개방으로 동일했고 후속 풍량도 모두 515/560 m³/h였다. 별도 센서가 35%를 보고하면 구동부와 위치 피드백을, 93%를 보고하면 공기 경로를 먼저 점검한다. 두 사건 모두 열려 있다. [설계한 18개 시험과 원본](../inspection-benchmark.md)
- 동일 입력의 세 판단 규칙을 비교했다. 점검을 계속해야 했던 16건에서 ACK만 보는 규칙은 14건, 후속 풍량만 보는 규칙은 2건, openSoom은 0건을 잘못 닫았다. 별도로 회복한 두 건은 세 방식 모두 맞혔다. 실제 시설 고장률과 건강 효과는 측정하지 않았다. [실행 영수증](../../evidence/runtime/inspection-benchmark.json)
- 운영 콘솔, 정비사용 웹 앱, MEC 정비 워커와 서비스 연동기는 각자 다른 권한으로 같은 사건을 읽는다. 자체 Sandbox에서 MEC 033을 통해 외부 가상 센서 제공자를 연결하고 MEC 046의 측정으로 작업을 갱신했다. 정비사의 기록은 새로운 장비 명령을 만들지 않는다. [MEC 실행 기록](../../evidence/runtime/option-c/index.json) · [두 실제 앱의 11초 시연](../assets/technician-handoff.gif)

공개된 세 팀과 경쟁할 기술적 이유가 있다. EdgeGuard가 보여준 비교 실험 규모와 무설치 데모의 접근성에서 우위를 주장할 근거는 없다. openSoom에는 실설비 검증과 공개 Hackster 글, 심사 상호작용, 연합학습 및 네트워크 위치 검증이 남아 있다. 남은 발표 시간에는 한 작업의 잘못된 종료를 피하고 현장 담당자의 다음 행동까지 바뀌는 장면을 우선한다. [17개 항목별 자체 심사](release-assessment.ko.md)
