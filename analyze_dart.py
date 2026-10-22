#!/usr/bin/env python3
"""Estimate the dart entry point in each calibrated camera image.

This is deliberately an offline lab tool. It reads two saved captures and a
saved Autodarts calibration; it does not contact or alter the board.
"""

from __future__ import annotations

import argparse
from collections import deque
from itertools import product
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


CAMERA_COUNT = 3
SECTORS = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5]


def board_homography(calibration: dict) -> np.ndarray:
    """Map camera pixels to one shared, unit-radius board plane."""
    source = np.asarray(calibration["doubleOuterPoints"][:20], dtype=np.float64)
    angles = np.arange(20, dtype=np.float64) * (2.0 * np.pi / 20.0)
    target = np.column_stack((np.cos(angles), np.sin(angles)))
    rows = []
    for (x, y), (u, v) in zip(source, target):
        rows.append([x, y, 1, 0, 0, 0, -u * x, -u * y, -u])
        rows.append([0, 0, 0, x, y, 1, -v * x, -v * y, -v])
    _, _, vectors = np.linalg.svd(np.asarray(rows), full_matrices=False)
    return vectors[-1].reshape(3, 3)


def map_to_board(point: dict, homography: np.ndarray) -> dict:
    mapped = homography @ np.asarray([point["x"], point["y"], 1.0])
    mapped /= mapped[2]
    return {"x": float(mapped[0]), "y": float(mapped[1])}


def calibrated_ring_radii(calibrations: dict) -> dict:
    collected = {"bullInner": [], "bullOuter": [], "trebleInner": [], "trebleOuter": [], "doubleInner": [], "doubleOuter": [1.0]}
    for camera in range(CAMERA_COUNT):
        calibration = calibrations[str(camera)]
        homography = board_homography(calibration)
        for name in ("trebleInner", "trebleOuter", "doubleInner"):
            for x, y in calibration[f"{name}Points"][:20]:
                point = map_to_board({"x": x, "y": y}, homography)
                collected[name].append(float(np.hypot(point["x"], point["y"])))
        for name in ("bullInner", "bullOuter"):
            ellipse = calibration[name]
            half_width = float(ellipse["width"]) / 2.0
            half_height = float(ellipse["height"]) / 2.0
            for x, y in (
                (ellipse["x"] - half_width, ellipse["y"]),
                (ellipse["x"] + half_width, ellipse["y"]),
                (ellipse["x"], ellipse["y"] - half_height),
                (ellipse["x"], ellipse["y"] + half_height),
            ):
                point = map_to_board({"x": x, "y": y}, homography)
                collected[name].append(float(np.hypot(point["x"], point["y"])))
    return {name: float(np.median(values)) for name, values in collected.items()}


def calibrated_ring_profiles(calibrations: dict) -> dict:
    profiles = {}
    for name in ("trebleInner", "trebleOuter", "doubleInner"):
        per_camera = []
        for camera in range(CAMERA_COUNT):
            calibration = calibrations[str(camera)]
            homography = board_homography(calibration)
            radii = []
            for x, y in calibration[f"{name}Points"][:20]:
                point = map_to_board({"x": x, "y": y}, homography)
                radii.append(float(np.hypot(point["x"], point["y"])))
            per_camera.append(radii)
        profiles[name] = np.median(np.asarray(per_camera), axis=0).tolist()
    profiles["doubleOuter"] = [1.0] * 20
    return profiles


def ring_radius_at_angle(profile: list[float], angle_degrees: float) -> float:
    position = (angle_degrees % 360.0) / 18.0
    lower = int(np.floor(position)) % 20
    fraction = position - np.floor(position)
    upper = (lower + 1) % 20
    return float(profile[lower] * (1.0 - fraction) + profile[upper] * fraction)


