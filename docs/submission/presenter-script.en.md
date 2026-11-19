# Did the air get better?

Use the [evaluation slides](../../deliverables/presentation/openSoom-evaluation.pptx), [720p air-quality demo](../../deliverables/video/openSoom-air-quality-720p.mp4) and [live operator console](http://127.0.0.1:19490/). Open the virtual cooking line before the session. Italic lines are stage directions. The three runs have independent measurement clocks. Read the seconds shown on the screen for the selected command. [Korean rehearsal](presenter-script.ko.md)

**Presentation pacing.** The measured English read-through plus the film takes 8:57. Reserve another 90 seconds of guided interaction across slides 3, 5 and 6. Give the room 30 seconds to compare the two pollutants and identify the outstanding limit, 30 seconds for the live target crossing, and 30 seconds to open the command history and inspect the original evidence. Together these give a planned 10:27 presentation. [Rehearsal timing](../../evidence/presentation/air-quality-rehearsal.json)

## 1 · Did the air get better?

Imagine you are taking over a shift. Someone has already responded to an air-quality warning. They opened a damper. The controller acknowledged the command. The fan is running. People are still in the room. What do you tell them about the air?

I want to know three things. How much did the air change after the adjustment? When did we first see the room reach its targets? And when I start my shift, have we actually seen it stay there? Those are questions about the room where people work. A receipt from the equipment answers a different, useful question about what the controller received. openSoom brings the two records together so the person on duty can answer responsibly.

## 2 · Why this question belongs to the facility

One starting point was a school kitchen in Seoul. A government inspection found ventilation performance that needed improvement. Installing equipment is an important step. Once a facility is operating, someone also has to decide whether an adjustment achieved the conditions intended for that zone. A technician visiting once and a supervisor taking over every morning need different evidence.

A classroom and a cooking line can use the same method and have different targets. The facility defines which conditions it expects. In this demonstration the cooking line tracks fine particles, called PM2.5, and carbon dioxide. We compare each to the target configured for that zone. The values in this talk come from virtual equipment, with real software processing the observations. A field deployment would first establish sensor placement, targets and sampling cadence with the facility.

## 3 · Read the room before diagnosing the equipment

Look at the cooking-line trial. The reading before the command was 75 micrograms of fine particles per cubic metre. In the recovery trial it fell to 15. Carbon dioxide went from 1,500 to 720 parts per million. Each comparison belongs to the same zone and the same adjustment. The operator can open the measurement records and check their acquisition times.

Now change just the outcome. In the persistent-particles trial the air is moving and carbon dioxide improves, but particles are still at 60. That is above this zone’s target of 45. A reassuring number on the carbon dioxide row would be a poor reason to close the warning. The operator needs to see which condition still needs attention. A different person coming on duty should be able to reach the same conclusion from the same evidence.

## 4 · When is an inspection useful?

If the room is still outside its targets, we next look for an appropriate follow-up. The case on this slide is a separate equipment test. Airflow remained low after the adjustment. An independent sensor then measured only 35 percent shaft opening. That gives the technician a concrete first check at the actuator and its position feedback. It still takes a field examination to identify the cause.

In the particles-only trial the measured airflow is already adequate. A high particle reading alone gives us no reason to send someone to inspect a damper shaft. Keeping the room alert open and knowing which inspection to request are two separate decisions. That distinction matters when the next person inherits the case.

## 5 · See the three outcomes

*Play the complete captioned air-quality film. Then open the dashboard, select the cooking line and run “Air clears after ventilation”. Let the audience watch the first valid observation and the next in-range observation. Allow about 30 seconds for this live demonstration.*

Watch the two clocks. The first starts at device acknowledgement and ends at the first subsequent observation where both pollutants meet their targets. The second counts the observed span in range. A single good reading starts a span of zero seconds. Only a later qualifying measurement adds time. The timestamps come from the measurements. Reading the screen a minute later cannot add a minute of evidence.

In the rebound trial the particles rise again. We still know when the targets were first reached, and we can see the earlier span that ended. That is exactly the distinction I would want at a shift change. When the sensor goes quiet, the interface shows that the evidence has aged. We cannot fill in the missing interval by assuming the room stayed the same.

## 6 · Put the evidence in the next shift’s hands

*Open Measurement evidence. Point to the baseline, the acknowledgement and the latest observation. Show the technician workbench if time permits.*

The supervisor can give a precise handover. Here is the last reading before the action. Here is the controller’s acknowledgement. Here are the later observations that support our decision. For every comparison the values keep their units, their time and their original measurement identity. A second adjustment starts its own comparison. The first one remains available for review.

The maintenance team sees its own work order. A technician can record which version they reviewed and what they intend to inspect. A recovered air-quality reading can sit alongside an open field inspection. That lets the supervisor describe the room as observed while the technician remains responsible for the work they have taken on.

## 7 · The equipment evidence has a specific job

In another workshop the airflow stayed at 515 cubic metres per hour, below the local target of 560. In the first adjustment the shaft fell well short of the requested opening. A later adjustment brought the shaft close to its requested position. The airflow was still low, so the first inspection shifted from the actuator to the airflow path. The same work order kept the sequence.

That example explains why our operating interface preserves several kinds of observation. Concentrations help tell a facility what happened in the room. Airflow and independent mechanical position can help a technician choose the next inspection when airflow itself is deficient. A facility with a trustworthy local sensor can use it directly. A facility that contracts a separate sensor provider can bring in the same evidence through the edge service.

## 8 · How it works

*Keep the implementation explanation to about one minute.*

The sensor adapter writes timestamped measurements to the facility’s oneM2M node. A subscription tells the operations app that new evidence is available. The app checks the original record, connects it to the correct command and acknowledgement, and applies that zone’s targets. The operator dashboard reads the result. An independently authorized maintenance app can work from the same event and maintain the inspection order. The CSE enforces the different permissions. In a separate cloud demonstration, our MEC service bridge registered an external provider and retrieved its virtual shaft reading. The operating app retained authority over the device. This lets a facility change an adapter or provider while keeping the decision and its history intelligible to both people.

## 9 · Try it at another site

A manager can use the Codex plugin or a standalone model to prepare a virtual trial under the facility’s own profile. One previous request asked what would happen if a lounge supplied an old reading. The recorded exercise produced zero new commands. The original source record could still be checked after restart. A model can help the manager ask the question in ordinary language. Measurement times, target comparisons and permissions stay in the service.

For a second facility, I would start with one observed zone. Agree on its targets, sensor cadence and what the team considers a meaningful time in range. Give the oncoming supervisor two records, one sustained and one with a rebound, and ask them to explain what happened without help.

## 10 · What we can show today

Across an earlier comparison, sixteen designed virtual cases still required investigation. Accepting the equipment acknowledgement alone closed fourteen of those cases. Looking only at two airflow readings closed two. openSoom kept all sixteen open. Today’s three runs make the reason visible directly in a room’s pollution readings and timestamps.

We can reproduce what changed after the adjustment and how long the sensors observed it. Demonstrating that a particular intervention caused the improvement, or that a real room stayed healthy for an entire shift, would require field evidence. The source, facility profiles and runnable trials are public. I would start a field pilot with the question we began with. When the next shift arrives, can they tell how much the air improved, how soon it reached the target, and how long that conclusion was supported? Thank you.
