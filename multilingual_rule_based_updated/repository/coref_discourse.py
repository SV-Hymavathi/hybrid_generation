import json
import re
# from repository.common_v4 import *
import repository.constant

def clean(word, inplace=''):
    """
    Clean concept words by removing numbers and special characters from it using regex.
    >>> clean("kara_1-yA_1")
    'karayA'
    >>> clean("kara_1")
    'kara'
    >>> clean("padZa_1")
    'pada'
    >>> clean("caDZa_1")
    'caDa'
    """
    # Replace specific patterns
    word = word.replace('dZ', 'd').replace('jZ', 'j').replace('DZ', 'D')
    # Remove numbers and special characters
    return re.sub(r'[^a-zA-Z]+', inplace, word)

def extract_discourse_data(discourse_json, segment_id):
    print(discourse_json,'kl')
    for item in discourse_json:
        if item['usr_id'] == segment_id:
            return item['discourse_rel'], item['speaker_view'], item['discourse_head_sent_id']
    return None, None, None

def extract_discourse_values(data, segment_id):
    # Initialize a list to store discourse values and a flag for specific data
    discourse_values = []
    # #print(data)
    # Assuming 'data' is a JSON string
    data = json.loads(data)
    sp_data = ''
    # #print('nnnnnnnm')
    # Iterate through each entry in the JSON data
    for entry in data:
        # usr_sub_id = entry.get('usr_id')
        rows = entry.get('tokens', [])
        # #print(discourse_head)
        # Collect discourse values from each row
        for row in rows:
            #print(row)
            discourse_value = row.get('discourse_rel', '')
            discourse_head = row.get('discourse_head', '')
            if discourse_value:
                # #print(discourse_head)
                if segment_id == discourse_head.split('.')[0] and 'coref' not in discourse_value:
                    spkview_value = row.get('speaker_view', '')

                    # Check if specific conditions are met
                    if 'AvaSyakawApariNAma' in discourse_value and 'nahIM' in spkview_value:
                        sp_data = 'nahIM wo'
                        return discourse_value, sp_data
                    
                    # Return default values if conditions are not met
                    
                    return discourse_value, None

    # Return default values if no matching discourse value is found
    
    return None, None

def extract_spkview_values(data, segment_id, POST_PROCESS_OUTPUT):
    # Iterate through each entry in the JSON data
    data = json.loads(data)
    for entry in data:
        usr_sub_id = entry.get('usr_id')
        rows = entry.get('tokens', [])

        # Collect discourse values from each row
        for row in rows:
            discourse_value = row.get('discourse_rel', '')
            discourse_head = row.get('discourse_head', '')
            spkview_value = row.get('speaker_view', '')
            
            if discourse_value:
                # disc_value = discourse_value.split(':')[1]
                if discourse_value in repository.constant.discourse_list and spkview_value in repository.constant.spkview_list:
                    # discourse_id = discourse_value.split('.')[0]
                    if segment_id == discourse_head.split('.')[0]:
                        # Process based on spkview_value
                        if 'BI_1' in spkview_value:
                            POST_PROCESS_OUTPUT = 'nA kevala ' + POST_PROCESS_OUTPUT
                            return POST_PROCESS_OUTPUT

    # Return POST_PROCESS_OUTPUT if no conditions are met
    return POST_PROCESS_OUTPUT

