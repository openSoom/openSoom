# openSoom evaluation script

Use the [English slides](../../deliverables/presentation/openSoom-evaluation.pptx), [slide PDF](../../deliverables/presentation/openSoom-evaluation.pdf) and [English 720p film](../../deliverables/video/openSoom-work-order-720p.mp4). The italic lines are screen cues. Have the film available offline with audio and captions, and open the local [operator console](http://127.0.0.1:19490/) and [technician workbench](http://127.0.0.1:19492/) before the session. The film replays the cooking-line case. The workbench and archive workshop are separate demonstrations with their own records. [Korean rehearsal script](presenter-script.ko.md) · [Q&A](technical-qa.md)

**Timed English read-through** · 11 minutes 27 seconds including 1 minute 45 seconds of video. The implementation explanation on slide 8 takes 51 seconds. Times below come from synthesized English narration and the actual film. Allow for your own speaking pace.

S1 0:00 · S2 0:41 · S3 1:47 · S4 2:55 · S5 3:56 · S6 6:01 · S7 7:05 · S8 8:16 · S9 9:07 · S10 10:21

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

## 5 · The recorded operator case

*Play the complete 720p operator film with audio. Return to slide 6.*

As the film plays, watch for the fully open command, the later airflow and the independent shaft position. This is the recorded cooking-line case. Its equipment is simulated. The software created the records you are about to see. After the film, we will follow one work order into the technician’s own workspace.

## 6 · From the shift supervisor to the technician

*Open the local operator console and technician workbench in separate tabs. Show the active facility and work-order ID. In the virtual demo, choose “Inspection scheduled” and “Save inspection entry.” Point to the returned record ID. If time is short, use the slide.*

Here is what changes at handover. The supervisor uses the operator console to check what the controller accepted and what the airflow sensor reported afterwards. The incident is still open. The supervisor can give the arriving technician a work-order identifier, the asset to inspect and the reason the job took priority. That is a more specific handover than asking someone to take a look at the ventilation.

The technician opens a separate workbench for that facility. They read the recommendation and the observations behind it. For this demo, they schedule the inspection and save an entry against the revision they reviewed. The workbench returns a receipt. Site operations can read that record back. The inspection entry tells the next shift what was recorded. The airflow incident still needs its own evidence before it can close.

The filmed case showed the operating side of this handover. The workbench is running locally for today’s demonstration. A technician working at a real facility would still have to examine the equipment and establish the cause.

## 7 · The same airflow shortfall can lead to two different inspections

*Point across the two rows. Both belong to the same conservation bench and work order. Each row has its own acknowledged command and independently timed virtual shaft reading.*

Consider another facility, an archive workshop with an extraction bench in the conservation room. Its own commissioning profile sets an airflow target of five hundred sixty cubic metres per hour. On both checks, the measured airflow is five hundred fifteen. If we only displayed that shortfall, the technician would receive the same advice twice.

In the first check, the controller accepts a request for eighty percent opening. The independent shaft sensor reads thirty-five percent. The first inspection is the actuator and its position feedback. On a later command the controller accepts ninety-five percent, and the shaft now reads ninety-three percent. The measured position is within this workshop’s configured tolerance. With airflow still low, the first inspection moves to the airflow path.

The work-order identifier stays the same. The second check has its own command and sensor reading. Depending on what the hardware actually does, the technician starts in a different place. Both outcomes came from the running software with virtual equipment. We have yet to measure which first inspections help technicians in a real workshop.

## 8 · Where the applications run

*Spend about one minute on architecture. Point from the local human applications to the edge and central services.*

The operator console and technician workbench serve two people. At the site, oneM2M stores readings, work orders and inspection receipts. Only operations can send device commands. The technician’s facility identity can record an inspection. In the background, a maintenance application updates work orders. A separate bridge retrieves independent readings. A provider can join through MEC 033 and share a virtual sensor reading through MEC 046. The central node reads shared records.

In our earlier Option C cloud test, the operator selected the north logical host, then the south. The Sandbox controller used Helm to place the site node and maintenance app together at each host. Both hosts shared one cloud VM. Today’s technician workbench runs locally.

## 9 · A manager can rehearse another zone

*Show the learning-space trial. Pause on the refusal and command count.*

A manager at another facility should be able to ask a different question. For this learning facility, the trial asks what happens if an eighty-eight-second-old airflow reading arrives from the lounge. The operator wants to know whether the system would still issue a command.

In the recorded test, a hosted language model used the shared plugin tools to save that trial, run it and read its result. The system refused the action on the old observation. Checking the oneM2M command container confirmed zero new device commands. In a separate restart test the same saved definition could be run again, and the adjacent zones retained their previous state. A fresh comparison created one virtual command and received a device acknowledgement.

That lets a manager test a proposed operating procedure before bringing a new zone into use. We also tested this through an installed Codex plugin. The model selected the trial tool for the lounge, with a different reading age of ninety-three seconds. A single approval allowed that specific virtual test. Codex saved, ran and read the trial. Again, zero device commands were added. After restarting the service we could still trace the result to the original observation.

## 10 · What should a field pilot test?

*Show the denominators. These are predeclared virtual cases. Leave the repository link visible for questions.*

We tested those two shift decisions on nine designed scenarios at each of two facilities. There were sixteen runs where the incident should stay open. An acknowledgement-only rule called fourteen recovered. A rule using the two latest airflow readings called two recovered. openSoom kept all sixteen open. In the four cases with a specific first inspection, its recommendation matched the reference in all four. The simpler rules gave a general inspection.

That tells us which evidence mattered in these software tests. The next question belongs to a real technician and a shift supervisor. I would start with one zone, its commissioned target and its actual inspection records. Did the work order send the technician to a sensible first check? Could the next shift see what was scheduled and what still needed verification? Those are the outcomes I would measure before expanding to a second zone.

The source, the virtual facility and the case-by-case records are public. You can change the facility profile and test how the same two decisions would play out at your own site. Thank you.
