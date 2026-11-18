# openSoom evaluation script

Use the [English slides](../../deliverables/presentation/openSoom-evaluation.pptx), [slide PDF](../../deliverables/presentation/openSoom-evaluation.pdf) and [English 720p film](../../deliverables/video/openSoom-work-order-720p.mp4). The italic lines are screen cues. Have the film available offline with audio and captions, and open the local [dashboard](http://127.0.0.1:19490/) before the session. A fresh run has its own incident and work-order IDs. The slides and film use the same retained run. [Korean rehearsal script](presenter-script.ko.md) · [Q&A](technical-qa.md)

**Timed English read-through** · 11 minutes 11 seconds including 1 minute 45 seconds of video. The implementation explanation on slide 8 takes 49 seconds. Times below come from synthesized English narration and the actual film. Allow for your own speaking pace.

S1 0:00 · S2 0:41 · S3 1:47 · S4 2:55 · S5 3:56 · S6 5:58 · S7 7:11 · S8 8:08 · S9 8:56 · S10 10:10

**If asked about deployment:** On one VM we selected two logical edges in turn. The actual Sandbox deployed the MN-CSE and maintenance app to each, where a fresh work order consumed the external shaft reading. [Controller and product receipts](../../evidence/runtime/option-c/index.json)

## 1 · Did the air actually move?

*Start on the cover.*

Imagine you take over a shift at a facility. The previous supervisor tells you that one zone had low airflow, that they requested a damper adjustment, and that the equipment acknowledged it. People are still working in the room. What would you need to see before you sign off on that incident?

I would want a fresh measurement from that zone, taken after the adjustment, and the airflow target that applies to this equipment. If the reading still falls short, I would want the technician coming on duty to know what has already been tried. Those are the two decisions I built openSoom around. Can the supervisor close the incident? If it stays open, what should maintenance inspect first?

## 2 · The inspection that prompted the question

*Show the source and the commissioning guidance.*

In November 2025, Korea’s Ministry of Employment and Labor inspected a school kitchen in Gangseo, Seoul. The ministry checked the performance of ventilation equipment, including hoods, and recommended improvements where performance was insufficient. The professional question for someone running that kitchen the following week is how to keep checking that the equipment delivers the performance expected in each part of the room.

There is a practical starting point. The UK Health and Safety Executive’s guidance on commissioning local exhaust ventilation calls for checking hood performance and recording measurements and operating conditions. Those records can supply a benchmark when performance is questioned later. Each site needs its own benchmark. The airflow target in today’s cooking-line demonstration belongs to a simulated facility profile.

A school kitchen made the question concrete. A production line or a learning facility can also have several zones, people who change shifts and equipment with different targets. The shared part is the decision they need to explain. [Ministry inspection report](https://www.moel.go.kr/news/enews/report/enewsView.do?news_seq=18528) · [HSE commissioning guide](https://www.hse.gov.uk/lev/commissioning.htm)

## 3 · The site operator’s decision

*Point to the target, then the follow-up measurement.*

Here is one cooking line in our virtual facility. Its configured target is nine hundred cubic metres per hour. The fan reports that it is running. Operations requests a fully open damper and the controller acknowledges the command. Now the operator checks the next airflow observations from the same zone. They stay at three hundred sixty cubic metres per hour.

That gives the supervisor a decision they can defend at handover. Keep the incident open. The record preserves the command that was tried, the acknowledgement that arrived and the later observation that justified leaving the incident unresolved. Imagine the incoming shift looking only at the last command. They might spend time repeating an adjustment that the controller has already accepted. The follow-up reading gives them a reason to move on to inspection.

There is one more detail the handover needs. Nine hundred is the target for this particular cooking line. A different room could have a different target, and a measurement taken before the adjustment could describe an earlier condition. Recording which zone, which target and when the air was measured keeps the comparison meaningful.

## 4 · The technician’s first inspection

*Compare the requested opening with the separate shaft reading.*

The technician has a different question. Several things can leave the measured airflow low. Looking at the airflow reading alone gives the technician a general inspection to perform, with little help choosing a starting point.

Now an independent sensor on the mechanical shaft becomes available. It reports thirty-five percent open after the actuator has had time to settle. Both the independent measurement and the command refer to this damper. A command for one hundred percent alongside a shaft measurement of thirty-five percent gives the technician a specific first check. Inspect actuator travel and position feedback. The technician still needs to establish what caused the mismatch in the field.

The same work order changes priority. The airflow incident remains open. A sensor from another asset, a value in the wrong unit or a reading without a usable measurement time would leave the technician with the earlier, general inspection. Choosing when the evidence is sufficient is as important as choosing what to do when it is.

## 5 · The recorded incident

*Play the full 720p work-order film with audio. Resume on slide 6.*

As the film plays, watch the requested opening, the later airflow and the independent shaft position. Together they tell two people on the same shift what to do next. The equipment is simulated. You will see the dashboard and the records produced by running the software.

## 6 · Handover on the live dashboard

*Switch to the dashboard. Select Northworks food production, then show Maintenance work order. Open Work order evidence. If the local dashboard is unavailable, use this slide’s capture and the film.*

Here is the record a manager can actually hand over. The command and the independent position appear next to the measured airflow. An open work order names the first inspection and shows the asset it belongs to. Opening the evidence lets us follow that decision back to the original measurement. Look at the order identifier and the independent sensor identifier. If two shifts discuss different pieces of equipment, those identifiers help them catch the mistake. The same information lets a technician check the source before acting on a surprising value.

There is a practical reason for keeping that identity. The maintenance app was stopped before this fault began in the recorded test. Operations still issued its permitted command and checked whether that restored airflow. When maintenance came back, it read the missed event and opened the work order. We restarted it again after the update and delivered duplicate notifications. The same order and the same set of revisions remained available.

For a team changing shifts, that means the person arriving can resume the inspection with the observations already attached. They can also explain why the incident remains open even though the technician now has a better first step.

## 7 · Where does this facility get the second measurement?

*Read across the three cases. The local and cloud demonstrations have different execution IDs.*

A facility with only the controller’s own report will have a general inspection to do. A facility that already has an independent shaft sensor can read it locally. In the case on screen, that was enough to change the work order.

Now consider a facility that contracts a different company to manage those sensors. Its technician needs access to the same measurement from a separate service. We ran the virtual incident again on a cloud host and obtained the independent reading from a running edge sensor-sharing service. The technician got the same priority on the work order for that cloud incident.

That is where the added integration earns its place. A site can use whichever source it has permission to access and give the technician the same reasoning for a first inspection. In a separate cloud test the provider was initially unavailable. The site authorized its enrolment through oneM2M. The independent reading then became available and updated the existing order.

## 8 · Where each application runs

*Use this slide for the implementation explanation. Trace the lower and upper paths once.*

The site’s oneM2M Middle Node stores readings, acknowledgements and incidents. Only the operations app issues device commands. The central node can read the resources shared by the site. Maintenance owns the work order. A separate bridge retrieves independent sensor evidence. Those applications have different permissions.

In the cloud test the bridge discovered the running sensor-sharing service through the ETSI MEC registry. It retrieved the independent reading and wrote a response to the site’s oneM2M node. Maintenance read that result and updated the work order. Our Option C design places oneM2M and the MEC platform on the same edge node. The two workers ran on one private Kubernetes host. Platform-managed placement across eligible hosts requires separate evidence.

## 9 · A manager can rehearse another zone

*Show the learning-space trial. Pause on the refusal and command count.*

A manager at another facility should be able to ask a different question. For this learning facility, the trial asks what happens if an eighty-eight-second-old airflow reading arrives from the lounge. The operator wants to know whether the system would still issue a command.

In the recorded test, a hosted language model used the shared plugin tools to save that trial, run it and read its result. The system refused the action on the old observation. Checking the oneM2M command container confirmed zero new device commands. In a separate restart test the same saved definition could be run again, and the adjacent zones retained their previous state. A fresh comparison created one virtual command and received a device acknowledgement.

That lets a manager test a proposed operating procedure before bringing a new zone into use. We also tested this through an installed Codex plugin. The model selected the trial tool for the lounge, with a different reading age of ninety-three seconds. A single approval allowed that specific virtual test. Codex saved, ran and read the trial. Again, zero device commands were added. After restarting the service we could still trace the result to the original observation.

## 10 · The next facility

*Return to the repository link. Leave this slide visible for questions.*

A facility adopting openSoom can start with its own zone names, commissioned targets, installed applications and equipment connections. A team with an existing local sensor can use it directly. A team with a separately managed sensor has a reason to connect the edge service. Both retain the operating question and a record they can follow.

For a real pilot, I would start with a technician and a shift supervisor in one zone. Compare the recorded readings with that site’s commissioning records. Ask whether the suggested first inspection helped them decide where to look, and which information the next shift still had to ask for. Those are field questions a software simulation cannot answer.

The repository contains the source, the virtual demo and the records behind today’s decisions. In this case, the manager keeps the incident open. The technician checks the actuator and its position feedback first. Both can point to the evidence that changed their decision. Thank you.
