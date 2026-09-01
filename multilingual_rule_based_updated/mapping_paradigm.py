import re

def parse_file(file_path):
    """
    Parses a file to extract mappings from words to their replacements, including 
    the character after the '/' if present.
    
    Args:
        file_path (str): The path to the file containing word mappings.
    
    Returns:
        dict: A dictionary where keys are replaced words and values are new words.
    """
    mappings = {}
    with open(file_path, 'r', encoding='utf-8') as file:
        for line in file:
            if ":" in line:  # Ensure it's a valid mapping line
                word, replacement = line.split(":", 1)  # Split into at most two parts
                replacement_parts = replacement.split("/")  # Split at the first '/'
                base_word = replacement_parts[0].strip()  # Word before '/'
                
                # Safely handle cases where there's no '/' or no part after '/'
                suffix = ""
                if len(replacement_parts) > 1 and replacement_parts[1]:
                    suffix = replacement_parts[1].split("_")[0]  # Extract portion before '_'
                
                mappings[word.strip()] = base_word + suffix  # Concatenate base word and suffix
    return mappings


def update_list_with_index(input_list, mappings):
    """
    Updates a list of strings by replacing words found in the mappings and 
    stores replaced words with their index in a dictionary.

    Args:
        input_list (list of str): The list of strings to update.
        mappings (dict): A dictionary of word mappings (replaced word : new word).

    Returns:
        tuple: A tuple containing the updated list and a dictionary of replaced words with their indices.
    """
    updated_list = []
    replaced_words_with_index = {}  # Dictionary to store replaced words with indices
    
    for idx, item in enumerate(input_list):
        for replaced_word, new_word in mappings.items():
            if replaced_word in item:
                item = re.sub(fr'\b{replaced_word}\b', new_word, item)  # Replace word with its mapping
                replaced_words_with_index[(idx, replaced_word)] = new_word  # Store index and word pair
        updated_list.append(item)
    return updated_list, replaced_words_with_index

def replace_words_in_sentence_with_index(sentence, replaced_words_with_index):
    """
    Replaces words in a sentence using the replaced_words_with_index dictionary, 
    appending extra characters if the word partially matches a key in the dictionary.

    Args:
        sentence (str): The input sentence to process.
        replaced_words_with_index (dict): A dictionary where keys are tuples of (index, replaced_word)
                                          and values are new words.

    Returns:
        str: The updated sentence with words replaced as per the dictionary.
    """
    def find_replacement(word, index):
        # Check if the exact word at the specific index matches
        key = (index, word)
        if key in replaced_words_with_index:
            return replaced_words_with_index[key]
        
        # Check for partial matches
        for (idx, replaced_word), new_word in replaced_words_with_index.items():
            if idx == index and word.startswith(new_word):
                extra_chars = word[len(new_word):]
                return replaced_word + extra_chars
        
        # Return the word unchanged if no match is found
        return word
    
    words = sentence.split()  # Split sentence into words
    updated_words = [find_replacement(word, idx) for idx, word in enumerate(words)]  # Replace words with index tracking
    return " ".join(updated_words)  # Join words back into a sentence

# Example usage
# if __name__ == "__main__":
#     # Example mappings
#     mappings = {
#         "Karca": "vAyumaNdala",
#         "viBin": "viBinna",
#         "par": "parawa"
#     }
    
#     # Example input list
#     list1 = [
#         '^yaha<cat:p><case:d><parsarg:0><gen:m><num:s><per:a>$',
#         '^Karca<cat:n><case:d><gen:m><num:s>$',
#         '^Karca<cat:n><case:o><gen:f><num:p>$',
#         '^viBin<cat:adj><case:o><gen:f><num:p>$',
#     ]
    
#     # Update the list using mappings
#     updated_list, replaced_words_with_index = update_list_with_index(list1, mappings)
#     print("Updated List:")
#     print(updated_list)
#     print("\nReplaced Words with Index:")
#     print(replaced_words_with_index)
    
#     # Example sentence
#     sentence = "Karca Karcana viBin"
#     updated_sentence = replace_words_in_sentence_with_index(sentence, replaced_words_with_index)
#     print("\nOriginal Sentence:")
#     print(sentence)
#     print("Updated Sentence:")
#     print(updated_sentence)
