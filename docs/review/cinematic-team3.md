# Team 3 — cinematic package and multi-application review

검토일: 2026-11-18. 담당 기준 **8, 9, 10, 17**. 기준 원문은 organizer PDF SHA-256 `42b38857fffae7c92739f84440b9db020ec6b79897c0f70db64c465ffd2cdfad`와 대조했다. 아래 한국어 설명과 인수 절차는 검토자의 요약·권고이며 공식 추가 채점 규칙이 아니다. 점수·총점·수상 가능성을 산출하지 않았다.

**판정:** 새 다중 앱 실행과 5분 영화에서 Team 3의 새 제품 실행 차단 결함은 발견하지 않았다. #10과 #17은 아래 한정된 실제 실행 범위에서 Expert 서술 충족을 지지한다. #8과 #9는 실제 외부 활동이 없어 열린 상태다. 최종 패키지 인수에는 캡처 도구 변경 이력, 발표 시간표, 실제 게시된 링크 확인이 남는다. 45초 PR 영화는 이번 판정 대상이 아니다.

## 검토 범위와 고정 식별자

시작 시 Git HEAD는 `1a0400cf00c7d64034b97540bc9bf1b7c4c445e8`였다. 새 소스·기사·영화는 작업 트리 또는 untracked 상태이므로 이 HEAD를 새 패키지의 immutable release라고 부르지 않는다.

| 파일 | 검토한 SHA-256 |
| --- | --- |
| `src/opensoom/multiapp.py` | `f98d90fae2525f6dbf512a6439506367a7c1ba722b35f7f1f9ba833e3087aad2` |
| `tests/test_multiapp.py` | `7ae416d8ce96778dbd6b12944aad8058ca680a3b0df6e33c36b702a8329564e9` |
| `docs/multi-application-scenario.md` | `aa6cf09bff89e14962963632d0bca5b9a5c5f6c028019adedbabfd8821e89e49` |
| `docs/submission/hackster-article.md` — 검토 중 문구 수정 후 | `63edb6d121fb8578a43e14da3e2376d200184a4feaa9fa45fbc6f25b4957dd1b` |
| `evidence/runtime/multiapp/index.json` | `1a971c9915d4725ee76e3f4a4e23a24ed18928f2e1ac4d3bebef2074fef2f25c` |
| `evidence/runtime/multiapp-revalidation/index.json` | `483f24e1529d90fafe44439e803791301c053964ca39a0f1b7b76fce8e8784ac` |
| `evidence/video/cinematic/dashboard-recordings.json` | `7fe7f051d65069dbb8369529d1818f7d48cfad13a2405471483ce6c97c22f9d6` |
| `deliverables/video/openSoom-demo-5min.mp4` | `da78876a685750be257dc142e383f72aea4a76c607f980d1c92dc2765ee33987` |
| `evidence/video/cinematic/demo-qa.json` | `4d9e8fc6ec265ef34efbbfb98aa3515af7d60c961043f66d0bc592cd326bd440` |

기사의 최초 검토본 해시는 `f3a1e6f7ec169ea7bc24e48b289efa1ad8e6546e135f9aa7d3145146b5e5d71b`였다. 아래 C3-001은 변경 후 다시 읽어 종료했다. 이 보고서는 나중 수정본에 자동 승계를 부여하지 않는다.

새 모델 호출, 서비스/CSE 상태 변경, 외부 메시지, 제품·기사·미디어 수정은 하지 않았다. 작성 파일은 이 보고서뿐이다. 현재 관련 tracked `src`, `plugin`, `profiles`, live-budget 설정은 기존 독립 closeout `ca10412ed1da62b92684e8163c2b6d092f450a5f` 이후 HEAD까지 변경이 없어 기존 검증의 명시된 범위를 재사용했다. 새 untracked `multiapp.py`는 별도로 확인했다.

## 실제 실행과 주장 범위

