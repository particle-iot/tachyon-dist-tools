from datetime import datetime
import boto3
import botocore
import json
import sys
import os
import hashlib

class S3WriteConflict(RuntimeError):
    pass

def generate_transaction_id(bucket, key):
    """
    Generate a transaction ID using an MD5 hash of the bucket and key.
    """
    data = f"{bucket}:{key}".encode("utf-8")
    return hashlib.md5(data).hexdigest()

def read_s3_object(bucket, key, file, transaction_file):
    s3 = boto3.client("s3")
    resp = s3.get_object(Bucket=bucket, Key=key)
    etag = resp["ETag"].strip('"')
    data = resp["Body"].read().decode("utf-8")
    with open(file, "w") as f:
        f.write(data)

    with open(transaction_file, "w") as f:
        json.dump({"Bucket": bucket, "Key": key, "ETag": etag, "ReadTime": datetime.now().isoformat()}, f)

def write_s3_object(bucket, key, file, transaction_file):
    s3 = boto3.client("s3")
    with open(file, "r") as f:
        data = f.read()
    with open(transaction_file, "r") as f:
        transaction = json.load(f)
    etag = transaction["ETag"]
    if transaction["Bucket"] != bucket or transaction["Key"] != key:
        raise ValueError("Transaction file does not match the specified bucket and key.")

    try:
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=data.encode("utf-8"),
            ContentType="application/json",
            IfMatch=etag
        )
        os.remove(transaction_file)
        return True
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "PreconditionFailed":
            raise S3WriteConflict(f"ETag mismatch for s3://{bucket}/{key}. Expected {etag}.", file=sys.stderr)
        else:
            raise

