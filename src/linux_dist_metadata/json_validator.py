import argparse
import json
import os
import sys
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012
from jsonschema import Draft202012Validator, ValidationError, SchemaError
from urllib.parse import urlparse

def prepare_validator(schema_filename):
    """
    Loads all JSON schemas from a folder, creates a registry, and returns a validator for the specified schema.

    Args:
        schema_folder (str): Path to the folder containing the JSON schema files.
        schema_filename (str): The filename of the schema to validate against.

    Returns:
        Draft202012Validator: A validator instance for the specified schema.
    """
    schema_folder = os.path.join(os.path.dirname(__file__), "schema")
    # Create an empty registry
    registry = Registry()

    # Load all schemas and add them to the registry
    for file_name in os.listdir(schema_folder):
        if file_name.endswith(".json"):
            file_path = os.path.join(schema_folder, file_name)
            with open(file_path, "r") as f:
                schema = json.load(f)
                schema_id = schema.get("$id")
                if not schema_id or not isinstance(schema_id, str):
                    raise ValueError(f"Schema {file_name} does not contain a $id field.")
                schema_resource = Resource.from_contents(contents=schema, default_specification=DRAFT202012)
                registry = registry.with_resource(uri=schema_id, resource=schema_resource)
            # print(f"Loaded schema: {schema_id}")

    # Load the main schema
    main_schema_path = os.path.join(schema_folder, schema_filename)
    with open(main_schema_path, "r") as f:
        main_schema = json.load(f)

    # Return the validator
    return Draft202012Validator(schema=main_schema, registry=registry)


def validate_json(data):
    """
    Validate a JSON object against its schema.

    Args:
        data (dict): The JSON object to validate.
        schema_folder (str): Path to the folder containing the JSON schema files.

    Raises:
        ValidationError: If the JSON data does not conform to the schema.
        SchemaError: If there is an error in the schema itself.
    """
    if "$schema" not in data:
        raise ValueError("JSON data does not contain a '$schema' field.")
    
    schema_url = urlparse(data["$schema"])
    schema_filename = os.path.basename(schema_url.path)
    validator = prepare_validator(schema_filename)
    validator.validate(data)


def main():
  parser = argparse.ArgumentParser(description="Validate a JSON file against a JSON schema.")
  parser.add_argument("json_file", type=str, help="Path to the JSON file to validate.")
  args = parser.parse_args()

  # Prepare the validator
  with open(args.json_file, "r") as f:
    data = json.load(f)
    if "$schema" not in data:
      raise ValueError("JSON file does not contain a 'schema' field.")
    try:
      schema_url = urlparse(data["$schema"])
      schema_filename = os.path.basename(schema_url.path)
      validator = prepare_validator(schema_filename)
      validator.validate(data)
      print("Validation successful!")
    except ValidationError as e:
      print(f"Validation failed: {e.message}")
      print(f"Path: {e.path}")
      sys.exit(1)
    except SchemaError as e:
      print(f"Schema error: {e.message}")
      sys.exit(1)
    except Exception as e:
      print(f"An error occurred: {e}")
      sys.exit(1)

if __name__ == "__main__":
  main()