def update_discourse_sentences(discourse_data, filtered_data):
    """
    Updates discourse sentences based on speaker-view data and discourse relations.

    Args:
        discourse_data (list): List of dictionaries containing discourse information.
        filtered_data (dict): Dictionary containing filtered sentences by user ID.

    Returns:
        dict: Updated filtered data with processed sentences.
    """
    updated_sentences = {}

    # Define speaker view prefixes
    speaker_view_prefixes = {
    'BI_1': 'but',
    'samAveSI': 'along with this',
    'alAvA_1': 'apart from this',
    'awirikwa': 'besides this',
    'nahIM': 'otherwise',
    'rcprop': 'as',
}
    # speaker_view_prefixes = {
    #     'BI_1': 'balki',
    #     'samAveSI': 'isake sAWa-sAWa',
    #     'alAvA_1': 'isake alAvA',
    #     'awirikwa': 'isake awirikwa',
    #     'nahIM': 'nahIM wo'
    # }

    special_discourse_rels = ['AvaSyakawApariNAma', 'vyaBicAra']

    # Process each discourse entry
    for discourse in discourse_data:
        usr_id = discourse['usr_id']
        discourse_head_sent_id = discourse['discourse_head_sent_id']
        discourse_rel = discourse['discourse_rel']
        speaker_view_data = discourse.get('speaker_view', None)

        # Determine the key to use for updated_sentences
        if discourse_rel in special_discourse_rels:
            key = discourse_head_sent_id
        else:
            key = usr_id

        # Initialize POST_PROCESS_OUTPUT with the sentence from filtered_data
        if key in filtered_data:  # Always initialize from usr_id
            sentence = filtered_data[key][0]
            POST_PROCESS_OUTPUT = sentence  # Start with the base sentence

            # Initialize updated_sentences[key] as a set for uniqueness
            if key not in updated_sentences:
                updated_sentences[key] = set()

            # Add prefix if speaker_view_data exists
            if speaker_view_data:
                for prefix_key, prefix in speaker_view_prefixes.items():
                    if prefix_key in speaker_view_data:
                        if prefix == 'balki':
                            POST_PROCESS_OUTPUT = f"{prefix} {POST_PROCESS_OUTPUT}"
                            updated_sentences[key].add(POST_PROCESS_OUTPUT)

                            prefix1 = 'nA kevala'
                            updated_sentences[discourse_head_sent_id] = set()
                            sentence = filtered_data[discourse_head_sent_id][0]
                            POST_PROCESS_OUTPUT1 = sentence  # Start with the base sentence
                            POST_PROCESS_OUTPUT1 = f"{prefix1} {POST_PROCESS_OUTPUT1}"
                            updated_sentences[discourse_head_sent_id].add(POST_PROCESS_OUTPUT1)
                        else:
                            # Before prepending, remove any equivalent marker already
                            # at the start of the sentence (avoids "also also", "but but")
                            EQUIVALENT_MARKERS = {
                                'but':             {'but', 'however', 'yet'},
                                'also':            {'also', 'moreover', 'furthermore'},
                                'along with this': {'also', 'moreover'},
                                'apart from this': {'besides', 'furthermore'},
                                'besides this':    {'besides', 'furthermore'},
                                'otherwise':       {'otherwise', 'else'},
                                'as':              {'as'},
                            }
                            sentence_words = POST_PROCESS_OUTPUT.strip().split()
                            equiv_set = EQUIVALENT_MARKERS.get(prefix, set())
                            if sentence_words and sentence_words[0].lower() in equiv_set:
                                sentence_words.pop(0)
                                POST_PROCESS_OUTPUT = ' '.join(sentence_words)

                            POST_PROCESS_OUTPUT = f"{prefix} {POST_PROCESS_OUTPUT}"
                            updated_sentences[key].add(POST_PROCESS_OUTPUT)
                        break
            else:
                # Use discourse_dict values if no speaker_view_data
                discourse_value = repository.constant.discourse_dict.get(discourse_rel, None)
                if isinstance(discourse_value, list):
                    for word in discourse_value:
                        updated_sentences[key].add(f"{word} {POST_PROCESS_OUTPUT}")
                elif discourse_value:
                    updated_sentences[key].add(f"{discourse_value} {POST_PROCESS_OUTPUT}")
                elif isinstance(POST_PROCESS_OUTPUT, str):
                    updated_sentences[key].add(f"{POST_PROCESS_OUTPUT}")


            # Handle special discourse relations
            if discourse_rel == 'vyaBicAra':
                try:
                    updated_sentences[usr_id] = set()
                    sentence = filtered_data[usr_id][0]
                    POST_PROCESS_OUTPUT = sentence
                    updated_sentences[usr_id].add(f"although {POST_PROCESS_OUTPUT}")
                except KeyError:
                    print(f"Error: usr_id {usr_id} not found in filtered_data")
                    updated_sentences[usr_id].add(f"Error: usr_id {usr_id} not found in filtered_data")
            elif discourse_rel == 'AvaSyakawApariNAma' and (speaker_view_data != 'nahIM'):
                try:
                    updated_sentences[usr_id] = set()
                    sentence = filtered_data[usr_id][0]
                    POST_PROCESS_OUTPUT = sentence
                    updated_sentences[usr_id].add(f"if {POST_PROCESS_OUTPUT}")
                except KeyError:
                    print(f"Error: usr_id {usr_id} not found in filtered_data")
                    updated_sentences[usr_id].add(f"Error: usr_id {usr_id} not found in filtered_data")


    # Update filtered_data with unique sentences from updated_sentences
    # filtered_data = {
    #     key: list(sentences) for key, sentences in updated_sentences.items()
    # }
    # print(updated_sentences)
    filtered_data = update_filtered_data(filtered_data, updated_sentences)
    # Write updated data to a file
    output_filename = 'update_discourse_sentences.txt'
    with open(output_filename, 'w', encoding='utf-8') as file:
        for key, sentences in filtered_data.items():
            file.write(f"{key}: {', '.join(sentences)}\n")

    print(f"Updated sentences have been written to {output_filename}")
    return filtered_data


