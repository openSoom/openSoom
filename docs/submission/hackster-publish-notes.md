# Hackster paste and asset notes

Use `docs/submission/hackster-article.md` as the English article body. It contains full source URLs, immutable public image URLs and a text resource tree; no repository-relative links or Mermaid renderer are required. This file is editorial preparation, not evidence of publication.

Suggested project summary: **Connect ventilation evidence, authorized actions and verified results across vendors and facilities with oneM2M and agent tools.**

Hardware field: **No physical hardware required for the demonstration.** Fans, dampers and sensor measurements are virtual. A Mac arm64/Python 3.12 environment is the verified source-checkout route; other OS or real devices need separate acceptance.

Software field: openSoom source, ACME CSE 2026.5.3, Python 3.12, uv, OpenSSL, MCP and Codex CLI 0.166.0. Use the repository lockfiles for exact library versions. The deterministic demonstration requires no paid API account. Actual inference uses separately configured credentials and finite persistent accounting.

## Assets to place

| Position | Asset | Publication condition |
| --- | --- | --- |
| Near the opening | `deliverables/video/openSoom-pr-45s.mp4` | Dedicated approximately 45-second PR film must exist, decode/play correctly and match the article before its prepared public link is used |
| Main walkthrough | `deliverables/video/openSoom-demo-5min.mp4` | Dedicated approximately five-minute demo must show the actual verified scenes, readable evidence and English narration/captions; inspect the rendered film, not only its script |
| Opening image | learning-space dashboard image already linked in the body | Original application screenshot; virtual measurements, actual software |
| Architecture | source-mapped distributed-lab image already linked in the body | Explanatory geometry; separate processes versus logical/resource cards are captioned |

The two video URLs in the body are final intended GitHub raw-file locations. Both dedicated masters now exist and have been reviewed as actual encoded files: the PR is exactly 45 seconds (`7cd91a052221c4c54baccf7560bda93cb595b905c8aeab0c7d3e441051220960`) and the demo is exactly 300 seconds (`c47b134ce2202c57a6089cad7a262eb0e16927e69e58af9593c95dcc7b2158ab`). Their technical/source QA is in `evidence/video/cinematic/`; the scoped review is `docs/review/cinematic-team2.md`. Push the reviewed files and verify the exact public targets before pasting the publication links. Replace links with approved video-host URLs only if those services are separately authorized and actually used.

Both body images use immutable public commit `1e525fe2dfe1afe8ed6fc4391c1a060513c5e879`; their paths and public repository visibility were checked through GitHub. Existing code/evidence links use full canonical repository URLs so new reviewed evidence can be published without breaking article links.

## Claims and final readback

- The two facility cases have actual CSE/application evidence: food-production recovery and learning-space non-recovery. The supplementary independent operations/maintenance scenario is captured in `evidence/runtime/multiapp/index.json`, run `ma-d1a54f066e`, with recovery, missing-ACK and no-recovery cases. Its current-source revalidation is separately retained as `ma-b9129cb90a` in `evidence/runtime/multiapp-revalidation/index.json`; the film preserves the original run. Its three separate worker processes, shared source CIN rereads and denied maintenance command write are distinct from the cohosted roles of the default dashboard service. Preserve that separation in the films and final readback. Publish the reviewed new source/evidence before using their full public article links.
- Retain the physical-simulation statement, facility-specific target caveat, protocol-profile separation and command/ACK/outcome distinction. Original source news is linked; its photos are not reused.
- Source code is Apache-2.0. Original project documentation, diagrams and media are CC BY 4.0; preserve third-party exceptions and attribution.
- Before publication, have a reviewer other than this editorial implementer read the final article against the same frozen code/evidence and actual films. Review the rendered/pasted page and captions/images as they will appear.
- Actual Hackster/video-service posting is outside this editorial task. After authorized publication, check logged-out article/repository/video access and record the real article URL/backlink and submission state. Prepared prose does not close those public-evidence conditions or establish official Expert scores.