- 원 영화 자료 **`ma-d1a54f066e`**는 이전 worker 소스 `48190fd748f55f576a136c82a60e9ea127ea540b857dd4422b434d53c686ee7a`에서 캡처됐다. 원본 ID·시각·21개 산출물 해시는 모두 보존되어 일치한다. 이 기록을 현재 소스와 동일하다고 주장하지 않는다.
- 수정 후 **`ma-b9129cb90a`**는 현재 소스와 8개 source hash가 모두 일치하며 실행 전후도 동일하다. 21개 산출물 해시가 일치한다. 세 시나리오 모두 서로 다른 operations/maintenance/device PID, 각자의 비관리자 AE origin, 동일 원본 CIN에 대한 서로 다른 read RQI, worker request/response RQI 일치를 확인했다. 각 사례의 6개 거부 요청은 실제 CSE `4103`이다. 기록상 자기 자식 프로세스가 종료됐고 기존 서비스 process record는 보존됐다.
- 두 실행 모두 recovery는 operations `verified_recovery`와 maintenance `observations_recovered_inspection_pending`, missing ACK는 `ack_timed_out`와 `inspection_required`, no recovery는 `unresolved_after_ack`와 `inspection_required`를 남긴다. 점검 작업이 관측 회복과 별개로 남는 것은 두 번째 앱의 실질적인 업무다.
- 독립적으로 `.venv/bin/python -m pytest tests/test_multiapp.py -q`를 실행해 **7 tests + 21 subtests**가 통과했다. 현재 소스는 stale/missing 관측이 양쪽 연속 표본 카운터를 끊는다. 단위 테스트는 실제 CSE 재실행 증거를 대체하지 않으며, 이번 검토자는 새 CSE 시나리오를 실행하지 않았다.
- 이 supplementary scenario는 **결정적 HTTP-loopback 실제 CSE 실행**이다. device publisher는 HTTP CSE create를 사용한다. 별도 native MQTT/TLS 캡처나 hosted-model 캡처의 기능을 이 실행에 합쳐 주장할 수 없다. callback은 알림을 힌트로만 쓰고 구성된 부모의 정확한 CIN을 각 origin으로 다시 읽는다. ACP는 주장된 로컬 origin에 대한 권한 검사이며 암호학적 장비 인증이 아니다.
- 새 worker의 no-recovery 자료는 ACK 값 100과 이후 `damper_pct=35`를 함께 남긴다. 반면 영화 learning dashboard 자료는 ACK 뒤 `damper_pct=100`, airflow `200 m³/h`다. 현재 영화는 이 두 실행을 별도로 소개하며 multiapp 장면에서 관측 댐퍼가 100이라고 주장하지 않는다. 이후 편집에서도 이 경계를 유지해야 한다.

## 기준별 Expert 대조

| 기준 | 공식 Expert 요지와 확인한 근거 | 판정·남은 조건 |
| --- | --- | --- |
| **8 Judge points** | 공개 포럼의 실제 교류에서 얻은 이점 또는 oneM2M 이해를 보여야 한다. `handoff.md`, `technical-qa.md`는 실제 교류가 없음을 명시한다. 자동 생성 문답, 내부 팀 검토, 게시 전 기사, 행정 문의는 이 근거를 만들지 않는다. | **OPEN — 실제 공개 교류 미검증.** 구체적인 기술 논점과 진짜 참여 내용·공개 URL·일시·이해 또는 적용 결과를 보존한다. |
| **9 Interview points** | 리소스 트리와 oneM2M 이점, 통합 방법론, 프로젝트를 계속할 때 oneM2M을 선택할 이유를 실제로 설명해야 한다. 기사·Q&A·영화는 준비 자료다. | **OPEN — 실제 인터뷰 미실시.** 영어 실연과 질문 응답의 실제 수행 근거가 필요하다. 내부 연습은 준비 검증으로만 표시한다. |
| **10 Security and Privacy** | 보안 프로토콜과 ACP의 결합: `cse-mqtt-tls-smoke.json`, `cse-https-smoke.json`의 TLS 1.3, 동일 리소스의 허용 read와 비특권 origin 거부, `release-acceptance.json/registered_AE_ACP_denials`의 실제 cross-facility read/diagnostic write `4103`, 역할별 ACP와 기존 owner/freshness 수정 closeout을 확인했다. 새 multiapp은 별도의 6개 실제 ACP 거부를 보강한다. | **한정된 secure single-installation에서 Expert 충족 지지.** 새 HTTP multiapp·distributed HTTP·API/callback까지 TLS로 보호됐다는 주장은 불가하다. origin 문자열/anonymous loopback MQTT는 production device authentication이 아니다. 기사와 영화는 현재 이를 구분한다. |
| **17 AI Agents & MCP** | 복수 도구의 조정, 복잡한 oneM2M 작업 흐름, 영속 상태: 실제 hosted `release-live-recovery.json`은 6개 모델 선택 도구 호출과 두 번의 결과 확인, `secure-live-no-recovery.json`은 6개 호출과 unresolved, `release-live-stale.json`은 5개 호출과 서버 거부를 남긴다. 공통 MCP 경로·service-owned run·실제 CSE 결과·기존 source/보안 closeout이 있다. `units-live.json`의 완료된 Codex 해석은 별도 과거 기록 해석이며 raw 형식 실패가 보존됐다. | **기존 한정된 실제 oneM2M/MCP 흐름에서 Expert 충족 지지.** 한 MCP 서버의 복수 도구 증거이며 multi-server routing/MEC 실행 증거는 아니다. 새 독립 앱의 deterministic 시연과 영상 제작은 모델 실행의 새 증거가 아니다. Codex CLI 검증은 사람의 첫 설치 또는 desktop usability 연구와 다르다. |