def update_filtered_data(filtered_data, updated_data):
    for key in updated_data:
        # Only overwrite when the discourse step actually produced something.
        # A speaker-view/discourse tag that matches no rule leaves an empty set
        # here; without this guard it would wipe the original sentence and the
        # USR would generate no output at all.
        if key in filtered_data and updated_data[key]:
            filtered_data[key] = updated_data[key]
    return filtered_data

def add_discourse_elements(discourse_data,spkview_data,sp_data, POST_PROCESS_OUTPUT):
    if len(discourse_data) <= 0:
        return POST_PROCESS_OUTPUT
    
    if isinstance(discourse_data, list):
        for data_values in discourse_data:
            if data_values!='' and 'coref' not in data_values:
                data_values=data_values.split(':')[1]
                # for element in repository.constant.discourse_dict:
                #     if element == data_values:
                # if data_values == 'samuccaya' and spkview_data in repository.constant.spkview_list:
                if 'BI_1' in spkview_data:
                    POST_PROCESS_OUTPUT = 'balki ' + POST_PROCESS_OUTPUT
                    break
                elif 'samAveSI' in spkview_data:
                    POST_PROCESS_OUTPUT = 'isake sAWa-sAWa ' + POST_PROCESS_OUTPUT
                    break
                elif 'alAvA_1' in spkview_data:
                    POST_PROCESS_OUTPUT = 'isake alAvA ' + POST_PROCESS_OUTPUT
                    break
                elif 'awirikwa' in spkview_data:
                    POST_PROCESS_OUTPUT = 'isake awirikwa ' + POST_PROCESS_OUTPUT
                    break
                elif 'nahIM' in spkview_data:
                    POST_PROCESS_OUTPUT = 'nahIM wo ' + POST_PROCESS_OUTPUT
                    break
                
                elif data_values in repository.constant.discourse_dict and isinstance(repository.constant.discourse_dict[data_values], str):
                    POST_PROCESS_OUTPUT = repository.constant.discourse_dict[data_values] + " " + POST_PROCESS_OUTPUT
                
                elif data_values in repository.constant.discourse_dict and isinstance(repository.constant.discourse_dict[data_values], list):
                    for i, value in enumerate(repository.constant.discourse_dict[data_values]):
                        separator = '/' if i != 0 else ' '
                        # separator = '/'
                        POST_PROCESS_OUTPUT = value + separator + POST_PROCESS_OUTPUT
                if 'nA kevala/' in POST_PROCESS_OUTPUT:
                    POST_PROCESS_OUTPUT = POST_PROCESS_OUTPUT.replace('nA kevala/', '')

    else:
        # for data_values in discourse_data:
        if discourse_data:
            # discourse_data=discourse_data.split(':')[1]
            if discourse_data in repository.constant.discourse_dict:
                if 'AvaSyakawApariNAma' in discourse_data and sp_data=='nahIM wo':
                    POST_PROCESS_OUTPUT = sp_data + " " + POST_PROCESS_OUTPUT
                elif isinstance(repository.constant.discourse_dict[discourse_data], str):
                    POST_PROCESS_OUTPUT = repository.constant.discourse_dict[discourse_data] + " " + POST_PROCESS_OUTPUT
                elif isinstance(repository.constant.discourse_dict[discourse_data], list):
                    for i in range(len(repository.constant.discourse_dict[discourse_data])):
                        if i!=0:
                            POST_PROCESS_OUTPUT = repository.constant.discourse_dict[discourse_data][i]+ '/'+ POST_PROCESS_OUTPUT
                        else:
                            POST_PROCESS_OUTPUT = repository.constant.discourse_dict[discourse_data][i] + " " + POST_PROCESS_OUTPUT
    return POST_PROCESS_OUTPUT
