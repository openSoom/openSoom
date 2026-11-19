# Single-page openSoom pitch and landing page

Serve this directory with any static HTTP server. It contains its own pinned Three.js modules, original geometry, styles, scripts and screenshot. The page needs no application service, model key, analytics or external font download.

```sh
python3 -m http.server 8095 --bind 127.0.0.1 --directory pitch
```

Open http://127.0.0.1:8095/. ES modules require HTTP serving; opening `index.html` directly as a file is not the supported preview path. Stop the preview with Ctrl-C. A future static host can serve this directory unchanged. No hosting account or public deployment has been created.

The English story covers the concrete reference case, oneM2M responsibilities, evidence-based control, actual prototype traces, reuse and limitations. **한국어 발표 가이드** opens a six-part presenter guide with section navigation and suggested demonstrations. The [English evaluation script](../docs/submission/presenter-script.en.md) and [Korean rehearsal script](../docs/submission/presenter-script.ko.md) give the current cues for film playback and the live dashboard. The [technical Q&A](../docs/submission/technical-qa.md) covers implementation details.

The opening lets a visitor compare three recorded cooking-line outcomes: recovery, persistent particles and rebound. Every value comes from the native ACME execution captured in [the case report](../evidence/runtime/air-quality-outcomes.json). Read the changes in each pollutant, first time to both targets and observed in-range duration. Select the live operator workspace to repeat a run. The workshop shaft-position comparison appears in the maintenance follow-up section. [Local launch](../README.md) · [Comparison methods](../docs/inspection-benchmark.md)

Three interactive views explain the facility, shared service layer and two-facility topology. Conditions illustrate a fault, verified recovery and central disconnection. These views are explanatory geometry and particles, not a computational airflow simulation, physical experiment or live runtime. The actual dashboard screenshot and linked repository evidence are labeled separately.

The page supports responsive layouts, keyboard-operable controls, reduced-motion preference, a pause button, textual explanations when WebGL2 is unavailable, and print styling. Browser checks and captures are in `evidence/pitch/`. Three.js **0.187.0** is pinned and vendored under MIT with original license and package-integrity metadata. Re-fetch with `python3 scripts/fetch_pitch_vendor.py`; no dependency install is needed to serve the page.

Original HTML/CSS/JS source is Apache-2.0; original copy, diagrams and media are CC BY 4.0. The vendored library retains MIT. GitHub evidence links become available when the reviewed repository release is pushed. Public Hackster/video-host links remain a separate handoff and are not invented here.

## Further visual pass

The facility scene uses a tighter responsive camera fit. A second Three.js sequence compares verified recovery, missing ACK, ACK without recovery and stale-data rejection. It is explanatory and makes no service requests. The sequence includes Korean explanations; [the complete Korean guide](../docs/project-guide.ko.md) includes a five-minute script and the actual evidence boundaries. Additional checks and screenshots: [visual-upgrade QA](../evidence/pitch/visual-upgrade-qa.json).

## Full architecture explorer

The full-width explorer under **Every layer has a job** expands the implementation into selectable components, resource families and paths. **Two facilities** shows 46 components across two facility API processes, two MN-CSEs and a central IN-CSE. **One installation** shows 34 components sharing one local service and one secure CSE. These are alternative deployment demonstrations. The component count includes logical modules and native resource groups; it is not a count of independent processes.

Choose **Observe & diagnose**, **Command → ACK → result**, **Share & reconcile**, or **Agent tool boundary** to follow a responsibility through the model. Select a component or a numbered path step to read its English/Korean explanation, execution boundary, resource path and source links. Layer checkboxes, fit/zoom controls and **Pause paths** adjust the view. The component index provides DOM selection. At mobile widths the canvas is hidden and the same components appear in readable groups.

The secure single-installation view scopes native MQTT/TLS to adapter observations, ACKs and SDT projection updates and HTTPS to CSE reads/commands. Local API/callback HTTP and MCP stdio are stated separately. The distributed view uses HTTP Mcc and selective announcements; central requests go through explicit replay and local validation. Dashed distributed agent links show a shared service contract whose agent execution was verified in the single-installation profile. The explorer does not imply MEC, CSE handover, federated learning, live control or physical ventilation performance.

`index.html` already includes `architecture.fragment.html` under `#system`, loads `architecture.css`, and loads `architecture.js` as an ES module. To reuse the explorer, insert the fragment once, load those files once and retain the pinned `vendor/` directory. No build step, API key or service connection is needed. The module exports `ARCHITECTURE_SOURCE_MAP`; [the source map](../evidence/pitch/architecture-source-map.json) records 51 total nodes, 77 relationships, their applicable topology and implementation/evidence references. [Architecture browser QA](../evidence/pitch/architecture-browser-qa.json) separates observed desktop/mobile checks from source-only and unexercised behavior.
