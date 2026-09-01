def rearrange_tuples(original_list):
    print("origial:",original_list)
    # Define dependencies for 4th index processing
    dependencies_4th = ['card', 'dem', 'intf', 'mod', 'ord', 'quant', 'rn', 'rs', 'r6', 'ru', 'rv', 'rmeas']
    
    # Define priority groups for ordering references
    priority_groups = [
        ['count', 'unit'],
        ['start', 'stop'],
        ["op1", "op2", "op3", "op4", "op5"],
        ['mod', 'head'],
        ['kriyamul', 'verbalizer'],
        ['count_every', 'count_value'],
        ['whole', 'part']
    ]

    # Function to extract the key from the last element of a tuple
    def extract_key(t):
        last_elem = t[-1]
        if not last_elem:
            return None
        parts = last_elem.split(':')
        if len(parts) < 2:
            return None
        return parts[1]

    # Function to determine priority of a key
    def get_key_priority(key):
        for group_idx, group in enumerate(priority_groups):
            if key in group:
                return (group_idx, group.index(key))
        return (len(priority_groups), 0)  # Lower priority for unknown keys

    # Create a new list to modify
    new_list = original_list.copy()

    # First pass: Process 4th index dependencies
    for i in reversed(range(len(new_list))):
        tup = new_list[i]
        fourth_elem = tup[4]
        if not fourth_elem:
            continue
        parts = fourth_elem.split(':')
        if len(parts) != 2:
            continue
        ref_index_str, dep_type = parts
        if dep_type not in dependencies_4th:
            continue
        ref_index = int(ref_index_str)
        ref_pos = next((j for j, t in enumerate(new_list) if t[0] == ref_index), None)
        if ref_pos is not None and i > ref_pos:
            moved_tup = new_list.pop(i)
            new_list.insert(ref_pos, moved_tup)

    # Second pass: Process bracketed tuples
    bracketed = []
    for idx, tup in enumerate(new_list):
        if tup[1].startswith('[') and tup[1].endswith(']'):
            bracketed.append((tup[0], idx))

    bracketed_sorted = sorted(bracketed, key=lambda x: -x[1])

    for bt in bracketed_sorted:
        bt_index, current_bt_pos = bt

        referring = []
        for idx, t in enumerate(new_list):
            last_elem = t[-1]
            if last_elem:
                parts = last_elem.split(':')
                if len(parts) >= 2 and parts[0] == str(bt_index):
                    referring.append((t, idx))

        # Sort by priority first, then by current index
        referring.sort(key=lambda x: (get_key_priority(extract_key(x[0])), x[1]))

        referring_indices = [idx for (t, idx) in referring]
        to_move_indices = [idx for idx in referring_indices if idx > current_bt_pos]

        # Pop elements from highest to lowest index
        moved_elements = []
        for idx in sorted(to_move_indices, reverse=True):
            moved_elements.append(new_list.pop(idx))

        # Insert in correct priority order (no reverse needed)
        if moved_elements:
            new_list[current_bt_pos:current_bt_pos] = moved_elements
    new_list = move_main_to_last(new_list)
    # Extract the list of indices after rearrangement
    index_order = [t[0] for t in new_list]
    # print(index_order,'new list')
    print("after order:",new_list)
    return index_order, new_list

def move_main_to_last(data):
    # Find the tuple with '0:main' in the 5th index (index 4)
    main_tuple = None
    for item in data:
        if item[4] == '0:main':
            main_tuple = item
            break
    
    # If found, remove it and append it to the end
    if main_tuple:
        data.remove(main_tuple)
        data.append(main_tuple)
    
    return data
import math


import math

def arrange_by_index_order(processed_words):
    result = []
    added = set()  # to track which tuples have been added (by id)

    def add_tuple(t):
        """Helper to add a tuple only once based on its id."""
        if id(t) not in added:
            result.append(t)
            added.add(id(t))

    for tup in processed_words:
        idx = tup[0]
        if isinstance(idx, int):
            # Before adding the int-tuple, add all float-tuple(s) that should come before it
            for ftup in processed_words:
                fidx = ftup[0]
                if isinstance(fidx, float) and math.floor(fidx) == idx:
                    add_tuple(ftup)
            add_tuple(tup)
        elif isinstance(idx, float):
            # Floats are handled before their floor int
            if not any(math.floor(other[0]) == math.floor(idx) and isinstance(other[0], int) for other in processed_words):
                # If no floor int exists, just add the float
                add_tuple(tup)

    return result



# def arrange_by_index_order(processed_words, index_order):
#     # Create a dictionary for quick lookup
#     word_dict = {item[0]: item for item in processed_words}
    
#     # Reorder the list based on index_order
#     ordered_words = [word_dict[idx] for idx in index_order if idx in word_dict]
    
#     return ordered_words
# # Original input data
# original = [
#     (1, 'BUna_1-o_1', '', '', '0:main', '', '', '', ''),
#     (2, 'pEna_1', '', '', '1:k2p', '', '', '', ''),
#     (3, 'badZA_1', '', '', '2:mod', '', '', '', ''),
#     (4, 'XaniyA_1', '', '', '1:k2', '', '', '', '11:op1'),
#     (5, '[meas_1]', '', '', '4:rmeas', '', '', '', ''),
#     (6, 'cutakI_1', '', '', '8:rmeas', '', '', '', '5:unit'),
#     (7, '1', '', '', '8:rmeas', '', '', '', '5:count'),
#     (8, 'karI+pawwA_1', '', '', '1:k2', '', '', '', '11:op2'),
#     (9, '[meas_2]', '', '', '8:rmeas', '', '', '', ''),
#     (10, '2', '', '', '8:rmeas', '', '', '', '9:count'),
#     (11, '[conj_1]', '', '', '1:k2', '', '', '', '')
# ]

# Get and print the rearranged list and index order
# index_order, result = rearrange_tuples(original)
# index_order, result
