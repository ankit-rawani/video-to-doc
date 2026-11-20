#!/usr/bin/env python3
"""Extract transcript, key frames, contact sheets and a merged timeline from a video.

Usage:
  python extract.py VIDEO [--out DIR] [--transcript FILE.vtt|.srt] [--model small]
                          [--only transcript|frames|timeline] [--force]
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

import cv2
import numpy as np


def fmt_ts(sec, sep=":"):
    sec = max(0, int(sec))
    return f"{sec // 3600:02d}{sep}{(sec % 3600) // 60:02d}{sep}{sec % 60:02d}"


def parse_ts(s):
    s = s.strip().replace(",", ".")
    parts = s.split(":")
    val = 0.0
    for p in parts:
        val = val * 60 + float(p)
    return val


# ---------------------------------------------------------------- transcript

def load_subtitle_file(path):
    """Parse .vtt or .srt (incl. Teams/Zoom `<v Speaker>` tags) into segments."""
    text = Path(path).read_text(encoding="utf-8-sig", errors="replace")
    segments = []
    blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n"))
    cue_re = re.compile(r"([\d:.,]+)\s*-->\s*([\d:.,]+)")
    for block in blocks:
        lines = [l for l in block.strip().split("\n") if l.strip()]
        for i, line in enumerate(lines):
            m = cue_re.search(line)
            if not m:
                continue
            body = " ".join(lines[i + 1:])
            speaker = None
            vm = re.match(r"\s*<v\s+([^>]+)>", body)
            if vm:
                speaker = vm.group(1).strip()
            else:
                sm = re.match(r"\s*([A-Z][\w .'-]{1,40}):\s", body)
                if sm:
                    speaker = sm.group(1).strip()
                    body = body[sm.end():]
            body = re.sub(r"<[^>]+>", "", body).strip()
            if body:
                segments.append({"start": parse_ts(m.group(1)), "end": parse_ts(m.group(2)),
                                 "text": body, "speaker": speaker})
            break
    # Teams/Zoom often split one utterance into many tiny cues; merge consecutive same-speaker cues.
    merged = []
    for seg in segments:
        if (merged and merged[-1]["speaker"] == seg["speaker"]
                and seg["start"] - merged[-1]["end"] < 1.5
                and len(merged[-1]["text"]) < 400):
            merged[-1]["text"] += " " + seg["text"]
            merged[-1]["end"] = seg["end"]
        else:
            merged.append(dict(seg))
    return merged


def decode_audio(video, sr=16000):
    """Decode the first audio stream to 16 kHz mono float32 via PyAV.

    Done here rather than in faster-whisper because its decoder passes kwargs removed in newer PyAV.
    """
    import av
    chunks = []
    with av.open(str(video)) as container:
        if not container.streams.audio:
            return None
        stream = container.streams.audio[0]
        resampler = av.AudioResampler(format="s16", layout="mono", rate=sr)
        for frame in container.decode(stream):
            for out in resampler.resample(frame):
                chunks.append(out.to_ndarray().reshape(-1))
        for out in resampler.resample(None):
            chunks.append(out.to_ndarray().reshape(-1))
    if not chunks:
        return None
    return np.concatenate(chunks).astype(np.float32) / 32768.0


def transcribe(video, model_size, language, device):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        sys.exit("faster-whisper not installed. Run: python -m pip install faster-whisper")
    print("[transcript] decoding audio ...", flush=True)
    try:
        audio = decode_audio(video)
    except Exception as e:
        print(f"[transcript] WARNING: could not decode audio ({e}); continuing without transcript.")
        return [], None
    if audio is None or len(audio) < 16000:
        print("[transcript] WARNING: no audio stream; continuing without transcript.")
        return [], None
    compute_type = "int8" if device == "cpu" else "default"
    print(f"[transcript] loading whisper model '{model_size}' on {device} ...", flush=True)
    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    seg_iter, info = model.transcribe(audio, language=language, vad_filter=True,
                                      beam_size=5, condition_on_previous_text=False)
    print(f"[transcript] language={info.language} (p={info.language_probability:.2f}), "
          f"audio duration={fmt_ts(info.duration)}", flush=True)
    segments, last_report = [], time.time()
    for s in seg_iter:
        segments.append({"start": round(s.start, 2), "end": round(s.end, 2),
                         "text": s.text.strip(), "speaker": None})
        if time.time() - last_report > 15:
            print(f"[transcript] ... {fmt_ts(s.end)} / {fmt_ts(info.duration)}", flush=True)
            last_report = time.time()
    return segments, info.language


# -------------------------------------------------------------------- frames

def small_gray(img, size=(256, 144)):
    g = cv2.cvtColor(cv2.resize(img, size, interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    return cv2.GaussianBlur(g, (3, 3), 0)


def changed_fraction(a, b, pixel_delta=30):
    return float(np.mean(cv2.absdiff(a, b) > pixel_delta))


def dhash(img, n=16):
    g = cv2.cvtColor(cv2.resize(img, (n + 1, n), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    return (g[:, 1:] > g[:, :-1]).flatten()


def extract_frames(video, out_dir, sample_interval, threshold, max_gap, settle_timeout,
                   dedupe_dist, max_width):
    """Segment the video into visually-stable spans and save one frame per span.

    A span ends when the picture changes by more than `threshold` (fraction of pixels) and the
    new picture has settled, or after `max_gap` seconds. The span's representative is its latest
    settled frame, so slide build-ups end up captured in their most complete state.
    Spans that look like an earlier saved frame (dHash) are recorded as revisits, not re-saved.
    """
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        sys.exit(f"Could not open video: {video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    n_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    est_duration = n_frames / fps if n_frames > 0 else 0
    out_dir.mkdir(parents=True, exist_ok=True)

    frames, saved_hashes = [], []  # saved_hashes: (frame_id, hash)
    state = {"img": None, "small": None, "start": 0.0, "end": 0.0}

    def save(img, path):
        if img.shape[1] > max_width:
            img = cv2.resize(img, (max_width, int(img.shape[0] * max_width / img.shape[1])),
                             interpolation=cv2.INTER_AREA)
        cv2.imwrite(str(path), img, [cv2.IMWRITE_JPEG_QUALITY, 88])

    def close_span():
        if state["img"] is None:
            return
        h = dhash(state["img"])
        for fid, prev_h in reversed(saved_hashes[-60:]):
            if int(np.count_nonzero(h != prev_h)) <= dedupe_dist:
                last = frames[-1]
                if last["id"] == fid and not last["revisit"]:
                    # Same screen split by a fade/flicker: merge, keeping the later settled image.
                    last["end"] = state["end"]
                    save(state["img"], out_dir.parent / last["file"])
                else:
                    frames.append({"id": fid, "file": None, "start": state["start"],
                                   "end": state["end"], "revisit": True})
                return
        fid = f"F{len(saved_hashes) + 1:03d}"
        fname = f"{fid}_{fmt_ts(state['start'], '-')}.jpg"
        save(state["img"], out_dir / fname)
        saved_hashes.append((fid, h))
        frames.append({"id": fid, "file": f"frames/{fname}", "start": state["start"],
                       "end": state["end"], "revisit": False})

    prev_small, unstable_since = None, None
    next_sample, t, frame_idx, last_report = 0.0, 0.0, 0, time.time()
    while True:
        if not cap.grab():
            break
        pos = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
        t = pos if pos > 0 or frame_idx == 0 else frame_idx / fps
        frame_idx += 1
        if t < next_sample:
            continue
        next_sample = t + sample_interval
        ok, img = cap.retrieve()
        if not ok:
            continue
        small = small_gray(img)

        if state["img"] is None:
            state.update(img=img, small=small, start=t, end=t)
        else:
            diff = changed_fraction(small, state["small"])
            stable = prev_small is not None and changed_fraction(small, prev_small) < threshold / 3
            if diff >= threshold:
                unstable_since = unstable_since if unstable_since is not None else t
                if stable or t - unstable_since >= settle_timeout:
                    close_span()
                    state.update(img=img, small=small, start=t, end=t)
                    unstable_since = None
            else:
                unstable_since = None
                if t - state["start"] >= max_gap:
                    close_span()
                    state.update(img=img, small=small, start=t, end=t)
                else:
                    state["end"] = t
                    if stable:
                        state.update(img=img, small=small)
        prev_small = small

        if time.time() - last_report > 15:
            total = f" / {fmt_ts(est_duration)}" if est_duration else ""
            print(f"[frames] ... {fmt_ts(t)}{total}  ({len(saved_hashes)} saved)", flush=True)
            last_report = time.time()

    state["end"] = t
    close_span()
    cap.release()
    for f in frames:
        f["start"], f["end"] = round(f["start"], 2), round(f["end"], 2)
    info = {"fps": round(fps, 3), "width": width, "height": height, "duration": round(t, 2)}
    return frames, info


def contact_sheets(frames, ws, cols=4, rows=5, thumb_w=400):
    sheet_dir = ws / "contact_sheets"
    sheet_dir.mkdir(exist_ok=True)
    for old in sheet_dir.glob("*.jpg"):
        old.unlink()
    unique = [f for f in frames if not f["revisit"]]
    per = cols * rows
    paths = []
    for si in range(0, len(unique), per):
        batch = unique[si:si + per]
        tiles = []
        for f in batch:
            img = cv2.imread(str(ws / f["file"]))
            th = int(img.shape[0] * thumb_w / img.shape[1])
            img = cv2.resize(img, (thumb_w, th), interpolation=cv2.INTER_AREA)
            label = f"{f['id']}  {fmt_ts(f['start'])}-{fmt_ts(f['end'])}"
            img = cv2.copyMakeBorder(img, 26, 0, 0, 0, cv2.BORDER_CONSTANT, value=(0, 0, 0))
            cv2.putText(img, label, (6, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1,
                        cv2.LINE_AA)
            tiles.append(img)
        th = max(t.shape[0] for t in tiles)
        tiles = [cv2.copyMakeBorder(t, 0, th - t.shape[0], 0, 0, cv2.BORDER_CONSTANT) for t in tiles]
        blank = np.zeros_like(tiles[0])
        while len(tiles) % cols:
            tiles.append(blank)
        grid_rows = [cv2.hconcat([cv2.copyMakeBorder(t, 4, 4, 4, 4, cv2.BORDER_CONSTANT,
                                                     value=(60, 60, 60)) for t in tiles[r:r + cols]])
                     for r in range(0, len(tiles), cols)]
        p = sheet_dir / f"sheet_{si // per + 1:02d}.jpg"
        cv2.imwrite(str(p), cv2.vconcat(grid_rows), [cv2.IMWRITE_JPEG_QUALITY, 80])
        paths.append(f"contact_sheets/{p.name}")
    return paths


# ------------------------------------------------------------------ timeline

def write_timeline(ws, segments, frames, duration, part_minutes):
    events = [(s["start"], 1, s) for s in segments] + [(f["start"], 0, f) for f in frames]
    events.sort(key=lambda e: (e[0], e[1]))
    part_len = part_minutes * 60
    n_parts = max(1, int(np.ceil(max(duration, 1) / part_len)))
    parts = [[] for _ in range(n_parts)]
    for t, kind, obj in events:
        pi = min(int(t // part_len), n_parts - 1)
        if kind == 0:
            if obj["revisit"]:
                line = (f"[{fmt_ts(t)}] >>> SCREEN returns to {obj['id']} "
                        f"(on screen until {fmt_ts(obj['end'])})")
            else:
                line = (f"[{fmt_ts(t)}] >>> SCREEN {obj['id']}: {obj['file']} "
                        f"(on screen until {fmt_ts(obj['end'])})")
        else:
            who = f"{obj['speaker']}: " if obj.get("speaker") else ""
            line = f"[{fmt_ts(t)}] {who}{obj['text']}"
        parts[pi].append(line)

    parts_dir = ws / "parts"
    parts_dir.mkdir(exist_ok=True)
    for old in parts_dir.glob("*.md"):
        old.unlink()
    full, part_files = [], []
    for i, lines in enumerate(parts):
        a, b = i * part_len, min((i + 1) * part_len, duration)
        header = f"## Part {i + 1} of {n_parts} ({fmt_ts(a)} - {fmt_ts(b)})\n"
        body = header + "\n" + "\n".join(lines) + "\n"
        name = f"part_{i + 1:02d}.md"
        (parts_dir / name).write_text(body, encoding="utf-8")
        part_files.append(f"parts/{name}")
        full.append(body)
    (ws / "timeline.md").write_text(
        "# Timeline (transcript + screen changes)\n\n"
        "Lines starting with `>>> SCREEN` mark when the picture changed; the frame file shows "
        "what was on screen from that time.\n\n" + "\n".join(full), encoding="utf-8")
    return part_files


# ---------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--out", help="workspace dir (default: <video_stem>_vdo2doc next to the video)")
    ap.add_argument("--transcript", help="existing .vtt/.srt transcript (skips whisper; keeps speaker names)")
    ap.add_argument("--model", default="small", help="whisper model: tiny|base|small|medium|large-v3 (default small)")
    ap.add_argument("--language", default=None, help="force language code, e.g. en (default: auto-detect)")
    ap.add_argument("--device", default="cpu", help="cpu or cuda (default cpu)")
    ap.add_argument("--no-transcript", action="store_true", help="skip transcription entirely")
    ap.add_argument("--only", choices=["transcript", "frames", "timeline"],
                    help="redo just one stage (others are reused from the workspace)")
    ap.add_argument("--force", action="store_true", help="recompute even if outputs already exist")
    ap.add_argument("--sample-interval", type=float, default=1.0, help="seconds between sampled frames (default 1)")
    ap.add_argument("--threshold", type=float, default=0.015,
                    help="fraction of changed pixels that counts as a new screen (default 0.015; raise to get fewer frames)")
    ap.add_argument("--max-gap", type=float, default=90, help="force a frame at least every N seconds (default 90)")
    ap.add_argument("--settle-timeout", type=float, default=3, help="seconds to wait for motion to settle (default 3)")
    ap.add_argument("--dedupe-dist", type=int, default=10, help="dHash bit distance for 'same screen' (default 10 of 256)")
    ap.add_argument("--max-width", type=int, default=1600, help="max saved frame width in px (default 1600)")
    ap.add_argument("--part-minutes", type=int, default=15, help="timeline part length in minutes (default 15)")
    args = ap.parse_args()

    video = Path(args.video).expanduser().resolve()
    if not video.exists():
        sys.exit(f"Video not found: {video}")
    ws = Path(args.out).expanduser().resolve() if args.out else video.parent / f"{video.stem}_vdo2doc"
    ws.mkdir(parents=True, exist_ok=True)
    meta_path = ws / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    meta.update({"video": str(video), "workspace": str(ws)})

    def run(stage, out_file):
        if args.only:
            return args.only == stage or not out_file.exists()
        return args.force or not out_file.exists()

    # transcript
    tr_path = ws / "transcript.json"
    if run("transcript", tr_path):
        t0 = time.time()
        if args.transcript:
            segments, lang, source = load_subtitle_file(args.transcript), args.language, f"file:{args.transcript}"
        elif args.no_transcript:
            segments, lang, source = [], None, "none"
        else:
            segments, lang = transcribe(video, args.model, args.language, args.device)
            source = f"whisper:{args.model}"
        tr_path.write_text(json.dumps(segments, indent=1, ensure_ascii=False), encoding="utf-8")
        meta.update({"transcript_source": source, "language": lang})
        print(f"[transcript] {len(segments)} segments in {time.time() - t0:.0f}s", flush=True)
    segments = json.loads(tr_path.read_text(encoding="utf-8"))

    # frames
    fr_path = ws / "frames.json"
    if run("frames", fr_path):
        t0 = time.time()
        fdir = ws / "frames"
        if fdir.exists():
            for old in fdir.glob("F*.jpg"):
                old.unlink()
        frames, vinfo = extract_frames(video, fdir, args.sample_interval, args.threshold, args.max_gap,
                                       args.settle_timeout, args.dedupe_dist, args.max_width)
        fr_path.write_text(json.dumps(frames, indent=1), encoding="utf-8")
        meta.update(vinfo)
        meta["contact_sheets"] = contact_sheets(frames, ws)
        meta["frame_settings"] = {k: getattr(args, k) for k in
                                  ("sample_interval", "threshold", "max_gap", "settle_timeout", "dedupe_dist")}
        print(f"[frames] {sum(not f['revisit'] for f in frames)} unique frames "
              f"({sum(f['revisit'] for f in frames)} revisits) in {time.time() - t0:.0f}s", flush=True)
    frames = json.loads(fr_path.read_text(encoding="utf-8"))

    # timeline
    duration = meta.get("duration") or max([s["end"] for s in segments] + [0])
    meta["parts"] = write_timeline(ws, segments, frames, duration, args.part_minutes)
    meta["unique_frames"] = sum(not f["revisit"] for f in frames)
    meta["transcript_segments"] = len(segments)
    meta_path.write_text(json.dumps(meta, indent=1), encoding="utf-8")

    print("\n=== done ===")
    print(f"workspace      : {ws}")
    print(f"duration       : {fmt_ts(duration)}")
    print(f"transcript     : {len(segments)} segments ({meta.get('transcript_source')})")
    print(f"unique frames  : {meta['unique_frames']}  -> {ws / 'frames'}")
    print(f"contact sheets : {', '.join(meta.get('contact_sheets', []))}")
    print(f"timeline parts : {', '.join(meta['parts'])}")


if __name__ == "__main__":
    main()
