import json
# from repository.common_v4 import log

def process_and_write_json(data, output_file):
    """
    Processes the given JSON data and writes the formatted output to a file.

    :param data: The JSON data to process (a dictionary with a 'bulk' key holding a list of dictionaries).
    :param output_file: The name of the output file (default is "formatted_output.txt").
    """
    try:
        # If the data is a string, parse it into a dictionary
        if isinstance(data, str):
            data = json.loads(data)  # Parse the JSON string into a Python dictionary
        
        # Access the 'bulk' key from the input data
        bulk_data = data.get("bulk", [])
        
        with open(output_file, "w", encoding="utf-8") as file:
            # Iterate through each entry in the 'bulk' list
            for entry in bulk_data:
                segment_id = entry.get("segment_id", "").strip()
                text = entry.get("text", "").strip()
                # file.write(f"{segment_id}\t{text}\n")  # Write segment_id and text as tab-separated values
                file.write(f"{text}\n")
        print(f"Formatted data successfully written to {output_file}")
    except Exception as e:
        print(f"An error occurred: {e}")

