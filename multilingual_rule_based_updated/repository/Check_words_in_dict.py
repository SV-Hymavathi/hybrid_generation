import repository.constant
# from pradigm_nov_20.find_paradigm_mar_17 import identify_paradigm
# construction_list =['cp', 'conj','temporal', 'disjunct', 'span','meas', 'widthmeas', 'depthmeas','volumemeas','nc', 'distmeas', 'rate', 'timemeas', 'waw', 'calender', 'massmeas', 'heightmeas', 'spatial','xvanxva','compound','ne']
# category_mapping = {
#     'n': 'noun',
#     'p': 'pronoun',
#     'adj': 'adjective',
#     'v': 'verb',
#     'adv': 'adverb',
#     'indec': 'indeclinable',
#     # Add more mappings as needed
# }
# global_starred_words ={}
import requests
from repository.common_v4 import log

def check_words_in_dict(words, processed_words, global_starred_words):
    """
    Check if each word in the list is present in a .txt file.
    If a word starts with '#', remove '#', check if the word is present in the file, 
    then replace '#' with '*' if not found, or leave as is if found.
    Also, store the word along with its descriptive category in the global list.
    Finally, send global_starred_words to the API and return its response.
    """
    words = words.split(' ')
    file_path = "repository/extracted_words.txt"
    processed_concepts = []
    has_star = False

    # Create a dictionary for word categories from `processed_words`
    word_categories = {entry[1]: entry[2] for entry in processed_words if len(entry) > 2}

    # Load the .txt file into a set for fast lookups
    with open(file_path, 'r', encoding='utf-8') as file:
        file_words = set(file.read().splitlines())

    for word in words:
        original_word = word
        word_to_check = word[1:] if word.startswith('#') else word

        # Check if the word is in the loaded set
        if word_to_check not in file_words:
            if original_word.startswith('#') and word_to_check not in repository.constant.construction_list:
                starred_word = f"*{word_to_check}"
                has_star = True
                processed_concepts.append(starred_word)
                
                # Map the category to its descriptive form
                category = word_categories.get(word_to_check, "unknown")
                descriptive_category = repository.constant.category_mapping.get(category, "unknown")
                
                # Add to global dictionary
                global_starred_words[starred_word.replace('*', '')] = descriptive_category
            elif original_word.startswith('#'):
                word_to_check = word_to_check.replace('#','')
                processed_concepts.append(word_to_check)
            else:
                processed_concepts.append(word_to_check)
        else:
            processed_concepts.append(original_word)
    return processed_concepts,global_starred_words, has_star

def identify_words_in_corpus(global_starred_words,processed_concepts,lang):
    if lang != "hi":
        return 
    log(f"Hitting PARADIGM API...")
    # Modify global_starred_words to match API input format
    api_input = {"words_with_categories": global_starred_words}
    
    # Send modified global_starred_words to the API
    api_url = "http://10.4.16.167:6010/get_paradigm"
    try:
        response = requests.post(api_url, json=api_input)
        response_data = response.json()  # Parse the JSON response
    except requests.exceptions.RequestException as e:
        response_data = {"error": str(e)}
    # processed_concepts, replaced_indices = replace_starred_words(processed_concepts, response_data)
    response_data, replaced_indices, updated_concepts = replace_starred_words(processed_concepts, response_data)
    # new_sent = transform_data(response_data, replaced_indices, updated_concepts)
    log(f"After hitting paradigm api : {response_data} ")
    return updated_concepts, response_data, replaced_indices

def replace_starred_words(processed_concepts, response_data):
    """
    Replace starred words (*word) in processed_concepts with their corresponding values 
    from response_data based on specific rules. Also, track the indices of replaced words.
    After replacement, re-add the '*' to the replaced word.

    Args:
        processed_concepts (list): List of words/concepts, some of which may be starred (*word).
        response_data (dict): Dictionary containing mappings for words to their replacements.

    Returns:
        tuple: A tuple containing:
            - updated_concepts (list): Updated list of concepts with starred words replaced.
            - replaced_indices (dict): A dictionary mapping indices of replaced words to their new values.
    """
    updated_concepts = []
    replaced_indices = {}  # To store indices of replaced words and their new values

    for index, word in enumerate(processed_concepts):
        if word.startswith('*'):  # Check if the word is starred
            original_word = word[1:]  # Remove the '*' to get the base word
            if original_word in response_data:  # Check if the word exists in response_data
                replacement = response_data[original_word][0]  # Get the first element of the list
                
                if '/' in replacement:  # If '/' is present in the replacement
                    base_word, suffix = replacement.split('/', 1)  # Split into base_word and suffix
                    descriptive_part = suffix.split('__')[0]  # Extract the part before '__'
                    new_word = base_word + descriptive_part  # Combine base_word and descriptive_part
                else:
                    new_word = replacement.split('__')[0]  # Take the part before '__'

                # Add the '*' back to the replaced word
                # new_word_with_star = f"*{new_word}"
                
                updated_concepts.append(new_word)  # Add the new word to the updated list
                replaced_indices[index] = new_word  # Track the index and the new word
            else:
                updated_concepts.append(word)  # If word not found in response_data, keep it as is
        else:
            updated_concepts.append(word)  # Non-starred words remain unchanged
    
    # new_sent = new_sent.split()
    return response_data, replaced_indices, updated_concepts

