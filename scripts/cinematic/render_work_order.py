#!/usr/bin/env python3
"""Build the 720p film from the retained browser recording and the same work order."""
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat
import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import textwrap

ROOT = Path(__file__).resolve().parents[2]
VIDEO = ROOT / "deliverables/video"
CAPTURE = ROOT / "evidence/video/work-order"
SOUND = "/usr/bin/say"
GREEN = "#183c34"
WHITE = "#f5f4eb"


def run(*args):
    subprocess.run([str(arg) for arg in args], check=True, stdout=subprocess.DEVNULL)


def duration(file):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(file)]))


def font(size, bold=False):
    filename = "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf"
    return ImageFont.truetype(filename, size)


def srt_clock(seconds):
    ms = round(seconds * 1000)
    return f"{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}"


def draw_title(file, top, title, body, foot):
    frame = Image.new("RGB", (1280, 610), GREEN)
    draw = ImageDraw.Draw(frame)
    draw.text((72, 62), top, font=font(24), fill="#c4d9af")
    draw.multiline_text((70, 137), textwrap.fill(title, 28), font=font(59, True), fill=WHITE, spacing=7)
    draw.multiline_text((73, 349), textwrap.fill(body, 69), font=font(26), fill="#dfead8", spacing=12)
    draw.text((73,545),foot,font=font(19),fill="#bed0bb")
    frame.save(file)


# Measured against decoded frames in this particular browser recording. Playwright
# wall time and the WebM presentation clock have different origins.
RETAINED_WEBM = "4b7f13f5de5b0d2e8abe28f85bba51f8e08e5463b78c99bae18efffaf17fa0ec"
RETAINED_FRAMES = {"facility": 15.0, "ack": 6.05, "flow": 8.15, "shaft": 10.6,
                   "order": 18.7, "receipt": 22.0}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decision_frames(captured, capture_dir, recording, tmp):
    recording_hash = digest(recording)
    frames = {}
    if captured.get("frames"):
        if recording_hash != captured.get("recording_sha256"):
            raise ValueError("Browser recording differs from its capture manifest")
        for scene in RETAINED_FRAMES:
            source = captured["frames"][scene]
            image = (capture_dir / source["file"]).resolve()
            if not image.is_relative_to(capture_dir.resolve()) or digest(image) != source["sha256"]:
                raise ValueError("Unverified screenshot for " + scene)
            frames[scene] = image
    elif recording_hash == RETAINED_WEBM:
        for scene, seconds in RETAINED_FRAMES.items():
            image = tmp / (scene + "-still.png")
            run("ffmpeg", "-v", "error", "-y", "-i", recording, "-ss", str(seconds), "-frames:v", "1", image)
            frames[scene] = image
    else:
        raise ValueError("Capture a screenshot for each scene in the new recording")
    return frames


def retained_lengths(captions, lines):
    # The published SRT preserves the edit's 24 fps frame boundaries.
    def frame(clock):
        h, m, s, ms = (int(n) for n in re.split('[:,]', clock))
        return round((h * 3600 + m * 60 + s + ms / 1000) * 24)
    blocks = captions.read_text().strip().split('\n\n')
    if len(blocks) != len(lines):
        raise ValueError("Captions do not match scene count")
    lengths = []
    previous = 0
    for block, (_, line) in zip(blocks, lines):
        _, times, *words = block.splitlines()
        start, end = map(frame, times.split(' --> '))
        if ' '.join(words) != line or start != previous or end <= start:
            raise ValueError("Caption text or timing differs from the narration")
        lengths.append((end - start) / 24)
        previous = end
    return lengths


SCREEN_FILTER = ("scale=1280:610:force_original_aspect_ratio=decrease,"
                 "pad=1280:610:(ow-iw)/2:(oh-ih)/2:color=0x183c34,setsar=1")


def pixels(source, filters, offset=None):
    seek = ["-ss", str(offset)] if offset is not None else []
    buf = subprocess.check_output(["ffmpeg", "-v", "error", *seek, "-i", str(source), "-vf", filters,
                                   "-frames:v", "1", "-pix_fmt", "rgb24", "-f", "rawvideo", "-"])
    return Image.frombytes('RGB', (1280, 610), buf)


