# bucket.py
from botocore.exceptions import ClientError
from minio_client import get_s3_client

BUCKET_NAME = "agreements"

def ensure_bucket():
    s3 = get_s3_client()
    try:
        s3.head_bucket(Bucket=BUCKET_NAME)
        print("Bucket zaten var:", BUCKET_NAME)
    except ClientError:
        s3.create_bucket(Bucket=BUCKET_NAME)
        print("Bucket oluşturuldu:", BUCKET_NAME)