## 발견과 최소 수정

### C3-001 — 과거 incident/ACK와 현재 run의 command 목록을 혼동할 수 있는 기사 문장

- 기준: **17**, 관련 4/7. 최초 기사에 `same evidence view retains the earlier acknowledged command`가 있어 새 observer의 `read_evidence.commands=[]`에서도 같은 도구 응답이 과거 명령을 직접 제공하는 것으로 읽힐 수 있었다. 실제 계약은 현재 run의 최근 10개 명령이며 완전한 facility history가 아니다.
- 영향: 과거 ACK를 현재 run의 성공 증거나 최신 관측으로 잘못 제시할 수 있다.
- 최소 수정과 제품 이유: 과거 캡처에 출처를 붙이고 run/incident 범위를 구분한다. 필요한 정보의 의미를 바꾸지 않고 설명의 재현성을 보존한다.
- **종료:** 수정 기사 `63edb6…`는 historical captures, original runs, 새 dashboard의 별도 run/command evidence를 명시한다. 원 실패나 이전 model 답변을 소급 변경하지 않았다. 추가 inference는 필요 없다.

### C3-002 — 영화 이후 capture tooling 변경을 final provenance에 분리해야 함

- 기준: **17**, 관련 5/6. 영화 자체 hash와 QA의 18개 source hash 중 16개는 현재 일치한다. 다음 두 캡처 도구만 달라졌다.

| 도구 | 영화 QA가 보존한 hash | 검토 시 현재 hash |
| --- | --- | --- |
| `capture_demo.py` | `0306390f8bcc8e2535426ea10d748e601e565aafe524b6f2661949a514fa38bc` | `35710d7d62114e9c0233395e4b1e594953e7d6db11bbba1ffdcf462eb9df6e39` |
| `capture_demo.cjs` | `6577dbcd93987bd846dea7b9334564600d3b98676f8f8636baa48184f02f9296` | `4a18b611f068273d932ab994accdc2b96b6a0b69a41ebce763f5e136d561773d` |

- 영향: 현재 도구와 영화 캡처 도구의 동일성·완전한 재현성을 잘못 주장할 수 있다. 이것만으로 원 WebM나 MP4의 진위가 무효가 되지는 않는다.
- 최소 수정: 원 QA hash와 원 rush/run을 보존하고, 변경 이유·영향 및 새 도구의 별도 사용 범위를 final provenance에 기록한다. 원래 hash를 현재 값으로 덮어쓰지 않는다. 같은 영상에 새 model 호출/재촬영은 필요하지 않다.
- 검증: final snapshot에서 MP4/rush/source mapping을 다시 검사하고, 두 hash 차이는 명시된 delta로만 남긴다. **OPEN — provenance follow-up; 제품 실행 blocker 아님.**

### C3-003 — 5분 영화 상영에 맞춰 발표 계획을 다시 배분해야 함

- 기준: **9**, 관련 5. 검토한 `technical-qa.md`는 4:30–6:18에 108초 구 영화를 배치하고 12분 발표라고 쓴다. `handoff.md`도 그 구 영화를 지칭한다. 같은 설명에 300초를 대입하면 **15분 12초**가 되어 명시된 10–15분 발표 범위를 넘고 질문 시간을 줄인다.
- 최소 수정: 새 영화 링크와 함께 총 발표 10–15분 안으로 구간을 다시 배분한다. 예를 들어 맥락·문제 1분, 5분 영화, 리소스/통합/권한 설명 3분, 결과·다음 실증 2분으로 11분 발표를 연습할 수 있다. 영화와 같은 내용을 반복하는 기존 구간을 줄이면 된다.
- 검증: 실제 소리 공유·전환·재생을 포함한 영어 연습을 시간 재어 기록한다. 숫자와 용어를 설명하는 담당자, 질문 대비 자료, 최종 링크를 함께 확인한다. **OPEN — handoff correction; 알고리즘 변경 불필요.**

### C3-004 — 공개 기술 교류 없이 #8을 종료할 수 없음

- 기준: **8**. 현재 자료는 외부 대화를 만들어내지 않았다고 정직하게 명시한다. 구현/영화의 발전은 실제 공개 교류 근거가 아니다.
- 최소 다음 행동: 별도 승인된 공개 채널에서 실제로 필요한 한 가지 논점을 논의한다. 예를 들어 ACME의 denied group aggregate와 개별 진단 read의 구분, 또는 SDT 단위 매핑의 한계를 실제 request/response와 함께 설명하고 기술 피드백을 구한다. 억지 질문이나 승인받지 않은 자동 게시를 만들지 않는다.
- 검증: 실제 public URL, 당사자·시각·기술 내용, 얻은 이해 또는 프로젝트에 적용한 점을 보존한다. 답변을 얻지 못하면 그 상태 그대로 남긴다. **OPEN — external interaction; source-release blocker와 별개.**

