
import json
from pathlib import Path

import rasterio
import matplotlib.pyplot as plt


# Xác định thư mục gốc dự án
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Đường dẫn dữ liệu đầu vào
RASTER_PATH = PROJECT_ROOT / "data" / "raster" / "orthophoto_normalized.tif"
GEOJSON_PATH = PROJECT_ROOT / "data" / "spatial_output" / "detections.geojson"

# Đường dẫn lưu ảnh kết quả
OUTPUT_PATH = PROJECT_ROOT / "data" / "spatial_output" / "detections_visualization.png"


def visualize_detections():

    # Đọc ảnh Orthophoto
    with rasterio.open(RASTER_PATH) as dataset:
        image = dataset.read([1, 2, 3])

        # Đưa ảnh về định dạng phù hợp với Matplotlib
        image = image.transpose(1, 2, 0)

        # Lấy phạm vi tọa độ ảnh
        bounds = dataset.bounds

    # Đọc dữ liệu GeoJSON
    with open(GEOJSON_PATH, "r", encoding="utf-8") as file:
        geojson = json.load(file)

    # Tạo khung hình
    fig, ax = plt.subplots(figsize=(16, 12))

    # Hiển thị Orthophoto
    ax.imshow(
        image,
        extent=[
            bounds.left,
            bounds.right,
            bounds.bottom,
            bounds.top
        ],
        origin="upper"
    )

    # Đánh dấu từng đối tượng
    for feature in geojson["features"]:

        # Lấy kinh độ và vĩ độ
        longitude, latitude = feature["geometry"]["coordinates"]

        # Lấy thông tin đối tượng
        object_id = feature["properties"]["id"]
        label = feature["properties"]["label"]

        # Vẽ vị trí đối tượng
        ax.scatter(
            longitude,
            latitude,
            color="red",
            marker="x",
            s=100,
            linewidths=2
        )

        # Ghi ID cạnh vị trí
        ax.annotate(
            str(object_id),
            (longitude, latitude),
            xytext=(8, 8),
            textcoords="offset points",
            color="yellow",
            fontsize=12,
            fontweight="bold"
        )

    # Thiết lập tiêu đề và nhãn
    ax.set_title("YOLO Detection Locations on Orthophoto")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")

    # Lưu ảnh kết quả
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    plt.savefig(
        OUTPUT_PATH,
        dpi=200,
        bbox_inches="tight"
    )

    plt.close()

    print("=" * 50)
    print("KIỂM TRA TRỰC QUAN HOÀN TẤT")
    print("Số đối tượng:", len(geojson["features"]))
    print("Ảnh kết quả:", OUTPUT_PATH)
    print("=" * 50)


if __name__ == "__main__":
    visualize_detections()
