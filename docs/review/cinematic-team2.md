# Team 2 — cinematic deliverables review

검토일: 2026-11-18. 담당 기준: **4, 5, 6, 7**. 1차 검토 뒤 수정된 실제 300초 영화와 실제 45초 PR을 재검토했다. **현재 최종 품질 판정과 발견 종료는 말미의 ‘최종 두 master 재검토’를 적용한다.** 앞부분은 원래 발견·원래 해시의 이력을 보존한다. 이 문서는 영상·편집 산출물의 범위 검토다. 공식 점수, 전체 release 또는 외부 게시 완료 승인이 아니다. 아래 개선 조건은 공식 rubric의 추가 채점 규칙이 아닌 내부 acceptance 권고다.

## 1차 판정과 식별

**화면·기술 내용·재생 형식은 양호하다. 최종 export 전에 T2-CIN-01의 시점 라벨을 보완하고, T2-CIN-02의 촬영 소스 이력을 명확히 해야 한다. 실제 음성의 발음·억양은 이번 검토 환경에서 미검증이다.**

| 산출물 | SHA-256 |
| --- | --- |
| `deliverables/video/openSoom-demo-5min.mp4` | `da78876a685750be257dc142e383f72aea4a76c607f980d1c92dc2765ee33987` |
| `evidence/video/cinematic/demo-qa.json` | `4d9e8fc6ec265ef34efbbfb98aa3515af7d60c961043f66d0bc592cd326bd440` |
| `evidence/video/cinematic/demo-contact-sheet.jpg` | `949c67de7af8de5789c78e5201652e436eea8b30035412eb26f64e2c17c6c26d` |
| `deliverables/video/cinematic/demo/script.en.json` | `de71a21f9b5be5c1f38390c9fcb8a2b3919693c6be64df97f67b8f7169d3c4f7` |
| `deliverables/video/cinematic/demo/captions.en.srt` | `09f2b0bf935a91b50a885c51c2103fc064f752e8ee95e28afe22615f5a1431f5` |

직접 추출한 1080p 프레임을 0:03, 0:20, 0:40, 1:06, 1:25, 1:51, 2:13, 2:36, 3:02, 3:26, 3:50, 4:12, 4:34, 4:52에서 검사했다. 0:58–1:10과 1:59–2:11은 2초 간격 전이 프레임도 확인했다. 전체 프레임을 연속 실시간 시청했다는 주장은 하지 않는다. 모든 영상/음성 패킷은 `ffmpeg -v error -xerror -nostdin -i … -f null -`로 끝까지 독립 디코드했고 exit 0이었다.

## 관찰한 품질과 사실 범위

- 실제 파일은 H.264 1920×1080, 24fps, 7,200프레임, AAC 48kHz mono, 정확히 300초, 23,423,100바이트다. QA의 영화 해시는 현재 파일과 일치한다.
- 어두운 녹색·밝은 종이색 화면, 큰 제목·수치, 일정한 여백과 자막 띠가 일관된다. 핵심 값 360/900, 1,035/900, 200/500은 단위를 함께 읽을 수 있다. 실제 UI의 세부 글씨는 작지만 주요 결과는 크게 재진술한다. 종합적인 제품/기술 소개로서 제작 노력과 끝까지 이어지는 흐름을 지지한다.
- 14개 장면은 문제 → 실제 두 시설 조작 → 프로토콜 → 독립 두 앱 → 권한 → 실제 모델 → 중앙 연결 중단 → 도입으로 진행한다. 반복 화면만 나열하지 않고 회복과 ACK 후 미회복을 대비해 운영 의미를 설명한다. 정비 work order가 물리 검사 완료를 뜻하지 않는다는 설명도 적절하다.
- `dashboard-recordings.json`의 실제 촬영 run은 food `demo-ca9cc112d5`/`cmd-f9d8c1c6e245`/recovered, learning `demo-6afdf15ef2`/`cmd-f2dc39c093da`/unresolved다. 보존된 두 원본 WebM의 해시는 QA와 일치한다. 화면의 관측값과 run 표시는 이 기록에 대응한다.
- 1:19–1:39는 별도 secure test의 동일 CIN `cinMuPppv2mAm`에 대한 native MQTT/TLS CREATE 2001과 HTTPS RETRIEVE 2000을 설명한다. 실제 dashboard 촬영의 HTTP loopback 실행 전체에 TLS를 덧씌운 주장이 아니다.
- 2:25–3:17의 두 앱은 별도 원본 run `ma-d1a54f066e-no-recovery`, CIN `cinixzfLRPrDC`, 두 소비자의 서로 다른 request ID 및 서로 다른 출력 resource를 재구성한다. 화면의 식별자는 원본 기록과 일치한다. 이 원본을 현재 수정 소스 재실행 `ma-b9129cb90a`로 바꾸어 부르지 않는다.
- 3:17–3:37은 정비의 명령 쓰기와 운영의 work-order 쓰기 거절을 별도 앱 실행에, 다른 시설 observer 읽기 거절을 별도 product-role test에 대응시킨다. 로컬 asserted identity의 ACP 집행이며 production device 인증 완료가 아니다.
- 3:37–4:02는 과거 실제 hosted-model run `agent-43ac7ce3f8d7`의 discover → group → evidence → action → verify → verify 순서를 분명히 `Archived hosted-model run`으로 표시한다. 촬영 중 모델이 새로 실행됐거나 이것이 Codex desktop 대화 화면이라는 주장이 없다.
- 4:02–4:23은 14.635초의 별도 중앙 중단 실험을 `Recorded test reconstruction`으로 표시하고, 기존 serving CSE 유지와 local continuation을 설명한다. MEC/handover로 표시하지 않는다.
- 4:23–4:46은 account-free fixture와 검증된 macOS arm64 환경을 명시한다. 실제 시설의 물리 제어 전에는 구성·관측 검증이 필요하다고 말한다. 생성 시설 장면은 illustrative 표기, 실제 앱 장면은 virtual equipment 표기를 유지한다.