def create_dict_with_ids(segment_id, PP_fulldata, interrogative_dict, foreign_words_dict,
                         calendar_dict, indec_dict, verb_dict, nonfinite_dict, morph_mapping, rad_dict):
    """
    Wraps all provided dictionaries with the given segment_id as key.

    Args:
        segment_id (str): ID of the current segment.
        All other args: Dictionary data for the segment.

    Returns:
        dict: Wrapped PP_fulldata with sent_id.
        dicts: Other dictionaries, each wrapped with sent_id.
    """
    # Attach sent_id to each dictionary
    PP_fulldata_dict_with_id = {segment_id: PP_fulldata}
    interrogative_dict = {segment_id: interrogative_dict}
    foreign_words_dict = {segment_id: foreign_words_dict}
    calendar_dict = {segment_id: calendar_dict}
    indec_dict = {segment_id: indec_dict}
    verb_dict = {segment_id: verb_dict}
    nonfinite_dict = {segment_id: nonfinite_dict}
    rad_dict = {segment_id: rad_dict}
    morph_mapping = {segment_id: morph_mapping}

    return (
        PP_fulldata_dict_with_id,
        interrogative_dict,
        foreign_words_dict,
        calendar_dict,
        indec_dict,
        verb_dict,
        nonfinite_dict,
        morph_mapping,
        rad_dict
    )


def update_morph_dict_coref(json_data, morph_dict):
    # Iterate through morph_dict
    for usr_id in morph_dict:
        # Check if the value is a list of tuples
        if isinstance(morph_dict[usr_id], list) and all(isinstance(item, tuple) for item in morph_dict[usr_id]):
            # Iterate through json_data for each usr_id
            for entry in json_data:
                coref_id = entry["coref_id"]
                coref_index = entry["index"]
                coref_word_sent_id = entry["coref_word_sent_id"]
                coref_word_index = int(entry["coref_word_index"])
                
                if usr_id == coref_word_sent_id:
                    # Iterate through the entries in morph_dict for the given usr_id
                    for i, (index, word, *rest) in enumerate(morph_dict[usr_id]):
                        # If the index matches coref_word_index
                        if index == coref_word_index:
                            # Check if the word has multiple tokens (e.g., "उसमें से")
                            tokens = word.split()
                            if len(tokens) > 1:
                                # Append coref_id to the first token if not already added
                                if f"({coref_id})" not in tokens[0]:
                                    k=len(tokens)
                                    tokens[k-1] = f"{tokens[k-1]}({coref_id})"
                                # Reassemble the word with the updated tokens
                                word = " ".join(tokens)
                            else:
                                # Append coref_id to the word if not already added
                                if f"({coref_id})" not in word:
                                    word = f"{word}({coref_id})"
                            # Update the morph_dict entry
                            morph_dict[usr_id][i] = (index, word, *rest)
                
                if entry["usr_id"] == usr_id:
                    # Iterate through the entries in morph_dict for the given usr_id
                    for i, (index, word, *rest) in enumerate(morph_dict[usr_id]):
                        # If the index matches coref_index
                        if index == coref_index:
                            # Check if the word has multiple tokens (e.g., "उसमें से")
                            tokens = word.split()
                            if len(tokens) > 1:
                                # Append coref_id to the first token if not already added
                                if f"({coref_id})" not in tokens[0]:
                                    tokens[0] = f"{tokens[0]}({coref_id})"
                                # Reassemble the word with the updated tokens
                                word = " ".join(tokens)
                            else:
                                # Append coref_id to the word if not already added
                                if f"({coref_id})" not in word:
                                    word = f"{word}({coref_id})"
                            # Update the morph_dict entry
                            morph_dict[usr_id][i] = (index, word, *rest)
        else:
            # Skip processing if the value is not a list of tuples
            print(f"Skipping {usr_id} as it is not a list of tuples.")
    
    return morph_dict

