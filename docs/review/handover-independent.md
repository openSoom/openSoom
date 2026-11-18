# Criterion 12 — independent handover review

2026-11-18, Team 1 / GPT-6.1 Sol Max. **판정: 아래 고정 소스와 한정된 실행 범위에서 #12 Expert 요건 충족을 지지한다. 남은 차단 사항은 없다.** 공식 점수·전체 릴리스·다른 기준의 승인은 아니다.

고정 소스 SHA-256:

- `src/opensoom/handover.py`: `c5b0a07fb7ff3e2845992e26200de8bd84463f37e286f5ad121fe353302f745c`
- `scripts/cse_handover_demo.py`: `d6a771af8ed36f4e8884e2794206fb5c1dd15f4ed3fdd40562806654cbc3b18d`

주최 측 원본 #12 Expert의 **availability 기반 자동 전환, state/SUB/security context 보존·복구, interruption 또는 loss 측정**을 직접 대조했다. 이 해시 이전의 실행은 역사적 정상 경로이며 최종 수정본의 대체 증거가 아니다.

| 실행 | 경우 | 결과 | 마지막 A 조회→첫 B 조회 간격 |
| --- | --- | --- | --- |
| 저자 `handover-b6e82ef69f` | 정상 | PASS | 0.164379초 |
| 저자 `handover-e19e38fe77` | 쓰기 전 1회 실패 주입 | PASS | 0.373669초 |
| **독립 `handover-6dbcd9ef97`** | 정상 | **PASS** | **0.173037초** |
| **독립 `handover-0e9d59cb52`** | 동일 실패 주입 | **PASS** | **0.379308초** |

저자 증거는 `evidence/runtime/handover/acceptance.json`, `failure-recovery.json`이다. [독립 실행 인덱스](../../evidence/runtime/handover/independent/index.json)의 두 JSON·A/B trace 총 6개가 독립 실행 디렉터리와 byte-for-byte 동일하고 해시와 일치함을 확인했다. 원본 trace 경로는 보존되므로 공개 복사본은 인덱스 설명대로 basename으로 찾는다. 네 실행 모두 source-before/source-after와 현재 고정 소스가 일치했다.

확인한 근거:

- **자동 trigger/실제 CSE:** operator 역할의 harness가 자기 A 프로세스만 계획 정지한다. B 선택·복사는 수동이 아니다. 실제 transport probe 두 번 실패 후 제어기가 preconfigured B를 준비한다. 서로 다른 실제 A/B CSE ID, 동일 logical URL의 A-backed200→503→B-backed200을 확인했다. source4103은 전환을 유발하지 않는 단위검사도 통과했다.
- **복구:** B에 새 CSE-local AE mapping·ACP·CNT·native SUB가 만들어졌다. logical facility ID, profile version, 마지막 관측/sequence, 열린 incident, pending command ID·원래 expiry가 보존됐다. B의 새 sequence4는 native callback과 해당 CIN의 권한 있는 재조회로 수용됐다. 보존 관측을 새 표본으로 세지 않는다.
- **fencing/replay:** actual source CSE-ID와 epoch를 검사한다. 옛 A 명령과 A가 새 B epoch를 가장한 명령은 거절됐다. B observer와 옛 A controller의 명령 쓰기는 실제 CSE4103이었다. 가상 효과는 한 번이며 DB reopen·중복 호출·실제 ACK 재시도 후에도 execution_count=1이다. ACK 충돌 후 GET도 device origin을 유지했다.
- **부분 복원 실패:** main이 발견한 activate-before-restore 창을 수정한 뒤 확인했다. durable `restore_pending`으로 목적지·snapshot을 고정하고 B에 idempotent 준비·readback을 마친 후 authority/snapshot/marker 삭제를 **한 SQLite 트랜잭션**으로 커밋한다. 준비 중 신규 상태/명령 갱신은 차단된다.
- **실패 주입의 정확한 의미:** 실제 B state write/readback2000 뒤 incident의 **HTTP dispatch 직전 synthetic transport failure 한 번**이다. CSE가 반환한 실제 장애라고 계산하지 않았다. 독립 실행에서 A/epoch1·stable503·B pending을 유지하고 다음 tick에 같은 snapshot을 재개, 준비 완료 후에만 B/epoch2로 전환했으며 resumed_after_failures=1이었다.
- **측정:** 표는 stop·준비·복구를 포함한 개별 관측 read gap이다. 평균·최대 지연·SLA가 아니다. 네 주입 sequence는 모두 수용됐지만 단절 중 연속 센서 생성 실험이 아니므로 무손실 스트리밍이나 전체 CSE history 복제를 입증하지 않는다. interruption 측정 요건에는 실행 근거가 있다.

`.venv/bin/python -m pytest tests/test_handover.py -q`를 독립 실행해 **13 passed**를 확인했다. 지속 복원 표식으로 새 controller가 같은 복원을 재개하는 검사, CAS 경쟁, stale/forged authority, scope/expiry/setpoint, 권한 오류 검사가 포함된다. source-CSE 바인딩과 ACK 재조회 origin 누락에 대한 교차검토 의견도 최종 소스·실행에서 해결됐다.

범위는 **별도 optional library와 logical endpoint의 application-managed serving-CSE 전환**이다. main Core/MCP 통합 handover, native AE-ID mobility, geographic/multi-host 배포, CSE 전체 복제, MEC/VM 이동을 실행한 것이 아니다. 두 CSE는 한 호스트의 loopback HTTP, AE origin은 신뢰된 로컬 주장이다. 살아 있는 controller/device가 공유하는 로컬 DB와 가상 actuator의 fencing이며, 분산 합의·controller/node DB 소실 HA·물리 보호를 입증하지 않는다. `docs/handover.md`는 이 범위를 구분한다.

최종 두 독립 실행은 자식 종료·임시 CSE 디렉터리 제거·기존 process-record 보존·A/B/callback port 닫힘을 확인했다. 초기 소켓 제한 시도는 capture 전에 실패했고 허용된 loopback 권한 심사 후 재실행했다. 새 LLM·유료 서비스·git·외부 발행 작업은 없었고 제품 파일도 수정하지 않았다.

main/Team4는 채택 extension/child gate에 이 최종 hash·정상/fault 증거·독립 검토를 연결하고 이전 defer/실패/실행 이력을 보존해야 한다. 구현 milestone 완료가 다른 경쟁 기준을 자동으로 닫지는 않는다.