def transform_data_star(response_data, replaced_indices, output_sentence):
    """
    Transforms the given response_data and replaced_indices into a structured dictionary,
    and modifies the output sentence based on the processed data.

    Args:
        response_data (dict): A dictionary with one or more key-value pairs.
        replaced_indices (dict): A dictionary mapping indices to replacement words.
        output_sentence (str): The original sentence to transform.

    Returns:
        str: The transformed sentence.
    """
    try:
        print(response_data,replaced_indices)
        # Step 1: Validate inputs
        if not isinstance(response_data, dict) or not isinstance(replaced_indices, dict):
            raise ValueError("Both response_data and replaced_indices must be dictionaries.")
        
        if not output_sentence:
            raise ValueError("output_sentence cannot be empty.")

        # Ensure response_data and replaced_indices have the same number of entries
        if len(response_data) != len(replaced_indices):
            raise ValueError("response_data and replaced_indices must have the same number of entries.")

        # Step 2: Process each star_word and its corresponding index-word pair
        for (star_word, paradigm), (index_in_sentence, new_word) in zip(response_data.items(), replaced_indices.items()):
            # Ensure paradigm has the expected structure
            if not isinstance(paradigm, list) or len(paradigm) < 1:
                raise ValueError(f"Paradigm for '{star_word}' is invalid.")
            
            paradigm_pattern = paradigm[0]  # Extract the pattern string from the paradigm

            # Call transform_sentence for the current star_word and index-word pair
            transformed_sentence = transform_sentence(
                output=output_sentence,  # Corrected parameter name
                transformed_data={
                    "star_word": star_word,
                    "paradigm": paradigm,
                    "index_in_sentence": index_in_sentence,
                    "new_word": new_word
                }
            )
            
            # Update the output_sentence with the transformed result
            output_sentence = transformed_sentence
        output_sentence = ' '.join(output_sentence)
        log(f'transform_data_star output : {output_sentence}')
        return output_sentence

    except Exception as e:
        return f"Error in transform_data: {str(e)}"


def transform_sentence(output, transformed_data):
    """
    Transforms a sentence by modifying the star_word based on the paradigm and replacing
    the word at the specified index in the output sentence.

    Args:
        output (str): The original sentence to transform.
        transformed_data (dict): The dictionary containing transformation details.

    Returns:
        str: The transformed sentence.
    """
    try:
        # Extract components from transformed_data
        star_word = transformed_data["star_word"]
        paradigm = transformed_data["paradigm"]
        index_in_sentence = transformed_data["index_in_sentence"]
        new_word = transformed_data["new_word"]

        # Step 1: Process the paradigm
        paradigm_pattern = paradigm[0]  # Extract the pattern string from the paradigm
        
        # Ensure the paradigm contains a '/'
        if '/' not in paradigm_pattern:
            raise ValueError("Paradigm pattern must contain a '/'")
        
        before_slash, after_slash = paradigm_pattern.split('/')
        
        # Ensure the after_slash contains '__'
        if '__' not in after_slash:
            raise ValueError("After-slash part of paradigm must contain '__'")
        
        char_to_remove = after_slash.split('__')[0]  # Get the character to remove

        # Step 2: Modify the star_word
        # Remove char_to_remove ONLY if it appears at the end of the star_word
        if star_word.endswith(char_to_remove):
            modified_star_word = star_word[:-len(char_to_remove)]  # Remove the last len(char_to_remove) characters
        else:
            modified_star_word = star_word  # No change if char_to_remove is not at the end

        # Step 3: Process the target word at index_in_sentence
        words = output.split()  # Split the output into a list of words

        # Ensure index_in_sentence is within bounds
        if index_in_sentence >= len(words):
            raise IndexError("Index out of range in the output sentence")

        target_word = words[index_in_sentence]  # Extract the word at the specified index

        # Split the target word into parts based on '/'
        parts = target_word.replace('#','').split('/')

        # Transform each part
        transformed_parts = []
        for part in parts:
            # Remove the prefix (before_slash) from the part
            remaining_suffix = part.replace(before_slash, '')
            # Construct the transformed part
            transformed_part = f"{modified_star_word}{remaining_suffix}"
            transformed_parts.append(transformed_part)

        # Join the transformed parts back together with '/'
        transformed_word = '/'.join(transformed_parts)

        # Replace the word at index_in_sentence with the transformed word
        words[index_in_sentence] = transformed_word
        transformed_output = ' '.join(words)  # Join the words back into a sentence

        return transformed_output.split()

    except Exception as e:
        return f"Error in transform_sentence: {str(e)}"
    

# if __name__ == "__main__":
#     # Example Input
#     response_data = {
#         'Anwarika': ['wIn/a__adj', 0, 2],
#         'saMkenxrIya': ['wIn/a__adj', 1, 1],
#         'mEMtala': ['calaciwr/a__n', 1, 1],
#         'sWalamaMdala': ['Karc/a__n', 1, 2]
        
#     }
#     replaced_indices = {
#         1: 'wIna',
#         5: 'wIna',
#         9: 'calaciwra',
#         10: 'Karca'
#     }
#     output_sentence = 'pqWvI #wIna BAga 3 ##pramuKa #wIna ##parawa hE kroda calaciwra Karca'

#     # Transform the sentence
#     result = transform_data(response_data, replaced_indices, output_sentence)
#     print(result)
# # Example Usage
# processed_concepts = ['*meMtala', '#UparI', 'BAga', 'XarAwala', '#Osawana', '100', 'kilomItara', 'gaharAI', 'Tosa', 'hE', 'span', 'depthmeas']
# response_data = {'meMtala': ['BIda/a__n', 0, 4]}

# updated_concepts = replace_starred_words(processed_concepts, response_data)
# print(updated_concepts)