import argparse
import json


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

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("existing_metadata", help="Path to the existing metadata file")
    ap.add_argument("updated_metadata", help="Path to the JSON file containing new builds to add")
    ap.add_argument("--origin_key", default="distribution_version", help="Key to match for replacing builds")
    ap.add_argument("--origin", help="Value of the origin_key to match for replacing builds")
    ap.add_argument("--dry-run", action="store_true", help="If set, do not write changes to the existing metadata file, just print the updated content")
    args = ap.parse_args()

    try:
        with open(args.updated_metadata, 'r') as f:
            update_info = json.load(f)

        new_builds = update_info.get("builds", [])

        for build in new_builds:
            if args.origin_key not in build:
                build[args.origin_key] = args.origin

        with open(args.existing_metadata, 'r') as f:
            existing_data = json.load(f)

        updated_data = replace_builds(existing_data, args.origin, new_builds, args.origin_key)

        if args.dry_run:
            print(json.dumps(updated_data, indent=2))
        else:
            with open(args.existing_metadata, 'w') as f:
                json.dump(updated_data, f, indent=2)
                f.write('\n')

    except Exception as e:
        print(f"Error updating release metadata: {e}")
        exit(1)
