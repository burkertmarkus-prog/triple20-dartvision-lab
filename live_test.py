#!/usr/bin/env python3
"""Local, read-only live test for one three-dart visit.

The script reads the existing Autodarts MJPEG streams, but it neither writes
to the Raspberry Pi nor uses the Autodarts score as input.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from analyze_dart import CAMERA_COUNT
from capture_board import read_jpeg, resolve_host


ROOT = Path(__file__).resolve().parent.parent


def read_frames(urls: list[str], timeout: float) -> list[bytes]:
    with ThreadPoolExecutor(max_workers=CAMERA_COUNT) as executor:
        frames = list(executor.map(lambda url: read_jpeg(url, timeout), urls))
    if len({hashlib.sha256(frame).hexdigest() for frame in frames}) == 1:
        raise RuntimeError("Alle Kameras liefern dasselbe Platzhalterbild.")
    return frames


def grayscale(frame: bytes) -> np.ndarray:
    return np.asarray(Image.open(BytesIO(frame)).convert("L"), dtype=np.int16)


def changed_pixels(left: bytes, right: bytes, pixel_threshold: int) -> int:
    first, second = grayscale(left), grayscale(right)
    if first.shape != second.shape:
        return 0
    # Ignore isolated compression noise by requiring a small local cluster.
    changed = (np.abs(first - second) >= pixel_threshold).astype(np.uint8)
    neighbours = (
        changed
        + np.roll(changed, 1, 0)
        + np.roll(changed, -1, 0)
        + np.roll(changed, 1, 1)
        + np.roll(changed, -1, 1)
    )
    return int((neighbours >= 3).sum())


def frame_scores(reference: list[bytes], current: list[bytes], threshold: int) -> list[int]:
    return [changed_pixels(a, b, threshold) for a, b in zip(reference, current)]


def save_capture(
    directory: Path,
    frames: list[bytes],
    urls: list[str],
    board: str,
    calibration: Path,
) -> None:
    directory.mkdir(parents=True, exist_ok=False)
    cameras = []
    for camera, (frame, url) in enumerate(zip(frames, urls)):
        filename = f"camera-{camera}.jpg"
        (directory / filename).write_bytes(frame)
        cameras.append({"camera": camera, "file": filename, "source": url, "bytes": len(frame)})
    (directory / "autodarts-calibration.json").write_bytes(calibration.read_bytes())
    manifest = {
        "schemaVersion": 1,
        "board": board,
        "capturedAt": datetime.now().astimezone().isoformat(),
        "captureMode": "local-live-test",
        "cameras": cameras,
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def find_calibration(board: str) -> Path:
    candidates = sorted((ROOT / "captures" / board).glob("*/autodarts-calibration.json"), reverse=True)
    if not candidates:
        raise FileNotFoundError("Keine lokale Autodarts-Kalibrierung gefunden.")
    return candidates[0]


def show_detection(report_path: Path, number: int) -> dict | None:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    detections = report.get("detections") or []
    detection = detections[0] if detections else report.get("consensus")
    if not detection or not detection.get("predictedField"):
        print(f"Wurf {number}: nicht sicher erkannt")
        return None
    field = detection["predictedField"]
    confidence = detection.get("confidence", "unbekannt")
    wire = " · nahe am Draht" if detection.get("nearWire") else ""
    print(f"Wurf {number}: {field} · Sicherheit {confidence}{wire}")
    return detection


def main() -> None:
    parser = argparse.ArgumentParser(description="Erkennt lokal eine Aufnahme mit bis zu drei Darts.")
    parser.add_argument("--host", default="dcapi4.local:3180")
    parser.add_argument("--board", default="board4")
    parser.add_argument("--calibration", type=Path)
    parser.add_argument("--interval", type=float, default=0.65)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--pixel-threshold", type=int, default=38)
    parser.add_argument("--change-pixels", type=int, default=110)
    parser.add_argument("--stable-pixels", type=int, default=75)
    parser.add_argument("--stable-frames", type=int, default=2)
    parser.add_argument("--max-darts", type=int, choices=(1, 2, 3), default=3)
    args = parser.parse_args()

    calibration = (args.calibration or find_calibration(args.board)).resolve()
    host = resolve_host(args.host)
    urls = [f"http://{host}/api/streams/cams/{camera}" for camera in range(CAMERA_COUNT)]
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d_%H-%M-%S")
    session = ROOT / "captures" / args.board / f"live-{stamp}"

    print("Leere und ruhige Scheibe erforderlich. Lese Referenz ...")
    baseline = read_frames(urls, args.timeout)
    save_capture(session / "step-0-empty", baseline, urls, args.board, calibration)
    previous = baseline
    armed = False
    stable_count = 0
    dart_count = 0
    print("Bereit. Jetzt jeweils einen Dart werfen (Abbruch mit Ctrl+C).")

    try:
        while dart_count < args.max_darts:
            time.sleep(args.interval)
            current = read_frames(urls, args.timeout)
            change = frame_scores(baseline, current, args.pixel_threshold)
            movement = frame_scores(previous, current, args.pixel_threshold)
            changed_cameras = sum(score >= args.change_pixels for score in change)
            stable_cameras = sum(score <= args.stable_pixels for score in movement)

            if changed_cameras >= 2:
                armed = True
                stable_count = stable_count + 1 if stable_cameras >= 2 else 0
            else:
                stable_count = 0

            if armed and stable_count >= args.stable_frames:
                dart_count += 1
                after_dir = session / f"step-{dart_count}-after"
                before_dir = session / f"step-{dart_count}-before"
                save_capture(before_dir, baseline, urls, args.board, calibration)
                save_capture(after_dir, current, urls, args.board, calibration)
                command = [
                    sys.executable,
                    str(ROOT / "tools" / "analyze_dart.py"),
                    str(before_dir),
                    str(after_dir),
                    "--calibration",
                    str(calibration),
                    "--max-darts",
                    "1",
                ]
                result = subprocess.run(command, check=True, capture_output=True, text=True)
                report_path = Path(result.stdout.strip().splitlines()[-1])
                show_detection(report_path, dart_count)
                baseline = current
                previous = current
                armed = False
                stable_count = 0
                if dart_count < args.max_darts:
                    print("Bereit für den nächsten Dart.")
                continue

            previous = current
    except KeyboardInterrupt:
        print("\nTest beendet.")

    if dart_count == args.max_darts:
        print(f"Aufnahme abgeschlossen. Lokale Testdaten: {session}")


if __name__ == "__main__":
    main()
