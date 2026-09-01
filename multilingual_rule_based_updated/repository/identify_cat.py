from repository.common_v4 import *

def identify_cat(words_list,sentence_type,lang):
    '''
    Functionality: There are various categorizations of the concepts such as - nouns, pronouns etc. This function Checks word for its type to process
    accordingly and add that word to its corresponnding list.

    Parameters:
        1. words_list: It is an array of tuples. Each tuple consists of concept wise USR info.

    Returns:
        All the categorized lists of nouns, pronouns etc. with input concept tuple appended in it

    For eg.
        #jaMgala meM eka Sera WA.
        jaMgala_1, Sera_1, hE_1-past
        1,2,3
        ,anim male,
        sg,,
        3:k7p, 3:k1,0:main
        ,,
        def,,
        ,,
        affirmative

    Result -
        indeclinables = []
        pronouns = []
        nouns = [(1, 'jaMgala_1', '', 'sg', '3:k7p', '', 'def', ''), (2, 'Sera_1', 'anim male', '', '3:k1', '', '', '')]
        adjectives = []
        verbs = [(3, 'hE_1-past', '', '', '0:main', '', '', '')]
        adverbs = []
        others = []
        nominal_verbs = []
    '''
    foreign_words=[]
    indeclinables = []
    pronouns = []
    nouns = []
    verbal_adjectives = []
    adjectives = []
    verbs = []
    others = []
    adverbs = []
    nominal_verb = []
    for word_data in words_list:
        if check_foreign_words(word_data):
            log(f'{word_data[1]} identified as foreign word.')
            foreign_words.append(word_data)
        elif check_indeclinable(word_data):
            log(f'{word_data[1]} identified as indeclinable.')
            indeclinables.append(word_data)
        elif check_digit(word_data):
            log(f'{word_data[1]} identified as noun.')
            nouns.append(word_data)
        elif check_verb(word_data,sentence_type,lang):
            log(f'{word_data[1]} identified as verb.')
            verbs.append(word_data)
        elif check_adjective(word_data):
            log(f'{word_data[1]} identified as adjective.')
            adjectives.append(word_data)
        # elif check_verbal_adjective(word_data):
        #     log(f'{word_data[1]} identified as adjective.')
        #     verbal_adjectives.append(word_data)
        elif check_pronoun(word_data,lang):
            log(f'{word_data[1]} identified as pronoun.')
            pronouns.append(word_data)
        elif check_adverb(word_data):
            log(f'{word_data[1]} identified as adverb.')
            adverbs.append(word_data)
        elif check_nominal_verb(word_data):
            log(f'{word_data[1]} identified as nominal verb form.')
            nominal_verb.append(word_data)
        elif check_noun(word_data):
            log(f'{word_data[1]} identified as noun.')
            nouns.append(word_data)
        elif check_named_entity(word_data):
            log(f'{word_data[1]} identified as named entity and processed as other word.')
            others.append(word_data)
        else:
            log(f'{word_data[1]} identified as other word, but processed as noun with default GNP.')  # treating other words as noun
            nouns.append(word_data)
    return [foreign_words,indeclinables, pronouns, nouns,verbal_adjectives, adjectives, verbs, adverbs, others, nominal_verb]

def check_named_entity(word_data):
    if word_data[2] == 'ne':
        return True
    return False

def check_noun(word_data):
    '''
    Functionality:
        1. Check semantic data has place/ ne
        2. Check if GNP row has number info sg or pl

    Parameters:
        word_data: tuple of concept with all its information

    Returns:
        True - if any of the above condition is met
        False - otherwise

    For eg.     :
        #राम ने दो रोटी और दाल खायी।
        rAma,xo_1,rotI_1,xAla_1,KA_1-yA_1
        1,2,3,4,5,6
        male per,,,,
        sg,,sg,sg,
        6:k1,3:card,6:k2,6:k2,0:main
        ,,,,,
        ,,,,,
        ,,,,,
        affirmative
        conj:[3,4]

        word_data = (1, 'rAma', 'male per', 'sg', '6:k1', '', '', '')
        Result     : True (as word_data[3] == 'sg')
    '''

    try:
        # identifying nouns from sem_cat
        if word_data[2] in ('place','Place','ne','NE') and '^' not in word_data[1]:
            return True
        # GNP present for a concept
        # if 'kriyAmUla' in word_data[8]:
        #     return True
        if 'pl' == word_data[3]:
            return True
        return False
    except IndexError:
        log(f'Index Error for GNP Info. Checking noun for {word_data[1]}', 'ERROR')
        raise ValueError(f'GNP info index error for noun {word_data[1]}')

