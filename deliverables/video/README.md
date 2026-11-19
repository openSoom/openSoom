# openSoom films

The current evaluation film is [Did the air get better? (720p)](openSoom-air-quality-720p.mp4). It shows three ordinary dashboard runs with virtual equipment: recovery, persistent particles and rebound. The 55.9-second MP4 has English narration and both visible and selectable captions. [Captions](openSoom-air-quality.en.srt) · [Frame acquisition, command IDs and checksum](../../evidence/video/air-quality-film.json)

The following films document earlier demonstrations.


| Film | Use | Editorial and technical sources |
| --- | --- | --- |
| [Work-order decision film](openSoom-work-order-720p.mp4) | Earlier maintenance walkthrough. 104.938 seconds, 1280 × 720, English voice and burned-in plus selectable captions | [Caption file](openSoom-work-order.en.srt), [browser source](cinematic/demo/maintenance-work-order.webm), [film manifest](../../evidence/video/work-order/film.json) |
| [45-second introduction](openSoom-pr-45s.mp4) | Public project introduction, with Firefly cinematography, original generated score, English voice and selectable English captions | [PR sources](cinematic/pr/), [production budget](../../evidence/video/cinematic/adobe-production.json) |
| [Five-minute demonstration](openSoom-demo-5min.mp4) | Extended walkthrough of two facilities and the independent application receipts | [Scene list, captions, recordings and reproduction](cinematic/demo/README.md) |

The work-order film is available for maintenance questions. Its local dashboard scene follows `demo-271a6c3a23` from a 100% command ACK to a 360 m³/h follow-up and an independent shaft reading of 35%. The later cloud comparison shows its own run ID. [English presenter notes](../../docs/submission/presenter-script.en.md) · [Local work order](../../evidence/runtime/maintenance-release-local.json) · [Cloud comparison](../../evidence/runtime/mec-maintenance-roundtrip.json)

## Reproduce and verify the work-order film

From the repository root, use Python with Pillow, FFmpeg and FFprobe. Rendering uses the macOS Arial fonts. To retain the approved narration and subtitle timing, run the following commands. The renderer writes a replacement MP4 after its duration check succeeds. To synthesize the English audio from the script on macOS, omit `--preserve-audio` and use the Samantha system voice.

```bash
python3 scripts/cinematic/render_work_order.py --preserve-audio deliverables/video/openSoom-work-order-720p.mp4
python3 scripts/cinematic/render_work_order.py --verify-screen
ffmpeg -v error -i deliverables/video/openSoom-work-order-720p.mp4 -map 0:v:0 -map 0:a:0 -f null -
```

The verification compares the beginning, middle and end of six narrated screens against the source recording. Check the facility at 20.96 s, ACK at 29.19 s, airflow at 37.75 s, shaft at 47.15 s, work order at 56.79 s and expanded receipt at 66.44 s. The original WebM frames for these views are at 15.0, 6.05, 8.15, 10.6, 18.7 and 22.0 seconds, respectively. These offsets apply to that file's SHA-256 `4b7f13f5de5b0d2e8abe28f85bba51f8e08e5463b78c99bae18efffaf17fa0ec`. [Film manifest and release SHA-256](../../evidence/video/work-order/film.json)

For a new recording, start the dashboard and matching landing page for the retained run. With Playwright and Chrome installed, point the capture script at those URLs and the corresponding JSON evidence. It saves the six validated screen poses, their hashes, and the WebM hash in `capture.json`. The renderer checks this manifest before using the screenshots. The capture leaves its files in the supplied directory.

```bash
node scripts/cinematic/capture_work_order.cjs "$DASHBOARD_URL" "$LANDING_URL" "$RUN_JSON" "$CAPTURE_DIR"
python3 scripts/cinematic/render_work_order.py --capture-dir "$CAPTURE_DIR" --recording "$CAPTURE_DIR/work-order.webm" --evidence "$RUN_JSON" --preserve-audio deliverables/video/openSoom-work-order-720p.mp4
```

The [CinematicDemo editing brief](cinematic/CinematicDemo.ko.md) describes the source footage in the earlier films.

## Earlier 108-second film

`openSoom-demo-en.mp4` is a 108-second, 1920 × 1080 film with English synthetic narration and burned-in English captions. `captions.en.srt`, `narration.en.txt`, and `storyboard.json` provide editable companion materials. The local `preview.html` player is for review; nothing is hosted or uploaded by this package.

The film moves from a specific virtual cooking-line fault to the shared oneM2M path, actual dashboard captures, a recorded hosted-model tool trace, command/ACK/result verification, a failed recovery, and reuse across two facilities and vendor formats.

## Evidence boundaries

- Dashboard pictures are actual browser captures of interactive run `demo-eea1329dfb`, command `cmd-06e0054c4e85`. The film displays the fault capture and the later recovered capture in sequence. This is an edited sequence of still captures, not continuous screen recording. The measurements and physical devices are virtual; the service/CSE operations are actual execution.
- The recorded live-model example is `agent-379720ef883c`, command `cmd-607d6d77947b`, using `gpt-5-mini`. The failed-recovery example is `agent-479f866b7e84`, command `cmd-838cfc0f207e`. Their source evidence is in `evidence/agent/secure-live-recovery.json` and `secure-live-no-recovery.json`.
- Codex CLI plugin registration and MCP transport were tested separately. The film does not claim a Codex model turn or a completed nontechnical-user study. Actual model decisions were executed by the standalone hosted API runner through the shared service path.
- The 900 m³/h target belongs to the simulated food-production profile. It is not a universal ventilation requirement, a physical certification, or a health-outcome claim. Facility diagrams are illustrative.
- Native oneM2M discovery, subscriptions, groups and access control are software claims. The film makes no claim of ETSI MEC deployment, serving-CSE handover, federated learning or geolocation integration.

## Reproduce

Run `python3 scripts/render_video.py` from the repository after installing Pillow and FFmpeg. The renderer reads an installed Avenir Next font on macOS, or DejaVu Sans on Linux. It does not bundle a font file. On macOS it uses the installed Samantha voice through `say`; a host restriction that prevents speech services must be resolved through the normal host permission mechanism. `--no-voice` renders a captioned silent alternative, and `--frames-only` renders the reviewable storyboard images.

All rendering is local. The renderer creates temporary intermediate audio and clips, deletes them on exit, then writes the MP4, captions, storyboard and render manifest. `evidence/video/asset-provenance.json` maps assets and claims to exact source files/hashes. `evidence/video/qa.json` records final decoding, playback and visual checks.

For browser review, run `python3 scripts/media_preview.py` and open `http://127.0.0.1:8768/preview.html`. This loopback-only server supports byte-range requests so native browser seeking works. Stop it with Ctrl-C after review. It is a temporary local viewer, not a production hosting service.

Original script, diagrams, captions and media: CC BY 4.0, openSoom contributors. Renderer source: Apache-2.0 under the project source license. System fonts and voice models are not redistributed and retain their vendors' terms. There is no stock footage, third-party music, purchased media or external hosting dependency.