## 구체적 발견과 최소 조치

### T2-CIN-01 — 결과 요약과 같은 화면의 현재 관측 시점 구분

- **관련:** #5, S5-G2. **상태:** 보완 요청.
- **관찰:** 0:58에서 왼쪽은 이미 `1,035 m³/h observed`인데 오른쪽 실제 UI의 cooking line은 아직 360 m³/h다. 약 0:59–1:00에 UI가 1,035로 바뀐다. 이후 나레이션이 권한 검사·ACK·후속 관측을 설명하는 동안 화면은 최종 상태를 보여준다.
- **영향/제품 이유:** 최종 결과 요약이라는 의도는 이해되지만, 동일 시점의 관측값처럼 읽으면 순서와 값이 다르게 보인다. 결과 검증을 설명하는 제품인 만큼 단계의 시간 의미를 보존해야 한다.
- **최소 개선:** 운영 장면 왼쪽을 `Final outcome` 또는 `Recorded final result`로 표시하거나, UI의 실제 회복 전환에 맞춰 360→1,035를 바꾼다. 장면 전체 재촬영은 필요하지 않다.
- **검증:** 수정 export의 0:58, 0:59, 1:00 및 command/ACK/outcome 전이에서 요약과 현재 상태가 구분되는지 확인한다.

### T2-CIN-02 — QA 소스 해시와 현재 캡처 도구의 차이

- **관련:** #6, S5-G3/S6-G2. **상태:** provenance 보완 요청; 영화/원본 WebM 무결성 결함은 아님.
- **관찰:** QA source map의 다른 원본·기록·스크립트는 일치하지만, 현재 `scripts/cinematic/capture_demo.py`와 `capture_demo.cjs`는 QA 기록과 다르다. 현재 해시는 각각 `35710d7d62114e9c0233395e4b1e594953e7d6db11bbba1ffdcf462eb9df6e39`, `4a18b611f068273d932ab994accdc2b96b6a0b69a41ebce763f5e136d561773d`다. 촬영 뒤 PR 기능을 추가했는지는 이 해시 차이만으로 확정하지 않는다.
- **영향/제품 이유:** 촬영 당시 코드와 현재 재현 도구를 구분하지 않으면 현재 소스 전체가 원본 촬영 해시와 일치한다고 오해할 수 있다.
- **최소 개선:** 촬영 당시 원본 source snapshot/식별자를 보존하고, 현재 수정 목적·호환 범위를 별도로 기록한다. 원본 영화나 원본 run ID를 바꿀 필요는 없다. 이력 없이 예전 QA hash만 현재 hash로 덮어쓰지 않는다.
- **검증:** 최종 manifest에서 촬영 source와 현재 render/reproduction source가 각각 추적되며, 현재 실제 파일 해시와 맞는지 확인한다.

### 비차단 편집 권고 — 가장 빠른 자막 구간

