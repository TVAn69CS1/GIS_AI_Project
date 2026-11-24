
import json
from pathlib import Path

import rasterio


# Xác định thư mục gốc của dự án
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Đường dẫn đến dữ liệu đầu vào
JSON_PATH = PROJECT_ROOT / "data" / "detections" / "detections.json"
RASTER_PATH = PROJECT_ROOT / "data" / "raster" / "orthophoto_normalized.tif"

# Đường dẫn lưu kết quả
OUTPUT_PATH = PROJECT_ROOT / "data" / "spatial_output" / "detections.geojson"


def convert_detections():
    # Đọc dữ liệu Bounding Box từ YOLO
    with open(JSON_PATH, "r", encoding="utf-8-sig") as file:
        data = json.load(file)

    features = []

    # Mở ảnh Orthophoto để lấy thông tin tọa độ
    with rasterio.open(RASTER_PATH) as dataset:

        # Kiểm tra hệ tọa độ
        if dataset.crs is None:
            raise ValueError("Orthophoto chưa có thông tin CRS!")

        if dataset.crs.to_epsg() != 4326:
            raise ValueError(
                f"CRS hiện tại là {dataset.crs}, cần xử lý chuyển đổi CRS."
            )

        # Duyệt qua từng đối tượng YOLO phát hiện
        for detection in data["detections"]:

            # Lấy tọa độ Bounding Box theo pixel
            bbox = detection["bbox_xyxy"]

            x_min = bbox["x_min"]
            y_min = bbox["y_min"]
            x_max = bbox["x_max"]
            y_max = bbox["y_max"]

            # Xác định tọa độ 4 góc của hình chữ nhật
            corners = [
                (x_min, y_min),  # Góc trên trái
                (x_max, y_min),  # Góc trên phải
                (x_max, y_max),  # Góc dưới phải
                (x_min, y_max),  # Góc dưới trái
                (x_min, y_min)   # Đóng Polygon bằng cách lặp lại góc đầu
            ]

            # Chuyển 4 góc từ pixel sang longitude, latitude
            polygon_coordinates = []

            for pixel_x, pixel_y in corners:
                longitude, latitude = dataset.transform * (pixel_x, pixel_y)

                polygon_coordinates.append([
                    longitude,
                    latitude
                ])

            # Lấy tọa độ tâm Bounding Box
            pixel_center_x = (x_min + x_max) / 2
            pixel_center_y = (y_min + y_max) / 2

            # Chuyển tọa độ tâm sang longitude, latitude
            center_longitude, center_latitude = (
                dataset.transform * (pixel_center_x, pixel_center_y)
            )

            # Tạo đối tượng GeoJSON dạng Polygon
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        polygon_coordinates
                    ]
                },
                "properties": {
                    "id": detection["id"],
                    "label": detection["label"],
                    "confidence": detection["confidence"],

                    # Tọa độ tâm theo pixel
                    "pixel_x": pixel_center_x,
                    "pixel_y": pixel_center_y,

                    # Tọa độ tâm theo GPS
                    "longitude": center_longitude,
                    "latitude": center_latitude,

                    # Tọa độ Bounding Box ban đầu
                    "bbox_xyxy": detection["bbox_xyxy"]
                }
            }

            features.append(feature)

    # Tạo cấu trúc GeoJSON hoàn chỉnh
    geojson_data = {
        "type": "FeatureCollection",
        "name": "detections",
        "features": features
    }

    # Tạo thư mục đầu ra nếu chưa tồn tại
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Ghi dữ liệu ra file GeoJSON
    with open(OUTPUT_PATH, "w", encoding="utf-8") as file:
        json.dump(
            geojson_data,
            file,
            ensure_ascii=False,
            indent=4
        )

    # Thông báo kết quả
    print("=" * 60)
    print("CHUYỂN ĐỔI TỌA ĐỘ HOÀN TẤT")
    print("Hệ tọa độ đầu ra: EPSG:4326")
    print("Số đối tượng:", len(features))
    print("Kiểu hình học: Polygon")
    print("Số góc mỗi Bounding Box: 4")
    print("File kết quả:", OUTPUT_PATH)
    print("=" * 60)

    # In tọa độ tâm và 4 góc của từng đối tượng
    for feature in features:
        properties = feature["properties"]
        corners = feature["geometry"]["coordinates"][0]

        print(f"\nĐối tượng ID: {properties['id']}")

        print(
            f"Tâm: Longitude = {properties['longitude']:.8f}, "
            f"Latitude = {properties['latitude']:.8f}"
        )

        print("Tọa độ 4 góc:")

        for index, coordinate in enumerate(corners[:4], start=1):
            print(
                f"Góc {index}: "
                f"Longitude = {coordinate[0]:.8f}, "
                f"Latitude = {coordinate[1]:.8f}"
            )


if __name__ == "__main__":
    convert_detections()
