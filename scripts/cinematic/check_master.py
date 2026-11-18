"""Decode each release master, verify its media, and regenerate the final-frame review sheet."""
import argparse
import hashlib
import io
import json
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "evidence/video/cinematic"


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def run(*args):
    return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


def frame_sheet(master, shots):
    cols = 3 if len(shots) <= 9 else 4
    thumb_w, thumb_h = 320, 180
    sheet = Image.new("RGB", (cols * thumb_w, ((len(shots) + cols - 1) // cols) * (thumb_h + 30)), "#132821")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=15)
    for index, (name, t) in enumerate(shots):
        data = run("ffmpeg", "-v", "error", "-nostdin", "-ss", str(t), "-i", str(master), "-frames:v", "1",
                   "-vf", f"scale={thumb_w}:{thumb_h}", "-c:v", "png", "-f", "image2pipe", "-").stdout
        image = Image.open(io.BytesIO(data)).convert("RGB")
        x, y = index % cols * thumb_w, index // cols * (thumb_h + 30)
        sheet.paste(image, (x, y))
        draw.text((x + 8, y + thumb_h + 6), f"{int(t // 60)}:{int(t % 60):02}  {name}", fill="white", font=font)
    encoded = io.BytesIO()
    sheet.save(encoded, "JPEG", quality=93)
    return encoded.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("which", choices=["demo", "pr"])
    parser.add_argument("--record", action="store_true",
                        help="Record a deliberately approved cut; by default compare it with the frozen manifest.")
    args = parser.parse_args()
    film = args.which
    stem = "openSoom-demo-5min" if film == "demo" else "openSoom-pr-45s"
    master = ROOT / "deliverables/video" / (stem + ".mp4")
    seconds = 300 if film == "demo" else 45
    qa_file = EVIDENCE / (film + "-qa.json")
    qa = json.loads(qa_file.read_text())
    media = json.loads(run("ffprobe", "-v", "error", "-show_entries",
                           "format=duration,size:stream=codec_name,codec_type,width,height,r_frame_rate,sample_rate,channels,duration,nb_frames:stream_tags=language",
                           "-of", "json", str(master)).stdout)
    video, audio = media["streams"][:2]
    assert (video["width"], video["height"], video["r_frame_rate"], video["nb_frames"]) == (1920, 1080, "24/1", str(seconds * 24))
    assert video["codec_name"] == "h264" and audio["codec_name"] == "aac" and audio["sample_rate"] == "48000"
    assert float(media["format"]["duration"]) == float(video["duration"]) == float(audio["duration"]) == seconds
    run("ffmpeg", "-v", "error", "-xerror", "-nostdin", "-i", str(master), "-f", "null", "-")
    report = run("ffmpeg", "-v", "info", "-nostats", "-nostdin", "-i", str(master), "-map", "0:a",
                 "-af", "ebur128=peak=true", "-f", "null", "-").stderr.decode().split("Summary:")[-1]
    loudness = float(re.search(r"I:\s*([-\d.]+) LUFS", report).group(1))
    peak = float(re.search(r"Peak:\s*([-\d.]+) dBFS", report).group(1))
    assert -21 < loudness < -14 and peak < -.7
    v = qa["verification"]
    if film == "pr":
        assert audio["channels"] == 2 and media["streams"][2]["codec_name"] == "mov_text"
        embedded = run("ffmpeg", "-v", "error", "-i", str(master), "-map", "0:s:0", "-f", "srt", "-").stdout.decode()
        captions = ROOT / "deliverables/video/cinematic/pr/captions.en.srt"
        # MP4 subtitle timescale can only carry millisecond rounding. Compare all
        # cue timings and text with the release sidecar after line normalization.
        assert embedded.strip().splitlines() == captions.read_text().strip().splitlines()
        v["caption_cues"] = len(re.findall("-->", embedded))
    shot_positions = [(item["shot"], item["sample"]) for item in qa["review_frames"]]
    sheet = frame_sheet(master, shot_positions)
    sheet_path = EVIDENCE / (film + "-contact-sheet.jpg")
    sheet_hash = hashlib.sha256(sheet).hexdigest()
    actual_sources = {k: digest(ROOT / k) for k in qa["audio_video_sources_sha256"]}
    master_hash = digest(master)
    if not args.record:
        if master_hash != qa["sha256"] or qa["media"] != media:
            raise ValueError("Release master differs from the frozen evidence.")
        differences = [k for k, val in actual_sources.items() if val != qa["audio_video_sources_sha256"][k]]
        if differences:
            raise ValueError("Source hashes differ from the release: " + ", ".join(differences))
        if sheet_hash != v["contact_sheet_sha256"] or digest(sheet_path) != sheet_hash:
            raise ValueError("Decoded review frames differ from the frozen contact sheet.")
        if abs(loudness - v["audio_loudness_LUFS"]) > .2 or abs(peak - v["true_peak_dBFS"]) > .2:
            raise ValueError("Audio levels differ from the measured release.")
    qa.update(media=media, sha256=master_hash, audio_video_sources_sha256=actual_sources)
    v.update(audio_loudness_LUFS=loudness, true_peak_dBFS=peak,
             decode="ffmpeg -v error -xerror -nostdin -i FINAL -f null - exited 0",
             contact_sheet_sha256=sheet_hash)
    if args.record:
        sheet_path.write_bytes(sheet)
        qa_file.write_text(json.dumps(qa, indent=2, ensure_ascii=False) + "\n")
    print(f"{film}: {seconds:.3f}s • {loudness:.1f} LUFS • {qa['sha256']}")


if __name__ == "__main__":
    main()