def classify_board_point(point: dict, radii: dict, profiles: dict) -> dict:
    x, y = float(point["x"]), float(point["y"])
    radius = float(np.hypot(x, y))
    if radius <= radii["bullInner"]:
        return {"field": "BULL", "nearWire": False, "wireDistance": None}
    if radius <= radii["bullOuter"]:
        return {"field": "SB", "nearWire": False, "wireDistance": None}
    angle = float(np.degrees(np.arctan2(y, x)))
    sector_index = int(np.floor((angle + 18.0) / 18.0)) % 20
    number = SECTORS[sector_index]
    treble_inner = ring_radius_at_angle(profiles["trebleInner"], angle)
    treble_outer = ring_radius_at_angle(profiles["trebleOuter"], angle)
    double_inner = ring_radius_at_angle(profiles["doubleInner"], angle)
    double_outer = ring_radius_at_angle(profiles["doubleOuter"], angle)
    # Roughly one millimetre on a regulation board. Measurements this close
    # to a wire are classified, but explicitly flagged for confirmation.
    wire_margin = 0.006
    if treble_inner - wire_margin <= radius <= treble_outer + wire_margin:
        distance = min(abs(radius - treble_inner), abs(radius - treble_outer))
        return {"field": f"T{number}", "nearWire": distance <= wire_margin, "wireDistance": distance}
    if double_inner - wire_margin <= radius <= double_outer * 1.03:
        distance = min(abs(radius - double_inner), abs(radius - double_outer))
        return {"field": f"D{number}", "nearWire": distance <= wire_margin, "wireDistance": distance}
    if radius <= double_outer * 1.03:
        distance = min(
            abs(radius - treble_inner),
            abs(radius - treble_outer),
            abs(radius - double_inner),
        )
        return {"field": f"S{number}", "nearWire": distance <= wire_margin, "wireDistance": distance}
    return {"field": "MISS", "nearWire": False, "wireDistance": abs(radius - double_outer)}


def estimate_component_entry(candidate: dict, largest: dict) -> dict:
    pixels = candidate["_pixelArray"]
    xy = np.column_stack((pixels[:, 1], pixels[:, 0])).astype(np.float64)
    centered = xy - xy.mean(axis=0)
    _, _, axes = np.linalg.svd(centered, full_matrices=False)
    projection = centered @ axes[0]
    low_end = xy[projection <= np.quantile(projection, 0.04)].mean(axis=0)
    high_end = xy[projection >= np.quantile(projection, 0.96)].mean(axis=0)

    if largest is not candidate and largest["pixels"] >= candidate["pixels"] * 1.5:
        flight_center = np.asarray([largest["center"]["x"], largest["center"]["y"]])
        chosen = max((low_end, high_end), key=lambda point: np.linalg.norm(point - flight_center))
    else:
        span = max(1.0, float(projection.max() - projection.min()))
        band = span * 0.18
        low_density = int((projection <= projection.min() + band).sum())
        high_density = int((projection >= projection.max() - band).sum())
        chosen = low_end if low_density < high_density else high_end
    return {"x": int(round(chosen[0])), "y": int(round(chosen[1]))}


def select_cross_camera_consensus(
    camera_results: list[dict],
    radii: dict,
    profiles: dict,
) -> dict | None:
    """Choose the candidate combination that represents one physical hit."""
    available = [
        (result["camera"], result["candidates"])
        for result in camera_results
        if result["candidates"]
    ]
    if len(available) < 2:
        return None

    best = None
    for combination in product(*(candidates for _, candidates in available)):
        points = [np.asarray([item["boardPoint"]["x"], item["boardPoint"]["y"]]) for item in combination]
        distances = [
            float(np.linalg.norm(points[left] - points[right]))
            for left in range(len(points))
            for right in range(left + 1, len(points))
        ]
        mean_distance = float(np.mean(distances))
        max_distance = float(np.max(distances))
        # Break near-ties in favour of a substantial dart component, without
        # allowing sheer changed-pixel area to overrule geometric agreement.
        size_penalty = float(np.mean([1.0 / np.sqrt(item["pixels"]) for item in combination])) * 0.02
        score = mean_distance + size_penalty
        if best is None or score < best["score"]:
            best = {
                "score": score,
                "meanDistance": mean_distance,
                "maxDistance": max_distance,
                "combination": combination,
            }

    if best is None:
        return None

    agreement_mode = "position"
    confidence = "high"
    if best["maxDistance"] > 0.25:
        fields = [
            classify_board_point(item["boardPoint"], radii, profiles)["field"]
            for item in best["combination"]
        ]
        # With existing darts in the board, the visible shaft endpoint can
        # shift radially between cameras. Accept a wider spread only when all
        # cameras still identify the same non-miss scoring field.
        field_counts = {field: fields.count(field) for field in set(fields) if field != "MISS"}
        majority_field = max(field_counts, key=field_counts.get, default=None)
        majority_count = field_counts.get(majority_field, 0)
        if best["maxDistance"] > 0.40 or majority_count < 2:
            return None
        agreement_mode = "field" if majority_count == len(fields) else "field-majority"
        confidence = "reduced"

    selected_by_camera = {}
    for (camera, _), candidate in zip(available, best["combination"]):
        selected_by_camera[camera] = candidate
        result = camera_results[camera]
        result["entryPoint"] = candidate["entryPoint"]
        result["boardPoint"] = candidate["boardPoint"]
        result["distanceToBull"] = round(
            float(
                np.hypot(
                    candidate["entryPoint"]["x"] - result["bull"]["x"],
                    candidate["entryPoint"]["y"] - result["bull"]["y"],
                )
            ),
            2,
        )
        result["selectedComponentPixels"] = candidate["pixels"]
        result["selectionMethod"] = "cross-camera-consensus"

    center = np.mean(
        [
            [candidate["boardPoint"]["x"], candidate["boardPoint"]["y"]]
            for candidate in best["combination"]
        ],
        axis=0,
    )
    return {
        "cameraCount": len(best["combination"]),
        "agreementMode": agreement_mode,
        "confidence": confidence,
        "meanDistance": round(best["meanDistance"], 4),
        "maxDistance": round(best["maxDistance"], 4),
        "boardPoint": {"x": float(center[0]), "y": float(center[1])},
        "selectedPixels": {
            str(camera): candidate["pixels"] for camera, candidate in selected_by_camera.items()
        },
    }