def transform_data(data):
    """
    Reads JSON data from a file, filters and transforms it based on the given conditions,
    and returns the transformed JSON data.
    
    :param input_file: Path to the input JSON file
    :return: Transformed JSON data
    """
    # Read data from the file
    # with open(input_file, 'r', encoding='utf-8') as file:
    #     data = json.load(file)
    
    # Initialize a list for the transformed data
    transformed_data = []
    
    # Process each entry in the data
    for entry in data:
        usr_id = entry["usr_id"]
        for token in entry["tokens"]:
            if token.get("discourse_rel") and token["discourse_rel"] != "coref":
                # Process discourse_head field
                discourse_head = token.get("discourse_head")
                if discourse_head and '.' in discourse_head:
                    discourse_head_sent_id, discourse_head_index = discourse_head.split('.')
                else:
                    discourse_head_sent_id, discourse_head_index = None, None
                
                # Create a new dictionary with the required fields
                new_entry = {
                    "usr_id": usr_id,
                    "discourse_head":discourse_head,
                    "discourse_head_sent_id": discourse_head_sent_id,
                    "discourse_head_index": discourse_head_index,
                    "discourse_rel": token.get("discourse_rel"),
                    "speaker_view": token.get("speaker_view", None)
                }
                transformed_data.append(new_entry)
    
    return transformed_data

#old version for coref
def process_coref(val, index_data,words_info,json_data,discourse_data,coref_list):
    json_data = json.loads(json_data)
    for i in range(len(discourse_data)):
        sub_coref_list=[]
        if 'coref' in discourse_data[i] and '.' in discourse_data[i]:
            # print(discourse_data[i],'discource')
            discourse_id_head = discourse_data[i].split(':')[0]
            discourse_id=discourse_data[i].split('.')[0]
            discourse_head=discourse_data[i].split('.')[1].split(':')[0]
            
            for j, sentence in enumerate(json_data):
                usr_sub_id = sentence.get('usr_id')
                tokens = sentence.get("tokens",[])
                if usr_sub_id == discourse_id:
                    for token in tokens:
                        # #print(discourse_head,'dhhh')
                        ind=token.get('index')
                        if str(ind) == discourse_head:
                            # print(token.get('morpho_sem'),'token')
                            sub_coref_list.append(index_data[i])  # Add the index data
                            concpt=token.get('concept')
                            coref_word = discourse_id_head+'_'+clean(concpt)  # Get coref word
                            sub_coref_list.append(coref_word)
                            morpho_sem = token.get('morpho_sem')
                            if morpho_sem:
                                words_info[i] = words_info[i][:3] + (morpho_sem,) + words_info[i][4:]
                            # print(words_info[i],'llll')
                            # sub_coref_list.append(morpho_sem)
                            # #print(sub_coref_list,'cpcccc')
                            break

        elif 'coref' in discourse_data[i]:  # No '.' in discourse_head, simpler case
            sub_coref_list.append(index_data[i])
            indx=int(discourse_data[i].split(':')[0])
            for processed_word in words_info:
                if processed_word[0]==indx:  # Check if indx is composed entirely of digits
                    coref_word1 = clean(processed_word[1])
                    morpho_sem = processed_word[3]
                    if morpho_sem:
                        words_info[i] = words_info[i][:3] + (morpho_sem,) + words_info[i][4:]
                    sub_coref_list.append(coref_word1)

                    break

        if sub_coref_list:  # Append to coref_list if there's any coreference info
            coref_list.append(sub_coref_list)
    # print(coref_list,'list')
    return coref_list,words_info

import json

