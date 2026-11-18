# openSoom evaluation film

Play [the five-minute English film](../../openSoom-demo-5min.mp4) during the evaluation presentation. It includes English narration, burned-in English subtitles, original background audio and [editable SRT captions](captions.en.srt). [English narration and shot durations](script.en.json) are supplied separately.

## Edit and evidence

| Elapsed | What the audience sees | Original material |
| --- | --- | --- |
| 0:00–0:15 | A kitchen extraction hood, followed by the operating question | Adobe Firefly generated motion and an illustrative kitchen still. The facility is fictional. |
| 0:15–0:33 | The performance assessment that motivated the question | [Yonhap reporting](https://www.yna.co.kr/view/AKR20261010032900004). The 17.9% figure relates to the 301 assessed upgraded school kitchens. |
| 0:33–1:19 | Cooking line, real dashboard controls and a verified simulated recovery | [Original food-session screen recording](food-session.webm), [run and command data](../../../../evidence/video/cinematic/dashboard-recordings.json). The operator used the dashboard to request the damper adjustment. |
| 1:19–1:39 | Device publication and management retrieval of the same resource | [MQTT/TLS and HTTPS trace](../../../../evidence/runtime/cse-mqtt-tls-smoke.json). This recorded protocol test used a separate secure installation. |
| 1:39–2:25 | Second facility, different supplier, studio remains unresolved after ACK | Firefly learning-space illustration followed by [original learning-session screen recording](learning-session.webm) and [the linked dashboard record](../../../../evidence/video/cinematic/dashboard-recordings.json). |
| 2:25–3:17 | One source resource, two independent application processes, two outputs | Labeled reconstruction of the [separate three-process run](../../../../evidence/runtime/multiapp/no_recovery/result.json). The full resource identifiers come from server readback. |
| 3:17–3:37 | Commands, orders and observations have different permissions | [Separate application access checks](../../../../evidence/runtime/multiapp/no_recovery/result.json) and [product role checks](../../../../evidence/application/release-acceptance.json). |
| 3:37–4:02 | Model-selected tool calls, two verification results | Recorded [hosted-model run](../../../../evidence/agent/release-live-recovery.json). The browser screencasts used deterministic virtual scenarios and required no model calls. |
| 4:02–4:23 | A measured central interruption with local operation | Labeled reconstruction of [the independent distributed test](../../../../evidence/runtime/product-multisite-continuity.json). Loopback HTTP Mcc connected the central and two facility CSEs. The food facility retained its serving CSE. |
| 4:23–4:46 | Reproducing the demo and bringing a second facility into scope | [Developer quickstart](../../../../README.md#run-the-local-demo), [extension instructions](../../../../docs/extending.md) and the two shipped facility profiles. |
| 4:46–5:00 | Open-source project and repository | Adobe Firefly illustrative mechanical-room photograph and the openSoom wordmark. |

The two unedited WebM rushes retain the actual interaction and changing browser UI. The cut removes setup time, reframes the browser and adjusts playback speed within individual takes. The food result panel identifies 1,035 m³/h as the final outcome of that take. The English subtitles condense the fastest phrases, and the script preserves the full spoken narration. The HTTP-loopback CSE and API were temporary isolated processes with separate databases. The screening film presents recorded secure protocols, multi-application behavior, hosted-model reasoning and central interruption as separate experiments. All sensors, actuators and physical measurements in the film are simulated.

## Reproduce the edit

The material was mastered on macOS using the bundled system Samantha voice, Avenir Next and Menlo fonts, Python with Pillow and NumPy, and FFmpeg with libx264 and AAC. Fonts and voice models are supplied by the local operating system. From the repository root:

```sh
python3 scripts/cinematic/demo_audio.py
python3 scripts/cinematic/render_demo.py
python3 scripts/cinematic/check_master.py demo
```

The supplied rushes are sufficient for this render. To film a fresh operator session on the supported machine, first install the project's pinned ACME runtime, Node.js with Playwright and Chrome. Run `scripts/cinematic/capture_demo.py` with the project Python. It allocates loopback ports, records two virtual sessions, writes the WebMs and sanitized session record to the requested output directory, and stops the two temporary services. A newly captured take has different run IDs and timestamps. To re-edit it, adopt its corresponding recording data and rushes together.

The screen recordings, direction, graphics, narration text and original score were made for openSoom. Original project media use CC BY 4.0 with attribution to openSoom contributors. Third-party dependencies and system software retain their own licenses.
