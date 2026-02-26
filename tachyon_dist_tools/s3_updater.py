from datetime import datetime
import pathlib
import boto3
import botocore
import argparse
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
    print(f"File {file} written from s3://{bucket}/{key}", file=sys.stderr)

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
            IfMatch=etag,
            ContentType="application/json"
        )
        print(f"File {file} written to s3://{bucket}/{key}", file=sys.stderr)
        os.remove(transaction_file)
        return True
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "PreconditionFailed":
            raise S3WriteConflict(f"ETag mismatch for s3://{bucket}/{key}. Expected {etag}.")
        else:
            raise

def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument("command", choices=["get", "put"], help="Command to execute")
    argparser.add_argument("--bucket", required=True, help="S3 bucket name")
    argparser.add_argument("--key", required=True, help="S3 object key")
    argparser.add_argument("--file", required=True, help="Local file path to read from or write to")
    args = argparser.parse_args()

    # Generate a transaction id using a hash of the bucket and key
    transaction_id = generate_transaction_id(args.bucket, args.key)

    try:
        transaction_file = os.path.join(pathlib.Path.home(), ".s3_updater", f"s3_transaction_{transaction_id}.json")
        os.makedirs(os.path.dirname(transaction_file), exist_ok=True)
        if args.command == "get":
            # Error if transaction file already exists
            if os.path.exists(transaction_file):
                raise RuntimeError(f"Transaction file {transaction_file} already exists. Please put the modified file or remove the transaction file before getting the file again.")
            read_s3_object(args.bucket, args.key, args.file, transaction_file)
            print(transaction_file)
        elif args.command == "put":
            write_s3_object(args.bucket, args.key, args.file, transaction_file)
        else:
            print(f"Unknown command: {args.command}", file=sys.stderr)
            sys.exit(2)
    except S3WriteConflict as e:
        print(f"Write conflict: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(127)

if __name__ == "__main__":
    main()
