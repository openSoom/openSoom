# openSoom 통합 릴리스 자체 심사

주최 측 한 장짜리 Rubric의 17개 항목을 GPT-6.2-Sol Max 여섯 팀이 독립 검토했다. 별도 Idea Model 리뷰어는 실제 시설 운영 판단과 도입 편의성을 검토한다. 첫 통합 심사의 공통 제품 리비전은 `f8fd12f38030b9984c0cc76d7f502fd0904086f4`다. 클라우드 실증과 최종 소스의 로컬 재실행은 각각 해당 실행의 소스 해시로 확인할 수 있다. **Expert는 해당 범위의 자체 판정**이다. 공인 점수와 합산 방식은 주최 측 소관이다. [원문 식별 정보와 17개 항목](../hackathon/rubric-baseline.json) · [검토 배정](review-charter.json) · [사전 심사](release-goal-review.ko.md)


## 환기 후 공기질 결과 검토

가상 조리 구역의 세 시험은 환기 후 풍량이 모두 1,035 m³/h였다. PM2.5와 CO₂를 함께 확인하니 운영 판단은 달랐다. 회복 시험은 장비 응답 후 6.20초에 두 목표를 처음 충족했고, 기록한 시점까지 10.24초간 연속 관측됐다. 입자 잔류 시험은 CO₂가 720 ppm까지 내려갔어도 PM2.5가 60 µg/m³로 남아 목표를 충족하지 못했다. 재상승 시험은 6.17초간 두 목표에 들어왔던 기록을 보존한다. 시간은 각 실행의 원본 측정 시각에서 계산한다. [발표에 사용한 시험](../../evidence/runtime/air-quality-outcomes.json) · [최종판 독립 재실행](../../evidence/runtime/air-quality-outcomes-final.json)

여섯 GPT-6.2 Sol Max 팀과 별도 Idea Model 담당자가 동일한 후보 `3a9a644`를 검토했다. 이후 누락된 측정이 뒤늦게 확인되면 직전 정상 구간을 끝내도록 고쳤고, 다른 시설의 명령 이력 조회는 HTTP 403으로 거절됨을 실제 서비스에서 확인했다. 공개 제품판 `6481bad`를 비로그인 환경에 설치해 전체 테스트 120개와 하위 검사 29개를 통과했고, 가상 장비와 실제 로컬 ACME에서 세 시험을 재현했다. 공개 자료 18개를 내려받아 Git 파일과 대조했다. [검토 내역](review-ledger.json) · [접근 범위 검증](../../evidence/application/air-quality-history-access.json) · [공개 설치와 자료 검증](../../evidence/release/air-quality-outcomes.json)

4·6번은 공개 Hackster 글과 저장소에서 연결되는 링크, 8·9번은 실제 기술 교류와 인터뷰, 14·15번은 연합학습과 네트워크 위치 활용의 실행 근거가 남아 있다. 그 밖의 항목은 아래 표의 시험 범위에서 자체 Expert 판정을 유지한다. 실제 시설에서 공기질을 개선했는지와 비개발자가 도움 없이 도입할 수 있는지는 현장 검증 과제다.

## 측정 신뢰성과 실제 건물 자료 검토

여섯 Rubric 팀과 별도 Idea Model 담당자는 제품 소스 `25a64ac`과 동일한 시험 묶음을 검토했다. 감점 위험 항목은 계속 **4·6·8·9·14·15번**이다. 공개 저장소 판본 `2f1c8b0`을 새로 설치해 여섯 가지 측정 순서, 정비사에게 전달된 회복 근거, 대기열 조회 수, 건물 자료 31개 방-일의 분석 결과를 재현했다. 전체 테스트 108개와 하위 검사 29개가 통과했고 공개 파일 18개가 Git 객체와 바이트 단위로 일치했다. [공개 설치 검증](../../evidence/release/measurement-integrity.json) · [검토 기록](review-ledger.json)

