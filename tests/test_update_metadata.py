import shutil
from unittest.mock import patch, MagicMock
import json
import unittest
import tempfile
import os

from hashlib import sha256
import linux_dist_metadata

def make_build(distribution_version, url, hash, origin="test-origin"):
    if not hash or len(hash) != 64:
       # Create a dummy sha256 hash for testing purposes using input parameters
       hash_input = (distribution_version + url).encode('utf-8')
       hash = sha256(hash_input).hexdigest()

    return {
        "release_name": "test",
        "version": "2.0.0",
        "region": "RoW",
        "variant": "base",
        "platform": "qcm6490",
        "board": "tachyon",
        "os": "linux",
        "distribution": "test",
        "distribution_version": distribution_version,
        "url": url,
        "sha256": hash,
        "origin": origin,
        "build_date": "2024-01-01T00:00:00Z"
    }

class TestUpdateBuilds(unittest.TestCase):
  def test_update_builds(self):
      distribution_version = "24.04"
      new_builds = { 
         "builds": [
            make_build("24.04", "http://example.com/test-distribution_version-RoW-2.0.0.tar.gz", "dummyhashvalue"),
            make_build("24.04", "http://example.com/test-distribution_version-NA-2.0.0.tar.gz", "dummyhashvalue")
      ] }

      data = {
          "builds": [
              make_build("24.04", "http://example.com/test-distribution_version-1.0.0.tar.gz", "oldhashvalue2"),
              make_build("24.04", "http://example.com/test-distribution_version-1.0.0.tar.gz", "oldhashvalue2"),
              make_build("24.04", "http://example.com/test-distribution_version-1.0.10.tar.gz", "oldhashvalue2"),
              make_build("24.04", "http://example.com/test-distribution_version-1.5.0.tar.gz", "oldhashvalue2"),
              make_build("20.04", "http://example.com/old-distribution_version-1.0.0.tar.gz", "oldhashvalue"),
              make_build("20.04", "http://example.com/test-distribution_version-1.1.0.tar.gz", "oldhashvalue2")
          ]
      }
      new_data = linux_dist_metadata.update_published_metadata.replace_builds(data, distribution_version, new_builds)
      assert len(new_data["builds"]) == 4
      other_distribution_versions = [ b for b in new_data["builds"] if "distribution_version" not in b or b["distribution_version"] != distribution_version ]
      assert len(other_distribution_versions) == 2
      versions = [ b["distribution_version"] for b in new_data["builds"] ]
      assert versions == ["20.04", "20.04", "24.04", "24.04"]

class TestUpdatePublishedMetadata(unittest.TestCase):

   @patch("linux_dist_metadata.s3.read_s3_object")
   @patch("linux_dist_metadata.s3.write_s3_object")
   def test_main(self, mock_write, mock_read):
        mock_read.return_value = None
        mock_write.return_value = True

        with tempfile.TemporaryDirectory() as tempdir:
          existing_metadata_path = os.path.join(tempdir, "existing_metadata.json")
          new_metadata_path = os.path.join(tempdir, "new_metadata.json")

          existing_metadata = {
              "$schema": "https://linux-dist.particle.io/schema/release_metadata_v1.json",
              "builds": [
                  make_build("20.04", "http://example.com/old-distribution_version-1.0.0.tar.gz", "oldhashvalue"),
                  make_build("20.04", "http://example.com/test-distribution_version-1.1.0.tar.gz", "oldhashvalue2"),
                  make_build("24.04", "http://example.com/test-distribution_version-1.0.0.tar.gz", "oldhashvalue2"),
                  make_build("24.04", "http://example.com/test-distribution_version-1.0.10.tar.gz", "oldhashvalue2"),
                  make_build("24.04", "http://example.com/test-distribution_version-1.5.0.tar.gz", "oldhashvalue2")
              ]
          }
          new_metadata = { 
             "$schema": "https://linux-dist.particle.io/schema/release_metadata_v1.json",
             "builds": [
                make_build("24.04", "http://example.com/test-distribution_version-RoW-2.0.0.tar.gz", "dummyhashvalue"),
                make_build("24.04", "http://example.com/test-distribution_version-NA-2.0.0.tar.gz", "dummyhashvalue")
          ] }

          with open(existing_metadata_path, 'w') as f:
              json.dump(existing_metadata, f)
          with open(new_metadata_path, 'w') as f:
              json.dump(new_metadata, f)

          mock_read.side_effect = lambda bucket, key, dest, transaction_file: shutil.copy(existing_metadata_path, dest)

       
          with patch("argparse._sys.argv", ["update_published_metadata.py", "test-bucket", "test-key", new_metadata_path, "--origin", "test-origin"]):
            try:
                from linux_dist_metadata.update_published_metadata import main
                main()
            except SystemExit as e:
                self.assertEqual(e.code, 0)



   @patch("linux_dist_metadata.s3.read_s3_object")
   @patch("linux_dist_metadata.s3.write_s3_object")
   def test_write_conflict(self, mock_write, mock_read):
        """Simulate a write conflict and ensure the retry logic works. Expected to fail after max retries."""
        mock_read.return_value = None
        mock_write.side_effect = linux_dist_metadata.s3.S3WriteConflict()

        with tempfile.TemporaryDirectory() as tempdir:
            existing_metadata_path = os.path.join(tempdir, "existing_metadata.json")
            new_metadata_path = os.path.join(tempdir, "new_metadata.json")

            existing_metadata = {
                "$schema": "https://linux-dist.particle.io/schema/release_metadata_v1.json",
                "builds": [
                    make_build("20.04", "http://example.com/old-distribution_version-1.0.0.tar.gz", "oldhashvalue"),
                    make_build("20.04", "http://example.com/test-distribution_version-1.1.0.tar.gz", "oldhashvalue2"),
                    make_build("24.04", "http://example.com/test-distribution_version-1.0.0.tar.gz", "oldhashvalue2"),
                    make_build("24.04", "http://example.com/test-distribution_version-1.0.10.tar.gz", "oldhashvalue2"),
                    make_build("24.04", "http://example.com/test-distribution_version-1.5.0.tar.gz", "oldhashvalue2")
                ]
            }
            new_metadata = { 
                "$schema": "https://linux-dist.particle.io/schema/release_metadata_v1.json",
                "builds": [
                    make_build("24.04", "http://example.com/test-distribution_version-RoW-2.0.0.tar.gz", "dummyhashvalue"),
                    make_build("24.04", "http://example.com/test-distribution_version-NA-2.0.0.tar.gz", "dummyhashvalue")
            ] }

            with open(existing_metadata_path, 'w') as f:
                json.dump(existing_metadata, f)
            with open(new_metadata_path, 'w') as f:
                json.dump(new_metadata, f)

            mock_read.side_effect = lambda bucket, key, dest, transaction_file: shutil.copy(existing_metadata_path, dest)

        
            with patch("argparse._sys.argv", ["update_published_metadata.py", "test-bucket", "test-key", new_metadata_path, "--origin", "test-origin", "--max_retries", "2"]):
                try:
                    from linux_dist_metadata.update_published_metadata import main
                    main()
                except SystemExit as e:
                    self.assertEqual(e.code, 1)
          
