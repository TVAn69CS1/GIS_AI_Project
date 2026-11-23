from pathlib import Path
from osgeo import gdal

gdal.UseExceptions()

# Xác định thư mục gốc của repo (từ .../raster_analysis/gdal/normalize_raster.py đi lùi 3 cấp)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUT_TIF = PROJECT_ROOT / "WebODM_Module1" / "Ket_Qua" / "orthophoto.tif"
OUTPUT_TIF = PROJECT_ROOT / "data" / "raster" / "orthophoto_normalized.tif"


def inspect_and_normalize(input_path: Path, output_path: Path) -> None:
    # 1. Đảm bảo thư mục đầu ra tồn tại
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 2. Mở file GeoTIFF
    ds = gdal.Open(str(input_path), gdal.GA_ReadOnly)
    if ds is None:
        raise FileNotFoundError(f"Không thể mở file ảnh: {input_path}")

    # 3. Lấy và in các thông tin của ảnh
    width = ds.RasterXSize
    height = ds.RasterYSize
    bands = ds.RasterCount
    gt = ds.GetGeoTransform()
    proj = ds.GetProjection()

    print("=== THÔNG TIN FILE ORTHOPHOTO GỐC ===")
    print(f"Đường dẫn file : {input_path}")
    print(f"Kích thước ảnh : {width} x {height} pixels")
    print(f"Số kênh (bands): {bands}")
    print(f"GeoTransform   : {gt}")
    print(f"Kích thước px  : X = {gt[1]}, Y = {abs(gt[5])}")
    print(f"Hệ tọa độ (CRS): {proj if proj else 'Không có thông tin CRS'}")

    # 4. Chuẩn hóa hệ tọa độ sang EPSG:4326 và nén file GeoTIFF
    warp_options = gdal.WarpOptions(
        format="GTiff",
        dstSRS="EPSG:4326",
        resampleAlg=gdal.GRA_Bilinear,
        creationOptions=[
            "COMPRESS=LZW",
            "TILED=YES",
            "BIGTIFF=IF_SAFER",
        ],
    )
    warped_ds = gdal.Warp(str(output_path), ds, options=warp_options)
    warped_ds.FlushCache()

    # 5. Đóng file an toàn
    warped_ds = None
    ds = None
    print(f"\n[OK] Đã xuất file chuẩn hóa tại: {output_path}")


if __name__ == "__main__":
    inspect_and_normalize(INPUT_TIF, OUTPUT_TIF)