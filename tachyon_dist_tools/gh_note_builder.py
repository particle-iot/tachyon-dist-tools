import json
import sys
import argparse

# Convert release metadata JSON to Markdown
def json_to_markdown(json_obj):
    builds = json_obj["builds"]
    images = {}
    for build in builds:
        region = build["region"]
        if region not in images:
            images[region] = []
        images[region].append(build)
    markdown_output = "## Images"

    for region, builds in images.items():
        markdown_output += f"\n\n### {region}"
        for build in builds:
            for artifact in build["artifacts"]:
                markdown_output += f"\n- {build['board']} {build['variant']} - {artifact['type']} [{build['release_name']}]({artifact['artifact_url']})"

    return markdown_output

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Convert JSON file to nested Markdown list.")
    parser.add_argument("input_file", type=str, help="Path to the input JSON file")
    parser.add_argument("-o", "--output", type=str, help="Path to save the Markdown output file (optional)")

    args = parser.parse_args()

    # Read the JSON file
    try:
        with open(args.input_file, "r") as file:
            data = json.load(file)
    except Exception as e:
        print(f"Error reading JSON file: {e}")
        sys.exit(1)

    # Convert JSON to Markdown
    markdown_output = json_to_markdown(data)

    # Save or print the output
    if args.output:
        try:
            with open(args.output, "w") as file:
                file.write(markdown_output)
            print(f"Markdown output saved to {args.output}")
        except Exception as e:
            print(f"Error writing to output file: {e}")
            sys.exit(1)
    else:
        print(markdown_output)

if __name__ == "__main__":
    main()