점검을 계속해야 하는 가상 16건에서 명령 수신만 본 규칙은 14건, 풍량만 본 규칙은 2건, openSoom은 0건을 잘못 종료했다. 다른 실험에서는 원본 ACME 기록이 뒤늦은 PM2.5 10 µg/m³를 보존했고 운영자가 읽는 표준 자원은 시간상 더 최근 값인 63 µg/m³를 유지했다. 회복 판정은 당시 도착한 관측에 근거한다. 가속 시연의 두 정상 측정은 23 ms 간격이며, 실제 현장의 지속 회복이나 고장 진단 성능은 별도 시험이 필요하다. ORNL 조사는 한 연구용 건물의 과거 급기를 분석한 결과다. [가상 시나리오](../inspection-benchmark.md) · [측정 순서 실증](../../evidence/runtime/observation-sequence.json) · [ORNL 원본과 분석](../../examples/ornl-vav/README.md)

기존 건물관리시스템과 정비 시스템도 신뢰할 수 있는 풍량·축 개도 정보를 받으면 같은 첫 점검을 선택할 수 있다. openSoom의 검증된 장점은 별도로 운영되는 센서를 연결하고, 권한이 다른 두 앱이 같은 근거와 작업 판본을 이어받는 데 있다. 실제 시설 도입 효과는 읽기 전용 파일럿에서 기존 업무와 비교할 수 있다. 시설별 목표와 최소 지속시간을 정한 뒤 관리자의 무도움 설정 소요시간, 정비사의 첫 점검 선택, 교대·재시작 후 원본 근거를 찾는 시간을 기록한다. [Idea Model 검토](review-ledger.json)

## 경쟁작 비교 후 재검토

6개 Rubric 팀과 독립 Idea Model 팀이 같은 제품 버전 `462d4d9`을 검토했다. 1·2·3·5·7·10·11·12·13·16·17번은 아래에 명시한 실증 범위에서 Expert로 판단했다. 4번은 영문 원고가 준비됐고 실제 Hackster 게시 화면 확인이 남았다. 6번은 공개 Hackster 역링크가 필요하다. 8·9번은 실제 공개 기술 교류와 인터뷰, 14·15번은 연합학습과 네트워크 위치 실증이 남아 있다. [항목별 검토 기록](review-ledger.json) · [공개 경쟁작 비교](public-project-comparison.ko.md)

이번 제품의 새 근거는 같은 사건을 다루는 두 사람용 앱, 임무가 분리된 엣지 워커, 동일 입력을 사용한 18개 가상 시험이다. 현재 브라우저 기록과 클라우드 HTTP 기록은 다른 실행이다. 이전 혼합 프로토콜·SDT·실제 LLM 실행은 각 기록에 쓰인 소스 버전을 유지한다. 검토 후 동일 시설의 관찰자에게 운영 API가 작업지시서를 반환하던 동작을 수정했다. 관찰자는 시설 상태를 읽고, 정비 역할은 작업지시서를 읽고, 운영자는 현재 판본의 점검 상태까지 확인하도록 실제 역할별 요청으로 재검증했다. [브라우저 인계](../../evidence/application/technician-browser.json) · [클라우드 인계](../../evidence/runtime/option-c/technician-handoff.json) · [최종 역할별 확인](../../evidence/runtime/technician-workbench.json) · [판단 비교](../inspection-benchmark.md)

기술자 워크벤치 공개판의 동영상·발표자료·기사 이미지 등 29개 URL은 로그인 없이 원본 바이트까지 대조했다. [공개 릴리스 확인](../../evidence/release/inspection-publication.json)

## 항목별 판정과 적용 범위