80개 영어 cue의 최대 속도는 약 **24.9자/초**, 짧은 한 cue의 최대 속도는 약 **218단어/분**이다. 장면 평균은 약 124–170단어/분이다. 2:25 이후 independent-process 설명과 4:23 이후 설치 설명의 짧은 cue를 조금 길게 두거나 덜 나누면 영어 비원어민의 읽기 부담이 줄어든다. 이는 공식 속도 제한 또는 내용 실패 판정이 아니다. 추출한 프레임에서 자막 넘침·잘림은 보지 못했다.

## 음성 확인의 한계

실제 영화의 0:00–0:12 음성을 추출해 오디오 입력을 시도했지만 도구가 `you do not support audio input`으로 생략했다. 따라서 발음·억양·음악과 목소리의 청감 균형을 들었다고 판정하지 않는다. 독립 측정한 integrated loudness **−19.5 LUFS**, true peak **−5.2 dBFS**, LRA **2.0 LU**는 QA와 일치하며 clipping 근거는 없다. 80개 자막은 0.850초부터 298.934초까지 놓인다. 발화 소스는 oneM2M/MQTT/HTTPS/TLS/Codex를 명시적 음성 철자로 바꾸고 시스템 Samantha를 사용한다. 이것은 발음 의도를 확인한 것이며 청취 결과가 아니다. 마지막 확인에는 실제 플레이어에서 브랜드명·기술 약어·단위와 가장 빠른 설치 구간의 청감 검토가 필요하다.

## 기사 보정과 남은 공개 조건

편집자 역할에서 `docs/submission/hackster-article.md`의 historical learning-space 기록과 새 dashboard 촬영 run을 구분했다. 원본 영화 multiapp run `ma-d1a54f066e`를 보존하고, 현재 수정 소스의 별도 재검증 `ma-b9129cb90a`와 `evidence/runtime/multiapp-revalidation/index.json` 링크를 인접하게 추가했다. 이 기사 수정은 편집자의 자체 변경이며 독립 article closeout을 대신하지 않는다.

#4 기사, #5 영상, #6 저장소의 article backlink, #7 상호 연결된 공개 홍보 자료는 아직 실제 게시·공개 접근 조건을 별도로 확인해야 한다. 이 검토는 새로운 외부 공개, Hackster/영상 플랫폼 게시 또는 공식 Expert 종결을 뜻하지 않는다. 45초 PR의 실제 파일과 최종 영화 수정본이 도착하면 같은 문서에 후속 판정을 덧붙인다. 새 모델/API 호출이나 운영 runtime 변경은 하지 않았다.

## 최종 두 master 재검토

**최종 판정: T2-CIN-01과 T2-CIN-02를 해결로 종료한다. 두 실제 master의 제작 품질과 사실 정합성에 새 blocker는 없다. #5의 내재적 Expert 제작 서술은 충족한다. #4의 출판 원고 품질과 #7의 oneM2M 홍보 품질도 Expert 서술을 충족한다는 판단이다. 실제 외부 게시 상태는 이 품질 판정과 별도로 기록한다.** 4점/5점의 구분과 심사자의 최종 주관적 평가는 보장하지 않는다.

### 최종 식별과 독립 확인

| 산출물 | SHA-256 |
| --- | --- |
| `deliverables/video/openSoom-demo-5min.mp4` | `c47b134ce2202c57a6089cad7a262eb0e16927e69e58af9593c95dcc7b2158ab` |
| `deliverables/video/openSoom-pr-45s.mp4` | `7cd91a052221c4c54baccf7560bda93cb595b905c8aeab0c7d3e441051220960` |
| `evidence/video/cinematic/demo-qa.json` | `b6655fd79eca3ab7352c8913f792d8af7a62de2fa7e01eb97e9dcbe2562bf2bd` |
| `evidence/video/cinematic/pr-qa.json` | `2f2501a71b244340da99aa05688989b83fb164411e4c533e10c9c490149b77f5` |
| `evidence/video/cinematic/narration-qa.json` | `250be29e6636e950de45ac310d759d8139933021cb2df05b10be6eb0458b3aa7` |
| `docs/submission/hackster-article.md` | `63edb6d121fb8578a43e14da3e2376d200184a4feaa9fa45fbc6f25b4957dd1b` |

두 최종 파일을 다시 끝까지 독립 디코드하여 각각 exit 0을 확인했다. 두 QA의 현재 source map과 contact-sheet hash도 모두 실제 파일과 일치했다. demo는 300.000초/7,200프레임/23,331,960바이트, PR은 45.000초/1,080프레임/13,897,316바이트다. 두 파일 모두 H.264 1920×1080/24fps와 48kHz AAC이다.

