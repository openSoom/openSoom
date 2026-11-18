# Team 1 — multi-application scenario closeout

검토일: 2026-11-18. 담당 기준: **1, 2, 3, 11**. 사용자 최신 지침대로 각 Expert 서술의 적용 부분을 실행 증거에 대조했다. 이 판정은 공식 점수·총점·트랙 적용 또는 수상 가능성 판정이 아니다.

**최종 판정: 네 담당 기준은 아래에 한정한 실행 범위에서 Expert 요건 충족을 지지한다.** #3의 기존 복수 앱 근거 부족을 실제 독립 프로세스와 서로 다른 업무 결과가 보강했다. 최초 검토에서 발견한 회복 카운터 결함은 수정 소스와 독립 재검증으로 종료한다. 이번 HTTP 다중 앱 실행에 기존 MQTT/TLS·SDT 실행을 합쳐 하나의 실행이라고 주장하지 않는다. 전체 17항목, 영상 품질, 공개 게시 및 대회 제출 완료는 이 보고서의 승인 범위가 아니다.

## 식별한 검토 대상

- 시작 시 Git HEAD: `1a0400cf00c7d64034b97540bc9bf1b7c4c445e8`. 새 다중 앱 소스와 문서는 아직 untracked/수정 상태여서 이 HEAD가 해당 내용의 식별자는 아니다. 아래 캡처의 SHA-256 및 보고서 말미 파일 해시로 범위를 고정한다.
- 최초 영화/시나리오 캡처: `evidence/runtime/multiapp/index.json`, **`ma-d1a54f066e`**, 원본 `multiapp.py` SHA-256 `48190fd748f55f576a136c82a60e9ea127ea540b857dd4422b434d53c686ee7a`.
- 수정 후 실제 CSE 캡처: `evidence/runtime/multiapp-revalidation/index.json`, **`ma-b9129cb90a`**, 수정 `multiapp.py` SHA-256 `f98d90fae2525f6dbf512a6439506367a7c1ba722b35f7f1f9ba833e3087aad2`.
- 두 캡처 각각 source-before/source-after 8개 일치, 현재 수정 실행의 8개 소스 해시 일치, 각각 산출물 21개 해시 일치. 최초 캡처와 원래 프로세스/사건 ID는 보존됐다.
- 기존 `evidence/release/source-reconciliation.json`의 runtime/설정/프로필/plugin 파일은 현재 해시와 모두 일치했다. 따라서 이전 팀1 `final-team1.json`과 `final-closeout-team1.json`의 MQTT/TLS·HTTPS 및 PM2.5 SDT 범위 판정을 이어받되 이번 새 앱의 지원 기능이라고 바꾸어 말하지 않는다.

## 엄격 Expert 대조

| 기준 | 공식 Expert 서술의 적용 부분 | 구체적 실행 근거와 판정 |
| --- | --- | --- |
| **1 — Innovative use of oneM2M** | group·announcement·pollingChannel 같은 복합 서비스를 하나 이상 사용 | **충족.** 새 실행에서 운영 앱의 native `/fopt` 요청은 실제 두 observation CNT에 대한 `m2m:agr/m2m:rsp` 성공 결과를 받았다. CSE가 개별 소비자 callback에 SUB 통지를 전달하고 각 앱이 정확한 CIN을 재조회한다. 근거: 두 run의 각 `operations-state.json` 첫 transition `native_group`, `*-requests.jsonl`, `result.json/subscriptions`. pollingChannel을 추가해야 한다는 요구는 없다. |
| **2 — Appropriate communication protocols** | 기기와 앱이 통신 조건에 따라 서로 다른 복수 프로토콜 사용 | **프로젝트의 명시된 두 실행 범위로 충족.** 기존 실제 secure single profile에서 어댑터 observation/ACK/SDT 갱신은 native CSE MQTT/TLS, 앱 CSE 조회·명령은 HTTPS이다. 발행 중심 장비 통신과 앱 request/response의 선택 이유가 문서화돼 있다. `cse-mqtt-tls-smoke.json` 및 `release-acceptance.json/checks/actual_product_mixed_protocol_trace`의 native primitive/동일 자원/CA 검사와 이전 독립 검토를 유지한다. **새 다중 앱 캡처는 HTTP-loopback뿐**이며 프로토콜 다양성의 새 단독 증거로 계산하지 않는다. |
| **3 — Innovative scenarios** | 복합 기기 → CSE → 복수의 복합 앱, 기기/앱이 oneM2M 공통 기능을 재구현하는 대신 활용 | **수정·재검증된 시나리오 범위에서 충족.** 가상 배기 설비는 다구역 풍량·PM2.5·CO₂·팬 보고와 댐퍼 제어, 장비 측 명령 허용/만료 검사, ACK 및 후속 결과를 결합한다. 운영 앱은 native 그룹 맥락·프로필·신선도·명령·ACK·관측/timeout 상태를 처리한다. 별도 정비 앱은 동일 사건으로 독립 CSE work order를 만들고 운영 회복 뒤에도 검사를 유지한다. 이는 UI 두 개/AE 수만으로 한 판단이 아니다. 서로 다른 PID·origin·callback·checkpoint·출력·쓰기 권한 및 실제 실패 분기를 확인했다. native SUB가 두 소비자에게 전달하고 CSE가 group·자원 저장·ACP를 집행한다. 후술 T1-C01 수정 전의 일반 회복 주장에는 결함이 있었으므로 현재 판정은 새 소스/재검증을 포함한다. |
| **11 — Data interoperability/discoverability** | semantics/SAREF 또는 TS-0023 SDT 같은 고급 모델 사용 | **기존 PM2.5 한정 구현 범위에서 충족.** `cod:aiQSr`, `cnd`, TS-0023 v5.6.0 `airQualitySensor.pm25`의 정수 µg/m³, 실제 type28 discovery, 잘못된 타입 rsc4000 거절, 두 프로필/어댑터의 앱 읽기를 이전 독립 검토에서 확인했다. 기존 관련 소스 해시는 유지된다. `release-acceptance`는 learning-b, `release-live-recovery`의 `read_evidence`는 food-a를 증명한다. SDT-G1/G2/G3 충족 판정을 유지한다. 새 multiapp worker 자체가 SDT discovery/모델을 사용한다는 증거는 없으며 그렇게 주장하지 않는다. |

