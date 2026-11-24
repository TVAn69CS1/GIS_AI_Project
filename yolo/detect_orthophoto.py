"""Detect houses/buildings on a GeoTIFF orthophoto using overlapping tiles."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from ultralytics import YOLO

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IMAGE = PROJECT_ROOT / "data" / "raster" / "orthophoto_normalized.tif"
DEFAULT_MODEL = Path("yolov8s-worldv2.pt")
GENERAL_PROMPTS = ["house", "building", "roof"]
TARGET_PROMPTS = ["small house with a bright roof", "house roof", "residential house",
                  "white rooftop", "building"]
# Areas marked by the user in the orthophoto screenshot, in source-image pixels.
# Each ROI includes a little surrounding context for the detector.
TARGET_ROIS = [
    (2600, 500, 4200, 2200),       # two small roofs at the upper-left
    (5800, 0, 7600, 1800),         # house compound near the top-center
    (8000, 800, 10100, 2400),      # house compound near the upper-right
    (11800, 3200, 13059, 5300),    # bright roof at the right edge
]
# Three repeatable false positives in the current orthophoto (road/forest).
# Apply only to the full-image pass so supplemental marked-roof detections remain.
IGNORE_ROIS = [
    (3950, 5000, 4900, 5800),
    (10150, 9900, 11000, 10750),
    (6400, 10700, 7400, 11600),
]
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "detections"


def detect(image: Path, model_path: Path, output_dir: Path, conf: float = 0.05,
           iou: float = 0.7, imgsz: int = 1280, device: str | None = None,
           tile_size: int = 768, overlap: float = 0.25,
           target_conf: float = 0.20) -> list[dict[str, Any]]:
    if not image.is_file():
        raise FileNotFoundError(f"Orthophoto not found: {image}")
    if tile_size <= 0 or not 0 <= overlap < 1:
        raise ValueError("tile_size must be positive and overlap must be in [0, 1).")
    output_dir.mkdir(parents=True, exist_ok=True)

    import cv2

    raster = cv2.imread(str(image), cv2.IMREAD_COLOR)
    if raster is None:
        raise OSError(f"OpenCV could not read image: {image}")
    height, width = raster.shape[:2]

    model = YOLO(str(model_path))
    is_world = "world" in model_path.name.lower()
    stride = max(1, int(tile_size * (1 - overlap)))

    def build_tile_specs(regions: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
        specs: list[tuple[int, int, int, int]] = []
        for rx1, ry1, rx2, ry2 in regions:
            rx1, ry1 = max(0, rx1), max(0, ry1)
            rx2, ry2 = min(width, rx2), min(height, ry2)
            xs = list(range(rx1, max(rx1 + 1, rx2 - tile_size + 1), stride))
            ys = list(range(ry1, max(ry1 + 1, ry2 - tile_size + 1), stride))
            if not xs or xs[-1] + tile_size < rx2:
                xs.append(max(rx1, rx2 - tile_size))
            if not ys or ys[-1] + tile_size < ry2:
                ys.append(max(ry1, ry2 - tile_size))
            specs.extend((x, y, min(x + tile_size, rx2), min(y + tile_size, ry2))
                         for y in ys for x in xs)
        return specs

    def run_pass(regions: list[tuple[int, int, int, int]], prompts: list[str] | None,
                 threshold: float, pass_name: str) -> list[dict[str, Any]]:
        if is_world and prompts:
            model.set_classes(prompts)
        specs = build_tile_specs(regions)
        found: list[dict[str, Any]] = []
        for tile_index, (x, y, x2, y2) in enumerate(specs, start=1):
            tile = raster[y:y2, x:x2]
            result = model.predict(source=tile, conf=threshold, iou=iou, imgsz=imgsz,
                                   device=device, verbose=False)[0]
            if result.boxes is not None:
                for box, score, class_id in zip(result.boxes.xyxy.cpu().tolist(),
                                                result.boxes.conf.cpu().tolist(),
                                                result.boxes.cls.cpu().tolist()):
                    bx1, by1, bx2, by2 = box
                    class_id = int(class_id)
                    label = prompts[class_id] if is_world and prompts else str(result.names[class_id])
                    found.append({"x1": bx1 + x, "y1": by1 + y, "x2": bx2 + x, "y2": by2 + y,
                                  "confidence": float(score), "class_id": class_id,
                                  "label": label, "source": pass_name})
            if tile_index % 25 == 0 or tile_index == len(specs):
                print(f"{pass_name}: processed {tile_index}/{len(specs)} tiles; {len(found)} detections.")
        return found

    # Keep the full-image detections and add a focused, higher-threshold pass
    # over user-marked roofs. This supplements rather than replaces existing hits.
    full_regions = [(0, 0, width, height)]
    general = run_pass(full_regions, GENERAL_PROMPTS if is_world else None, conf, "full-image")
    before_filter = len(general)
    general = [item for item in general if not any(
        rx1 <= (item["x1"] + item["x2"]) / 2 <= rx2
        and ry1 <= (item["y1"] + item["y2"]) / 2 <= ry2
        for rx1, ry1, rx2, ry2 in IGNORE_ROIS
    )]
    print(f"Ignored {before_filter - len(general)} known false positives in road/forest areas.")
    targeted = run_pass(TARGET_ROIS, TARGET_PROMPTS if is_world else None,
                        target_conf, "marked-roofs")

    def overlap_ratio(a: dict[str, Any], b: dict[str, Any]) -> float:
        xx1, yy1 = max(a["x1"], b["x1"]), max(a["y1"], b["y1"])
        xx2, yy2 = min(a["x2"], b["x2"]), min(a["y2"], b["y2"])
        inter = max(0.0, xx2 - xx1) * max(0.0, yy2 - yy1)
        area_a = (a["x2"] - a["x1"]) * (a["y2"] - a["y1"])
        area_b = (b["x2"] - b["x1"]) * (b["y2"] - b["y1"])
        return inter / max(area_a + area_b - inter, 1e-9)

    def dedupe(candidates: list[dict[str, Any]], threshold: float) -> list[dict[str, Any]]:
        kept_items: list[dict[str, Any]] = []
        for candidate in sorted(candidates, key=lambda item: item["confidence"], reverse=True):
            if all(overlap_ratio(candidate, selected) <= threshold for selected in kept_items):
                kept_items.append(candidate)
        return kept_items

    # Preserve the established full-image hits; supplement only distinct target hits.
    kept = dedupe(general, 0.5)
    for candidate in dedupe(targeted, 0.25):
        if all(overlap_ratio(candidate, item) <= 0.5 for item in kept):
            kept.append(candidate)

    detections: list[dict[str, Any]] = []
    for index, item in enumerate(kept, start=1):
        x1, y1, x2, y2 = (round(item[key], 2) for key in ("x1", "y1", "x2", "y2"))
        detections.append({
            "id": index, "class_id": item["class_id"], "label": item["label"],
            "confidence": round(item["confidence"], 6), "source_pass": item["source"],
            "bbox_xyxy": {"x_min": x1, "y_min": y1, "x_max": x2, "y_max": y2},
            "bbox_xywh": {"x_center": round((x1 + x2) / 2, 2),
                          "y_center": round((y1 + y2) / 2, 2),
                          "width": round(x2 - x1, 2), "height": round(y2 - y1, 2)},
        })
        # OpenCV uses BGR: this is bright red for clearer visibility on foliage.
        color = (0, 0, 255)
        cv2.rectangle(raster, (int(x1), int(y1)), (int(x2), int(y2)), color, 3)
        cv2.putText(raster, f"{item['label']} {item['confidence']:.2f}",
                    (int(x1), max(22, int(y1) - 8)), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, color, 2, cv2.LINE_AA)

    image_out = output_dir / "orthophoto_detections.jpg"
    if not cv2.imwrite(str(image_out), raster, [cv2.IMWRITE_JPEG_QUALITY, 92]):
        raise OSError(f"Could not write result image: {image_out}")

    payload = {
        "source_image": str(image), "model": str(model_path),
        "image_width": width, "image_height": height,
        "search_scope": "full orthophoto plus supplemental pass over four user-marked roof areas; three known false-positive areas excluded from full-image pass",
        "coordinate_note": "Bounding boxes use image pixel coordinates; origin is top-left.",
        "count": len(detections), "detections": detections,
    }
    (output_dir / "detections.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    fields = ["id", "class_id", "label", "confidence", "source_pass", "x_min", "y_min", "x_max", "y_max",
              "x_center", "y_center", "width", "height"]
    with (output_dir / "detections.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for item in detections:
            writer.writerow({**{key: item[key] for key in ("id", "class_id", "label", "confidence", "source_pass")},
                             **item["bbox_xyxy"], **item["bbox_xywh"]})
    print(f"Detected {len(detections)} objects; results saved to: {output_dir}")
    return detections


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, default=DEFAULT_IMAGE, help="Input orthophoto GeoTIFF")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL, help="YOLO checkpoint")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--conf", type=float, default=0.05, help="Confidence for full-image pass")
    parser.add_argument("--target-conf", type=float, default=0.20,
                        help="Higher confidence threshold for supplemental roof pass")
    parser.add_argument("--iou", type=float, default=0.7)
    parser.add_argument("--imgsz", type=int, default=1280)
    parser.add_argument("--device", default=None, help="cpu, 0, etc.; auto-selected by default")
    parser.add_argument("--tile-size", type=int, default=768, help="Tile edge length in pixels")
    parser.add_argument("--overlap", type=float, default=0.25, help="Overlap ratio between tiles")
    args = parser.parse_args()
    detect(args.image, args.model, args.output, args.conf, args.iou, args.imgsz,
           args.device, args.tile_size, args.overlap, args.target_conf)


if __name__ == "__main__":
    main()