def draw_selected_point(after_path: Path, result: dict) -> Image.Image:
    marked = Image.open(after_path).convert("RGB")
    draw = ImageDraw.Draw(marked)
    bull_x, bull_y = result["bull"]["x"], result["bull"]["y"]
    draw.ellipse((bull_x - 6, bull_y - 6, bull_x + 6, bull_y + 6), outline="cyan", width=3)
    point = result["entryPoint"]
    if point:
        radius = 11
        draw.ellipse(
            (point["x"] - radius, point["y"] - radius, point["x"] + radius, point["y"] + radius),
            outline="lime",
            width=4,
        )
        draw.line((point["x"] - 15, point["y"], point["x"] + 15, point["y"]), fill="lime", width=2)
        draw.line((point["x"], point["y"] - 15, point["x"], point["y"] + 15), fill="lime", width=2)
    return marked


def dilate(mask: np.ndarray, radius: int = 2) -> np.ndarray:
    padded = np.pad(mask, radius)
    result = np.zeros_like(mask)
    height, width = mask.shape
    for dy in range(radius * 2 + 1):
        for dx in range(radius * 2 + 1):
            result |= padded[dy : dy + height, dx : dx + width]
    return result


def components(mask: np.ndarray) -> list[np.ndarray]:
    height, width = mask.shape
    visited = np.zeros_like(mask)
    found: list[np.ndarray] = []
    for start_y, start_x in zip(*np.where(mask & ~visited)):
        if visited[start_y, start_x]:
            continue
        queue = deque([(int(start_y), int(start_x))])
        visited[start_y, start_x] = True
        pixels: list[tuple[int, int]] = []
        while queue:
            y, x = queue.popleft()
            pixels.append((y, x))
            for next_y in range(max(0, y - 1), min(height, y + 2)):
                for next_x in range(max(0, x - 1), min(width, x + 2)):
                    if mask[next_y, next_x] and not visited[next_y, next_x]:
                        visited[next_y, next_x] = True
                        queue.append((next_y, next_x))
        found.append(np.asarray(pixels, dtype=np.int32))
    return found


def polygon_mask(size: tuple[int, int], points: list[list[int]]) -> np.ndarray:
    image = Image.new("1", size, 0)
    ImageDraw.Draw(image).polygon([tuple(point) for point in points], fill=1)
    return np.asarray(image, dtype=bool)


