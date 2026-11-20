"""Build a synthetic slide-talk video with TTS narration for testing the skill."""
import subprocess
import wave
from fractions import Fraction
from pathlib import Path

import av
import cv2
import numpy as np

HERE = Path(__file__).parent
W, H, FPS = 1280, 720, 10

SCRIPT = [  # (slide_key, narration)
    ("title", "Welcome everyone. Today I will walk through the Q3 ingestion pipeline redesign for Project Falcon."),
    ("problem", "First, the problem. Our current pipeline writes events directly to Postgres. At peak we see twelve thousand events per second, and write latency goes above eight hundred milliseconds."),
    ("problem2", "On top of that, we lose about zero point three percent of events during deploys, because there is no buffer."),
    ("cam", "Let me pause here. Any questions so far? Okay, nobody, let's continue."),
    ("arch", "Here is the proposed architecture. As you can see, producers now publish to a Kafka queue. A pool of writer workers consumes from the queue and batch inserts into Postgres."),
    ("chart", "This chart shows the load test results. With batching, p99 latency drops from eight hundred milliseconds to ninety milliseconds, and throughput reaches twenty five thousand events per second."),
    ("arch", "Going back to the architecture diagram, note that the dead letter queue on the right catches malformed events."),
    ("actions", "Next steps. Priya will set up the Kafka cluster by October tenth. Raj will migrate the writer service. We decided to keep Postgres instead of moving to ClickHouse for now."),
]


def tts(text, path):
    ps = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
          "$f = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, 'Sixteen', 'Mono'); "
          f"$s.SetOutputToWaveFile('{path}', $f); $s.Speak(\"{text}\"); $s.Dispose()")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)