#3의 ‘복합성’에는 공식 PDF에 없는 프로세스 수·코드 줄 수·물리 장비 수의 추가 기준을 만들지 않았다. 가상 장비가 허용된 조건에서, 독립 제어 검증과 다른 권한/업무를 가진 실제 여러 앱의 실행을 서술에 대응시켰다. 각 기준의 정확한 4점/5점은 심사자의 판단이다.

## 독립 실행·전달·업무 결과 확인

최초 run에서 각 시나리오별 operations/maintenance/device PID는 각각 `60692/60693/60695`, `60703/60704/60707`, `60741/60754/60755`로 달랐다. 수정 후 run도 각 시나리오에 서로 다른 세 PID를 기록한다. 각 프로세스는 자기 non-admin AE origin으로만 CSE에 요청했다. 원래 run은 총 58개의 worker request/response trace를 독립 확인했으며 `CAdmin` 요청이 없었다. 관리자 provisioning은 worker와 분리돼 있다.

최초 source CIN의 `ri`는 recovery `cinr4He2VekLk`, missing-ACK `cinNkbldNRC9v`, no-recovery `cinixzfLRPrDC`이다. 두 소비자의 native receipt가 같은 `ri`를 포함하고, 각자의 권한으로 재조회한 authoritative 결과도 같은 `ri`이며 request ID는 다르다. 수정 후 run에서도 같은 상관관계를 다시 확인했다. 단순 공통 event_id 텍스트만 비교한 판정이 아니다.

| 실제 캡처 사례 | 운영 앱의 CSE 출력/상태 | 정비 앱의 별도 CSE 출력/상태 |
| --- | --- | --- |
| recovery | 명령 1개·ACK 1개·서로 다른 후속 정상 표본 2개 → `verified_recovery` | `observations_recovered_inspection_pending`; 검사 업무는 유지 |
| missing_ack | 명령 1개·ACK 0개 → `ack_timed_out` | `inspection_required` |
| no_recovery | 명령 1개·ACK 1개·후속 불량 표본 2개 → `unresolved_after_ack` | `inspection_required` |

각 run에서 시나리오마다 maintenance 제어 쓰기, observation 위조, outsider 읽기, operations의 work-order 쓰기, maintenance의 operations-report 쓰기, device의 SUB 생성에 대해 실제 **4103 여섯 건**, 총 18건을 확인했다. 성공 결과는 해당 앱 origin의 CSE readback으로도 확인됐다. 모든 worker error 목록은 비었고 종료·기존 runtime record 보존을 확인했다. 이는 trusted-loopback에서 주장된 origin에 대한 ACP 집행이며 암호학적 장비 신원 인증은 아니다.

## 발견·수정·재검증: T1-C01

