# list_agreements.py
from minio_client import get_s3_client

def list_user_agreements(disk: str, user_id: str):
    s3 = get_s3_client()
    prefix = f"{disk}/{user_id}/"

    response = s3.list_objects_v2(
        Bucket="agreements",
        Prefix=prefix,
    )

    files = []
    for obj in response.get("Contents", []):
        files.append(obj["Key"])

    return files
