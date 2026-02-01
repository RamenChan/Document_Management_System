from fastapi import FastAPI, UploadFile, File, HTTPException
from datetime import datetime
import uuid
import contract_pb2
from minio_client import get_s3_client
from compressor import compress_file 

BUCKET_NAME = "agreements"

app = FastAPI(title="Agreement Service")

def ensure_bucket(s3):
    try:
        s3.head_bucket(Bucket=BUCKET_NAME)
    except:
        s3.create_bucket(Bucket=BUCKET_NAME)

@app.post("/agreements/upload")
async def upload_agreement(file: UploadFile = File(...)):
    s3 = get_s3_client()
    ensure_bucket(s3)

    # ✅ Sadece pdf/jpg kabul edelim (istersen genişletiriz)
    filename_lower = (file.filename or "").lower()
    if not (filename_lower.endswith(".pdf") or filename_lower.endswith(".jpg") or filename_lower.endswith(".jpeg")):
        raise HTTPException(status_code=400, detail="Sadece PDF/JPG/JPEG destekleniyor")

    # UUID & timestamp
    user_uuid = str(uuid.uuid4())
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    # Object paths (senin istediğin upload_pdf klasörüyle)
    base_path = f"K/{user_uuid}/{timestamp}/upload_pdf"
    file_key = f"{base_path}/{file.filename}"
    metadata_key = f"{base_path}/metadata.pb"

    # 1) Dosyayı oku
    original_bytes = await file.read()
    if not original_bytes:
        raise HTTPException(status_code=400, detail="Boş dosya yüklenemez")

    # 2) Optimize et (akıllı karar içeride)
    comp = compress_file(filename=file.filename, data=original_bytes)
    optimized_bytes = comp["data"]

    # 3) Optimize edilmiş dosyayı MinIO’ya yaz
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=file_key,
        Body=optimized_bytes,
        ContentType=file.content_type or "application/octet-stream",
        Metadata={
            "compression": comp["algorithm"],
            "original_size": str(comp["original_size"]),
            "optimized_size": str(comp["optimized_size"]),
            "original_hash": comp["original_hash"],
            "optimized_hash": comp["optimized_hash"],
        }
    )

    # 4) Protobuf metadata (optimizasyon bilgilerini de ekleyelim)
    metadata = contract_pb2.AgreementMetadata(
        agreement_id=str(uuid.uuid4()),
        user_uuid=user_uuid,
        disk="K",
        file_name=file.filename,
        content_type=file.content_type or "application/octet-stream",
        file_size=len(optimized_bytes),  # ✅ artık saklanan boyut
        created_at=datetime.utcnow().isoformat(),
    )

    metadata_bytes = metadata.SerializeToString()

    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=metadata_key,
        Body=metadata_bytes,
        ContentType="application/octet-stream",
        Metadata={
            "compression": comp["algorithm"],
            "original_size": str(comp["original_size"]),
            "optimized_size": str(comp["optimized_size"]),
            "saving_ratio": str(
                round(1 - (comp["optimized_size"] / comp["original_size"]), 4)
            ) if comp["optimized_size"] < comp["original_size"] else "0"
        }
    )

    # Response
    return {
        "user_uuid": user_uuid,
        "timestamp": timestamp,
        "object_key": file_key,
        "metadata_key": metadata_key,
        "compression": {
            "algorithm": comp["algorithm"],
            "original_size": comp["original_size"],
            "optimized_size": comp["optimized_size"],
        }
    }