실제 최종 PR에서 1.25, 3.45, 7.1, 11.4, 16.7, 25.7, 31.9, 36.8, 42.25초의 1080p 프레임을 직접 추출해 검사했다. 수정 demo는 58/59/60/149/274초와 갱신된 전체 장면 contact sheet를 확인했다. 기존 원본 take·원본 run·식별자는 바뀌지 않았다.

### 기존 발견 종료

- **T2-CIN-01: resolved.** 수정된 실제 영화 0:58–1:00에 왼쪽 1,035 수치 위의 **FINAL OUTCOME** 라벨이 보인다. 오른쪽 UI의 당시 360→1,035 전이와 최종 결과 요약을 구분한다. 별도 원본 장면·값을 다시 만들거나 조작하지 않았다.
- **T2-CIN-02: resolved, provenance scope.** `demo-qa.json/recorder_lineage`는 원래 두 capture hash를 보존하고, 현재 hash는 별도 source map에 둔다. 촬영 뒤 추가된 `--take food-unresolved`와 기본 demo 경로의 구별을 기록했다. 현재 Python/CJS를 읽어 PR 전용 분기와 기본 food `exhaust_fault` → learning `no_recovery` 경로, 공통 `shoot` 함수에 대응시켰다. 원 WebM 두 개의 기존 hash가 유지되고, 이전 master hash `da78876…`도 보존됐다. 현재 source의 새로운 촬영을 원본 run으로 소급 주장하지 않는다.
- **빠른 자막 권고: 개선 확인.** demo의 최대 cue 속도가 24.9→**20.7자/초**로 줄었으며 80개 cue는 겹치지 않는다. 축약 자막의 의미가 전체 발화 원고와 맞고, 가장 조밀한 독립 앱/설치 장면의 실제 새 자막을 확인했다. 남은 짧은 cue의 최대 약208단어/분은 공식 제한이나 blocker로 삼지 않는다.

### 45초 PR의 실제 품질

세 가지 Adobe motion source를 사용하는 renderer의 실제 입력 경로와 현재 source hash를 확인했다. 실제 출력 장면은 주방 → 기계 연결부 → 학습 공간으로 바뀌고, 두 실제 dashboard take 및 별도 multiapp 재구성과 조합된다. 생성 시설은 illustrative, 360/900 장면은 simulated telemetry, 앱 화면은 actual app/virtual equipment, 두 앱 그림은 separate multi-application run의 reconstruction으로 표시한다. 이 연결이 동일 runtime의 한 연속 촬영이라는 주장은 없다.

큰 제목, 짧은 문장, 녹색·아이보리 대비, 360/900과 200/500 단위, CSE를 거쳐 나뉘는 Operations/Maintenance, 실제 ACK 뒤에도 낮은 풍량, 마지막 프로젝트 로고와 읽기 쉬운 저장소 URL이 45초 안에 맞물린다. 25.7초의 실제 UI에는 ACK 수신과 unresolved 결과가 함께 보이며, 해당 PR 전용 run은 `demo-49a9dd79ed`, command `cmd-57931cb2b1ea`다. 값이 회복된 food demo의 다른 take를 이 미회복 장면으로 바꾸어 부르지 않았다. 불필요한 기술 문장으로 짧은 PR을 채우지 않으면서 oneM2M의 공유·재사용 가치를 소개한다.

PR의 10개 선택형 영어 `mov_text` cue를 실제 MP4에서 추출해 SRT와 정확히 같음을 확인했다. cue는 겹치지 않고 최대 **16.0자/초**, 마지막 종료는43.122초다. 선택형 CC를 켜지 않은 추출 프레임에 자막이 없는 것은 자막 누락이 아니다. 화면 자체의 핵심 메시지는 자막 없이도 읽힌다.

### 실제 음성에 대한 측정·ASR 범위

최종 AAC를 독립 측정한 PR은 **−17.5 LUFS/−1.6 dBFS true peak/LRA 5.5**, demo는 **−19.5 LUFS/−5.2 dBFS/LRA 2.0**으로 QA와 일치한다. clipping 근거를 보지 못했다. PR source는 Adobe Jennifer 영어 speech와 stereo score이며 편집 도구에 speech 구간별 music ducking이 구현돼 있다.