def process_coreferences(data):
    # Dictionary to keep track of coref words and assigned IDs
    coref_dict = {}
    coref_counter = 1

    # Set to track already processed coreferences (to avoid duplicates)
    processed_coreferences = set()

    # List to store the new JSON structure
    new_json = []

    # Dictionary to store sentence_type mapped to usr_id
    sentence_type_dict = {}
    # Process each story and token
    for story in data:
        usr_id = story["usr_id"]
        sentence_type = story.get("sent_type", "affirmative")
        # Store sentence_type in the dictionary with usr_id as the key
        sentence_type_dict[usr_id] = sentence_type
        for token in story.get("tokens", []):
            if "discourse_head" in token and "discourse_rel" in token and token["discourse_rel"] == "coref":
                discourse_head = token["discourse_head"]
                token_index = token.get("index", None)
                
                # Handle case where discourse_head contains a reference to another story
                if '.' in discourse_head:
                    discourse_head_parts = discourse_head.split('.')
                    coref_word_sent_id = discourse_head_parts[0]  # First part as coref_word_sent_id
                    coref_word_index = discourse_head_parts[1]   # Second part as coref_word_index

                    # Find the coref_word and morpho_sem in the referenced story
                    coref_word = None
                    morpho_sem = None
                    for ref_story in data:
                        if ref_story["usr_id"] == coref_word_sent_id:
                            for ref_token in ref_story.get("tokens", []):
                                if ref_token["index"] == int(coref_word_index):
                                    coref_word = ref_token.get("concept")
                                    coref_word_gender = ref_token.get("sem_category")
                                    morpho_sem = ref_token.get("morpho_sem", None)
                                    break
                            break

                    # Assign or retrieve the coref_id, ensure uniqueness based on both coref_word and discourse_head
                    if coref_word:
                        coref_key = (coref_word, discourse_head)  # Key based on coref_word and discourse_head
                        if coref_key not in coref_dict:
                            coref_dict[coref_key] = coref_counter
                            coref_counter += 1

                        coref_id = coref_dict[coref_key]

                        # Check for duplicates and add the entry to new_json if it's not a duplicate
                        coref_entry_key = (usr_id, token_index, coref_id)
                        if coref_entry_key not in processed_coreferences:
                            processed_coreferences.add(coref_entry_key)

                            # Add to the new JSON structure
                            new_json.append({
                                "usr_id": usr_id,
                                "index": token_index,
                                "coref_id": coref_id,
                                "coref_word": coref_word,
                                "coref_word_gender":coref_word_gender,
                                "morpho_sem": morpho_sem,
                                "discourse_head": discourse_head,
                                "coref_word_sent_id": coref_word_sent_id,
                                "coref_word_index": coref_word_index
                            })

                else:
                    # Handle case where discourse_head is an index within the same story
                    coref_word_sent_id = usr_id  # Use usr_id as coref_word_sent_id
                    coref_word_index = discourse_head  # Use discourse_head as coref_word_index
                    coref_word = None
                    morpho_sem = None
                    for ref_token in story.get("tokens", []):
                        if ref_token["index"] == int(coref_word_index):
                            coref_word = ref_token.get("concept")
                            morpho_sem = ref_token.get("morpho_sem", None)
                            break

                    # Assign or retrieve the coref_id, ensure uniqueness based on both coref_word and discourse_head
                    if coref_word:
                        coref_key = (coref_word, discourse_head)  # Key based on coref_word and discourse_head
                        if coref_key not in coref_dict:
                            coref_dict[coref_key] = coref_counter
                            coref_counter += 1

                        coref_id = coref_dict[coref_key]

                        # Check for duplicates and add the entry to new_json if it's not a duplicate
                        coref_entry_key = (usr_id, token_index, coref_id)
                        if coref_entry_key not in processed_coreferences:
                            processed_coreferences.add(coref_entry_key)

                            # Add to the new JSON structure
                            new_json.append({
                                "usr_id": usr_id,
                                "index": token_index,
                                "coref_id": coref_id,
                                "coref_word": coref_word,
                                "morpho_sem": morpho_sem,
                                "discourse_head": discourse_head,
                                "coref_word_sent_id": coref_word_sent_id,
                                "coref_word_index": coref_word_index
                            })

    # Write the new JSON structure to a file
    with open('coreferences.json', 'w', encoding='utf-8') as outfile:
        json.dump(new_json, outfile, ensure_ascii=False, indent=4)

    return new_json, coref_dict, sentence_type_dict

# Example usage
# Load input data

# Example usage — only runs when executed directly, not on import
if __name__ == '__main__':
    with open('output.json', 'r', encoding='utf-8') as infile:
        input_data = json.load(infile)
    new_json, coref_dict, sentence_type_dict = process_coreferences(input_data)