### C3-005 — 인터뷰 수행과 일정 확정은 준비물과 구별해야 함

- 기준: **9**. 기사·영상·Q&A는 준비되어 있으나 실제 심사 설명·응답 증거는 없다. 로컬 handoff에 따르면 public deliverables는 11월 20일, slide upload는 22일, interview는 23–25일이다. 정확한 cutoff/timezone 및 팀별 PICK은 이 검토에서 별도 확인하지 않았다.
- 최소 다음 행동: 실제 주어진 slot/PICK과 KST/UTC 헤더를 사람이 확인하고, 그 slot의 영어 발표·응답을 수행한다. 리소스 트리에서 한 fault CIN → 두 subscription → group context → scoped command → ACK → 후속 관측 → 서로 다른 두 앱 출력까지 설명할 수 있어야 한다. 이어서 왜 raw MQTT/custom API 대신 oneM2M인지, 언제 단일 앱이 더 단순한지, 다음 실제 adapter에도 oneM2M을 유지할 이유를 답한다.
- 검증: 승인된 녹화/실제 노트 또는 발표 사실·질문·응답·시각을 보존한다. 내부 rehearsal은 별도 label을 쓴다. **OPEN — actual interview; 준비물로 종료 불가.**

## 영화 확인과 남은 패키지 인수

검토한 MP4는 **300.000초, H.264 1920×1080 24 fps, AAC 오디오**다. 독립 전체 `ffmpeg -v error -xerror -nostdin -i … -f null -` decode가 exit 0으로 끝났다. 14개 장면 contact sheet, 영어 대본·SRT·source map을 읽었고 MP4에서 직접 7/134/185/230초 프레임을 decode해 실제 인코딩된 장면도 확인했다. 청취 기반 내레이션 품질이나 300초의 모든 프레임을 사람이 관람한 것으로 주장하지 않는다.

화면의 `Illustrative facility`, `Virtual equipment`, `Recorded dashboard`, `CSE readback`, `Archived hosted-model run`, 별도 outage reconstruction 표시는 현재 실행 범위와 맞는다. food 화면 `demo-ca9cc112d5`의 1,035 m³/h 회복과 learning 화면 `demo-6afdf15ef2`의 200/500 m³/h 미회복은 각각의 dashboard record와 맞는다. multiapp 장면은 원 `ma-d1a54f066e-no-recovery`의 CIN/출력을 쓰며 model 장면은 별도 `agent-43ac7ce3f8d7`의 6개 호출을 쓴다. 현재 영상은 독립 두 앱을 LLM이 조정했다고 말하지 않는다. 14.635초는 별도 중앙 단절 1회 실험이며 serving-CSE handover가 아니다.

최종 담당자는 다음의 구체적인 인수 증거를 남기면 된다.

1. 수정 후 같은 release SHA에 영화·대본·캡션·원 WebM·run IDs·기술 증거·capture-tool delta를 함께 고정한다. 다른 값을 같은 장면이나 같은 run으로 합치지 않는다.
2. 실제 발표 장치에서 영상 끝까지 재생하고 영어 음성/자막·screen share audio·읽기 쉬운 숫자를 확인한다. 간단한 실제 관람 기록은 decode 검사와 구분한다.
3. 새 45초 파일은 해당 담당자의 별도 내용/기술 검토를 받는다. 이번 5분 검토를 그 영화의 승인으로 재사용하지 않는다.
4. 승인된 GitHub push 후 정확한 영화 경로 두 개, 새 multiapp 소스/재검증 경로와 hash를 원격에서 확인한다. article의 intended URL만으로 게시 완료를 주장하지 않는다. Hackster 게시, Discord 메시지, 평가 시트·Drive 업로드는 기존 GitHub 권한으로 대신 승인된 일이 아니다.
5. 실제로 승인·게시한 뒤 logged-out article/repository/video 링크와 최종 article backlink를 확인하고, #8·#9는 실제 활동의 증거가 생길 때만 재검토한다. deadline, provisional permission 또는 준비된 원고는 organizer acceptance의 증거가 아니다.

원 실패한 Codex 답변·raw 형식 실패와 shared batch 회계는 이전 closeout의 상태를 그대로 유지한다. 이번 작업은 새 inference·회계 초기화·한도 확대를 하지 않았다. 실물 제어 권한이나 관측 우선 기본값도 변경하지 않았다.
