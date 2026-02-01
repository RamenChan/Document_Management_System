# download.py
from minio_client import get_s3_client

def download_agreement(object_key: str, target_path: str):
    s3 = get_s3_client()

    s3.download_file(
        Bucket="agreements",
        Key=object_key,
        Filename=target_path,
    )

    print("İndirildi:", target_path)