def base(title):
    img = np.full((H, W, 3), 250, np.uint8)
    cv2.rectangle(img, (0, 0), (W, 90), (120, 60, 20), -1)
    cv2.putText(img, title, (40, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (255, 255, 255), 3, cv2.LINE_AA)
    return img


def text(img, s, y, size=0.9, color=(40, 40, 40)):
    cv2.putText(img, s, (60, y), cv2.FONT_HERSHEY_SIMPLEX, size, color, 2, cv2.LINE_AA)


def box(img, x, y, w, h, label, color):
    cv2.rectangle(img, (x, y), (x + w, y + h), color, -1)
    cv2.rectangle(img, (x, y), (x + w, y + h), (30, 30, 30), 2)
    cv2.putText(img, label, (x + 12, y + h // 2 + 8), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (20, 20, 20), 2, cv2.LINE_AA)


def arrow(img, p, q):
    cv2.arrowedLine(img, p, q, (30, 30, 30), 3, tipLength=0.04)


def slide(key, progress):
    if key == "title":
        img = np.full((H, W, 3), (120, 60, 20), np.uint8)
        cv2.putText(img, "Project Falcon", (330, 320), cv2.FONT_HERSHEY_SIMPLEX, 2.4, (255, 255, 255), 5, cv2.LINE_AA)
        cv2.putText(img, "Q3 Ingestion Pipeline Redesign", (310, 410), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (220, 220, 220), 2, cv2.LINE_AA)
        return img
    if key in ("problem", "problem2"):
        img = base("The problem today")
        text(img, "- Events written directly to Postgres", 180)
        text(img, "- Peak: 12,000 events/sec", 240)
        text(img, "- Write latency > 800 ms at peak", 300)
        if key == "problem2":  # build-up bullet
            text(img, "- ~0.3% events lost during deploys (no buffer)", 360, color=(30, 30, 200))
        return img
    if key == "cam":
        img = np.full((H, W, 3), 35, np.uint8)
        for i, (x, y) in enumerate([(40, 40), (660, 40), (40, 380), (660, 380)]):
            cv2.rectangle(img, (x, y), (x + 580, y + 300), (70 + 20 * i, 80, 90), -1)
            r = 60 + int(4 * np.sin(progress * 30 + i))  # "talking" motion
            cv2.circle(img, (x + 290, y + 140), r, (150, 170, 200), -1)
            cv2.putText(img, ["Ankit", "Priya", "Raj", "Mei"][i], (x + 12, y + 285),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        return img
    if key == "arch":
        img = base("Proposed architecture")
        box(img, 60, 300, 200, 90, "Producers", (200, 230, 255))
        box(img, 360, 300, 220, 90, "Kafka queue", (180, 255, 200))
        box(img, 680, 300, 230, 90, "Writer pool", (255, 220, 180))
        box(img, 1000, 300, 220, 90, "Postgres", (220, 200, 255))
        box(img, 680, 520, 260, 80, "Dead-letter Q", (180, 180, 255))
        arrow(img, (260, 345), (360, 345))
        arrow(img, (580, 345), (680, 345))
        arrow(img, (910, 345), (1000, 345))
        arrow(img, (795, 390), (795, 520))
        text(img, "batch inserts", 1000 - 300, size=0.6)
        return img
    if key == "chart":
        img = base("Load test results (p99 latency, ms)")
        cv2.line(img, (150, 620), (1150, 620), (30, 30, 30), 2)
        cv2.line(img, (150, 620), (150, 150), (30, 30, 30), 2)
        for i, (lab, val, col) in enumerate([("Current", 800, (80, 80, 220)), ("Batched", 90, (80, 180, 80))]):
            x = 300 + i * 400
            hpx = int(val / 800 * 420)
            cv2.rectangle(img, (x, 620 - hpx), (x + 200, 620), col, -1)
            cv2.putText(img, f"{val} ms", (x + 40, 610 - hpx), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (30, 30, 30), 2)
            cv2.putText(img, lab, (x + 40, 660), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (30, 30, 30), 2)
        cv2.putText(img, "Throughput: 25k events/sec", (760, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (30, 30, 30), 2)
        return img
    if key == "actions":
        img = base("Next steps")
        text(img, "1. Kafka cluster - Priya - by Oct 10", 200)
        text(img, "2. Migrate writer service - Raj", 260)
        text(img, "Decision: stay on Postgres (not ClickHouse) for now", 360, color=(30, 120, 30))
        return img


def main():
    tmp = HERE / "tts"
    tmp.mkdir(exist_ok=True)
    clips = []
    for i, (key, line) in enumerate(SCRIPT):
        p = tmp / f"{i}.wav"
        tts(line.replace('"', ""), str(p))
        with wave.open(str(p)) as w:
            pcm = np.frombuffer(w.readframes(w.getnframes()), np.int16)
        pcm = np.concatenate([pcm, np.zeros(16000 * 2, np.int16)])  # 2 s pause after each line
        clips.append((key, pcm))

    out = HERE / "falcon_review.mp4"
    container = av.open(str(out), "w")
    vs = container.add_stream("libx264", rate=FPS)
    vs.width, vs.height, vs.pix_fmt = W, H, "yuv420p"
    aus = container.add_stream("aac", rate=16000)
    aus.layout = "mono"

    for key, pcm in clips:
        n = int(len(pcm) / 16000 * FPS)
        for f in range(n):
            img = slide(key, f / max(n, 1))
            # fade-in transition for the first 0.5 s of each slide
            if f < 5:
                img = (img.astype(np.float32) * (0.4 + 0.12 * f)).astype(np.uint8)
            frame = av.VideoFrame.from_ndarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB), format="rgb24")
            for pkt in vs.encode(frame):
                container.mux(pkt)
    for pkt in vs.encode():
        container.mux(pkt)

    audio = np.concatenate([c[1] for c in clips])
    step = 1024
    for s in range(0, len(audio), step):
        chunk = audio[s:s + step].reshape(1, -1)
        af = av.AudioFrame.from_ndarray(chunk, format="s16", layout="mono")
        af.sample_rate = 16000
        af.pts = s
        af.time_base = Fraction(1, 16000)
        for pkt in aus.encode(af):
            container.mux(pkt)
    for pkt in aus.encode():
        container.mux(pkt)
    container.close()
    print(f"wrote {out}  ({len(audio) / 16000:.0f}s)")


if __name__ == "__main__":
    main()
