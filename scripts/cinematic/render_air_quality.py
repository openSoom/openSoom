"""Render the earlier three-trial film into a private archive directory."""
import argparse
import json
import shutil
import tempfile
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw

from render_work_order import duration, font, run, srt_clock, digest

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / ".runtime/three-trial-film"
SCENES = {
    "air_quality_recovery": ("Recovery", [
        "Did the room air improve after ventilation? Watch the two pollutant readings.",
        "Both reach their targets. The second clock measures the observed spell in range."]),
    "air_quality_persistent": ("Particles persist", [
        "The same virtual cooking line receives another adjustment.",
        "Carbon dioxide falls. Fine particles stay above the zone target. Neither clock records attainment."]),
    "air_quality_rebound": ("Rebound", [
        "Here the readings initially reach both targets. Each new sample can extend the observed time.",
        "Particles rise again. The first target time and the previous spell remain visible."])
}


def render(directory, output):
    output.mkdir(parents=True, exist_ok=True)
    captured = json.loads((directory / "capture.json").read_text())["cases"]
    with tempfile.TemporaryDirectory(prefix="opensoom-outcome-film-") as tmpdir:
        tmp = Path(tmpdir)
        subtitle, scene_files, evidence = [], [], {}
        clock = 0
        for idx, (key, (heading, lines)) in enumerate(SCENES.items()):
            case = captured[key]
            frames = case["frames"]
            voices = []
            for j, line in enumerate(lines):
                voice = tmp / f"{idx}-{j}.aiff"
                run("/usr/bin/say", "-v", "Samantha", "-r", "156", "-o", voice, line)
                voices.append(voice)
            # The second caption describes the decisive screen. Keep the last
            # recorded frame displayed while its corresponding narration finishes.
            split = max(duration(voices[0]) + 0.45, frames[-1]["seconds"] - 1.1)
            length = split + duration(voices[1]) + 0.85
            cuts = sorted({0.0, split, length, *(p["seconds"] for p in frames)})
            manifest = tmp / f"{idx}.txt"
            entries = []
            selected = 0
            for n, (start, end) in enumerate(zip(cuts, cuts[1:])):
                while selected + 1 < len(frames) and frames[selected + 1]["seconds"] <= start:
                    selected += 1
                file = tmp / f"{idx}-{n}.png"
                with Image.open(directory / frames[selected]["file"]) as original:
                    screen = original.convert("RGB").crop((233, 40, 1266, 593))
                    screen.thumbnail((1180, 584), Image.Resampling.LANCZOS)
                canvas = Image.new("RGB", (1280, 720), "#123e34")
                draw = ImageDraw.Draw(canvas)
                draw.text((54, 12), "openSoom  /  " + heading, font=font(24, True), fill="#ffffff")
                draw.text((1226, 16), "Recorded dashboard · virtual cooking line",
                          anchor="ra", font=font(18), fill="#d2e2cb")
                canvas.paste(screen, ((1280-screen.width)//2, 55))
                caption = textwrap.fill(lines[int(start >= split)], 84)
                draw.multiline_text((640,662), caption, anchor="mm", font=font(23),
                                    fill="white", align="center", spacing=3)
                canvas.save(file)
                entries.append(f"file '{file.name}'\nduration {end-start:.6f}\n")
            entries.append(f"file '{file.name}'\n")
            manifest.write_text("".join(entries))
            clip = tmp / f"{idx}.mp4"
            split_ms = round(split*1000)
            run("ffmpeg", "-v","error","-y","-f","concat","-safe","0","-i",manifest,
                "-i",voices[0],"-i",voices[1],"-filter_complex",
                f"[1:a]adelay=180:all=1[a];[2:a]adelay={split_ms}:all=1[b];[a][b]amix=inputs=2:normalize=0,apad[audio]",
                "-map","0:v","-map","[audio]","-vf","fps=24,format=yuv420p","-t",str(length),
                "-c:v","libx264","-preset","fast","-crf","19","-c:a","aac","-ar","48000","-b:a","128k",clip)
            actual = duration(clip)
            for j,(start,end) in enumerate([(0,split),(split,actual)]):
                subtitle.append(f"{len(subtitle)+1}\n{srt_clock(clock+start)} --> {srt_clock(clock+end)}\n{lines[j]}\n")
            evidence[key]={k:v for k,v in case.items() if k!="frames"}
            evidence[key].update(starts_at=round(clock,3),seconds=actual,browser_frames=len(frames))
            clock+=actual
            scene_files.append(clip)
        concat=tmp/"list.txt"
        concat.write_text("".join(f"file '{file.name}'\n" for file in scene_files))
        srt=output/"openSoom-air-quality.en.srt"
        srt.write_text("\n".join(subtitle))
        movie=output/"openSoom-air-quality-720p.mp4"
        run("ffmpeg","-v","error","-y","-f","concat","-safe","0","-i",concat,"-i",srt,
            "-map","0:v","-map","0:a","-map","1:s","-c","copy","-c:s","mov_text",
            "-metadata:s:s:0","language=eng","-movflags","+faststart",movie)
        run("ffmpeg","-v","error","-i",movie,"-f","null","-")
        shutil.copyfile(directory/"air_quality_recovery-panel.png",output/"air-quality-dashboard.png")
        result={"public_film":movie.name,"sha256":digest(movie),"seconds":duration(movie),"resolution":[1280,720],
                "method":"Three distinct ordinary UI runs on a local native ACME and virtual equipment. Cropped original browser frames retain acquisition order and recorded elapsed time. Last screen held for narration. English synthetic voice, burned-in and selectable subtitles.",
                "cases":evidence}
        (output/"air-quality-film.json").write_text(json.dumps(result,indent=2)+"\n")
        print(json.dumps({"seconds":result["seconds"],"sha256":result["sha256"]}))

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory",type=Path)
    parser.add_argument("--output-dir", type=Path, default=ARCHIVE)
    args = parser.parse_args()
    render(args.directory.resolve(), args.output_dir.resolve())
