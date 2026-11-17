# Facility dashboard

The buildless dashboard in `web/` is served by the openSoom service. It has no framework, external font, icon or CDN dependency. All SVG marks, equipment symbols and facility geometry are original project assets.

## Operator experience

The screen answers four questions: which zones are reporting, what needs attention, which actions are pending, and whether later observations established recovery. A selectable isometric zone schematic keeps the facility visible beside the operating workflow. The latest action separates request, device acknowledgement and verified outcome. Recent events and an evidence dialog preserve the path from observation to result.

The visual system uses warm off-white surfaces, dark evergreen navigation, soft green observation states and amber attention states. Text labels accompany color. The layout adapts from desktop to mobile, supports keyboard zone selection, visible focus, native dialog focus handling, a skip link and reduced motion. Mobile zone buttons keep names, readings and status readable alongside the simplified schematic. English is the primary interface language; the help dialog includes Korean operator guidance.

## Runtime contract

- The service returns `GET /api/state` with facilities, zones and observations, incidents, commands, events, runs and runtime connection state. Observations use `{value, unit, observed_at, received_at, source, quality}`. The dashboard does not generate equipment values.
- `POST /api/demo/start` receives `{facility_id, scenario, autorun}`. Supported UI scenarios are `normal`, `exhaust_fault`, `stale`, `missing_ack` and `no_recovery`. The response identifies the background run; subsequent polls provide progress.
- `GET /api/runs/{id}` retrieves the actual recorded run. The evidence dialog supplements that record with matching commands and events, preserving request IDs and acknowledgements even when an older run has no recorded steps. Without a run, `POST /api/tools/read_evidence` can retrieve scoped evidence.
- Tool calls use `POST /api/tools/{name}` with `{arguments: ...}`. `verify_result` receives facility and command IDs. Zone actions request `set_damper` with value 100 or `request_maintenance` with null value, a reason and a unique request ID. The server must enforce authentication, facility/profile scope, freshness and allowed actions.
- The service replaces `__OPENSOOM_TOKEN__` in the `opensoom-token` meta element with a scoped token. An unreplaced or absent token gives a read-only dashboard. The browser uses it only in the Authorization header; it is not stored in local storage or printed in the evidence dialog.
- Serve static assets at `/assets/`. The root HTML and all API paths are same-origin. The service binds to its intended local interface and validates write origins/authentication; this frontend does not establish that server boundary.

Facility selection is stored locally as an ID only. Polling occurs every two seconds while visible, with overlapping polls suppressed and request timeouts. Service failures leave the last received values visible with an explicit non-live notice. CSE availability is reported separately from dashboard availability. Error messages are shown without exposing stack traces.

## Evidence boundaries

The facility drawing is an illustrative layout. Its airflow lines indicate a reported running fan with a reported airflow observation; they are not computational fluid dynamics or measured capture performance. Numeric values and status come from the service. A running fan, successful CSE operation, device ACK and recovered incident remain different states.

The optional zone trend contains only distinct timestamped observations collected since the page opened. It does not fabricate earlier history. Run-mode labels come from recorded execution mode; deterministic scenarios are not labeled as live model decisions. The virtual facility label and help text identify simulated physical readings and the limits of the demonstration. The workflow and action panel use the facility's active run, falling back to its latest recorded run; a prior verified command is not presented as recovery for a new scenario. Archived incidents without verified resolution timestamps do not increase the recovery count.

## Verification

Implementation-author QA was performed in Chrome against the live local service at `http://127.0.0.1:8090/`, using the `learning-b` facility for mutations. All four paths were observed: verified recovery, stale control rejection, missing device ACK timeout, and acknowledged action without measured recovery. The latter remained unresolved with zero verified recoveries. Actual run IDs, command states, request IDs, source hashes and captured images are recorded in [the dashboard QA record](../evidence/dashboard/qa.json).

The default desktop view (1785 × 1034) and a 393 × 852 mobile viewport were inspected. Both had equal content and layout widths, with no horizontal overflow. Keyboard zone selection, metric switching, mobile help, native dialog errors and evidence retrieval were exercised. The final live browser check reported no console errors. `node --check web/app.js`, unique HTML ID/static SVG checks, CSS brace balance and `git diff --check` passed.

An earlier static preview without the API showed the intended offline/empty state and disabled actions. That preview is layout evidence only. These checks do not replace independent Rubric review, comprehensive accessibility validation, other-browser testing or physical equipment validation. The evidence contains deterministic scenario runs, not live-model claims.