| # | 항목 | 판정과 근거 |
|---|---|---|
| 1 | oneM2M 기능 | **Expert.** 네이티브 그룹 fan-out 하나에 실제 멤버별 2000을 받았다. 보안 프로필에서는 세 구역의 최근 CIN을 한 번에 조회했다. [실행 기록](../../evidence/application/release-acceptance.json) |
| 2 | 통신 프로토콜 | **Expert.** 장치 업데이트와 ACK에는 MQTT/TLS, 앱의 특정 자원 조회와 명령에는 HTTPS를 썼다. 동일 CIN을 두 바인딩으로 확인했다. [제품 흐름과 바인딩 기록](../../evidence/application/release-acceptance.json) · [동일 CIN 확인](../../evidence/runtime/cse-mqtt-tls-smoke.json) |
| 3 | 활용 시나리오 | **Expert.** 가상 다구역 장치의 동일 원본을 실제 CSE가 여러 앱에 전달한다. 운영 앱은 회복을 판정하고, 정비 앱은 독립 권한으로 점검 순서를 기록한다. [복수 앱](../multi-application-scenario.md) · [작업지시서](../../evidence/runtime/maintenance-release-local.json) |
| 4 | 기사 품질 | **Expert 수준 영문 원고.** 사진·구성도·프로토콜·자원 설계에 장치 ACK와 실제 풍량이 엇갈린 사례 및 oneM2M의 이점을 담았다. 공개 Hackster 렌더링은 게시 후 확인한다. [영문 기사](../submission/hackster-article.md) |
| 5 | 영상 품질 | **Expert.** 720p 신작은 실제 브라우저 화면, 영문 음성·자막 11개, 마지막 작업지시서까지 한 사건의 결정을 보여준다. 교정본의 ACK·풍량·축 위치·원본 근거가 각 대사와 일치하는지 프레임으로 재검토했다. 기존 45초·5분 작품은 별도 사례다. [영상](../../deliverables/video/openSoom-work-order-720p.mp4) · [제작·검증](../../deliverables/video/README.md) |
| 6 | GitHub 품질 | **Proficient 확인, Expert 열림.** 독립 클린 설치에서 README로 실제 MN·IN과 작업지시서를 재현했다. 공개 Hackster 기사를 게시한 뒤 README에 해당 URL을 넣고 로그아웃으로 역링크를 검증해야 한다. [README](../../README.md) · [클린 실행](../../evidence/release/final-work-order-acceptance.json) |
| 7 | oneM2M 홍보 | **Expert.** 기사·영상·저장소가 같은 관측을 여러 앱에서 재사용하고 구독·그룹·ACP를 CSE에 맡기는 운영상 이유를 보여준다. [기사](../submission/hackster-article.md) · [화면과 근거](../../pitch/README.md) |
| 8 | 심사자 가점 | **열림.** 운영진 공지와 팀 내부 대화는 확인했다. 프로젝트에 유익했던 공개 기술 교류의 검증된 링크가 필요하다. [제출 인계](../submission/handoff.md) |
| 9 | 인터뷰 | **열림.** 자원 구조, 통합 방법, oneM2M을 계속 채택할 이유를 답하는 자료와 시간 측정이 있다. 실제 질의응답은 배정된 인터뷰에서 이루어진다. [영문 Q&A](../submission/technical-qa.md) · [리허설](../../evidence/presentation/acceptance.json) |
| 10 | 보안·프라이버시 | **Expert, 시험 환경 범위.** TLS와 역할별 ACP의 허용·거부를 실증했다. 시설 제거 후 원래 정비 AE는 보존된 관측과 ACK 읽기에 각각 4103을 받고 운영 AE는 같은 원본에 각각 2000을 받았다. [TLS](../../evidence/runtime/cse-mqtt-tls-smoke.json) · [권한 회수](../../evidence/runtime/facility-retirement.json) |
| 11 | 데이터 상호운용성 | **Expert, PM2.5 범위.** 두 어댑터에서 TS-0023 airQualitySensor 표준 자원의 µg/m³ 정수형 측정값을 실제로 발견·조회했다. CO₂와 풍량은 별도 단위로 보존된다. [표준 매핑과 증거](../standard-model.md) |
| 12 | CSE 전환·연속성 | **Expert, 단일 호스트의 두 CSE 범위.** 가용성 감지 후 대체 CSE로 자동 전환, 미해결 상태·구독·권한 복원, 한 번의 명령 효과와 측정된 서비스 중단을 확인했다. 독립 정상 실행에서 관측한 읽기 중단은 0.173초였다. [독립 재실행 기록](../../evidence/runtime/handover/independent/index.json) |
| 13 | oneM2M–MEC 앱 배포 | **Expert, 두 논리 MEC 호스트 범위.** 운영자가 목적지를 지정하면 실제 Sandbox 컨트롤러가 각 호스트에 MN-CSE와 정비 앱을 Helm으로 설치했다. 두 곳 모두 Mcc 등록과 새 사건 처리에 성공했다. 물리 VM은 한 대다. [배포·복구 영수증](../../evidence/runtime/option-c/index.json) |
| 14 | 연합학습 | **열림.** 실제 ESTIMED VM, 분산 클라이언트의 학습·집계 및 동적 선택·장애 회복형 복수 라운드 증거가 없다. 사이트 간 학습의 필요와 데이터가 확인되면 평가한다. [적용 근거](../extension-decisions.md) |
| 15 | 위치 서비스 | **열림.** 고정 설비는 시설·구역·자산 ID로 식별한다. 네트워크·MEC 위치 이벤트로 정비 배정이나 이동 정책이 바뀌는 실증이 필요하다. 35%는 기계축 개도다. [센서 응답](../../evidence/runtime/option-c/native-services.json) |
| 16 | MEC 서비스 | **Expert.** 시설의 oneM2M 요청 한 건으로 실제 033 제공자 등록과 046 구독을 각각 201로 생성하고 200으로 재조회했다. 테스트 콜백 204로 연결을 확인했다. 독립 가상 센서의 35%는 별도 046 GET에서 받았고, 같은 명령에 연결된 작업지시서가 3판에서 4판으로 갱신됐다. 브리지 재시작 후 동일 구독을 재사용했고 시험 후 삭제를 확인했다. [단일 실행 영수증](../../evidence/runtime/option-c/commissioned-sensor-roundtrip.json) |
| 17 | AI 에이전트·MCP | **Expert, 실제 oneM2M 워크플로 범위.** 독립 모델이 저장·실행·재조회 세 도구를 골랐고, Codex는 별도 실행에서 같은 세 작업을 수행하는 플러그인 도구를 선택했다. 저장한 버전과 원래 CIN은 재시작 후 재조회됐으며 오래된 관측으로 새 명령은 0건이었다. [모델별 영수증](../../evidence/agent/scenario-authoring/README.md) |

