#!/usr/bin/env python3
"""Grab a frame at a timestamp and/or crop a region of an image.

Usage:
  python grab.py --video VIDEO --at 00:12:34 -o frames/custom_0012.jpg
  python grab.py --image frames/F012_00-12-30.jpg --crop 0.5,0.1,0.5,0.6 -o frames/F012_chart.jpg
  python grab.py --video VIDEO --at 754.5 --crop 0,0,0.7,1 -o frames/x.jpg

--crop is x,y,w,h as fractions (0-1) of the image size, e.g. 0.5,0,0.5,1 = right half.
"""
import argparse
import sys
from pathlib import Path

import cv2


def parse_ts(s):
    val = 0.0
    for p in s.strip().split(":"):
        val = val * 60 + float(p)
    return val


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--video")
    src.add_argument("--image")
    ap.add_argument("--at", help="timestamp (HH:MM:SS, MM:SS or seconds) when using --video")
    ap.add_argument("--crop", help="x,y,w,h fractions")
    ap.add_argument("--max-width", type=int, default=1600)
    ap.add_argument("-o", "--out", required=True)
    args = ap.parse_args()

    if args.video:
        if not args.at:
            sys.exit("--at is required with --video")
        cap = cv2.VideoCapture(args.video)
        cap.set(cv2.CAP_PROP_POS_MSEC, parse_ts(args.at) * 1000)
        ok, img = cap.read()
        cap.release()
        if not ok:
            sys.exit(f"Could not read frame at {args.at}")
    else:
        img = cv2.imread(args.image)
        if img is None:
            sys.exit(f"Could not read image {args.image}")

    if args.crop:
        x, y, w, h = (float(v) for v in args.crop.split(","))
        H, W = img.shape[:2]
        x0, y0 = int(x * W), int(y * H)
        x1, y1 = min(W, x0 + int(w * W)), min(H, y0 + int(h * H))
        img = img[y0:y1, x0:x1]

    if img.shape[1] > args.max_width:
        img = cv2.resize(img, (args.max_width, int(img.shape[0] * args.max_width / img.shape[1])),
                         interpolation=cv2.INTER_AREA)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    print(f"wrote {out} ({img.shape[1]}x{img.shape[0]})")


if __name__ == "__main__":
    main()