def verify_screen(args):
    report = json.loads((CAPTURE / "film.json").read_text())
    captured = json.loads((args.capture_dir / "capture.json").read_text())
    film = VIDEO / "openSoom-work-order-720p.mp4"
    if digest(film) != report["film_sha256"]:
        raise ValueError("Film bytes differ from the release manifest")
    with tempfile.TemporaryDirectory(prefix="opensoom-screen-check-") as raw:
        images = decision_frames(captured, args.capture_dir, args.recording, Path(raw))
        expected = {scene: pixels(path, SCREEN_FILTER) for scene, path in images.items()}
        start, tested = 0, 0
        for row in report["scenes"]:
            scene, length = row["scene"], row["seconds"]
            if scene in expected:
                for offset in (.2, length / 2, length - .2):
                    actual = pixels(film, "crop=1280:610:0:0", start + offset)
                    errors = {name: sum(ImageStat.Stat(ImageChops.difference(actual, image)).mean) / 3
                              for name, image in expected.items()}
                    if min(errors, key=errors.get) != scene or errors[scene] > 5:
                        raise ValueError(f"Screen mismatch during {scene} at {start + offset:.3f}s")
                    tested += 1
            start += length
    print(f"Matched {tested} screen positions across {len(expected)} narrated scenes.")