`narration-qa.json`은 실제 두 최종 master hash와 일치하는 **faster-whisper base.en, CPU int8의 offline ASR 결과**다. PR 9개 segment, demo65개 segment에서 두 시설·수치·단위·ACK 후 미회복·독립 앱·실제 모델 두 번 확인·중앙 중단·설치 설명이 의도한 순서로 인식됐다. `Open Zoom`/`OpenSUM`, `1M2M`, `code ex` 같은 고유명사 표기는 ASR의 오인 가능성을 갖는다. 이를 확인 없이 실제 발음 결함으로 단정하지 않는다. 자막은 브랜드명을 정확히 제공한다.

이 확인은 사람의 청취나 리뷰어의 직접 청감을 주장하지 않는다. 발음의 미세한 뉘앙스와 취향에 따른 음악 균형 평가는 제한돼 있지만, 실제 영어 발화·명료한 영어 자막·정상 음량과 디코드·내용 인식의 근거가 있다. 주관적 직접 청취를 별도의 새 공식 통과 조건으로 추가하지 않는다.

### 기준 4–7의 품질과 외부 상태를 구분한 판정

| 기준 | 내재적 품질 판정 | 별도로 남은 상태 |
| --- | --- | --- |
| **4 Quality of Article** | **Expert 품질 서술 충족.** 서비스·실제/가상 하드웨어 경계·자원 트리·프로토콜/권한·재현 명령·그림·두 시설 사례·독립 앱·문제 출처·추가 교훈·oneM2M 이점이 출판 가능한 영어 원고로 연결된다. 저는 원고 편집자이므로 이 품질 견해가 저자와 독립된 closeout은 아니다. 다른 팀의 원고 사실 readback을 함께 적용해야 한다. | Hackster에 실제 게시됐다는 증거는 없다. 게시 권한·실제 article URL·전송 후 페이지 이미지/링크 검사는 별도 handoff다. 미게시가 원고의 내재적 품질 실패를 뜻하지 않는다. |
| **5 Quality of Video** | **Expert 제작 서술 충족.** 실제 두 최종 master는 합리적인 제작 노력, 끝까지 볼 만한 흐름, 기사에 관심을 주는45초 PR, 내용을 종합하는300초 demo를 구체적으로 보여준다. 실제 앱 조작·별도 실행의 근거·영어 발화/자막·물리 가상 표시가 일치한다. | 새 remote revision에서 두 영화의 실제 공개 다운로드/재생 링크 확인은 아직 이 로컬 검토가 수행하지 않았다. 외부 video-host 계정에 게시해야만 이 내재적 제작 서술을 충족한다는 추가 조건은 만들지 않는다. |
| **6 Quality of Github** | 독립 목적 설명·설치/배포·소스 안내·한계·profile/adapter 확장·clean lifecycle 근거를 갖춘 저장소 품질은 **Expert 서술을 지지**한다. README는 영문 article copy와 두 영화로 연결된다. 현재 runtime을 새로 설치/실행했다는 주장은 아니며 기존 검증된 경로와 이번 문서/영상 변경 범위의 판단이다. | 새 기사·영상·source/evidence를 포함한 remote revision 검증은 main의 release check로 남는다. 실제 Hackster URL의 backlink는 게시 뒤 반영해야 한다. 현재 draft link를 이미 존재하는 Hackster URL로 부르지 않는다. |
| **7 Promotion of oneM2M** | **Expert 홍보 품질 서술 충족.** 원고·두 영화·README는 공유 CIN, native notification, group context, ACP, 실제 프로토콜 binding을 사용자가 이해할 업무 차이로 설명하고 표준 및 프로젝트 자료로 이어 준다. 단순한 oneM2M 로고 부착을 넘어 선택 이유와 재사용 가치를 추천하는 일관된 자료다. | 공개 링크의 최종 배포 상태와 실제 행사 제출은 별도다. 그 상태가 아직 pending이라는 이유로 이미 확인한 내재적 홍보 품질을 미달로 분류하지 않는다. |

내부 **S5-G2**의 실제 playable media/영어/가독성/가상 표시/사실 정합성을 지지하며, **S5-G3**의 원본 take·발화/SRT·renderer·asset provenance·source 이력도 이 식별 범위에서 지지한다. **S6-G2**의 준비 산출물 품질을 지지한다. GitHub push 및 실제 외부 게시 상태를 이 파일에서 대신 승인하거나 생성하지 않았다. 최종 점수와 전체17항목의 판단은 각 담당자의 공식 서술 대조 및 실제 행사 심사와 구분한다.