def analyze_camera(
    before_path: Path,
    after_path: Path,
    calibration: dict,
    threshold: int,
) -> tuple[dict, Image.Image]:
    before_image = Image.open(before_path).convert("RGB")
    after_image = Image.open(after_path).convert("RGB")
    before = np.asarray(before_image, dtype=np.int16)
    after = np.asarray(after_image, dtype=np.int16)
    difference = np.max(np.abs(after - before), axis=2)
    raw_changed = difference >= threshold

    board_mask = polygon_mask(after_image.size, calibration["doubleOuterPoints"])
    changed_on_board = raw_changed & board_mask
    joined = dilate(changed_on_board, radius=2)

    bull_x, bull_y = map(float, calibration["bull"])
    homography = board_homography(calibration)
    candidates = []
    for joined_component in components(joined):
        if joined_component.shape[0] < 18:
            continue
        ys = joined_component[:, 0]
        xs = joined_component[:, 1]
        original = raw_changed[ys, xs]
        original_pixels = joined_component[original]
        if original_pixels.shape[0] < 8:
            continue
        original_y = original_pixels[:, 0]
        original_x = original_pixels[:, 1]
        distances = np.hypot(original_x - bull_x, original_y - bull_y)
        nearest_index = int(np.argmin(distances))
        nearest = original_pixels[nearest_index]
        width = int(original_x.max() - original_x.min() + 1)
        height = int(original_y.max() - original_y.min() + 1)
        candidates.append(
            {
                "pixels": int(original_pixels.shape[0]),
                "joinedPixels": int(joined_component.shape[0]),
                "nearest": {"x": int(nearest[1]), "y": int(nearest[0])},
                "distanceToBull": round(float(distances[nearest_index]), 2),
                "box": {
                    "left": int(original_x.min()),
                    "top": int(original_y.min()),
                    "right": int(original_x.max()),
                    "bottom": int(original_y.max()),
                },
                "elongation": round(max(width, height) / max(1, min(width, height)), 3),
                "center": {"x": float(original_x.mean()), "y": float(original_y.mean())},
                "_pixelArray": original_pixels,
            }
        )

    sizeable = [candidate for candidate in candidates if candidate["pixels"] >= 8]
    largest = max(sizeable, key=lambda item: item["pixels"], default=None)
    for candidate in sizeable:
        candidate["entryPoint"] = estimate_component_entry(candidate, largest)
        candidate["boardPoint"] = map_to_board(candidate["entryPoint"], homography)

    # This local choice remains as a fallback. The main routine replaces it
    # with a cross-camera consensus whenever at least two cameras agree.
    selected = max(
        [candidate for candidate in sizeable if candidate["pixels"] >= 35],
        key=lambda item: item["pixels"] * item["elongation"],
        default=None,
    )
    entry_point = selected["entryPoint"] if selected else None

    marked = after_image.copy()
    draw = ImageDraw.Draw(marked)
    draw.ellipse((bull_x - 6, bull_y - 6, bull_x + 6, bull_y + 6), outline="cyan", width=3)
    if selected:
        point = entry_point
        radius = 11
        draw.ellipse(
            (point["x"] - radius, point["y"] - radius, point["x"] + radius, point["y"] + radius),
            outline="lime",
            width=4,
        )
        draw.line((point["x"] - 15, point["y"], point["x"] + 15, point["y"]), fill="lime", width=2)
        draw.line((point["x"], point["y"] - 15, point["x"], point["y"] + 15), fill="lime", width=2)

    return {
        "changedPixelsOnBoard": int(changed_on_board.sum()),
        "bull": {"x": int(bull_x), "y": int(bull_y)},
        "entryPoint": entry_point,
        "distanceToBull": (
            round(float(np.hypot(entry_point["x"] - bull_x, entry_point["y"] - bull_y)), 2)
            if entry_point
            else None
        ),
        "selectedComponentPixels": selected["pixels"] if selected else 0,
        "selectionMethod": "local-fallback" if selected else None,
        "candidateCount": len(candidates),
        "candidates": [
            {key: value for key, value in candidate.items() if not key.startswith("_")}
            for candidate in sorted(candidates, key=lambda item: item["pixels"], reverse=True)
        ],
    }, marked


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--calibration", type=Path)
    parser.add_argument("--confirmed-field")
    parser.add_argument("--threshold", type=int, default=35)
    args = parser.parse_args()

    calibration_path = args.calibration or args.after / "autodarts-calibration.json"
    calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
    output_dir = args.after / "dart-analysis"
    output_dir.mkdir(exist_ok=True)
    report = {
        "schemaVersion": 2,
        "confirmedField": args.confirmed_field,
        "before": str(args.before.resolve()),
        "after": str(args.after.resolve()),
        "threshold": args.threshold,
        "cameras": [],
    }

    for camera in range(CAMERA_COUNT):
        result, marked = analyze_camera(
            args.before / f"camera-{camera}.jpg",
            args.after / f"camera-{camera}.jpg",
            calibration[str(camera)],
            args.threshold,
        )
        result["camera"] = camera
        result["markedImage"] = f"camera-{camera}-entry.jpg"
        report["cameras"].append(result)

    report["ringRadii"] = calibrated_ring_radii(calibration)
    report["ringProfiles"] = calibrated_ring_profiles(calibration)
    report["consensus"] = select_cross_camera_consensus(
        report["cameras"], report["ringRadii"], report["ringProfiles"]
    )
    if report["consensus"]:
        classification = classify_board_point(
            report["consensus"]["boardPoint"], report["ringRadii"], report["ringProfiles"]
        )
        report["consensus"]["predictedField"] = classification["field"]
        report["consensus"]["nearWire"] = classification["nearWire"]
        report["consensus"]["wireDistance"] = (
            round(float(classification["wireDistance"]), 6)
            if classification["wireDistance"] is not None
            else None
        )
        report["consensus"]["matchesConfirmedField"] = (
            args.confirmed_field is None
            or report["consensus"]["predictedField"].upper() == args.confirmed_field.upper()
        )
    for camera, result in enumerate(report["cameras"]):
        marked = draw_selected_point(args.after / f"camera-{camera}.jpg", result)
        marked.save(output_dir / result["markedImage"], quality=94)

    report_path = output_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(report_path)


if __name__ == "__main__":
    main()