def render(args):
    source = json.loads(args.evidence.read_text())
    captured = json.loads((args.capture_dir / "capture.json").read_text())
    assert source["run_id"] == captured["run_id"] and source["after"]["work_order_id"] == captured["work_order_id"]
    assert source["after"]["sample"]["value"] == 35 and source["airflow"]["observed"] == 360
    cloud = json.loads((ROOT / "evidence/runtime/mec-maintenance-roundtrip.json").read_text())
    assert cloud["after"]["work_order_id"] == cloud["before"]["data"]["work_order_id"]
    assert cloud["after"]["provider_receipt"]["lookup_status"] == 200 and cloud["after"]["sample"]["value"] == 35
    model = json.loads((ROOT / "evidence/agent/scenario-authoring/standalone-verified.json").read_text())
    assert model["outcome"] == "PASS_HOSTED_LLM_E2E"
    scenes = [
        ("kitchen", "A fan is running. A damper has acknowledged its command. Can the shift supervisor close the ventilation incident?"),
        ("problem", "A Korean labor ministry inspection called for better exhaust performance in a school kitchen. Each facility needs a way to check its own equipment between inspections."),
        ("facility", "In this virtual cooking line, the site target is nine hundred cubic metres per hour. The operations app requests a fully open damper."),
        ("ack", "The controller acknowledges one hundred percent. That tells the operator the command arrived. It still leaves a question about the air."),
        ("flow", "The next airflow measurement is three hundred sixty cubic metres per hour. The operator keeps the incident open and maintenance starts a general inspection."),
        ("shaft", "A separate sensor on the mechanical shaft reports thirty-five percent open. The technician now has a reason to check actuator travel and position feedback first."),
        ("order", "Here is the live dashboard for that run. The work order keeps its original identity. Its inspection priority changes while the airflow incident stays open."),
        ("receipt", "The source measurement, command and inspection are linked through actual oneM2M resources. Restarting the maintenance app recovered the same order without duplicating it."),
        ("cloud", "In a second run, the bridge discovered an actual MEC sensor-sharing service, retrieved a separate provider’s shaft measurement, and returned it to the facility. The same inspection took priority."),
        ("agent", "At a learning facility, a manager can describe another trial. A hosted model saved a new lounge scenario and read the result. Stale evidence created zero device commands."),
        ("close", "Run openSoom on your own machine. Choose the zone, set the facility target, and replay the decision with virtual equipment. The code, traces and tools are open source.")
    ]
    order_id = source["after"]["work_order_id"]
    with tempfile.TemporaryDirectory(prefix="opensoom-film-", dir=VIDEO) as raw:
        tmp = Path(raw)
        draw_title(tmp / "problem.png", "Why this matters", "An installed system still needs checking.",
                   "A November 2025 school-kitchen inspection in Seoul called for improvements to ventilation performance.", "Source · Republic of Korea Ministry of Employment and Labor, 3 Nov 2025")
        draw_title(tmp / "cloud.png", "Cloud test · ETSI MEC 046 Sensor Sharing", "A second provider, the same inspection.",
                   "The bridge discovered the service, read the mapped sensor and wrote its response to the MN-CSE. The technician saw 35% on the same work order.", cloud["run_id"] + "  /  " + cloud["after"]["work_order_id"])
        draw_title(tmp / "agent.png", "A second facility · Westside learning hub", "Try it in another room.",
                   "An actual model saved a lounge scenario, ran it and read back the CSE observation. The stale reading produced zero new device commands.", model["id"])
        draw_title(tmp / "close.png", "openSoom", "Did the air actually move?",
                   "Replay the virtual case. Change the facility profile. Connect a different adapter.", "github.com/openSoom/openSoom")
        frames = decision_frames(captured, args.capture_dir, args.recording, tmp)
        captions = VIDEO / "openSoom-work-order.en.srt"
        lengths = retained_lengths(captions, scenes) if args.preserve_audio else None
        total, subtitles, media = 0, [], []
        for index, (scene, line) in enumerate(scenes):
            prefix = tmp / str(index)
            audio = prefix.with_suffix(".aiff")
            if lengths is None:
                run(SOUND, "-v", "Samantha", "-r", "162", "-o", audio, line)
                seconds = duration(audio)
                if seconds < 1:
                    raise ValueError("Narration unavailable")
                length = round((seconds + .65) * 24) / 24
            else:
                length = lengths[index]
            cap = Image.new("RGB", (1280,110), GREEN)
            draw = ImageDraw.Draw(cap)
            if scene == "kitchen":
                draw.text((22, 5), "AI-generated kitchen illustration", font=font(17, True), fill="#c4d9af")
            wrapped = textwrap.fill(line, width=92)
            draw.multiline_text((640,55),wrapped,font=font(23),fill=WHITE,anchor="mm",align="center",spacing=5)
            sub = prefix.with_suffix(".png")
            cap.save(sub)
            if scene == "kitchen":
                inputs = ["-stream_loop", "-1", "-i", VIDEO / "cinematic/firefly/kitchen-motion.mp4"]
            else:
                inputs = ["-loop", "1", "-framerate", "24", "-i", frames.get(scene, tmp / (scene + ".png"))]
            clip = prefix.with_suffix(".mp4")
            filters = (f"[0:v]fps=24,{SCREEN_FILTER},tpad=stop_mode=clone:stop_duration=30[top];"
                       "[top][1:v]vstack=inputs=2,format=yuv420p[v]")
            audio_input = [] if lengths else ["-i", audio]
            audio_map = [] if lengths else ["-map", "2:a", "-af", "apad", "-c:a", "aac", "-ar", "48000", "-ac", "2"]
            run("ffmpeg", "-loglevel", "error", "-y", *inputs, "-loop", "1", "-framerate", "24", "-i", sub,
                *audio_input, "-filter_complex", filters, "-map", "[v]", *audio_map, "-t", length,
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", clip)
            subtitles.append(f"{index+1}\n{srt_clock(total)} --> {srt_clock(total+length)}\n{textwrap.fill(line,80)}\n")
            total += length
            media.append({"scene":scene,"seconds":length})
        manifest = tmp/"segments.txt"
        manifest.write_text("".join(f"file '{i}.mp4'\n" for i in range(len(scenes))))
        output = VIDEO / "openSoom-work-order-720p.mp4"
        edited = tmp / "final.mp4"
        if args.preserve_audio:
            # Preserve the original AAC packets and English text timing, including
            # the established video delay relative to the first AAC packet.
            delay = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                "stream=start_time", "-of", "csv=p=0", str(args.preserve_audio)], text=True).strip()
            run("ffmpeg", "-v", "error", "-y", "-itsoffset", delay, "-f", "concat", "-safe", "0", "-i", manifest,
                "-i", args.preserve_audio, "-map", "0:v", "-map", "1:a:0", "-map", "1:s:0", "-c", "copy",
                "-metadata:s:s:0", "language=eng", "-movflags", "+faststart", edited)
            if abs(duration(edited) - duration(args.preserve_audio)) > .001:
                raise ValueError("Edited video no longer matches the original audio duration")
        else:
            captions.write_text("\n".join(subtitles))
            run("ffmpeg","-loglevel","error","-y","-f","concat","-safe","0","-i",manifest,"-i",captions,
                "-map","0:v","-map","0:a","-map","1:0","-c:v","copy","-c:a","aac","-c:s","mov_text",
                "-metadata:s:s:0","language=eng","-movflags","+faststart",edited)
        edited.replace(output)
        report = {"run_id":source["run_id"],"work_order_id":order_id,"sensor_route":source["sensor_path"],
                  "seconds":duration(output),"dimensions":[1280,720],"software":"real CSE + dashboard capture",
                  "cloud_comparison_run":cloud["run_id"],"equipment":"virtual","opening":"AI-generated facility illustration",
                  "narration":"English synthesized voice","captions":"burned in and selectable","scenes":media,
                  "film_sha256": digest(output)}
        (CAPTURE/"film.json").write_text(json.dumps(report,indent=2)+"\n")
        print(json.dumps(report))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recording", type=Path, default=VIDEO / "cinematic/demo/maintenance-work-order.webm")
    parser.add_argument("--capture-dir", type=Path, default=CAPTURE)
    parser.add_argument("--evidence", type=Path, default=ROOT / "evidence/runtime/maintenance-release-local.json")
    parser.add_argument("--preserve-audio", type=Path, help="Reuse the current film's encoded narration and subtitles")
    parser.add_argument("--verify-screen", action="store_true", help="Compare the film to its six source screens")
    arguments = parser.parse_args()
    if arguments.verify_screen:
        verify_screen(arguments)
    else:
        render(arguments)
