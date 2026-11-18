# Optional serving-CSE maintenance transition

This separate release experiment asks: during planned maintenance of a local
ventilation controller/CSE, can the same logical facility endpoint resume through
an independent CSE without losing the last observation, open incident, profile
version or a pending command's identity?

It runs actual **ACME 2026.5.3** CSE processes A and B and an application-managed
logical HTTP endpoint. After the harness stops **its own A process**, two failed
transport probes automatically prepare/select B. A permission denial does not
trigger a transition. The device response is simulated. No existing openSoom API,
broker, CSE profile or database is stopped, reset or reconfigured.

## Reproduce

Use the already installed project environment and pinned CSE environment. The
supported rehearsal host is macOS with Python 3.12.12. No model call, Docker,
host account, paid service or external infrastructure is needed.

```sh
.venv/bin/python -m pytest tests/test_handover.py -q
.venv/bin/python scripts/cse_handover_demo.py
```

If the CSE environment is absent, follow the existing pinned runtime installation
in `deploy/README.md`; this demo never installs dependencies automatically.
Loopback sockets and child-process execution must be permitted by the host.
An independent rerun can retain the original acceptance artifact:

```sh
.venv/bin/python scripts/cse_handover_demo.py \
  --evidence tmp/handover-independent/acceptance.json
```

Exercise one transient target write failure separately:

```sh
.venv/bin/python scripts/cse_handover_demo.py \
  --inject-target-write-failure \
  --evidence evidence/runtime/handover/failure-recovery.json
```

That flag injects one explicit **pre-HTTP-dispatch transport failure** during the
B incident write, after an actual B state write/readback has succeeded. The A
process is still actually stopped. The evidence distinguishes this injected
error from real CSE responses. Authority remains A and the stable endpoint stays
unavailable while preparation is incomplete; the next tick resumes B and the
same persisted snapshot without a manual destination choice or new command ID.

The harness chooses unused loopback ports and private temporary base directories
for both CSEs, starts them without remote registration/MQTT and checks their
different actual CSE IDs. A/B and callback listeners are closed, processes are
waited for, and the temporary directories are removed even on a failed test.
Existing project process-record hashes are compared before/after. Failure before
socket creation can terminate before the per-run capture is available; the host
error must not be presented as a test pass.

Successful output is `PASS_REAL_SERVING_CSE_MAINTENANCE_HANDOVER`. Inspect the
matching unique run JSON and source hashes; a success alias from an earlier run
is not proof that a later invocation passed. Every captured run has a unique
`handover-...json`; selected oneM2M traces retain request/response IDs and hashes.
The default success alias is `evidence/runtime/handover/acceptance.json`. Failed
captured runs are retained alongside it and do not overwrite a successful alias.

## What is rebuilt and fenced

`src/opensoom/handover.py` is a reusable, optional library rather than a change to
the current Core service. It contains:

- `ServingCSE`: a fixed configured endpoint, expected actual CSE ID and its local
  resource/AE mappings. Application-level `facility_id` stays stable; CSE-local
  registrations and resource IDs are recreated at B, not assumed to migrate.
- `MaintenanceHandover`: native AE/CNT/ACP/SUB provisioning, last state and open
  incident restoration, bounded availability-driven A-to-B routing and a scoped
  pending-command reissue. There is no automatic failback or unlimited flapping.
- `AuthorityStore`: one durable local SQLite authority epoch, active CSE ID and
  command execution ledger. Compare-and-swap transition and simulated effect
  deduplication use immediate transactions.

Target preparation has a durable `restore_pending` marker. State, incident, last
observation and pending command are written with deterministic names and checked
by authoritative readback before activation. A partial write can resume at the
same target for up to three transient failures; new command/observation submission
and callback-state updates pause during preparation. Authority, restored local
snapshot and removal of the pending marker commit in one SQLite transaction,
avoiding an activate-before-restore or commit/marker-cleanup crash window. Prepared
B commands cannot execute under the still-active A authority. Permission or
content conflicts fail closed rather than causing an automatic permission change.

After A becomes unavailable, B receives fresh least-privilege ACPs and native
subscriptions; the configured callback receives a verification request and
observation notifications. Callback data is only a hint: the controller re-reads
the identified observation CIN from the **active, fixed CSE** using its scoped AE.
The restored old observation retains its timestamp/sequence and cannot count as a
new sample. A genuinely new B observation advances the sequence after a native
notification and authoritative read.

The pending command keeps its logical ID, payload and original expiry but gets
the committed B epoch/source-CSE envelope. The virtual actuator checks the active
target **and actual source CSE ID**, epoch, facility/profile version, bounded
issued/expiry interval and 0–100 percent setpoint. An old A command is fenced even
if it claims B's new target/epoch. The durable logical-command ledger prevents a
second simulated effect after replay, database reopen or an ACK retry. A reused
command ID with changed business arguments conflicts. ACK and subsequent
observations remain distinct; the open incident is not falsely resolved by this
maintenance experiment.

This preserves application state held by the still-running controller/device. It
does not reconstruct an unavailable controller's lost local database. All future
production integrations must define their own authority durability and device
enforcement rather than assuming these local transactions span remote devices.

## Evidence and interpretation

The run records actual A/B CSEBase identities, A/B AE registrations, target ACP and
native SUB resources, the stable logical URL before/after, automatic trigger
history, restored last observation/incident/pending command, expired-authority
refusals, an unprivileged observer's native CSE 4103 write denial, a separate ACK
read, one applied command and a persisted duplicate receipt. Four injected
observation sequences must each appear once in the accepted notification path.

Interruption is measured from the last successful A-backed logical-endpoint read
to its first successful B-backed read, including source stopping and target
rebuild. This is a conservative observed read gap in one run, not an SLA. The
four injected sample checks do not establish asynchronous packet loss, continuous
sampling during the gap or complete CSE-history replication.

The Expert descriptor for rubric criterion 12 concerns automated handover,
state/subscription/security continuity and interruption/loss measurement. This
experiment supplies concrete candidate evidence for independent review. Its
author's PASS is not independent rubric closeout or a guaranteed official score.

## Explicit limits

- This is application-managed **serving-CSE endpoint transition**, not a claim
  that the oneM2M implementation natively moves an AE-ID/registration.
- The two standalone IN-CSEs are independent processes on one host. This is not
  geographic distribution, native CSE replication, process/VM migration, MEC
  hosting, MEC service consumption, federated learning or geolocation.
- CSE and callback traffic uses loopback HTTP. AE origins are trusted local
  claims. ACP allow/deny is real, but cryptographic client identity and production
  network security are not established.
- The shared local authority database and trusted virtual actuator are the
  fencing boundary. This is not a distributed consensus/lease service, physical
  actuator safety mechanism or abrupt controller/node failure HA.
- Physical values and device setpoints are simulated; no ventilation-performance
  or health outcome is claimed. The existing single-service path is unchanged.
