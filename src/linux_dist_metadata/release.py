#python 3 app

# {
#   "$schema": "<TODO: Schema URL>",
#   "release_name": "tachyon-ubuntu-20.04-releasedev-99.99.99",
#   "version": "99.99.99",
#   "platform": "qcm6490",
#   "board": "formfactor",
#   "os": "linux",
#   "distribution": "ubuntu",
#   "distribution_version": "20.04",
#   "distribution_variant": "releasedev",
#   "sources": [
#      { "syscon": "syscon-firmware-0.7.2.bin" },
#      { "linux": "tachyon-ubuntu-20.04-pre-fcd78d162.zip" } 
#   ],
#   "targets": [
#     {
#       "qcm6490": {
#         "edl": {
#           "base": "images/qcm6490",
#           "firehose": "prog_firehose_ddr.elf",
#           "program_xml": [
#             "rawprogram_unsparse0.xml",
#             "rawprogram1.xml",
#             "rawprogram2.xml",
#             "rawprogram3.xml",
#             "rawprogram4.xml",
#             "rawprogram5.xml"
#           ],
#           "patch_xml": [
#             "patch0.xml",
#             "patch1.xml",
#             "patch2.xml",
#             "patch3.xml",
#             "patch4.xml",
#             "patch5.xml"
#           ]
#         }
#       }
#     },
#     {
#       "syscon": {
#         "binary": {
#           "base": "images/syscon",
#           "binary": "mcu-program.bin"
#         }
#       }
#     }
#   ],
#   "build_date": "2024-12-16T19:29:39.021Z"
# }

# a python app that takes in:
# - release_name
# - version
# - distribution
# - distribution_version
# - distribution_variant
# - multiple input targets that are key:value pairs of "type" and "path"
#   - a syscon folder contains the simple binary file
#   - a qcm6490 folder contains the firehose, program_xml, and patch_xml files and has special treatment
# - multiple sources that are key:value pairs that are meta data for what went into the build
# - an output folder where the release exists

# when the program runs, it goes this:
# iterates over all input targets
# for qcm6490, it does this for the EDL build:
#    - scans the input folder for rawprogram* images
#    - scans the input folder for patch* images
#    - scans the input folder for *firehose* image (just one of them)
# for syscon, it does:
#    - scans the input folder for x binary files
# the targets are created in the above json example - note patch and program xml collections

# and outputs the JSON at the top of the program into:
# - output_folder/manifest.json

import os
import json
import argparse
from datetime import datetime


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Generate a release manifest from existing folder structure.")
    parser.add_argument("--release_name", required=True, help="Name of the release.")
    parser.add_argument("--version", required=True, help="Version of the release.")
    parser.add_argument("--board", required=True, help="Which board this is for!")
    parser.add_argument("--region", default="na", help="Region of the release.")
    parser.add_argument("--variant", default="base", help="Variant of the release.")
    parser.add_argument("--distribution", required=True, help="Linux distribution (e.g., ubuntu).")
    parser.add_argument("--distribution_version", required=True, help="Linux distribution version (e.g., 20.04).")
    parser.add_argument("--distribution_variant", required=True, help="Linux distribution variant.")
    parser.add_argument("--sources", required=True, action='append', help="Source in 'key:value' format. Can be passed multiple times.")
    parser.add_argument("--targets", required=True, action='append', help="Target in 'type:path' format. Can be passed multiple times.")
    parser.add_argument("--output_folder", required=True, help="Path where the release folder exists.")
    return parser.parse_args()


def validate_path(output_folder, target_path):
    """Validate that the given path exists within the output folder."""
    full_path = os.path.join(output_folder, target_path)
    if not os.path.exists(full_path):
        raise ValueError(f"Path does not exist: {full_path}")
    return full_path


def parse_key_value_list(items, delimiter=":"):
    """Parse a list of key:value pairs."""
    result = []
    for item in items:
        if delimiter not in item:
            raise ValueError(f"Invalid format: {item}. Expected 'key{delimiter}value'.")
        key, value = item.split(delimiter, 1)
        result.append({"key": key, "value": value})
    return result


def scan_target_qcm6490(folder):
    """Scan the qcm6490 folder for specific files."""
    edl = {
        "base": "images/qcm6490/edl",
        "firehose": None,
        "program_xml": [],
        "patch_xml": []
    }
    for file in os.listdir(folder):
        if "firehose" in file and not edl["firehose"]:
            edl["firehose"] = file
        elif "rawprogram" in file:
            edl["program_xml"].append(file)
        elif "patch" in file:
            edl["patch_xml"].append(file)

    #sort "rawprogram" and "patch" arrays by the last digit in the string
    #the string is variable length. Some of the strings are "rawprogram_unsparse0.xml" and some are "rawprogram1.xml"
    #as such, we need to split at the .xml and then sort by the last digit of the left side of the split
    edl["program_xml"] = sorted(edl["program_xml"], key=lambda x: int(x.split(".xml")[0][-1]))
    edl["patch_xml"] = sorted(edl["patch_xml"], key=lambda x: int(x.split(".xml")[0][-1]))

    return {"edl": edl}


def scan_target_syscon(folder):
    """Scan the syscon folder for binary files."""
    binary_files = [file for file in os.listdir(folder) if file.endswith(".bin")]
    return {
        "binary": {
            "base": "images/syscon",
            "binary": binary_files[0] if binary_files else None
        }
    }


def generate_manifest(
    release_name,
    version,
    region,
    variant,
    board,
    distribution,
    distribution_version,
    distribution_variant,
    sources,
    targets,
    output_folder,
):
    """Generate the manifest JSON."""
    manifest = {
        "$schema": "https://linux-dist.particle.io/schema/image_manifest_v1.json",
        "release_name": release_name,
        "version": version,
        "region": region,
        "variant": variant,
        "platform": "qcm6490",
        "board": board,
        "os": "linux",
        "distribution": distribution,
        "distribution_version": distribution_version,
        "distribution_variant": distribution_variant,
        "sources": [{"key": src["key"], "value": src["value"]} for src in sources],
        "targets": [],
        "build_date": datetime.now().isoformat(),
    }

    # Scan targets and populate the manifest
    for target in targets:
        target_type, target_path = target["key"], target["value"]
        full_path = validate_path(output_folder, target_path)

        if target_type == "qcm6490":
            manifest["targets"].append({target_type: scan_target_qcm6490(full_path)})
        elif target_type == "syscon":
            manifest["targets"].append({target_type: scan_target_syscon(full_path)})
        else:
            raise ValueError(f"Unknown target type: {target_type}")

    # Write the manifest to output folder
    manifest_path = os.path.join(output_folder, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=4)
    print(f"Manifest written to {manifest_path}")


def main():
    args = parse_args()

    print("args", args)

    # Parse sources and targets
    sources = parse_key_value_list(args.sources, delimiter=":")
    targets = parse_key_value_list(args.targets, delimiter=":")

    # Print parsed sources and targets
    print("sources", sources)
    print("targets", targets)

    # Generate the manifest
    manifest = generate_manifest(
        args.release_name,
        args.version,
        args.region,
        args.variant,
        args.board,
        args.distribution,
        args.distribution_version,
        args.distribution_variant,
        sources,
        targets,
        args.output_folder
    )



if __name__ == "__main__":
    main()
  