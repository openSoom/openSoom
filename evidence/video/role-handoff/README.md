# How the two incidents were filmed

The evaluation film moves from a local air-quality trial to a separate cloud maintenance incident. Both used virtual equipment. The two original runs have different commands and incident IDs.

| Segment | Recorded input | What the film shows |
| --- | --- | --- |
| 00:00–00:21 · Operations | [Original operator recording](operator-source.mp4) and [stored command and incident](operator-incident.json), run `demo-bd5a62228f`. | The dashboard updates in acquisition order. It ends at PM2.5 60 µg/m³ and CO₂ 720 ppm. The PM2.5 target was 45 and the CO₂ target was 1,200. The same incident was archived open. The last dashboard frame is held while this disposition is explained. |
| 00:21–00:56 · Maintenance | [Cloud technician handoff](../../runtime/option-c/technician-handoff.json), run `demo-c172aa90d9`. | The recorded workbench renders successive archived states of `work-incident-ece6a50668`. Revision 3 is a general inspection at 360 m³/h against 900. The MEC 046 GET returned a separate virtual shaft sensor value of 35% for the 100% command. Revision 4 recommends checking actuator travel and position feedback first. The technician's scheduled entry belongs to that revision. The operator's later read still shows an open incident. |

The held operator panel shows the 02:05:41 KST observation. The on-screen source reference identifies the subsequent persisted sample at 02:05:43 KST. Both returned PM2.5 60 µg/m³, CO₂ 720 ppm and airflow 1,035 m³/h for the same run. [Both native reads and their acquisition times](operator-native-readings.json)

The cloud screen is an offline replay of the recorded response using the actual technician HTML, CSS and JavaScript. The public receipt includes the selected work order, so the replay shows its detail pane. The replay supplies its facility zone label from the food-production profile, the original requested opening from the recorded command and the scheduled activity from the recorded entry. The film identifies this replay on screen. The public source receipt records the real integration through native services; the film requests no cloud resources. A human inspection or physical repair would require field evidence.

The [filmed workbench sources](filmed-workbench) preserve the exact HTML, CSS and JavaScript from [the filmed release](https://github.com/openSoom/openSoom/tree/e3a036e185cff099c2e7c2f239e10a7ac5740b9c/src/opensoom/technician_web). Replay uses these files so that the recorded evidence remains reproducible as the live dashboards evolve.

## Rebuild

From the repository root, use a macOS host with the Samantha English voice, Arial, FFmpeg/ffprobe, Python and Pillow. The film renderer reads the retained source clip, three workbench screenshots and the two source records. It writes the current MP4, English SRT and [source manifest](../air-quality-film.json).

```sh
python3 scripts/cinematic/render_role_handoff.py
python3 scripts/cinematic/verify_role_handoff.py
```

To recapture the technician detail views, run the following with Playwright available to Node and Chrome installed. Set `FILM_CHROME` if the executable is outside the standard macOS application path. Recorded responses are served inside the browser's request interception. The command produces three PNGs for the renderer in this directory.

```sh
node scripts/cinematic/capture_role_workbench.cjs evidence/video/role-handoff
```

The source-only operator clip and incident excerpt can also be regenerated from the original [capture procedure](../../../scripts/cinematic/capture_air_quality.cjs) and its paired persisted SQLite database using [retain_role_source.py](../../../scripts/cinematic/retain_role_source.py). A new live trial has its own IDs. The retained release source is sufficient to render the existing film.
