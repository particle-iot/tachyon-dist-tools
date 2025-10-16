import unittest
import os, sys
import json
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012
from jsonschema import validate, ValidationError, SchemaError, Draft202012Validator
from unittest.mock import patch, mock_open


from linux_dist_metadata import prepare_validator
from linux_dist_metadata import release


class TestImageManifest(unittest.TestCase):

 
  @patch("linux_dist_metadata.release.validate_path")
  @patch("linux_dist_metadata.release.scan_target_qcm6490")
  @patch("linux_dist_metadata.release.scan_target_syscon")
  def test_generate_manifest(self, mock_scan_target_syscon, mock_scan_target_qcm6490, mock_validate_path):
    mock_validate_path = os.path.join
    mock_scan_target_qcm6490.return_value = {
        "edl": {
          "base": "images/qcm6490/edl",
          "firehose": "prog_firehose_ddr.elf",
          "program_xml": [
            "rawprogram_unsparse0.xml",
            "rawprogram1.xml",
            "rawprogram2.xml",
            "rawprogram3.xml",
            "rawprogram4.xml",
            "rawprogram5.xml"
          ],
          "patch_xml": [
            "patch0.xml",
            "patch1.xml",
            "patch2.xml",
            "patch3.xml",
            "patch4.xml",
            "patch5.xml"
          ]
        }
      }
    mock_scan_target_syscon.return_value = {
      "binary": {
        "base": "images/syscon",
        "binary": "v0.7.16"
      }
    }

    # Accumulate written content in a list
    written_data = []

    with patch("builtins.open", mock_open()) as mock_file:
      # Mock write method to append written data to the list
      mock_file().write.side_effect = lambda data: written_data.append(data)

      release.generate_manifest(
        "tachyon-ubuntu-20.04-na-headless-99.0.99",
        "99.0.99",
        "na",
        "base",
        "tachyon",
        "ubuntu",
        "20.04",
        "ubuntu",
        [{'key': 'qcm6490', 'value': 'image-48-ff4c992de'}, {'key': 'syscon', 'value': 'v0.7.16'}, {'key': 'qcm6490_bp_fw', 'value': '1.0.5'}],
        [{'key': 'qcm6490', 'value': 'images/qcm6490/edl'}, {'key': 'syscon', 'value': 'images/syscon'}],
        "/tmp/output"
      )


      mock_file.assert_called_with("/tmp/output/manifest.json", "w")
      manifest = "".join(written_data)
      self.assertIsNotNone(manifest)
      manifest_data = json.loads(manifest)
      self.assertEqual(manifest_data["region"], "na")
      self.assertEqual(manifest_data["variant"], "base")
  
    validator = prepare_validator("image_manifest_v1.json")

    try:     
      validator.validate(json.loads(manifest))
    except (ValidationError, SchemaError) as e:
      self.fail(f"Manifest validation failed: {e}")
  
if __name__ == "__main__":
    unittest.main()
