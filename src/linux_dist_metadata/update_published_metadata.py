import json
import os
import random
import shutil
import tempfile
import time

from argparse import ArgumentParser

def replace_builds(data, origin_value, new_builds, origin_key="distribution_version"):
    if "builds" not in data or not isinstance(data["builds"], list):
        raise ValueError("Release metadata does not contain a 'builds' field or it is not a list.")
    updated_builds = [ k for k in data["builds"] if origin_key not in k or k[origin_key] != origin_value ]
    for b in new_builds["builds"]:
        if origin_key not in b:
            b[origin_key] = origin_value
        if b[origin_key] == origin_value:
            updated_builds.append(b)

    updated_builds.sort(key=lambda build: build[origin_key])
    data["builds"] = updated_builds
    return data

def main():
  from . import json_validator
  from . import s3

  ap = ArgumentParser()
  ap.add_argument("bucket", help="S3 bucket name")
  ap.add_argument("key", help="S3 object key")
  ap.add_argument("new_metadata", help="Path to the JSON file containing new builds to replace or add")
  ap.add_argument("--origin_key", default="origin", help="Key to match for replacing builds")
  ap.add_argument("--origin", required=True, help="Value of the origin_key to match for replacing builds")
  ap.add_argument("--max_retries", type=int, default=10, help="Maximum number of retries on write conflict")
  args = ap.parse_args()

  for i in range(args.max_retries):
    try:
      tempdir = tempfile.mkdtemp()
      # Download the existing metadata
      existing_metadata_local = f"{tempdir}/existing_metadata.json"
      transaction_file = f"{tempdir}/s3_transaction.json"
      s3.read_s3_object(args.bucket, args.key, existing_metadata_local, transaction_file)
      print(f"Existing metadata downloaded to {existing_metadata_local}")

      # Load and validate the new metadata
      with open(args.new_metadata, 'r') as f:
        new_data = json.load(f)
        json_validator.validate_json(new_data)
      print(f"New metadata from {args.new_metadata} loaded and validated")

      # Load and validate the existing metadata
      with open(existing_metadata_local, 'r') as f:
        existing_data = json.load(f)
        json_validator.validate_json(existing_data)
      print(f"Existing metadata from {existing_metadata_local} loaded and validated")

      # Update the metadata and validate
      updated_data = replace_builds(existing_data, args.origin, new_data, args.origin_key)
      json_validator.validate_json(updated_data)
      print("Metadata updated and validated successfully")

      # Write the updated metadata back to S3
      updated_metadata_file = f"{tempdir}/updated_metadata.json"
      with open(updated_metadata_file, 'w') as f:
        json.dump(updated_data, f, indent=2)
        f.write('\n')
      print(f"Updated metadata written to {updated_metadata_file}")

      s3.write_s3_object(args.bucket, args.key, updated_metadata_file, transaction_file)
      print("Updated metadata published successfully!")
      break # Exit the retry loop on success
    except s3.S3WriteConflict as e:
      print(f"Write conflict detected (attempt {i}/{args.max_retries}). Retrying...")
      time.sleep(random.uniform(0.25, 1.0) * (2 ** i))  # Exponential backoff
    except Exception as e:
      print(f"Error updating metadata: {e}")
      exit(1)
    finally:
      try:
        if os.path.exists(tempdir):
          shutil.rmtree(tempdir)
          print(f"Temporary directory {tempdir} removed")
      except Exception as cleanup_error:
        print(f"Error during cleanup: {cleanup_error}")
  else:
    print(f"Failed to update metadata after {args.max_retries} attempts due to repeated write conflicts.")
    exit(1)

if __name__ == "__main__":
  main()
