# openSoom 통합 릴리스 자체 심사

주최 측 한 장짜리 Rubric의 17개 항목을 GPT-6.2-Sol Max 여섯 팀이 독립 검토했다. 별도 Idea Model 리뷰어는 실제 시설 운영 판단과 도입 편의성을 검토한다. 코어 실증 `34095f6`, 통합 후보 `449850c`, 해당 커밋 이후의 보완 실행을 구별한다. **Expert는 해당 범위의 자체 판정**이다. 공인 점수와 합산 방식은 주최 측 소관이다. [원문 식별 정보와 17개 항목](../hackathon/rubric-baseline.json) · [검토 배정](review-charter.json) · [사전 심사](release-goal-review.ko.md)

| # | 항목 | 판정과 근거 |
|---|---|---|
| 1 | oneM2M 기능 | **Expert.** 네이티브 그룹 fan-out 하나에 실제 멤버별 2000을 받았다. 보안 프로필에서는 세 구역의 최근 CIN을 한 번에 조회했다. [실행 기록](../../evidence/application/release-acceptance.json) |
| 2 | 통신 프로토콜 | **Expert.** 장치 업데이트와 ACK에는 MQTT/TLS, 앱의 특정 자원 조회와 명령에는 HTTPS를 썼다. 동일 CIN을 두 바인딩으로 확인했다. [바인딩 영수증](../../evidence/runtime/cse-mqtt-tls-smoke.json) |
| 3 | 활용 시나리오 | **Expert.** 가상 다구역 장치의 동일 원본을 실제 CSE가 여러 앱에 전달한다. 운영 앱은 회복을 판정하고, 정비 앱은 독립 권한으로 점검 순서를 기록한다. [복수 앱](../multi-application-scenario.md) · [작업지시서](../../evidence/runtime/maintenance-release-local.json) |
| 4 | 기사 품질 | **Expert 수준 영문 원고.** 사진·구성도·프로토콜·자원 설계에 장치 ACK와 실제 풍량이 엇갈린 사례 및 oneM2M의 이점을 담았다. 공개 Hackster 렌더링은 게시 후 확인한다. [영문 기사](../submission/hackster-article.md) |
| 5 | 영상 품질 | **Expert.** 720p 신작은 실제 브라우저 화면, 영문 음성·자막 11개, 마지막 작업지시서까지 한 사건의 결정을 보여준다. 교정본의 ACK·풍량·축 위치·원본 근거가 각 대사와 일치하는지 프레임으로 재검토했다. 기존 45초·5분 작품은 별도 사례다. [영상](../../deliverables/video/openSoom-work-order-720p.mp4) · [제작·검증](../../deliverables/video/README.md) |
| 6 | GitHub 품질 | **Proficient 확인, Expert 열림.** 독립 클린 설치에서 README로 실제 MN·IN과 작업지시서를 재현했다. 공개 Hackster 기사를 게시한 뒤 README에 해당 URL을 넣고 로그아웃으로 역링크를 검증해야 한다. [README](../../README.md) · [클린 실행](../../evidence/release/clean-work-order.json) |
| 7 | oneM2M 홍보 | **Expert.** 기사·영상·저장소가 같은 관측을 여러 앱에서 재사용하고 구독·그룹·ACP를 CSE에 맡기는 운영상 이유를 보여준다. [기사](../submission/hackster-article.md) · [화면과 근거](../../pitch/README.md) |
| 8 | 심사자 가점 | **열림.** 운영진 공지와 팀 내부 대화는 확인했다. 프로젝트에 유익했던 공개 기술 교류의 검증된 링크가 필요하다. [제출 인계](../submission/handoff.md) |
| 9 | 인터뷰 | **열림.** 자원 구조, 통합 방법, oneM2M을 계속 채택할 이유를 답하는 자료와 시간 측정이 있다. 실제 질의응답은 배정된 인터뷰에서 이루어진다. [영문 Q&A](../submission/technical-qa.md) · [리허설](../../evidence/presentation/acceptance.json) |
| 10 | 보안·프라이버시 | **Expert, 시험 환경 범위.** TLS와 역할별 ACP의 허용·거부를 실증했다. 시설 제거 후 원래 정비 AE는 보존된 관측과 ACK 읽기에 각각 4103을 받고 운영 AE는 같은 원본에 각각 2000을 받았다. [TLS](../../evidence/runtime/cse-mqtt-tls-smoke.json) · [권한 회수](../../evidence/runtime/facility-retirement.json) |
| 11 | 데이터 상호운용성 | **Expert, PM2.5 범위.** 두 어댑터에서 TS-0023 airQualitySensor 표준 자원의 µg/m³ 정수형 측정값을 실제로 발견·조회했다. CO₂와 풍량은 별도 단위로 보존된다. [표준 매핑과 증거](../standard-model.md) |
| 12 | CSE 전환·연속성 | **Expert, 단일 호스트의 두 CSE 범위.** 가용성 감지 후 대체 CSE로 자동 전환, 미해결 상태·구독·권한 복원, 한 번의 명령 효과와 측정된 서비스 중단을 확인했다. 독립 정상 실행 중단 0.173초. [전환 증거](../../evidence/runtime/handover/acceptance.json) |
| 13 | oneM2M–MEC 앱 배포 | **Expert, 두 논리 MEC 호스트 범위.** 운영자가 목적지를 지정하면 실제 Sandbox 컨트롤러가 각 호스트에 MN-CSE와 정비 앱을 Helm으로 설치했다. 두 곳 모두 Mcc 등록과 새 사건 처리에 성공했다. 물리 VM은 한 대다. [배포·복구 영수증](../../evidence/runtime/option-c/index.json) |
| 14 | 연합학습 | **열림.** 실제 ESTIMED VM, 분산 클라이언트의 학습·집계 및 동적 선택·장애 회복형 복수 라운드 증거가 없다. 사이트 간 학습의 필요와 데이터가 확인되면 평가한다. [적용 근거](../extension-decisions.md) |
| 15 | 위치 서비스 | **열림.** 고정 설비는 시설·구역·자산 ID로 식별한다. 네트워크·MEC 위치 이벤트로 정비 배정이나 이동 정책이 바뀌는 실증이 필요하다. 35%는 기계축 개도다. [센서 응답](../../evidence/runtime/option-c/native-services.json) |
| 16 | MEC 서비스 | **Expert.** 시설의 oneM2M 요청 한 건으로 실제 033 제공자 등록과 046 구독을 각각 201로 생성하고 200으로 재조회했다. 테스트 콜백 204로 연결을 확인했다. 독립 가상 센서의 35%는 별도 046 GET에서 받았고, 같은 명령·작업지시가 3판에서 4판으로 바뀌었다. 브리지 재시작 후 동일 구독을 재사용했고 시험 후 삭제를 확인했다. [단일 실행 영수증](../../evidence/runtime/option-c/commissioned-sensor-roundtrip.json) |
| 17 | AI 에이전트·MCP | **Expert, 실제 oneM2M 워크플로 범위.** 독립 모델이 저장·실행·재조회 세 도구를 골랐고, Codex는 별도 실행에서 같은 세 작업을 수행하는 플러그인 도구를 선택했다. 저장한 버전과 원래 CIN은 재시작 후 재조회됐으며 오래된 관측으로 새 명령은 0건이었다. [모델별 영수증](../../evidence/agent/scenario-authoring/README.md) |

실제 시설에 관한 외부 자료는 배기 성능을 확인할 필요를 뒷받침한다. 가상 측정값으로 선별한 점검 우선순위의 현장 효과와 관리자의 무도움 첫 사용성은 별도 연구 과제다. 설정 시험에서는 보존 작업장의 두 구역과 자체 센서 바인딩을 코드 수정 없이 활성화·재시작·재실행했다. 후속 명령 시험에서는 같은 사건에서 이미 지난 명령의 응답이 새 점검을 덮어쓰지 않았다. [시설 설정 실행](../../evidence/agent/facility-onboarding.json) · [세 번째 시설에서 동일 정비 앱 실행](../../evidence/agent/facility-worker-generalization.json) · [연속 명령 실행](../../evidence/runtime/maintenance-command-followup.json) · [현장 문제와 배포 선택](../mec-application-contract.ko.md)
