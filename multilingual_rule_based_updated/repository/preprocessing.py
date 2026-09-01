from repository.constant import *
import repository.constant
def preprocess_id(input_text):
    """
    Preprocess the input text by replacing segment and sentence identifiers.
    """# Read a file while removing BOM

    # Manually remove BOM from a string
    clean_text = input_text.lstrip("\ufeff")

    return clean_text.replace('</segment_id>', '</id>').replace('</sent_id>', '</id>')

def process_segment(segment):
    """
    Process an individual segment to extract its details and generate output.
    """
    if not segment.strip():
        return None, None, None

    lines = segment.strip().splitlines()
    if not lines:
        return None, None, None

    segment_id_value = ""
    sentence = ""
    words, indices, entities = [], [], []
    extra_columns = [[] for _ in range(6)]

    if "<segment_id=" in lines[0] or "<sent_id=" in lines[0]:
        segment_id_value = lines[0].split('=')[1].strip('>')

    if len(lines) > 1:
        sentence = lines[1].strip()

    try:
        for line in lines[2:-1]:
            columns = line.split()
            if not columns:
                continue

            words.append(columns[0])
            indices.append(columns[1])
            entities.append(columns[2] if columns[2] != '-' else '')

            for idx in range(6):
                extra_columns[idx].append(columns[3 + idx] if len(columns) > 3 + idx and columns[3 + idx] != '-' else '')

        last_line_marker = lines[-1].strip() if lines[-1].strip() else ""

        output = [
            sentence,
            ','.join(words),
            ','.join(indices),
            ','.join(entities),
            *(','.join(col) for col in extra_columns),
            last_line_marker,
        ]

        return segment_id_value, sentence, output

    except IndexError as e:
        print(f"IndexError encountered in preprocessing: {e}")
        return None, None, "Error: Missing or incomplete data in input lines"