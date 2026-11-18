# The fan is running

[Watch the 45-second PR film](../../openSoom-pr-45s.mp4) · [English closed captions](captions.en.srt) · [Master verification and source hashes](../../../../evidence/video/cinematic/pr-qa.json)

The film follows an operator and a maintenance team responding to one simulated airflow fault. Each facility defines the target for its own zone. Values are cubic metres per hour.

| Time | Picture | Source |
| --- | --- | --- |
| 0:00–0:05 | A working fan raises a question about airflow. | [Adobe Firefly kitchen motion](../firefly/kitchen-motion.mp4), an illustrative facility |
| 0:05–0:10 | The cooking line delivers 360 against its configured target of 900. | [Illustrative Firefly plant motion](../firefly/plant-motion.mp4) with [recorded case values](../../../../evidence/video/cinematic/pr-dashboard-recording.json) |
| 0:10–0:13 | The facility manager opens the airflow view. | [Original dashboard take](food-unresolved-session.webm) |
| 0:13–0:21.5 | Two independent applications use one observation to request a permitted action and open an inspection order. | Reconstructed from a [separate three-process run and its CSE readbacks](../../../../evidence/runtime/multiapp/no_recovery/result.json) |
| 0:21.5–0:29 | A device acknowledges the command. Airflow stays at 360. | [Cooking-line recording](food-unresolved-session.webm), run `demo-49a9dd79ed`, command `cmd-57931cb2b1ea` |
| 0:29–0:34 | A learning facility introduces a second zone profile. | [Adobe Firefly learning-space motion](../firefly/learning-motion.mp4), an illustrative facility |
| 0:34–0:38.5 | The studio delivers 200 against its configured 500 target. | [Actual second-facility recording](../demo/learning-session.webm), [run `demo-6afdf15ef2`](../../../../evidence/video/cinematic/dashboard-recordings.json) |
| 0:38.5–0:45 | oneM2M and the openSoom repository | [Original project mark](../../../../web/mark.svg) and editorial motion design |

The physical sensors and actuators are simulated. Both unedited WebM takes show the real openSoom browser UI and service operating against a temporary ACME CSE. The application diagram uses the independently executed multi-application evidence. The source observation was `cinixzfLRPrDC`.

Adobe Firefly provided three moving scene illustrations, the Jennifer English speech recording and the original stereo score. The local edit places each spoken phrase against the relevant picture and reduces music beneath speech. The MP4 contains selectable English CC. Original project media are licensed under CC BY 4.0 with attribution to openSoom contributors.

## Reproduce the master

On the editing system, use Python, NumPy, Pillow, FFmpeg with libx264 and AAC, and the macOS Avenir Next and Menlo fonts. The supplied video takes and sound stems are sufficient.

```sh
python3 scripts/cinematic/pr_audio.py
python3 scripts/render_pr_film.py --final-picture --mix tmp/pr-film/pr-mix.wav
python3 scripts/cinematic/check_master.py pr
```

To capture a new isolated cooking-line fault, use `python3 scripts/cinematic/capture_demo.py --take food-unresolved --output tmp/pr-film/new-take` after setting up the local ACME and Playwright prerequisites. A new recording has its own identifiers. Preserve its associated JSON record when editing.
