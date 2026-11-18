"""Time the Adobe narration to the picture, duck the stereo score, and author English CC."""
import json
from pathlib import Path
import subprocess

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
STEMS = ROOT / "deliverables/video/cinematic/firefly"
PR = ROOT / "deliverables/video/cinematic/pr"
WORK = ROOT / "tmp/pr-film"
SAMPLE_RATE = 48000
LENGTH = 45

# Original speech in/out, edited in-point, tempo (pitch preserved), and closed caption.
# Original boundaries lie in inter-phrase pauses in the 26.500-second Jennifer recording.
LINES = [
    (.09, 1.108, .48, .79, "The fan is running."),
    (1.108, 2.43, 2.40, .79, "But is the air moving?"),
    (2.47, 5.82, 5.25, .80, "On this cooking line, the airflow is less than half its target."),
    (5.87, 9.49, 10.18, .80, "openSoom follows a single reading into two applications."),
    (9.49, 11.35, 15.00, .81, "Operations checks the damper."),
    (11.35, 14.25, 17.80, .80, "Maintenance sees which fault still needs attention."),
    (14.25, 17.76, 22.00, .78, "A device can acknowledge a command while the airflow stays low."),
    (17.76, 21.89, 29.45, .80, "From the production floor to the classroom, each space keeps its own target."),
    (21.89, 24.11, 36.96, .79, "oneM2M connects the devices."),
    (24.11, 26.13, 40.68, .79, "openSoom shows what happened next."),
]


def ffmpeg(args, data=None):
    return subprocess.run(["ffmpeg", "-v", "error", "-nostdin", *args], input=data,
                          stdout=subprocess.PIPE, check=True).stdout


def timestamp(seconds):
    millis = round(seconds * 1000)
    return f"00:{millis // 60000:02}:{millis // 1000 % 60:02},{millis % 1000:03}"


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    samples = SAMPLE_RATE * LENGTH
    voice = np.zeros(samples, dtype="float32")
    clock = np.arange(samples, dtype="float32") / SAMPLE_RATE
    duck = np.zeros_like(voice)
    cues = []
    for start, end, position, tempo, caption in LINES:
        raw = ffmpeg(["-i", str(STEMS / "pr-narration.wav"), "-af",
                      f"atrim=start={start}:end={end},asetpts=PTS-STARTPTS,atempo={tempo}",
                      "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "f32le", "-"])
        speech = np.frombuffer(raw, dtype="<f4").copy()
        edge = round(.006 * SAMPLE_RATE)
        speech[:edge] *= np.linspace(0, 1, edge)
        speech[-edge:] *= np.linspace(1, 0, edge)
        frame = round(position * SAMPLE_RATE)
        voice[frame:frame + len(speech)] += speech
        active = np.flatnonzero(np.abs(speech) > .003)
        if len(active) == 0:
            raise ValueError(f"Empty speech segment at {start}")
        on = position + active[0] / SAMPLE_RATE
        off = position + active[-1] / SAMPLE_RATE
        cues.append({"start": round(on, 3), "end": round(off + .08, 3), "text": caption})
        duck = np.maximum(duck, np.minimum(np.clip((clock - on + .24) / .24, 0, 1),
                                          np.clip((off + .70 - clock) / .70, 0, 1)))

    music_raw = ffmpeg(["-i", str(STEMS / "pr-score.wav"), "-ar", str(SAMPLE_RATE),
                         "-ac", "2", "-f", "f32le", "-"])
    music = np.frombuffer(music_raw, dtype="<f4").reshape((-1, 2))
    if music.shape[0] != samples:
        raise ValueError("The original stereo music must run for exactly 45 seconds.")
    score_gain = 10 ** ((-6.5 - duck * 8.5) / 20)
    fade = np.minimum(np.clip(clock / .12, 0, 1), np.clip((LENGTH - clock) / .85, 0, 1))
    mix = music * (score_gain * fade)[:, None] + voice[:, None] * (10 ** (5.5 / 20))
    ffmpeg(["-y", "-f", "f32le", "-ar", str(SAMPLE_RATE), "-ac", "2", "-i", "-",
            "-af", "loudnorm=I=-16.5:TP=-1.7:LRA=10", "-ar", str(SAMPLE_RATE),
            "-c:a", "pcm_s24le", "-t", "45.000", str(WORK / "pr-mix.wav")],
           mix.astype("<f4").tobytes())
    if any(cues[i]["end"] >= cues[i + 1]["start"] for i in range(len(cues) - 1)):
        raise ValueError("Overlapping English closed captions")
    (WORK / "pr-voice-timings.json").write_text(json.dumps(cues, indent=2) + "\n")
    srt = "\n\n".join(f"{i}\n{timestamp(c['start'])} --> {timestamp(c['end'])}\n{c['text']}"
                      for i, c in enumerate(cues, 1))
    (PR / "captions.en.srt").write_text(srt + "\n")
    print(f"Mixed {len(cues)} speech cues against the original stereo score.")


if __name__ == "__main__":
    main()
