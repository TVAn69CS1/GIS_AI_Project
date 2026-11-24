# YOLO detection on the orthophoto

This module runs an Ultralytics YOLO checkpoint on the project's GeoTIFF and
exports an annotated image plus machine-readable detections for the GPS/GeoJSON
step. Bounding boxes are pixel coordinates with origin at the image's top-left.

## Run

1. The project's normalized orthophoto is expected at
   `GIS_AI_Project/data/raster/orthophoto_normalized.tif` (or pass another path
   with `--image`).
2. In a Python environment, install dependencies:

   ```powershell
   cd GIS_AI_Project\yolo
   pip install -r requirements.txt
   ```

3. Run detection:

   ```powershell
   python detect_orthophoto.py
   ```

The default checkpoint is Ultralytics `yolov8s-worldv2.pt`. Ultralytics
downloads it on first run. The script first scans the full orthophoto using the
general prompts `house`, `building`, and `roof`, then performs a supplemental
pass over the four areas marked by the user with more roof-specific prompts and
a higher confidence threshold. Detections from the full-image pass are kept;
only distinct supplemental boxes are added. Three known road/forest false
positive areas from this orthophoto are excluded from the full-image pass.
Both passes use 768-pixel tiles with 25% overlap. To use a different checkpoint, pass
`--model path\to\checkpoint.pt`. For a specialized checkpoint with its own
classes, the script uses those classes without the text prompts.

Outputs go to `GIS_AI_Project/data/detections/`:

- `orthophoto_detections.jpg`: orthophoto with boxes, labels and confidence.
- `detections.json`: image dimensions, the pass that found each object, and `xyxy` plus center/size `xywh` pixel boxes.
- `detections.csv`: flat table of class, confidence and pixel coordinates.

Example for a large orthophoto or custom checkpoint:

```powershell
python detect_orthophoto.py --image ..\data\raster\orthophoto.tif --model ..\models\best.pt --imgsz 1280 --conf 0.3
```
