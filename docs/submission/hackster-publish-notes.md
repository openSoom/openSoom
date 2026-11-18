# Hackster paste and asset notes

Use `docs/submission/hackster-article.md` as the English article body. It contains full source URLs, immutable public image URLs and a text resource tree; no repository-relative links or Mermaid renderer are required. Place the 720p work-order film first in the demo-video field. After the release is pushed, open the article’s source and video links in a signed-out browser before submitting the public article URL.

Suggested project summary: **Connect ventilation evidence, authorized actions and verified results across vendors and facilities with oneM2M and agent tools.**

Hardware field: **No physical hardware required for the demonstration.** Fans, dampers and sensor measurements are virtual. A Mac arm64/Python 3.12 environment is the verified source-checkout route; other OS or real devices need separate acceptance.

Software field: openSoom source, ACME CSE 2026.5.3, Python 3.12, uv, OpenSSL, MCP and Codex CLI 0.166.0. Use the repository lockfiles for exact library versions. The deterministic demonstration requires no paid API account. Actual inference uses separately configured credentials and finite persistent accounting.

## Assets to place

| Position | Asset | Verified status |
| --- | --- | --- |
| Main demo / evaluation film | `deliverables/video/openSoom-work-order-720p.mp4` | English, 1280 × 720, 104.938 seconds. Console ACK, airflow, shaft position, work order and expanded receipt accompany the corresponding narration. |
| Near the opening | `deliverables/video/openSoom-pr-45s.mp4` | Actual 45-second master reviewed and published; anonymous full download matches the master hash |
| Extended historical walkthrough | `deliverables/video/openSoom-demo-5min.mp4` | Actual 300-second English demo reviewed and published; anonymous full download matches the master hash |
| Current work-order image | `evidence/video/work-order/dashboard-order.png` | Actual screenshot of the same work order as the 720p demo. Upload beside the current main case or retain the pinned image URL. |
| Opening image | learning-space dashboard image already linked in the body | Original application screenshot; virtual measurements, actual software |
| Architecture | source-mapped distributed-lab image already linked in the body | Explanatory geometry; separate processes versus logical/resource cards are captioned |

For the current film, verify the complete public MP4 against SHA-256 `9ca85b4c3b7eff22f50333c3f2119aa532146c3c2c6783ff9313568a644d1628`. Check the 100% ACK at 29.19 s, 360 m³/h at 37.75 s, 35% shaft reading at 47.15 s and the open work-order receipt at 66.44 s. Run `python3 scripts/cinematic/render_work_order.py --verify-screen` on the source checkout to compare all six screens, and test playback with sound and English captions in the published article. [Reproduction commands](../../deliverables/video/README.md) · [Film manifest](../../evidence/video/work-order/film.json)

The two earlier film URLs are public GitHub raw-file locations. Both dedicated masters have been reviewed as actual encoded files: the PR is exactly 45 seconds (`7cd91a052221c4c54baccf7560bda93cb595b905c8aeab0c7d3e441051220960`) and the demo is exactly 300 seconds (`c47b134ce2202c57a6089cad7a262eb0e16927e69e58af9593c95dcc7b2158ab`). Their technical/source QA is in `evidence/video/cinematic/`; the scoped review is `docs/review/cinematic-team2.md`. The maintainer completed a logged-out check at public commit `c7d068e4992b1c0adca7c81c1c0011cd6c828062`: all 34 article/asset targets returned HTTP 200, and both complete MP4 downloads matched the published master hashes byte for byte. No separate video-host upload is claimed. Replace links with video-host URLs only if those services are separately authorized and actually used.

Both body images use immutable public commit `1e525fe2dfe1afe8ed6fc4391c1a060513c5e879`; their paths and public repository visibility were checked through GitHub. Existing code/evidence links use full canonical repository URLs so new reviewed evidence can be published without breaking article links.

## Claims and final readback

- The two facility cases have actual CSE/application evidence: food-production recovery and learning-space non-recovery. The supplementary independent operations/maintenance scenario is captured in `evidence/runtime/multiapp/index.json`, run `ma-d1a54f066e`, with recovery, missing-ACK and no-recovery cases. Its current-source revalidation is separately retained as `ma-b9129cb90a` in `evidence/runtime/multiapp-revalidation/index.json`; the film preserves the original run. Its three separate worker processes, shared source CIN rereads and denied maintenance command write are distinct from the cohosted roles of the default dashboard service. Those reviewed source/evidence paths are included in the completed GitHub access check.
- The optional maintenance paragraph is a later editorial addition grounded in `handover-b6e82ef69f` and its actual CSE receipts. It is separate from the unchanged film/outage story. The follow-up anonymous check at `aecd7e2` verified the live article, guide and unique run links. Ten downloaded files matched the local bytes. [Public receipt](../../evidence/release/cinematic-publication.json) · [Independent criterion 12 review](../review/handover-independent.md).
- Retain the physical-simulation statement, facility-specific target caveat, protocol-profile separation and command/ACK/outcome distinction. Original source news is linked; its photos are not reused.
- Source code is Apache-2.0. Original project documentation, diagrams and media are CC BY 4.0; preserve third-party exceptions and attribution.
- Independent readback of the cinematic article and film evidence is completed in `docs/review/cinematic-team1.md`, `cinematic-team2.md` and `cinematic-team3.md`; the reports retain their exact reviewed hashes and the article editor's role. When pasting into Hackster, check the actual rendered page, captions, images and outgoing links. The optional later maintenance paragraph retains its own source/run attribution.
- Actual Hackster/video-service posting is outside this editorial task. After authorized Hackster publication, check the logged-out Hackster page, its repository/video links and the README's real article backlink, then record the actual article URL and submission state. The completed GitHub checks do not claim a public Hackster page or event submission.
