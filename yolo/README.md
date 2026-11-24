# Nhận diện nhà trên ảnh trực giao bằng YOLO

Thư mục này chứa chương trình nhận diện nhà/mái nhà trên ảnh trực giao GeoTIFF. Chương trình dùng YOLO-World của Ultralytics, vẽ bounding box lên ảnh và lưu kết quả dưới dạng JSON, CSV.

## Yêu cầu

- Python đã cài đặt.
- Các thư viện trong `requirements.txt`.
- Ảnh đầu vào mặc định: `GIS_AI_Project/data/raster/orthophoto_normalized.tif`.
- Checkpoint mặc định: `yolov8s-worldv2.pt`. Ultralytics sẽ tải checkpoint nếu chưa có trong thư mục chạy.

## Cài đặt và chạy

Mở PowerShell tại thư mục dự án rồi chạy:

```powershell
cd GIS_AI_Project\yolo
pip install -r requirements.txt
python detect_orthophoto.py
```

Có thể chọn ảnh, checkpoint hoặc ngưỡng nhận diện khác:

```powershell
python detect_orthophoto.py --image ..\data\raster\orthophoto_normalized.tif --model yolov8s-worldv2.pt --conf 0.05 --target-conf 0.20
```

## Chương trình xử lý như thế nào?

1. Đọc ảnh GeoTIFF bằng OpenCV và nạp checkpoint YOLO-World.
2. Chia ảnh lớn thành các ô 768 × 768 pixel. Các ô chồng lấn 25% để giảm khả năng bỏ sót đối tượng nằm ở rìa ô.
3. Quét toàn ảnh với các mô tả chung `house`, `building`, `roof`.
4. Quét bổ sung bốn vùng có mái nhà được đánh dấu, dùng mô tả cụ thể hơn như `house roof`, `residential house` và `white rooftop`.
5. Bỏ các dự đoán ở ba vùng đường/rừng thường bị nhận nhầm; gộp các bounding box bị trùng giữa các ô và hai lượt quét.
6. Vẽ bounding box màu đỏ cùng nhãn và độ tin cậy, sau đó ghi ảnh và bảng kết quả.

Các vùng bổ sung và vùng loại trừ được khai báo bằng tọa độ pixel trong `detect_orthophoto.py`. Nếu thay ảnh đầu vào bằng ảnh khác, cần cập nhật các vùng này cho phù hợp.

## Tham số chính

- `--conf`: ngưỡng confidence cho lượt quét toàn ảnh; mặc định `0.05`.
- `--target-conf`: ngưỡng confidence cho lượt quét bổ sung vùng khoanh; mặc định `0.20`.
- `--imgsz`: kích thước ảnh đưa vào model; mặc định `1280`.
- `--tile-size`: kích thước cạnh mỗi ô, tính bằng pixel; mặc định `768`.
- `--overlap`: tỷ lệ chồng lấn giữa các ô; mặc định `0.25`.
- `--device`: thiết bị chạy model, ví dụ `cpu` hoặc `0` cho GPU đầu tiên. Mặc định để Ultralytics tự chọn.

## File kết quả

Kết quả được lưu trong `GIS_AI_Project/data/detections/` và sẽ ghi đè kết quả cũ khi chạy lại:

- `orthophoto_detections.jpg`: ảnh trực giao có khung đỏ, nhãn và confidence.
- `detections.json`: kích thước ảnh, lượt quét tìm thấy đối tượng và thông tin bounding box.
- `detections.csv`: cùng dữ liệu nhận diện ở dạng bảng.

Trong JSON/CSV, tọa độ bounding box là tọa độ pixel của ảnh, gốc `(0, 0)` nằm ở góc trên bên trái. `bbox_xyxy` là tọa độ hai góc của khung; `bbox_xywh` gồm tâm khung, chiều rộng và chiều cao. Tọa độ chưa được chuyển sang kinh độ/vĩ độ; bước đó cần dùng thông tin địa lý của GeoTIFF.

## Lưu ý

YOLO-World nhận diện theo mô tả văn bản, không phải checkpoint được huấn luyện riêng trên bộ ảnh của dự án. Confidence cao không đảm bảo dự đoán đúng; cần kiểm tra ảnh kết quả trước khi dùng dữ liệu cho bản đồ hoặc báo cáo. Bộ checkpoint này không tự tạo GeoJSON.
