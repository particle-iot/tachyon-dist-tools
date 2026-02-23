import json
import os
import random
import shutil
import tempfile
import time
from argparse import ArgumentParser

from tachyon_dist_tools import update_builds
from tachyon_dist_tools import json_validator
from tachyon_dist_tools import s3_updater

def main():
  ap = ArgumentParser()
  ap.add_argument("bucket", help="S3 bucket name")
  ap.add_argument("key", help="S3 object key")
  ap.add_argument("new_metadata", help="Path to the JSON file containing new builds to replace or add")
  ap.add_argument("--origin_key", default="distribution_version", help="Key to match for replacing builds")
  ap.add_argument("--origin", help="Value of the origin_key to match for replacing builds")
  ap.add_argument("--max_retries", type=int, default=10, help="Maximum number of retries on write conflict")
  args = ap.parse_args()

  schema_folder = json_validator.get_default_schema_folder()

  for i in range(args.max_retries):
    try:
      tempdir = tempfile.mkdtemp()
      # Download the existing metadata
      existing_metadata_local = f"{tempdir}/existing_metadata.json"
      transaction_file = f"{tempdir}/s3_transaction.json"
      s3_updater.read_s3_object(args.bucket, args.key, existing_metadata_local, transaction_file)
      print(f"Existing metadata downloaded to {existing_metadata_local}")

      # Load and validate the new metadata
      with open(args.new_metadata, 'r') as f:
        new_data = json.load(f)
        json_validator.validate_json(new_data, schema_folder)
      print(f"New metadata from {args.new_metadata} loaded and validated")

      # Load and validate the existing metadata
      with open(existing_metadata_local, 'r') as f:
        existing_data = json.load(f)
        json_validator.validate_json(existing_data, schema_folder)
      print(f"Existing metadata from {existing_metadata_local} loaded and validated")

      # Update the metadata and validate
      updated_data = update_builds.replace_builds(existing_data, args.origin, new_data, args.origin_key)
      json_validator.validate_json(updated_data, schema_folder)
      print("Metadata updated and validated successfully")

      # Write the updated metadata back to S3
      updated_metadata_file = f"{tempdir}/updated_metadata.json"
      with open(updated_metadata_file, 'w') as f:
        json.dump(updated_data, f, indent=2)
        f.write('\n')
      print(f"Updated metadata written to {updated_metadata_file}")

      s3_updater.write_s3_object(args.bucket, args.key, updated_metadata_file, transaction_file)
      print("Updated metadata published successfully!")
      break # Exit the retry loop on success
    except s3_updater.S3WriteConflict as e:
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
