import unittest
import os
import json
from jsonschema import ValidationError

from tachyon_dist_tools.json_validator import (
    validate_json,
    prepare_validator,
    get_default_schema_folder,
)


class TestGetDefaultSchemaFolder(unittest.TestCase):
    def test_returns_valid_path(self):
        """Test that get_default_schema_folder returns a path containing schema files."""
        schema_folder = get_default_schema_folder()
        self.assertTrue(os.path.isdir(schema_folder), f"Schema folder does not exist: {schema_folder}")

        # Check that schema files are present
        expected_files = ["release_metadata_v1.json", "image_manifest_v1.json", "build_metadata_v1.json"]
        for filename in expected_files:
            filepath = os.path.join(schema_folder, filename)
            self.assertTrue(os.path.isfile(filepath), f"Expected schema file not found: {filepath}")


class TestPrepareValidator(unittest.TestCase):
    def test_prepare_validator_returns_validator(self):
        """Test that prepare_validator returns a working validator."""
        schema_folder = get_default_schema_folder()
        validator = prepare_validator(schema_folder, "build_metadata_v1.json")
        self.assertIsNotNone(validator)

    def test_prepare_validator_invalid_schema(self):
        """Test that prepare_validator raises on missing schema file."""
        schema_folder = get_default_schema_folder()
        with self.assertRaises(FileNotFoundError):
            prepare_validator(schema_folder, "nonexistent_schema.json")


class TestValidateJson(unittest.TestCase):
    def _make_valid_build(self):
        return {
            "release_name": "tachyon-ubuntu-20.04-na-headless-1.0.0",
            "version": "1.0.0",
            "region": "NA",
            "variant": "headless",
            "platform": "qcm6490",
            "board": "formfactor_dvt",
            "os": "linux",
            "distribution": "ubuntu",
            "distribution_version": "20.04",
            "build_date": "2024-12-16T19:29:39.021Z",
        }

    def test_validate_valid_release_metadata(self):
        """Test that valid release metadata passes validation."""
        data = {
            "$schema": "https://linux-dist.particle.io/schema/release_metadata_v1.json",
            "builds": [
                {
                    **self._make_valid_build(),
                    "artifacts": [
                        {
                            "artifact_url": "https://example.com/release.zip",
                            "sha256_checksum": "abc123",
                            "type": "release_image",
                        }
                    ],
                }
            ],
        }
        # Should not raise
        validate_json(data)

    def test_validate_valid_build_metadata(self):
        """Test that valid build metadata passes validation."""
        data = {
            "$schema": "https://linux-dist.particle.io/schema/build_metadata_v1.json",
            **self._make_valid_build(),
        }
        validate_json(data)

    def test_validate_missing_schema_field(self):
        """Test that missing $schema field raises ValueError."""
        data = {"builds": []}
        with self.assertRaises(ValueError) as context:
            validate_json(data)
        self.assertIn("$schema", str(context.exception))

    def test_validate_invalid_data(self):
        """Test that invalid data raises ValidationError."""
        data = {
            "$schema": "https://linux-dist.particle.io/schema/build_metadata_v1.json",
            # Missing required fields
        }
        with self.assertRaises(ValidationError):
            validate_json(data)

    def test_validate_with_explicit_schema_folder(self):
        """Test that passing an explicit schema_folder works."""
        schema_folder = get_default_schema_folder()
        data = {
            "$schema": "https://linux-dist.particle.io/schema/build_metadata_v1.json",
            **self._make_valid_build(),
        }
        # Should not raise
        validate_json(data, schema_folder)


if __name__ == "__main__":
    unittest.main()