- **기준/관련 내부 게이트:** #3, 추가 다중 앱 시나리오의 회복/실패 계약 및 S1-G2 계열 검증 의미. 기존 main service가 같은 결함을 가진다는 판정은 아니다.
- **관찰:** 최초 소스 `48190…`의 `operations_observation`은 stale/missing을 즉시 반환하면서 기존 recovery/unresolved 표본 수를 지우지 않았다. `fresh nominal → missing → fresh nominal`, `fresh nominal → stale → fresh nominal`을 메모리 전용 probe로 실행하면 중간 count=1이 남고 마지막에 `verified_recovery`가 됐다. 최초 테스트 6개/17 subtests는 통과했지만 이 혼합 순서를 검사하지 않았다.
- **영향/제품 필요성:** 데이터 공백이 끼었는데도 문서의 ‘연속된 신선한 정상 표본’처럼 회복을 설명할 수 있었다. 시설 관리자와 별도 정비 앱이 검증 결과를 신뢰하려면 실제 counter 의미가 계약과 같아야 한다.
- **최소 수정:** main이 ACK 대기 중에는 invalid 관측을 포함해 버퍼링하고, ACK 이후 판정에서 stale/missing이 recovery/unresolved streak를 모두 초기화하도록 바꿨다. 새로운 제품 기능을 추가하지 않았다.
- **독립 재검증:** 수정 소스 `f98d90…`를 읽고 `.venv/bin/python -m pytest tests/test_multiapp.py -q`를 실행해 **7 passed, 21 subtests passed**를 확인했다. 새 네 조합(정상/불량 × stale/missing)에서 invalid 관측이 streak를 끊는다. 추가 메모리 probe에서 ACK 이후 nominal→missing/stale→nominal은 `awaiting_outcome`, count=1로 남았고, ACK 도착 전 버퍼에 missing이 섞인 경우에도 같았다. 이는 새 native 혼합 센서 실험이 아니라 isolated unit/probe 증거이다.
- **실제 CSE 재검증:** `ma-b9129cb90a`는 수정 소스와 일치하고 기존 recovery/missing_ack/no_recovery 세 native 시나리오를 다시 통과했다. 8 source/21 artifact 해시, 세 프로세스·분리 origin·상관관계·native service·18 ACP 거절·정비 분기·cleanup을 다시 확인했다.
- **최종 상태:** **resolved, scoped to the identified corrected source and revalidation.** 최초 영화 run을 수정 후 run인 것처럼 재명명하지 않는다. 현재 기사에서 지정한 최초 run의 캡처된 세 결과는 그대로 유효하다.

## 영어 기사 사실 검토

검토한 Hackster 초안의 multi-application 절은 실제 증거와 일치한다. 세 프로세스/등록 AE, 같은 CIN의 서로 다른 소비자 재조회, native fan-out, 운영 명령과 CSE 거절, 회복 후에도 유지되는 검사 업무, HTTP-loopback 및 dashboard/LLM runner와의 분리를 명시한다. 이번 실행을 실제 모델이나 secure MQTT/TLS 실행이라고 부르지 않는다. 추가로 확인한 기사 사실 오류는 없다.

원래 `ma-d1a54f066e`를 보존된 실행으로 링크하는 것은 정확하다. 현재 수정 후 동작의 식별자는 별도 `ma-b9129cb90a`이다. 업데이트된 기사·영상에서 ‘최신 소스의 정확한 run’이라고 표현하려면 새 기록을 함께 인용해야 한다. 초안의 공개 GitHub 링크가 게시 후 실제 접근 가능한지와 Hackster/영상 업로드 상태는 main/Team2의 공개 검증 항목으로 남는다.

## 판정의 범위

소프트웨어 CSE·native notification·요청·권한·각 앱의 상태 전이는 실제 실행이다. 센서/댐퍼/물리 배기 반응은 가상이다. 건강 효과·인증된 환기 성능·multi-host·MEC·serving-CSE handover·FL·geolocation을 입증하지 않는다. native group 성공은 장비 ACK/회복과 구분하며, 예전 group member denial의 수동 진단 fallback을 native mixed aggregate라고 바꾸어 말하지 않는다.

현재 팀1의 추가 동작 차단 사항은 없다. 경쟁 기준의 최종 닫힘은 본 보고서의 특정 근거와 범위로만 기록해야 하며, 전체 milestone 완료나 다른 팀 기준을 대신하지 않는다. 이 검토는 새 LLM 호출, live CSE/시설 변경, 외부 발행을 하지 않았고 제품/기사/영상 파일을 수정하지 않았다.

## 검토 시점 파일 SHA-256

- `src/opensoom/multiapp.py`: `f98d90fae2525f6dbf512a6439506367a7c1ba722b35f7f1f9ba833e3087aad2`
- `scripts/cse_multiapp_smoke.py`: `a449d1a6168a120eda618c3cd940a79a6c2cce616abcfbec3f49f16c1df36ebd`
- `tests/test_multiapp.py`: `7ae416d8ce96778dbd6b12944aad8058ca680a3b0df6e33c36b702a8329564e9`
- `docs/multi-application-scenario.md`: `aa6cf09bff89e14962963632d0bca5b9a5c5f6c028019adedbabfd8821e89e49`
- `docs/submission/hackster-article.md`: `f3a1e6f7ec169ea7bc24e48b289efa1ad8e6546e135f9aa7d3145146b5e5d71b`
- `evidence/runtime/multiapp/index.json`: `1a971c9915d4725ee76e3f4a4e23a24ed18928f2e1ac4d3bebef2074fef2f25c`
- `evidence/runtime/multiapp-revalidation/index.json`: `483f24e1529d90fafe44439e803791301c053964ca39a0f1b7b76fce8e8784ac`
- `AGENTS.md`: `c644b2587575e9947cb1820be6a6aaf0a94b6cffb7d91a1a6429103ed0c1af47`
- `docs/hackathon/rubric-baseline.json`: `2eddd5ef6bb2bf7bb9354b92a432512546be3b522e3f84724d016b4dd2055a94`
