from pathlib import Path
import numpy as np
from osgeo import gdal, osr

gdal.UseExceptions()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUT_NORMALIZED_TIF = PROJECT_ROOT / "data" / "raster" / "orthophoto_normalized.tif"
OUTPUT_CLASS_TIF = PROJECT_ROOT / "data" / "raster" / "classification_veg_soil.tif"


def analyze_vegetation_and_area(
    input_tif: Path,
    output_tif: Path,
    exg_threshold: float = 0.08,
    utm_epsg: int = 32648,
) -> None:
    output_tif.parent.mkdir(parents=True, exist_ok=True)

    # 1. Mở ảnh đã chuẩn hóa
    ds = gdal.Open(str(input_tif), gdal.GA_ReadOnly)
    if ds is None:
        raise FileNotFoundError(f"Không tìm thấy file: {input_tif}")

    if ds.RasterCount < 3:
        raise ValueError(f"Ảnh cần ít nhất 3 kênh RGB, hiện có {ds.RasterCount} kênh.")

    # 2. Đọc kênh R, G, B
    r = ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
    g = ds.GetRasterBand(2).ReadAsArray().astype(np.float32)
    b = ds.GetRasterBand(3).ReadAsArray().astype(np.float32)

    # 3. Xác định vùng ảnh hợp lệ (khác 0 cả 3 kênh)
    valid_mask = (r > 0) | (g > 0) | (b > 0)
    if not np.any(valid_mask):
        raise ValueError("Ảnh không có pixel hợp lệ nào.")

    # 4. Chuẩn hóa về [0, 1] và tính chỉ số Excess Green (ExG = 2G - R - B)
    max_val = 255.0 if r.max() <= 255.0 else float(np.percentile(r[valid_mask], 99))
    r_norm = np.clip(r / max_val, 0.0, 1.0)
    g_norm = np.clip(g / max_val, 0.0, 1.0)
    b_norm = np.clip(b / max_val, 0.0, 1.0)

    exg = 2.0 * g_norm - r_norm - b_norm

    # 5. Phân loại: 0 = NoData, 1 = Thực vật, 2 = Đất / Khác
    class_map = np.zeros(r.shape, dtype=np.uint8)
    veg_mask = valid_mask & (exg > exg_threshold)
    soil_mask = valid_mask & (~veg_mask)

    class_map[veg_mask] = 1
    class_map[soil_mask] = 2

    # 6. Xuất ảnh phân loại ra GeoTIFF
    driver = gdal.GetDriverByName("GTiff")
    out_ds = driver.Create(
        str(output_tif),
        ds.RasterXSize,
        ds.RasterYSize,
        1,
        gdal.GDT_Byte,
        options=["COMPRESS=LZW", "TILED=YES"],
    )
    out_ds.SetGeoTransform(ds.GetGeoTransform())
    out_ds.SetProjection(ds.GetProjection())

    out_band = out_ds.GetRasterBand(1)
    out_band.WriteArray(class_map)
    out_band.SetNoDataValue(0)
    out_band.FlushCache()

    # 7. Tính diện tích 1 pixel theo mét bằng cách chuyển sang hệ tọa độ UTM
    src_srs = osr.SpatialReference()
    src_srs.ImportFromWkt(ds.GetProjection())
    src_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

    dst_srs = osr.SpatialReference()
    dst_srs.ImportFromEPSG(utm_epsg)
    dst_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

    coord_tf = osr.CoordinateTransformation(src_srs, dst_srs)
    gt = ds.GetGeoTransform()

    x0, y0 = gt[0], gt[3]
    x_dx, y_dx = x0 + gt[1], y0
    x_dy, y_dy = x0, y0 + gt[5]

    ux0, uy0, _ = coord_tf.TransformPoint(x0, y0)
    ux_dx, uy_dx, _ = coord_tf.TransformPoint(x_dx, y_dx)
    ux_dy, uy_dy, _ = coord_tf.TransformPoint(x_dy, y_dy)

    px_w_m = np.hypot(ux_dx - ux0, uy_dx - uy0)
    px_h_m = np.hypot(ux_dy - ux0, uy_dy - uy0)
    pixel_area_m2 = px_w_m * px_h_m

    # 8. Thống kê số pixel và diện tích từng lớp
    veg_px = int(np.sum(class_map == 1))
    soil_px = int(np.sum(class_map == 2))

    veg_m2 = veg_px * pixel_area_m2
    soil_m2 = soil_px * pixel_area_m2
    total_m2 = veg_m2 + soil_m2

    veg_pct = (veg_m2 / total_m2 * 100.0) if total_m2 > 0 else 0.0
    soil_pct = (soil_m2 / total_m2 * 100.0) if total_m2 > 0 else 0.0

    print("=== KẾT QUẢ PHÂN TÍCH PHỔ & DIỆN TÍCH ===")
    print(f"Ngưỡng ExG sử dụng  : > {exg_threshold}")
    print(f"Hệ UTM tính diện tích: EPSG:{utm_epsg}")
    print(f"Diện tích 1 pixel   : {pixel_area_m2:.4f} m²")
    print(f"Thực vật (Class 1)  : {veg_px} px | {veg_m2:.2f} m² | {veg_m2/10000:.4f} ha | {veg_pct:.2f}%")
    print(f"Đất / Khác (Class 2): {soil_px} px | {soil_m2:.2f} m² | {soil_m2/10000:.4f} ha | {soil_pct:.2f}%")
    print(f"Tổng diện tích vùng : {total_m2:.2f} m² | {total_m2/10000:.4f} ha")
    print(f"\n[OK] Đã lưu ảnh phân loại tại: {output_tif}")

    out_ds = None
    ds = None


if __name__ == "__main__":
    # Đổi utm_epsg=32649 nếu khu vực chụp nằm ở miền Nam Việt Nam
    analyze_vegetation_and_area(
        INPUT_NORMALIZED_TIF,
        OUTPUT_CLASS_TIF,
        exg_threshold=0.08,
        utm_epsg=32648,
    )