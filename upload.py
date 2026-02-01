import os
from compressor import compress_file
from minio_client import get_s3_client
import mimetypes
import io
import pikepdf


def optimize_pdf(data: bytes) -> bytes:
    input_io = io.BytesIO(data)
    output_io = io.BytesIO()

    try:
        with pikepdf.open(input_io) as pdf:
            # Eski sürümlerle uyumlu minimal parametre seti
            pdf.save(output_io, compress_streams=True)

        optimized = output_io.getvalue()
        return optimized if len(optimized) < len(data) else data

    except Exception:
        # PDF optimize edilemezse sistemi kırma -> orijinali sakla
        return data
        




def upload_agreement(local_file_path: str, disk: str, user_id: str, timestamp: str):
    s3 = get_s3_client()

    file_name = os.path.basename(local_file_path)
    object_key = f"{disk}/{user_id}/{timestamp}/{file_name}"

    with open(local_file_path, "rb") as f:
        original_bytes = f.read()

    comp = compress_file(filename=file_name, data=original_bytes)
    optimized_bytes = comp["data"]

    content_type, _ = mimetypes.guess_type(file_name)
    content_type = content_type or "application/octet-stream"

    s3.put_object(
        Bucket="agreements",
        Key=object_key,
        Body=optimized_bytes,
        ContentType=content_type,
        Metadata={
            "compression": comp["algorithm"],
            "original_size": str(comp["original_size"]),
            "optimized_size": str(comp["optimized_size"]),
            "original_hash": comp["original_hash"],
            "optimized_hash": comp["optimized_hash"],
        }
    )

    print(f"Yüklendi: {object_key} | {comp['original_size']} → {comp['optimized_size']} bytes")
    return object_key