def check_pronoun(word_data,lang):
    '''
    Functionality:
        1. Check if the concept belongs to PRONOUN_TERMS list ('speaker', 'kyA', 'Apa', 'jo', 'koI' etc.)
        2. Check if dependency relation is not r6 and discourse data is coref

    Parameters:
        word_data: tuple of concept with all its information

    Returns:
        True - if any of the above condition is met
        False - otherwise

    For eg.     :
        #मैंने आज स्नान किया।
        speaker,Aja_1,snAna+kara_1-yA_1
        1,2,3
        anim male,,
        sg,,
        3:k1,3:k7t,0:main
        ,,
        ,,
        ,,
        affirmative

        word_data     : (1, 'speaker', 'anim male', 'sg', '3:k1', '', '', '')
    Result:
        True (as 'speaker' exists in PRONOUN_TERMS list)
    '''

    try:
        lang_module = importlib.import_module(f'language_rules.{lang}')

        if clean(word_data[1]) in lang_module.PRONOUN_TERMS:
            return True
        elif 'coref' in word_data[5]:
            if 'r6' not in word_data[4]: # for words like apanA
                return True
        else:
            return False
    except IndexError:
        log(f'Index Error for GNP Info. Checking pronoun for {word_data[1]}', 'ERROR')
        raise ValueError(f'GNP info index error for pronoun {word_data[1]}')

def check_adjective(word_data):
    '''
    Functionality:
        1. Check if dependency data is any of the following - 'card', 'mod', 'meas', 'ord', 'intf'
        2. Check if dependency relation is k1s and does not have GNP info
        3. Check if dependency relation is r6 and discourse data is coref

    Parameters:
        word_data: tuple of concept with all its information

    Returns:
        True - if any of the above condition is met
        False - otherwise

    For eg.     :
        #राम ने दो रोटी और दाल खायी।
        rAma,xo_1,rotI_1,xAla_1,KA_1-yA_1
        1,2,3,4,5,6
        male per,,,,
        sg,,sg,sg,
        6:k1,3:card,6:k2,6:k2,0:main
        ,,,,,
        ,,,,,
        ,,,,,
        affirmative
        conj:[3,4]

        word_data     : (2, 'xo_1', '', '', '3:card', '', '', '')
    Result:
        True (as dependency relation is card)
    '''

    # Convert the tuple to a list
    word_data_list = list(word_data)

    if word_data_list[4] != '' and ':' in word_data_list[4]:
        rel = word_data_list[4].strip().split(':')[1]
        if word_data_list[1] == "$kim":
            return False

        if rel=='mod' and (word_data_list[3]==('mawupa') or word_data_list[2]=='season'):
            return False
        if rel in repository.constant.ADJECTIVE_DEPENDENCY:
            return True
        if word_data_list[3] == '' and rel not in repository.constant.ADJECTIVE_DEPENDENCY and word_data_list[5] != '0:main':
            word_data_list[3] = 'sg'
        if rel == 'k1s' and word_data_list[3] == '': # k1s and no GNP -> adj
            return True
        # if rel == 'k1s' and word_data_list[3] in ('compermore','comperless'): 
        #     return True
        if word_data[3]=='kqwpft':
            return True
        
        # if word_data_list[5] != '':
        #     if ':' in word_data_list[5]:
        #         coref = word_data_list[5].strip().split(':')[1]
        #         if rel == 'r6' and coref == 'coref': # for words like apanA
        #             return True

    # Convert the list back to a tuple
    word_data = tuple(word_data_list)

    return False

def check_nonfinite_verb(word_data):
    '''Check if word is a non-fininte verb by the USR info'''

    if word_data[4] != '' and ':' in word_data[4]:
        rel = word_data[4].strip().split(':')[1]
        # if rel in ('rpk','rbk', 'rvks', 'rbks','rsk', 'rbplk'):
        if rel in ('rpk','rbk'):
            return True
    return False