실제 시설에 관한 외부 자료는 배기 성능을 확인할 필요를 뒷받침한다. 가상 측정값으로 선별한 점검 우선순위의 현장 효과와 관리자의 무도움 첫 사용성은 별도 연구 과제다. 설정 시험에서는 보존 작업장의 두 구역과 자체 센서 바인딩을 코드 수정 없이 활성화·재시작·재실행했다. 후속 명령 시험에서는 같은 사건에서 이미 지난 명령의 응답이 새 점검을 덮어쓰지 않았다. [시설 설정 실행](../../evidence/agent/facility-onboarding.json) · [세 번째 시설에서 동일 정비 앱 실행](../../evidence/agent/facility-worker-generalization.json) · [연속 명령 실행](../../evidence/runtime/maintenance-command-followup.json) · [현장 문제와 배포 선택](../mec-application-contract.ko.md)

## 동결본 검증과 외부 제출

실행 또는 완성된 매체로 Expert를 확인한 항목은 **1·2·3·5·7·10·11·12·13·16·17번, 11개**다. **4번**은 영문 원고의 본문·도해·근거가 Expert 수준이며 실제 Hackster 게시 화면을 확인해야 한다. **6번**은 Proficient, **8·9·14·15번**은 열린 항목이다. 이 분류는 합산 점수나 수상 예측으로 환산하지 않는다. [일곱 독립 검토 결과](review-ledger.json) · [외부 제출 인계](../submission/handoff.md)

새 체크아웃에서 실제 ACME를 설치하고 운영·정비 흐름, 세 번째 시설 재사용, 시설 제거 후 권한 회수를 재현했다. 테스트 90개 및 하위 테스트 29개가 통과했다. 최종 대시보드의 ‘Run scenario’로 만든 새 사건에서는 100% 명령과 ACK 뒤에 360 m³/h가 측정됐고, 독립 개도 35%가 도착하자 같은 열린 작업의 점검 순서가 바뀌었다. GitHub에 게시된 파일 17개를 로그인 없이 끝까지 읽어 원본 바이트와 비교했다. [클린 설치](../../evidence/release/final-work-order-acceptance.json) · [브라우저 재시연](../../evidence/release/dashboard-replay.json) · [공개 파일 검증](../../evidence/release/final-work-order-publication.json)

클라우드 기록은 각 실행 당시의 배포 판본을 검증한다. MEC 센서 연동기의 소스는 이번 측정 순서 보강 판본과 같다. 변경한 운영·정비 워커 및 정비사 화면은 로컬 ACME와 가상 장비로 검증했다. 가상 장비로 입증한 범위에는 실제 설비 고장률과 비기술 관리자의 무도움 첫 설치 성공률이 포함되지 않는다. [클라우드 실행과 소스 해시](../../evidence/runtime/option-c/commissioned-sensor-roundtrip.json) · [로컬 측정 순서 재검증](../../evidence/runtime/observation-sequence.json) · [정비사 회복 근거 확인](../../evidence/runtime/field-recovery.json)
