# Did the air get better?

Use the [evaluation slides](../../deliverables/presentation/openSoom-evaluation.pptx), [English captioned film](../../deliverables/video/openSoom-air-quality-720p.mp4) and [Korean rehearsal](presenter-script.ko.md). Slide 5 presents two separate incidents. The first uses a local operator dashboard. The second uses records from one cloud MEC work order. Keep the downloaded MP4 alongside the slides for offline playback.

**Presentation pacing.** Allow 30 seconds on each of slides 3, 5 and 6 for the three guided exercises. Their offline versions use the slide, the downloaded film and the recorded handoff. [Measured English rehearsal](../../evidence/presentation/air-quality-rehearsal.json)

## 1 · Did the air get better?

Imagine you are taking over a shift. Someone has already responded to an air-quality warning. They opened a damper. The controller acknowledged the command. The fan is running. People are still in the room. What do you tell them about the air?

I want to know three things. How much did the air change after the adjustment? When did we first see the room reach its targets? And when I start my shift, have we actually seen it stay there? Those are questions about the room where people work. A receipt from the equipment answers a different, useful question about what the controller received. openSoom brings the two records together so the person on duty can answer responsibly.

## 2 · Why this question belongs to the facility

One starting point was a school kitchen in Seoul. A government inspection found ventilation performance that needed improvement. Installing equipment is an important step. Once a facility is operating, someone also has to decide whether an adjustment achieved the conditions intended for that zone. A technician visiting once and a supervisor taking over every morning need different evidence.

A classroom and a cooking line can use the same method and have different targets. The facility defines which conditions it expects. In this demonstration the cooking line tracks fine particles, called PM2.5, and carbon dioxide. We compare each to the target configured for that zone. The values in this talk come from virtual equipment, with real software processing the observations. A field deployment would first establish sensor placement, targets and sampling cadence with the facility.

## 3 · Why the operator keeps the alert open

*Give the audience 30 seconds to compare the last two readings with the targets on the slide. Ask which value they would report to the next shift. The slide works offline.*

These two readings come from the same zone after one adjustment. Fine particles fell from 75 to 60 micrograms per cubic metre. Carbon dioxide fell from 1,500 to 720 parts per million. Put yourself in the operator’s chair. There is a 52 percent drop on the right, and the ventilation system is moving air. Would you tell the next shift the warning is over?

Look at the particle target. This facility chose 45, and the latest reading is 60. The system has yet to observe both measures inside their targets together. The operator keeps the alert open and can hand over a precise reason. In a separate recovery trial, both limits were reached after about six seconds and stayed within range across the next ten seconds of observations. Each clock belongs to its own trial.

## 4 · Why maintenance calls for a different measurement

Now consider a different incident, recorded in the cloud. A damper accepted a command to open fully, yet the zone was getting only 360 cubic metres per hour against its target of 900. The initial work order called for a general inspection. With that information, a technician still has several plausible places to start.

The facility then connected a separately managed sensor through the edge service. It measured the damper shaft at 35 percent open. The mismatch between the request and the physical position in this simulation gives a technician a specific place to begin. Check the actuator travel and its position feedback first. A person still has to inspect the equipment to determine the cause. This second incident has its own command, measurements and work order.

## 5 · Keep the alert open. Choose the first inspection.

*Play the full English-captioned film on slide 5. Click the film poster in PowerPoint slide-show mode. The separate MP4 is the offline fallback. After playback, give the audience 30 seconds to identify the moment the inspection priority changed. Pause on the revision 3 and revision 4 records or return to slide 4.*

In the opening scene the operator can explain exactly why the alert is still open. Carbon dioxide is within target and particles remain high. Those two readings justify keeping the room under observation. On their own they tell a technician very little about a particular damper.

The second scene starts a separate low-flow case. Revision three of the work order called for a general inspection. When the independent shaft measurement arrived, the maintenance app updated the same work order to revision four. Its first check became the actuator and position feedback. The operator still owned the room alert. That is the moment that makes the second application worth having.

## 6 · What each person hands over

*Allow 30 seconds. Identify the reviewed work-order revision, the scheduled inspection and the open incident. Use the embedded film’s final scene and slide 6 offline. The optional local [technician workbench](http://127.0.0.1:19492/) shows a separately seeded case.*

On the maintenance side, scheduling an inspection is a real action someone has to own. In the cloud trial, the technician application recorded an inspection against revision four. The operator’s view then showed the scheduled activity on that same order. The room incident was still open and there was no additional damper command. The field interface was exercised automatically using virtual equipment.

At the next shift, the supervisor can say what the air measurements support. The technician can say what they intend to inspect and which measurement justified it. A later sensor reading can change the room’s status while the inspection remains open. That separation lets both people work from a shared record without handing either person the other’s authority.

## 7 · The equipment evidence has a specific job

In another workshop the airflow stayed at 515 cubic metres per hour, below the local target of 560. In the first adjustment the shaft fell well short of the requested opening. A later adjustment brought the shaft close to its requested position. The airflow was still low, so the first inspection shifted from the actuator to the airflow path. The same work order kept the sequence.

That example explains why our operating interface preserves several kinds of observation. Concentrations help tell a facility what happened in the room. Airflow and independent mechanical position can help a technician choose the next inspection when airflow itself is deficient. A facility with a trustworthy local sensor can use it directly. A facility that contracts a separate sensor provider can bring in the same evidence through the edge service.

## 8 · How the measurements reach each app

*Keep the implementation explanation to about one minute.*

The adapter writes timestamped measurements to the facility’s oneM2M node. Its subscriptions notify the operations app, which reads the original observations, matches them to the command and applies the facility’s targets. Only site operations can issue device commands. The maintenance app has a different permission. It can request an independent measurement and revise the work order. A separate bridge discovers and reads the external sensor through the MEC platform. The technician’s app records the planned inspection against the exact revision it reviewed. We tested the cloud maintenance path on one virtual machine. A facility that already has a suitable local sensor can provide that evidence directly. We would choose oneM2M again for sites where equipment vendors change and separate teams need the same evidence under different permissions.

## 9 · Try it at another site

A manager can use the Codex plugin or a standalone model to prepare a virtual trial under the facility’s own profile. One previous request asked what would happen if a lounge supplied an old reading. The recorded exercise produced zero new commands. The original source record could still be checked after restart. A model can help the manager ask the question in ordinary language. Measurement times, target comparisons and permissions stay in the service.

For a second facility, I would start with one observed zone. Agree on its targets, sensor cadence and what the team considers a meaningful time in range. Give the oncoming supervisor two records, one sustained and one with a rebound, and ask them to explain what happened without help.

## 10 · What the next shift can verify

Across an earlier comparison, sixteen designed virtual cases still needed investigation. Accepting the equipment acknowledgement alone closed fourteen of them. Looking only at two airflow readings closed two. openSoom kept all sixteen open. In the four cases designed with a specific first inspection, the maintenance rule selected the expected check. Those figures describe our virtual test set.

The film puts two decisions in front of us. Is there enough evidence to hand over the room as recovered? And if the equipment still underperforms, what should someone inspect first? One supervisor can point to the particle reading; one technician can point to the shaft measurement. The project is open source and both records are available for review. Our next test is to give a real shift team its own calibrated measurements and find out whether they can make that handover without us. Thank you.