def check_verb(word_data,sentence_type,lang):
    '''
    Functionality:
        1. Check for both finite and non-finite verbs-
            nonfinite verbs     : checked by dependency
            main verb     : identified by '-' in it
    Parameters:
        word_data: tuple of concept with all its information

    Returns:
        True - if any of the above condition is met
        False - otherwise

    For eg.     :
        #मैंने आज स्नान किया।
        speaker,Aja_1,snAna+kara_1-yA_1
        1,2,3
        anim male,,
        sg,,
        3:k1,3:k7t,0:main
        ,,
        ,,
        ,,
        affirmative

        word_data     : (3, 'snAna+kara_1-yA_1', '', '', '0:main', '', '', '')
    Result:
        True (as '-' in 'snAna+kara_1-yA_1')

    '''
    # if '-' not in word_data[1]:
    #     rword = word_data[1]
    #     if rword in extract_tamdict_hin():
    #         return True
    if '-' in word_data[1] and '[' not in word_data[1]:
        rword = word_data[1].split('-')[-1]
        # ##print(sss)
        if rword in extract_tamdict(lang):
            return True
        else:
            log(f'Verb "{rword}" not found in TAM dictionary', 'WARNING')
            return False
    elif sentence_type[1:] in repository.constant.exception_no_tam_sentence_type and word_data[4]=='0:main' and word_data[1] not in repository.constant.construction_list:
        return True
    elif word_data[4] != '' and ':' in word_data[4]:
        rel = word_data[4].strip().split(':')[1]
        if rel in ('main', 'rcelab', 'rcdelim','rcloc'):
            return True
        elif rel in repository.constant.NON_FINITE_VERB_DEPENDENCY:
            return True
    return False


def check_adverb(word_data):
    '''
    Functionality: Check for kr_vn/ krvn in dependency row.

    Parameters:
        word_data: tuple of concept with all its information

    Returns:
        True - if any of the above condition is met
        False - otherwise
    '''
    if word_data[4] != '' and ':' in word_data[4]:
        rel = word_data[4].strip().split(':')[1]
        if rel in ('kr_vn', 'krvn', 'krvnneg', 'vkvn', 'freq', 'rad', 're', 'rprop'):
            return True
    return False

def check_foreign_words(word_data):
    '''checks ^ is present infront of word 
    if it is present then it is a foreign word'''

    # if word_data[1][0]=='^' and word_data[2]=='fw':   
    if word_data[1][0]=='^':        
        return True
    else:
        return False

def check_indeclinable(word_data):
    '''
    Functionality:
        Return True as indeclinable if:
        1. the semantic info of the concept is 'unit'
        2. Check if word is in INDECLINABLE_WORDS or UNITS list in repository.constant.py

    Parameters:
        word_data: tuple of concept with all its information

    Returns:
        True - if any of the above condition is met
        False - otherwise

    For eg.:
        #मैंने आज स्नान किया।
        speaker,Aja_1,snAna+kara_1-yA_1
        1,2,3
        anim male,,
        sg,,
        3:k1,3:k7t,0:main
        ,,
        ,,
        ,,
        affirmative

        word_data = (2, 'Aja_1', '', '', '3:k7t', '', '', '')

    Result:
        True (as Aja exists in repository.constant.INDECLINABLE_WORDS)

    '''
    if word_data[2] == 'unit':
        return True
    
    if (clean(word_data[1]) in repository.constant.UNITS or 
        word_data[8] and ':' in word_data[8] and word_data[8].split(':')[1] in ('unit', 'per_unit') or 
        clean(word_data[1]) in repository.constant.INDECLINABLE_WORDS):
        return True
    return False

def check_digit(word_data):
    '''
    Functionality:
        Return True if:
        1. the concept has digits or float value

    Parameters:
        word_data: tuple of concept with all its information

    '''
    num = word_data[1]
    if '_' in num:
        num = num.strip().split('_')[0]
    if num.isdigit():
        return True
    else:
        try:
            float_value = float(num)
            return True
        except ValueError:
            return False
    return False

def check_nominal_verb(word_data):
    '''
    Functionality: Check if dependency value belongs to NOMINAL_VERB_DEPENDENCY list and there is no GNP information

    Parameters:
        word_data: tuple of concept with all its information

    Returns:
        True - if any of the above condition is met
        False - otherwise
    '''
    # if word_data[4].strip() != '':
    #     relation = word_data[4].strip().split(':')[1]
    #     gnp_info = word_data[3]
    #     if relation in repository.constant.NOMINAL_VERB_DEPENDENCY and gnp_info == '':
    #         return True
    # return False
    if word_data[4].strip() != '' and ':' in word_data[4]:
        relation = word_data[4].strip().split(':')[1]
        # gnp_info = word_data[3]
        term=clean(word_data[1])
        # ##print(word_data[3],'vkl')
        #     return False
        tags = find_tags_from_dix_as_list(term)
        # print(tags,term,'tags3')
        for tag in tags:
            if tag.get('cat') =='v' and relation in repository.constant.NOMINAL_VERB_DEPENDENCY:
                # noun_type = category = 'vn'
                return True
                    # term += 'nA'
                # log(f'{term} processed as nominal verb with index {index} gen:{gender} num:{number} person:{person} noun_type:{noun_type} case:{case} and postposition:{postposition}')
                # break
    else:
        return False

