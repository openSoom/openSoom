# Publish the air-quality demonstration

Use the [English article](hackster-article.md). Its opening compares the change in PM2.5 and CO₂, the first observed time at both targets and the observed duration. The cooking-line profile and any thresholds in these recordings belong to a virtual facility.

**Project summary** · See how the air in a room changes after a ventilation adjustment, how soon it meets the facility’s targets and how long the readings stay in range.

| Placement | Stable source |
| --- | --- |
| Source repository | [openSoom/openSoom](https://github.com/openSoom/openSoom) |
| Primary demo video | [English captioned 720p MP4](https://github.com/openSoom/openSoom/raw/refs/heads/main/deliverables/video/openSoom-air-quality-720p.mp4) · [English SRT](../../deliverables/video/openSoom-air-quality.en.srt) |
| Cover and opening example | [Observed air-quality outcome, actual dashboard](../../evidence/application/air-quality-dashboard.png) |
| First-results table | [Source values, three separate commands and native observations](../../evidence/runtime/air-quality-outcomes.json) |
| Further examples | Keep the work-order and architecture images next to their respective paragraphs. The older [maintenance film](../../deliverables/video/openSoom-work-order-720p.mp4) illustrates the optional diagnostic follow-up. |

The deterministic replay runs without physical hardware or a model account. The local software uses ACME oneM2M, Python 3.12 and uv. AI workflows are available via the Codex plugin or a standalone hosted-model runner using configured credentials.

On Hackster, add the source and primary video, confirm playback without signing in and check the images, captions and links on the published article. Add that public article URL to the GitHub README and use the organizer’s specified submission channels. The article’s API trial, screenshot and film are independent executions. Quote the times belonging to the corresponding run.
