import json
import argparse

def convert_format(input_filename, output_filename):
    # Load the original log_rnp.json data
    with open(input_filename, 'r', encoding='utf-8') as infile:
        data = json.load(infile)

    brazil_data = []

    # Process each timestamp entry
    for entry in data:
        # Extract only the satellites list, ignoring the "time" key
        satellites = entry.get("satellites", [])
        brazil_data.append(satellites)

    # Save to the new satellites_brazil.json file format
    with open(output_filename, 'w', encoding='utf-8') as outfile:
        # Using a more compact representation to mimic the dense array format
        json.dump(brazil_data, outfile, separators=(', ', ': '))
        
    print(f"Successfully converted data. Saved to {output_filename}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="json log converter")

    parser.add_argument("--input_log", required=True)
    parser.add_argument("--output", required=True)

    args = parser.parse_args()
    
    convert_format(args.input_log, args.output)