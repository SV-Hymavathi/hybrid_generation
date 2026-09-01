import json
import re

class USR_to_json:
    def __init__(self, input_text):
        self.input_text = input_text
        self.data = []
        self.current_sentence = {}
        self.current_tokens = []
        self.default_usr_id = "Geo_ncert_-"
        self.usr_id = self.default_usr_id
        # NO return statement here — __init__ must return None

    def parse_input_text(self):
        for line in self.input_text.strip().split('\n'):
            line = line.strip()

            if not line:
                continue

            if line.startswith("<segment_id=") or line.startswith("<sent_id="):
                self.usr_id = self.extract_usr_id(line)

            elif line.startswith("#") or line.startswith("%"):
                self.process_sentence_metadata(line)

            elif line.startswith("</segment_id>") or line.startswith("</sent_id>") or line.startswith("</id>"):
                self.finalize_sentence()

            elif line:
                try:
                    token = self.process_token_info(line)
                    if token is not None:
                        self.current_tokens.append(token)
                except (IndexError, ValueError) as e:
                    print(f"[WARNING USR_to_JSON] Skipping line due to error: {e} — line: '{line}'")
                    continue

        if self.current_sentence:
            self.finalize_sentence()

        return self.data

    def extract_usr_id(self, line):
        return line.split('=')[1].strip('>').replace('\t', ' ')

    def process_sentence_metadata(self, line):
        if line.startswith("#"):
            self.current_sentence["text"] = self.extract_sentence_text(line)
            self.current_sentence["usr_id"] = self.usr_id
        elif line.startswith("%"):
            self.current_sentence["sent_type"] = self.extract_sentence_type(line)

    def extract_sentence_text(self, line):
        return line[1:].strip().replace('\t', ' ')

    def extract_sentence_type(self, line):
        return line.strip('%')

    def finalize_sentence(self):
        # A USR block with no '%...' line leaves sent_type unset, which crashes
        # downstream coreference processing. Default it to a plain declarative.
        if "usr_id" in self.current_sentence and "sent_type" not in self.current_sentence:
            self.current_sentence["sent_type"] = "affirmative"
        self.current_sentence["tokens"] = self.current_tokens
        self.data.append(self.current_sentence)
        self.current_sentence = {}
        self.current_tokens = []
        self.usr_id = self.default_usr_id

    def process_token_info(self, line):
        token_info = re.split(r'\s+', line)

        # Must have at least 9 columns
        if len(token_info) < 9:
            print(f"[WARNING USR_to_JSON] Skipping short line: '{line}'")
            return None

        index = self.extract_token_index(token_info)
        if index is None:
            return None

        token = {}
        token["index"] = index
        token["concept"], token["tam"], token["is_combined_tam"], token["type"] = self.process_concept(token_info[0])
        token["dep_rel"], token["dep_head"] = self.process_dependency_data(token, token_info[4])
        token["constr_value"], token["constr_concept_index"] = self.process_construction(token_info[8])

        self.extract_sem_cat(token, token_info[2])
        self.process_morpho_sem(token, token_info[3])
        self.process_discourse_info(token, token_info[5])
        self.process_speaker_view_or_key_value(token, token_info[6])
        self.process_construct_info(token, token_info[8])
        self.process_special_types(token, token_info[0])

        if "cxn_construct" in token_info[8]:
            parts = token_info[8].split(':')
            if len(parts) >= 2:
                token["cxn_construct"] = parts[1]
                try:
                    token["construct_head"] = int(parts[0])
                except ValueError:
                    token["construct_head"] = "-"

        return token

    def extract_token_index(self, token_info):
        try:
            return int(token_info[1])
        except (ValueError, IndexError):
            print(f"[WARNING USR_to_JSON] Skipping line with invalid token index: '{token_info}'")
            return None

    def process_concept(self, concept):
        type = None
        if concept.startswith("$"):
            concept = concept[0:]
            type = "pron"

        if "-" in concept and not concept.startswith("[") and not concept.endswith("]"):
            concept_parts = concept.split("-", 1)
            tam = concept_parts[1] if concept_parts[1] else None
            concept_name = concept_parts[0]

            if tam:
                return concept_name, tam, True, type
            else:
                return concept_name, None, False, type
        return concept, None, False, type

    def process_construction(self, constr_info_row):
        dep_info = constr_info_row.split(':')
        constr_value = dep_info[1] if len(dep_info) > 1 else "-"
        constr_concept_index = dep_info[0]
        if constr_concept_index != "-":
            try:
                constr_concept_index = int(constr_concept_index)
            except ValueError:
                constr_concept_index = "-"
        return constr_value, constr_concept_index

    def process_dependency_data(self, token, dependency_row):
        if ':' in dependency_row:
            dep_info = dependency_row.split(':')
            dep_rel = dep_info[1] if len(dep_info) > 1 else "-"
            dep_head = dep_info[0]
            if dep_head:
                try:
                    dep_head = int(dep_head)
                except ValueError:
                    dep_head = "-"
            return dep_rel, dep_head
        else:
            return dependency_row, "-"

    def extract_sem_cat(self, token, sem_cat_row):
        if sem_cat_row != "-":
            token["sem_category"] = sem_cat_row

    def process_morpho_sem(self, token, morpho_sem_info):
        if morpho_sem_info != "-":
            token["morpho_sem"] = morpho_sem_info

    def process_discourse_info(self, token, discourse_info):
        if discourse_info != "-":
            discourse_parts = discourse_info.split(":")
            token["discourse_head"] = discourse_parts[0] if discourse_parts[0] != "-" else "-"
            token["discourse_rel"] = discourse_parts[1] if len(discourse_parts) > 1 else "-"

    def process_speaker_view_or_key_value(self, token, speaker_view_info):
        if speaker_view_info.startswith("[") and speaker_view_info.endswith("]"):
            bracket_content = speaker_view_info.strip("[]")
            if ":" in bracket_content:
                key, value = bracket_content.split(":", 1)
                token[key] = value
        else:
            if speaker_view_info != "-":
                token["speaker_view"] = speaker_view_info

    def process_construct_info(self, token, construct_info_raw):
        if len(construct_info_raw) > 1:
            construct_info = construct_info_raw.split(':')
            if construct_info[0] != "-":
                token["cxn_construct"] = construct_info[1] if len(construct_info) > 1 else "-"
                try:
                    token["construct_head"] = int(construct_info[0])
                except ValueError:
                    token["construct_head"] = "-"

    def process_special_types(self, token, concept):
        if "conj" in concept:
            token["type"] = "conjunction"
        elif "rate" in concept:
            token["type"] = "rate"
        elif "dist_meas" in concept:
            token["type"] = "distance_measurement"

    def save_to_json(self, output_file):
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=4)

    def get_json_output(self):
        return json.dumps(self.data, ensure_ascii=False, indent=4)