# Technical interview notes

Use the [English slides](../../deliverables/presentation/openSoom-evaluation.pptx), [English script](presenter-script.en.md) and [Korean rehearsal script](presenter-script.ko.md) for the 10–15 minute presentation and video. The organizer allocates 20 minutes including questions. The film first shows the local operator keeping the particle alert open. A second incident follows the maintenance app from low airflow to an inspection priority, using a retained cloud MEC response. The original cloud test exercised the technician web service over HTTP.

### What exactly do the outcome clocks measure?

The baseline is the accepted fresh measurement available when the command was issued. Both post-action pollutant readings must come from one eligible measurement in that zone. The first clock ends at the first observed joint target crossing after device ACK. The second spans consecutive qualifying observations, starting at zero for one point. It stops accumulating at the last eligible point. A rebound or a gap ends that spell; a later qualifying sample can start another. A new action has a separate record. These are observed intervals in virtual trials. They do not establish how long a real room stayed continuously in range or whether the command alone caused the change. [Results and original readings](../../evidence/runtime/air-quality-outcomes.json)

### Which problem did you observe, and which part is a product hypothesis?

A November 2025 inspection in Seoul documented inadequate ventilation performance at a school kitchen and recommended improvements. HSE commissioning guidance calls for checking hood performance against measurements and operating conditions. openSoom tests a product hypothesis arising from that problem. Site staff may be able to make better handover and inspection decisions when command, acknowledgement, follow-up airflow and independent feedback can be read together. A field study would need to measure the usefulness and accuracy of those decisions. [Ministry inspection](https://www.moel.go.kr/news/enews/report/enewsView.do?news_seq=18528) · [HSE guidance](https://www.hse.gov.uk/lev/commissioning.htm)

### What did the operator and technician each decide?

The local operator saw PM2.5 stay at 60 µg/m³ against 45, even as CO₂ improved to 720 ppm and airflow reached 1,035 m³/h. The alert stayed open. In a separate cloud incident, the damper acknowledged 100% but airflow stayed at 360 m³/h against 900. The MEC 046 service supplied an independent virtual shaft reading of 35%. Maintenance revised the existing order from 3 to 4 and prioritized checking actuator travel and position feedback. The technician scheduled it. The operator saw the disposition while the incident stayed open. A field inspection would establish the cause. [Cloud handoff used in the film](../../evidence/runtime/option-c/technician-handoff.json)

### What can the two people record, and who changes the work order?

The shift supervisor uses the operator console to compare the acknowledged setting with fresh airflow from the same zone. The facility technician opens an independent workbench, selects an order and sees the particular revision, command and sensor evidence. Selecting **Inspection scheduled** and **Save inspection entry** records the activity against that revision and returns its oneM2M resource ID. The technician identity can write inspection entries for that facility. The background maintenance AE owns work-order changes, and site operations owns commands and evaluates airflow recovery. In a field pilot a person would perform the inspection and establish its result. [Local operator console](http://127.0.0.1:19490/) · [Local technician workbench](http://127.0.0.1:19492/) · [Technician service](../../src/opensoom/technician.py) · [Local browser receipts](../../evidence/application/technician-browser.json)

### Would the system always suggest inspecting the actuator?

In the archive workshop’s conservation zone, the measured airflow stayed at 515 m³/h against the facility’s 560 m³/h target. An 80% command paired with 35% independent shaft position directed the technician to actuator travel and feedback. A later 95% command paired with 93% shaft position directed the technician to the airflow path. The configured position tolerance was nine percentage points. Both updates retained `work-incident-bcd88d20e6` and each referenced its own command and settled virtual encoder reading. This run used the local sensor route. [Archive workshop commissioning](../../evidence/agent/facility-worker-generalization.json)

### Which simpler policy did you compare against, and what is the denominator?

Nine predeclared cases ran in each of two virtual facilities. Sixteen of the eighteen runs should stay unresolved. An acknowledgement-only rule declared 14 of those recovered, a two-fresh-airflow rule declared 2, and openSoom declared 0. All three handled the two expected recoveries. Four runs had a specific expected first inspection. openSoom matched all four, while the simpler rules offered general inspections. The paired low-flow cases for each site used the same command and airflow with different virtual shaft values. These designed cases test the reasoning and implementation. A field pilot would need to measure diagnostic accuracy and maintenance outcomes separately. [Case definitions and comparison](../../docs/inspection-benchmark.md) · [Executed cases](../../evidence/runtime/inspection-benchmark.json)

### Why use oneM2M?

Multiple producers and consumers need independent permission to use the same observations. oneM2M supplies discovery, native subscriptions, group retrieval, access control and sharing between CSEs. Maintenance can retrieve the exact observation on which operations based its decision. A new app can use those resources without putting its own state or device control into the operations application. [Resource design](../architecture.md) · [Independent applications](../../evidence/runtime/maintenance-release-local.json)

At the next multi-vendor facility we would use oneM2M again. A new sensor adapter or technician application can join the same site resource model, and the CSE enforces its own access rights. In the workbench, reading an order revision and writing an inspection CIN linked by `work_order_ri` makes the decision traceable across applications. [Resource tree and application roles](../architecture.md#resource-tree)

### What is the difference between MN-CSE, MEC, and the applications?

The MN-CSE is the facility’s oneM2M common service entity. Its resource tree holds observations, commands, ACKs and work-order exchanges. The IN-CSE is the infrastructure-tier common service entity. Mcc connects CSEs. The operations and maintenance applications consume CSE services over Mca. At the edge, a separately deployed bridge discovers and calls the MEC provider’s service and publishes the response to the MN-CSE. Only site operations can command the device. The maintenance application writes the work order. [Application and deployment contract](../mec-application-contract.ko.md)

### What ran on the cloud host?

The equipment and sensor readings were simulated. The private Kubernetes deployment on one VM ran site operations, a real ACME MN-CSE, separately credentialed maintenance and bridge workers, an independent provider CSE and pinned ETSI service components. In cloud run `demo-c24628832a`, the bridge used MEC 011 to discover the MEC 046 sensor-sharing endpoint. It retrieved a shaft reading, returned it through oneM2M, and maintenance changed work order `work-incident-97b8877461` to a specific first inspection. The actual request and response IDs identify that journey. This sensor-service trial used directly launched workloads. The separate north and south runs below exercised managed placement. [Cloud work-order receipt](../../evidence/runtime/mec-maintenance-roundtrip.json) · [Platform components](../../evidence/runtime/option-c/native-services.json)

### Who chose the target host, and who deployed the apps?

The operator selected the north logical host first, then the south. On each target, the Sandbox controller and virtualization engine installed the site MN-CSE and inspection worker as two Helm releases. Each placement ran a fresh work order and each MN registered to the IN-CSE. The original work-order snapshot survived redeployment. Both shared one cloud VM, CSE storage and a service catalog. The host choices came from the operator’s topology. Separately, a terminated maintenance pod resumed reconciliation in 14.768 seconds. [Deployment receipts](../../evidence/runtime/option-c/index.json) · [Pod recovery](../../evidence/runtime/option-c/managed-worker-restart.json)

### Did a second functional MEC service change the outcome?

Yes. A separate cloud run began with the provider unavailable. A site-authorized oneM2M request selected an installed provider profile. The bridge used MEC 033 to register that provider again. The MEC 046 service then supplied an independent reading, after which maintenance updated the inspection priority. The original command and the still-open airflow incident remained linked to the work order. This was run `demo-4f65728fd2`, separate from the filmed local case and the first cloud 046 case. [MEC 033 and 046 commissioning record](../../evidence/runtime/mec-provider-commissioning.json)

### Did subscribing to the sensor service deliver the shaft measurement?

In south-edge run `demo-a8c5ef7ada`, the bridge enrolled the virtual sensor provider through MEC 033 and confirmed registration. The MEC 046 service then created a subscription, tested the callback and returned the stored subscription on request. Restarting the bridge reused that subscription. The callback confirmed connectivity. A separate MEC 046 read supplied the virtual shaft position of 35%. Maintenance read the returned observation through oneM2M and updated the existing work order from revision 3 to 4. [South-edge request and response record](../../evidence/runtime/option-c/commissioned-sensor-roundtrip.json)

### When is MEC useful for a facility?

An independent reading already supplied by the local oneM2M system can support the same technical decision. MEC is useful when another provider manages the independent sensor and exposes it through a discoverable edge service. The local and cloud demonstrations agreed on the inspection while retaining separate incident, execution and work-order IDs. With neither source available, the technician retains a general inspection. [Local comparison](../../evidence/runtime/maintenance-release-local.json) · [Provider service comparison](../../evidence/runtime/mec-maintenance-roundtrip.json)

### Could a bad sample change the inspection or create another order?

The bridge checks the facility, asset, sensor, unit, observation time and elapsed time after the command. Recorded local tests sent an unrelated asset, a wrong unit, a missing measurement time and a reading made before the actuator settled. Each left the existing decision in place. A restart plus duplicate callbacks retained exactly the same revision set. The site configuration defines tolerance, settling time and freshness. [Acceptance record](../../evidence/runtime/maintenance-release-local.json)

### What can a facility manager do through the agent?

A hosted model used the common MCP tools to save a named trial for the learning facility’s lounge, execute it and read the exact CSE result. An 88-second-old observation produced zero new device commands. The scenario definition and its version persist in the service and can be replayed after a restart. A separate fresh-observation test produced a virtual command and ACK. A separate native Codex run selected the test tool with a 93-second-old reading and an 83% damper request. A single scoped approval authorized the virtual trial. The service saved, ran and reread it. Its CSE command count stayed unchanged, and the original observation and version survived an API restart. The earlier rejected attempt and the later granted scope remain separately recorded. [Scenario results](../../evidence/agent/scenario-authoring/README.md) · [Codex authoring receipt](../../evidence/agent/scenario-authoring/codex-authored-accepted.json)

### What changes at a new facility?

A facility administrator chooses its zones, profile, equipment bindings, installed apps, authorized operations and site-specific targets. The release includes food-production and learning-space profiles and two virtual vendor formats. A new protocol or physical device needs a tested adapter. First-use validation with nontechnical staff and field calibration remain future pilot work. [Configuration](../../config/facilities.json) · [Adoption guide](../../README.md)

### Which protocol and semantic claims can be reproduced?

In the secure product test, repeated device telemetry and acknowledgements used a persistent native MQTT/TLS connection. Operations used HTTPS for identified resource reads and commands with a request/response. The ordinary local film used HTTP loopback. [Secure product acceptance](../../evidence/application/release-acceptance.json) The shared standard field is the TS-0023 air-quality sensor PM2.5 value, exposed in integer µg/m³ and discoverable as a flexContainer. The canonical measurement also preserves timestamp, units and original precision. CO₂ ppm and volumetric airflow use their own typed fields. In a separate native group test, a denied member produced a top-level 4103 on the pinned ACME version. Separate diagnostic member reads retain their own outcome. [Native MQTT evidence](../../evidence/runtime/cse-mqtt-tls-smoke.json) · [Standard model](../standard-model.md)

### Which identities can act?

Worker gateway credentials bind each allowed role to its facility-specific AE identity. The recorded tests denied maintenance and bridge device commands, bridge work-order writes, another facility’s data, and mismatched credentials and originator. The standalone local broker profile is server-authenticated TLS with trusted loopback clients. Production identity provisioning and field-device security need separate validation. [Recorded denials](../../evidence/runtime/maintenance-release-local.json)

### How do you distinguish a central outage, a maintenance app restart and a serving-CSE transfer?

During the central outage test the facility kept its current local CSE and completed an operation while the IN-CSE was down. In the separate local maintenance restart test the MN-CSE stayed available and the restarted app caught up on durable events. In a separate planned-maintenance experiment two failed probes moved a stable endpoint to the second same-host CSE and restored incident state and access configuration. Each test has its own failure boundary. [Central outage](../../evidence/runtime/product-multisite-continuity.json) · [Application restart](../../evidence/runtime/maintenance-release-local.json) · [Serving-CSE transfer](../../evidence/runtime/handover/acceptance.json)

### What would convince you the product works in the field?

Start with one zone under observation. Establish the facility’s own targets with its commissioning records and a competent technician. Compare openSoom’s priorities with measured performance and actual inspections. Record whether a shift can recover the incident history, which first inspections prove useful, where independent evidence is absent and whether new facilities can configure the same workflow. Public traces let another team reproduce the software tests while the physical pilot proceeds.

### Before the interview

Download the [PPTX](../../deliverables/presentation/openSoom-evaluation.pptx), [PDF](../../deliverables/presentation/openSoom-evaluation.pdf) and [720p MP4](../../deliverables/video/openSoom-air-quality-720p.mp4). Play the two-case film on slide 5. Use slide 6 to trace the work order, the technician’s disposition and the operator’s still-open incident. If the lab is unavailable, keep the same three 30-second audience exercises offline. Use the slide 3 table to identify the outstanding pollutant, pause the film on the separate MEC case on slide 5, and inspect the saved order revision and scheduling receipt on slide 6. Upload the slides to the designated Drive folder by Sunday, 22 November 2026, confirm the organizer’s assigned `PICK` slot and join before it begins. [Submission handoff](handoff.md)
