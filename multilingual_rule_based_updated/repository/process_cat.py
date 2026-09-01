from repository.common_v4 import *
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate
from postposition import get_matching_word_from_sheet
import json
import pandas as pd
print(pd.__version__)
import requests
from io import StringIO
import csv

# Set by process_all_cat when verb generation fails for the current sentence, so
# the caller can emit a marker chunk instead of dropping the whole sentence.
LAST_VERB_FAILED = False
LAST_VERB_FAIL_REASON = ''

def process_all_cat(categorized_words_list,index_data,gnp_data,seman_data,depend_data,spkview_data,sentence_type,words_info,k1_not_need,has_changes,lang):

    # foreign_words_data,indeclinables_data, pronouns_data, nouns_data,verbal_adjectives, adjectives_data, verbs_data, adverbs_data, others_data, nominal_forms_data = identify_cat(
    #         words_info,sentence_type)
    foreign_words_data,indeclinables_data, pronouns_data, nouns_data,verbal_adjectives, adjectives_data, verbs_data, adverbs_data, others_data, nominal_forms_data = categorized_words_list
    
    processed_foreign_words = process_foreign_word(index_data,foreign_words_data,words_info,verbs_data,lang)
    processed_indeclinables = process_indeclinables(indeclinables_data)
    processed_nouns = process_nouns(index_data,seman_data,nouns_data, words_info, verbs_data,lang)
    # #print(processed_nouns)
    processed_pronouns = process_pronouns(index_data,pronouns_data, processed_nouns, processed_indeclinables, words_info, verbs_data,lang)
    processed_others = process_others(others_data)
    process_nominal_form = process_nominal_verb(index_data,nominal_forms_data, processed_nouns, words_info, verbs_data,lang)
    # Verb processing can fail (e.g. unresolved TAM, missing k1 subject). Instead
    # of aborting the whole sentence, drop only the verb and flag it, so the rest
    # of the chunks (subject, objects, obliques) are still produced.
    global LAST_VERB_FAILED, LAST_VERB_FAIL_REASON
    LAST_VERB_FAILED = False
    LAST_VERB_FAIL_REASON = ''
    try:
        processed_verbs, processed_auxverbs ,verb_dict,nonfinite_dict = process_verbs(verbs_data, seman_data, gnp_data, depend_data, sentence_type, spkview_data,processed_nouns, processed_pronouns,index_data, words_info,k1_not_need,lang, False)
    except Exception as _verb_err:
        log(f'verb processing failed; dropping verb only: {_verb_err}', 'WARN')
        processed_verbs, processed_auxverbs, verb_dict, nonfinite_dict = [], [], {}, {}
        LAST_VERB_FAILED = True
        LAST_VERB_FAIL_REASON = str(_verb_err).splitlines()[-1][:120] if str(_verb_err).strip() else type(_verb_err).__name__
    # processed_adjectives = process_verbal_adjective(verbal_adjectives,processed_nouns, words_info, verbs_data)
    processed_adjectives = process_adjectives(adjectives_data,gnp_data,index_data, processed_nouns, processed_verbs)
    process_adverbs(adverbs_data, processed_nouns, processed_verbs, processed_others,lang, reprocessing=False)
    postposition_finalization(processed_nouns, processed_pronouns,processed_foreign_words, words_info,lang)
    # Every word is collected into one and sorted by index number.
    processed_words = collect_processed_data(index_data,processed_foreign_words,processed_pronouns,processed_nouns,processed_adjectives,
                                                processed_verbs, processed_auxverbs,processed_indeclinables, processed_others)
    
    log(f'processed_words:{processed_words}')
    return processed_foreign_words,processed_indeclinables,processed_nouns,processed_pronouns,processed_others,process_nominal_form,processed_verbs, processed_auxverbs,processed_adjectives,processed_words,verb_dict,nonfinite_dict


def process_change(rules_info,categorized_words_list,words_info,processed_nouns,processed_pronouns,processed_others,processed_foreign_words,processed_indeclinables, k1_not_need,lang):

    (src_sentence, root_words, index_data, seman_data, gnp_data, depend_data, 
 discourse_data, spkview_data, scope_data, construction_data, sentence_type) = rules_info
    index_data = [int(x) for x in index_data]
    foreign_words_data,indeclinables_data, pronouns_data, nouns_data,verbal_adjectives, adjectives_data, verbs_data, adverbs_data, others_data, nominal_forms_data = categorized_words_list
    
    global LAST_VERB_FAILED, LAST_VERB_FAIL_REASON
    try:
        processed_verbs, processed_auxverbs,verb_dict,nonfinite_dict = process_verbs(verbs_data, seman_data, gnp_data, depend_data, sentence_type, spkview_data, processed_nouns, processed_pronouns,index_data, words_info, k1_not_need,lang,reprocess=True)
    except Exception as _verb_err:
        log(f'verb reprocessing failed; dropping verb only: {_verb_err}', 'WARN')
        processed_verbs, processed_auxverbs, verb_dict, nonfinite_dict = [], [], {}, {}
        LAST_VERB_FAILED = True
        LAST_VERB_FAIL_REASON = str(_verb_err).splitlines()[-1][:120] if str(_verb_err).strip() else type(_verb_err).__name__
    processed_adjectives = process_adjectives(adjectives_data,gnp_data,index_data, processed_nouns, processed_verbs)
    process_adverbs(adverbs_data, processed_nouns, processed_verbs, processed_others,lang, reprocessing=True)
    processed_words = collect_processed_data(index_data,processed_foreign_words,processed_pronouns, processed_nouns,  processed_adjectives, processed_verbs,processed_auxverbs,processed_indeclinables,processed_others)
    return processed_words,verb_dict,nonfinite_dict


# def check_main_verb(depend_data):
    # flag=False
    # for dep in list(depend_data):
    #     if dep:
    #         dep1=dep.strip().split(':')[1]
    #         if dep1== 'main' or dep1=='rcelab' or dep1=='rcdelim':
    #             flag=True
    #             break
    # if flag==False:
    #     return(log('USR error. Main verb not identified. Check the USR.'))
        # sys.exit()
def get_main_verb(relation_head, verbs_data, flag, main_verb):
    """
    Process construction data based on relation_head and verbs_data.
    
    Parameters:
        relation_head (str): The head of the relation being processed.
        verbs_data (list): A list of verbs data, each represented as a list.
        flag (bool): A flag indicating if a matching verb has been found.
        main_verb (list): The main verb object to be updated.
    
    Returns:
        tuple: Updated main_verb and flag.
    """
    # Iterate through the verbs data
    for verb in verbs_data:
        # Check if the verbalizer matches the relation head
        # verbalizer_match = f"{relation_head}:verbalizer" == verb[8]
        if 'verbalizer' in verb[8] and verb[4] == '0:main':
            main_verb = verb
            flag = True
            break
        elif verb[4] == '0:main':
            main_verb = verb

        # Check if the relation_head matches verb[0] (as an integer)
        # elif int(relation_head) == verb[0]:
        #     main_verb = verb
        #     break
        # else:
        #     main_verb = verb
    
    # If no match is found, return the original main_verb and flag
    return main_verb, flag

def convert_to_devanagari(text):
    # Convert English text to Devanagari script
    devanagari_text = transliterate(text, sanscript.ITRANS, sanscript.DEVANAGARI)
    return devanagari_text

def process_foreign_word(index_data,foreign_words_data,words_info,verbs_data,lang):
    # for verb in verbs_data:
    #    if len(verb[4]) > 0 and verb[4].strip().split(':')[1] == 'main' or verb[4].strip().split(':')[1] == 'rcelab' or verb[4].strip().split(':')[1] == 'rcdelim':
    #         main_verb = verb
    #         break
    processed_foreign_words=[]
    flag=False
    for i,foreign_word in enumerate(foreign_words_data):
        index=foreign_word[0]
        gender, number, person, case = get_default_GNP()
        category='n'
        type=''
        main_verb = ''
        foreign_list = list(foreign_word)
        # for main verb
        relation_head = foreign_word[4].strip().split(':')[0]
        relation = (foreign_word[4].strip().split(':')[1] if ':' in foreign_word[4] else '')
        # if int(relation_head) in index_data and relation=='k1':
        main_verb,flag=get_main_verb(relation_head,verbs_data,flag,main_verb)
        # for verb in verbs_data:
        #     # if len(verb[4]) > 0 and verb[4].strip().split(':')[1] == 'main' or verb[4].strip().split(':')[1] == 'rcelab' or verb[4].strip().split(':')[1] == 'rcdelim':
        #     v = relation_head + ':verbalizer'
        #     if v == verb[8]:
        #         # id = construction_data.index(v)
        #         main_verb=verb
        #         break
        #     elif int(relation_head)==verb[0]:
        #         main_verb=verb
        #         break
        # else:
        #     main_verb=verb
        if lang == "en":
            # A multi-component NE arrives as 'A+B+C'. cleans() would turn the
            # '+' into '-' and then strip it, gluing the parts into one token
            # ('Siva+ballaBapura' -> 'SivaballaBapura'). Keep the components as
            # separate words so they transliterate/translate individually.
            foreign_list[1] = cleans(foreign_list[1], inplace=' ').strip()
            foreign_list[1] = ' '.join(foreign_list[1].split())
        else:
            foreign_list[1] = foreign_list[1].replace('^','')
            # if '_' in foreign_list[1]:
            foreign_list[1]=clean(foreign_list[1])
            foreign_list[1]=convert_to_devanagari(foreign_list[1])
        # foreign_list[1]=convert_to_hindi(foreign_list[1])
        foreign_word = tuple(foreign_list)
        case,postposition = preprocess_postposition_new('noun', foreign_word, words_info, main_verb,index_data,lang)
        # if flag:
        #     del processed_postpositions_dict[float(index)]
        processed_foreign_words.append((index,foreign_word[1],category,case,gender,number,person,type,postposition,relation_head,relation))
        
    return processed_foreign_words

def process_nominal_verb(index_data,nominal_verbs_data, processed_noun, words_info, verbs_data,lang):

   nominal_verbs = []
   flag=False
#    for verb in verbs_data:
#        if len(verb[4]) > 0 and verb[4].strip().split(':')[1] == 'main' or verb[4].strip().split(':')[1] == 'rcelab' or verb[4].strip().split(':')[1] == 'rcdelim':
#             main_verb = verb
#             break
    
   for nominal_verb in nominal_verbs_data:
        index = nominal_verb[0]
        term = clean(nominal_verb[1])
        gender = 'm'
        number = 's'
        person = 'a'
        # category = 'n'
        noun_type = 'common'
        case = 'o'
        postposition = ''
        main_verb=''

        log_msg = f'{term} identified as nominal, re-identified as other word and processed as common noun with index {index} gen:{gender} num:{number} person:{person} noun_type:{noun_type} case:{case} and postposition:{postposition}'

        relation = ''
        if nominal_verb[4] != '':
            relation = (nominal_verb[4].strip().split(':')[1] if ':' in nominal_verb[4] else '')

        relation_head = nominal_verb[4].strip().split(':')[0]
        # relation = nominal_verb[4].strip().split(':')[1]
        # if int(relation_head) in index_data and relation=='k1':
        main_verb,flag = get_main_verb(relation_head,verbs_data,flag,main_verb)

        case, postposition = preprocess_postposition_new('noun', nominal_verb, words_info, main_verb, index_data,lang)
        # ##print(processed_postpositions_dict,index,flag,'klllll')
        # if flag:
        #     del processed_postpositions_dict[float(index)]
        # tags = find_tags_from_dix_as_list(term)
        # for tag in tags:
        #     if (tag[0] == 'cat' and tag[1] == 'v'):
        noun_type = 'vn'
        category='vn'
        if relation in ('k2', 'rt', 'rh','rblpk','rblak','rblsk'):
            term = term + 'nA'
            log_msg = f'{term} processed as nominal verb with index {index} gen:{gender} num:{number} person:{person} noun_type:{noun_type} case:{case} and postposition:{postposition}'
            noun = (index, term, category, case, gender, number, person, noun_type, postposition)
            processed_noun.append(noun)
            log(log_msg)
            # break
        elif relation in ('k1'):
            case='d'
            term = term + 'nA'
            log_msg = f'{term} processed as nominal verb with index {index} gen:{gender} num:{number} person:{person} noun_type:{noun_type} case:{case} and postposition:{postposition}'
            noun = (index, term, category, case, gender, number, person, noun_type, postposition)
            processed_noun.append(noun)
            log(log_msg)
            # break
        else:
            noun = (index, term, category, case, gender, number, person, noun_type, postposition)
            processed_noun.append(noun)
        # nominal_verbs.append(noun)
        
   return processed_noun

def process_adverb_as_noun(concept, processed_nouns):
    index, term, *_ = concept
    case = 'd' if ('+se_') not in term else 'o'
    term = clean(term.split('+')[0])
    category, gender, number, person, noun_type, postposition = 'n', 'm', 'p', 'a', 'abstract', 'se'
    processed_postpositions_dict[index] = postposition
    noun = (index, term, category, case, gender, number, person, noun_type, postposition)
    processed_nouns.append(noun)
    log(f' Adverb {term} processed as an abstract noun with index {index} gen:{gender} num:{number} case:{case},noun_type:{noun_type} and postposition:{postposition}')
    return

def process_adverb_as_verb(concept, processed_verbs):
    index, term, *_ = concept
    term = clean(term)
    gender, number, person, category, type, case = 'm', 's', 'a', 'v', 'adverb', 'd'
    # tags = find_tags_from_dix_as_list(term)
    # # ##print(tags,'tags5')
    # for tag in tags:
    #     if tag['cat']== 'v':
    tam = 'kara'
    adverb = (index, term, category, gender, number, person, tam, case, type)
    processed_verbs.append(adverb)
    log(f'{term} adverb processed as a verb with index {index} gen:{gender} num:{number} person:{person}, and tam:{tam}')
    return

def process_adverbs(adverbs, processed_nouns, processed_verbs, processed_indeclinables, lang,reprocessing):
    for adverb in adverbs:
        term = clean(adverb[1])
        relation = (adverb[4].strip().split(':')[1] if ':' in adverb[4] else '')
        relation_head = adverb[4].strip().split(':')[0]

        if lang == 'en':
            new_entry = (adverb[0], term, 'adv',relation_head, relation)
            if new_entry not in processed_indeclinables:
                processed_indeclinables.append(new_entry)
                log(f'adverb {adverb[1]} processed as English adverb')
            continue

        # Hindi logic
        tags = find_tags_from_dix_as_list(term, lang='hi')
        for tag in tags:
            if tag.get('cat') == 'v':  # verb
                return process_adverb_as_verb(adverb, processed_verbs)
            elif tag.get('cat') == 'adj':  # adjective
                term += 'rUpa_se'
                new_entry = (adverb[0], term, 'indec')
                if new_entry not in processed_indeclinables:
                    processed_indeclinables.append(new_entry)
                    log(f'adverb {adverb[1]} processed as indeclinable (from adj) with form {term}')
                return

        # If not verb/adj
        for processed in processed_indeclinables:
            if term == processed[1]:
                log(f'adverb {adverb[1]} already processed as indeclinable, no further processing')
                return
        processed_indeclinables.append((adverb[0], term, 'indec'))
        log(f'adverb {adverb[1]} processed as indeclinable with form {term}')


def process_indeclinables(indeclinables):
    '''
    Functionality:
        1. They do not require any furthur processing
        2. Make a tuple with - index, term, type(indec)

    Parameters:
        indeclinables: List of indeclinable data

    Returns:
        list of tuples.

    for eg.     :
        indeclinables: [(2, 'Aja_1', '', '', '3:k7t', '', '', '')]

    Result:
       processed_indeclinables: [(2, 'Aja', 'indec')]
    '''

   
    processed_indeclinables = []
    for indec in indeclinables:
        clean_indec = clean(indec[1])

        if 'unit' in indec[-1]:
            add_unit = "unit"
            if indec[4] != "":
                relation_head= indec[4].strip().split(':')[0]
                relation = (indec[4].strip().split(':')[1] if ':' in indec[4] else '')
            elif 'unit' in indec[-1]:
                relation_head = indec[-1].strip().split(':')[0]
                relation = indec[-1].strip().split(':')[1]
            processed_indeclinables.append((indec[0], clean_indec, 'indec', add_unit, relation_head, relation))
        else:
            processed_indeclinables.append((indec[0], clean_indec, 'indec'))

    return processed_indeclinables


def process_nouns(index_data,seman_data,nouns, words_info, verbs_data,lang):
    '''
    Functionality:
        1. Make a noun tuple
        2. We update update_additional_words_dict(index, 'before', 'eka'), if number == 's' and noun[6] == 'some'

    Parameters:
        1. nouns - List of noun data
        2. words_info - List of USR info word wise
        3. verbs_data - List of verbs data

    Returns:
        processed_nouns = List of noun tuples where each tuple looks like - (index, word, category, case, gender, number, proper/noun type= proper, common, NC, nominal_verb, CP_noun or digit, postposition)

    For eg.:
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

        nouns     : [(1, 'rAma', 'male per', 'sg', '6:k1', '', '', ''), (3, 'rotI_1', '', 'sg', '6:k2', '', '', ''), (4, 'xAla_1', '', 'sg', '6:k2', '', '', '')]
        words_info     : [(1, 'rAma', 'male per', 'sg', '6:k1', '', '', ''), (2, 'xo_1', '', '', '3:card', '', '', ''), (3, 'rotI_1', '', 'sg', '6:k2', '', '', ''), (4, 'xAla_1', '', 'sg', '6:k2', '', '', ''), (5, 'KA_1-yA_1', '', '', '0:main', '', '', '')]
        verbs_data     : [(5, 'KA_1-yA_1', '', '', '0:main', '', '', '')]

    Result:
        processed_nouns     : [(1, 'rAma', 'n', 'o', 'm', 's', 'a', 'proper', 'ne'), (3, 'rotI', 'n', 'd', 'f', 's', 'a', 'common', None), (4, 'xAla', 'n', 'd', 'f', 's', 'a', 'common', None)]
    '''

    processed_nouns = []
    main_verb = ''
    flag=False
    # for verb in verbs_data:
    #     if len(verb[4]) > 0 and verb[4].strip().split(':')[1] == 'main' or verb[4].strip().split(':')[1] == 'rcelab' or verb[4].strip().split(':')[1] == 'rcdelim':
    #         main_verb = verb
    #         ##print(main_verb,'vbb')
            # break
    # if not len(main_verb):
    #     log('USR error. Main verb not identified. Check the USR.')
    #     sys.exit()
        # return None
    dates_mapping = {
                '1': 'st', '2': 'nd', '3': 'rd', '4': 'th', '5': 'th', '6': 'th', '7': 'th', '8': 'th',
                '9': 'th', '10': 'th', '11': 'th', '12': 'th', '13': 'th', '14': 'th', '15': 'th',
                '16': 'th', '17': 'th', '18': 'th', '19': 'th', '20': 'th', '21': 'st', '22': 'nd',
                '23': 'rd', '24': 'th', '25': 'th', '26': 'th', '27': 'th', '28': 'th', '29': 'th',
                '30': 'th', '31': 'st'
            }

    for noun in nouns:
        category = 'n'
        index = noun[0]
        # dependency = noun[4].strip().split(':')[1]
        gender, number, person = extract_gnp_noun(noun)
        # ##print(noun)
        relation = relation_head = ''
        if noun[4] not in [""]: #for not removed empty
            relation_head = noun[4].strip().split(':')[0]
            relation = (noun[4].strip().split(':')[1] if ':' in noun[4] else '')
        # if int(relation_head) in index_data and relation=='k1':
        
        main_verb,flag = get_main_verb(relation_head,verbs_data,flag,main_verb)
        

        if noun[6] == 'respect': # respect for nouns
            number = 'p'
        noun_type = 'common' if '_' in noun[1] else 'proper'

        # if 'kriyAmUla' in noun[8]:
        if clean(noun[8]) in ('start','end','whole','mod','count','avayavI'):
            case='d'
            postposition=None
        else:
            case, postposition = preprocess_postposition_new('noun', noun, words_info, main_verb, index_data,lang)

        if '+' in noun[1]:
            processed_nouns = handle_compound_nouns(noun, processed_nouns, category, case, gender, number, person, postposition)

        else:
            term = noun[1]
            if check_is_digit(term):
                if '_' in term:
                    clean_noun = term.strip().split('_')[0]
                else:
                    clean_noun = term
                noun_type = 'digit'
            else:
              
                clean_noun = clean(noun[1])

            if 'era' == noun[2] and lang == "hi":
                clean_noun = clean_noun.replace('00','')
                clean_noun=clean_noun +'_vIM_saxI'
            
            # print(seman_data)
            # print(noun[2],'iiii')
            # if 'mod' in noun[8]:
            #     postposition=None
            #     processed_postpositions_dict[index] = postposition
            #     case='d'

            if any(condition for condition in [
                ('era' in seman_data and noun[2] in ('dom', 'moy', 'yoc')),
                ('yoc' in seman_data and noun[2] in ('dom', 'moy')),
                ('moy' in seman_data and noun[2] == 'dom')
            ]) and lang=="hi":
                postposition = None
                processed_postpositions_dict[index] = postposition
                case = 'd'
            elif all(item not in seman_data for item in ('era', 'moy', 'yoc')) and noun[2] == 'dom' and lang == 'hi':
                clean_noun = clean_noun+ '_wArIKa'
            if noun[2]=='clocktime' and lang=='hi':
                clean_noun = clean_noun + '_baje'
            

            elif noun[2] in ('dom', 'moy' ,'yoc') and lang == 'en':

                day_str = str(clean_noun).lstrip('0')  # remove leading zeros, if any
                mapped_value = dates_mapping.get(day_str, '')
                clean_noun = clean_noun + mapped_value

            elif noun[2] in ('era') and lang == "en":
                era_str = str(clean_noun)
               
                if era_str.endswith("00"):
                    era_str = era_str[:-2]  # remove last two zeros
                    
                    mapped_value = dates_mapping.get(era_str, '')  
                    clean_noun = era_str + mapped_value +""+ "century"



            if noun[2]=='clocktime' and lang=='en':
                clean_noun = clean_noun + "o'clock"
            
            #removing the peposition if concept is constructiojn
            # if clean(noun[1]) in repository.constant.construction_list:
            #     postposition=None
            #     if index in processed_postpositions_dict:
            #         del processed_postpositions_dict[index]
                
            processed_nouns.append((noun[0], clean_noun, category, case, gender, number, person, noun_type, postposition,relation_head,relation))
        log(f'{noun[1]} processed as noun with case:{case} gen:{gender} num:{number} noun_type:{noun_type} postposition: {postposition} relation_head:{relation_head} realtion:{relation}.')
    return processed_nouns

def process_pronouns(index_data, pronouns, processed_nouns, processed_indeclinables, words_info, verbs_data, lang):
    import importlib
    import json

    lang_module = importlib.import_module(f'language_rules.{lang}')
    sheet_url = "hindi_pronoun - Sheet1.csv"

    processed_pronouns = []
    flag = False

    for pronoun in pronouns:
        # Guard: ensure pronoun tuple has enough elements
        if len(pronoun) < 7:
            log(f'Skipping pronoun {pronoun} — insufficient fields ({len(pronoun)} < 7)', 'WARNING')
            continue

        index = pronoun[0]
        main_verb = ''
        term = clean(pronoun[1])
        animvalue = pronoun[2]
        gnp = pronoun[3]
        check_coref = 'coref' in pronoun[5] if len(pronoun) > 5 and pronoun[5] else False

        # Safe relation extraction
        if len(pronoun) > 4 and pronoun[4] and ':' in str(pronoun[4]):
            relation_head = pronoun[4].strip().split(':')[0]
            relation = (pronoun[4].strip().split(':')[1] if ':' in pronoun[4] else '')
        else:
            relation_head = ''
            relation = '-'

        spkview_data = pronoun[6] if len(pronoun) > 6 else '-'
        main_verb, flag = get_main_verb(relation_head, verbs_data, flag, main_verb)

        if is_kim(term):
            gender, number, person, case = get_default_GNP()
            processed_pronouns, processed_indeclinables = process_kim(index, index_data, relation, animvalue, gnp, case,
                                                                       pronoun, words_info, main_verb,
                                                                       processed_pronouns, processed_indeclinables,
                                                                       processed_nouns, lang)
        elif is_yax(term):
            gender, number, person, case = get_default_GNP()
            processed_pronouns, processed_indeclinables = process_yax(index, index_data, relation, animvalue, gnp, case,
                                                                       pronoun, words_info, main_verb,
                                                                       processed_pronouns, processed_indeclinables,
                                                                       processed_nouns, lang)
        else:
            category = 'p'
            case = 'o'
            parsarg = 0
            fnum = None
            gender, number, person = extract_gnp(pronoun)

            # ── Infer animacy for $wyax r6 from head noun ──
            if term in ['wyax', 'apanA'] and relation == 'r6' and animvalue in ['-', '', None]:
                for wi in words_info:
                    if str(wi[0]) == str(relation_head):
                        wi_seman = str(wi[2]) if len(wi) > 2 else ''
                        if any(a in wi_seman for a in ['anim', 'per', 'male', 'female']):
                            animvalue = 'anim'
                        else:
                            animvalue = 'null'
                        break
                # Also check processed_nouns
                if animvalue in ['-', '', None]:
                    for pn in processed_nouns:
                        if str(pn[0]) == str(relation_head):
                            pn_seman = str(pn[2]) if len(pn) > 2 else ''
                            if any(a in pn_seman for a in ['anim', 'per', 'male', 'female']):
                                animvalue = 'anim'
                            else:
                                animvalue = 'null'
                            break

            if relation == "r6":
                fnoun = int(relation_head) if relation_head and relation_head.isdigit() else None
                if fnoun is not None:
                    fnoun_data = getDataByIndex(fnoun, processed_nouns, index=0)
                    if fnoun_data:
                        # Do NOT overwrite explicit gender for apanA
                        if term != 'apanA':
                            gender = fnoun_data[4]

                        fnum = fnoun_data[5]
                        case = fnoun_data[3]

                if term == 'apanA':
                    parsarg = '0'

            if check_coref and lang == 'en':
                with open("coreferences.json", "r", encoding="utf-8") as f:
                    coref_entries = json.load(f)
                for entry in coref_entries:
                    coref_word = entry.get("coref_word")
                    coref_word_gender = entry.get("coref_word_gender")
                    morpho_sem = entry.get("morpho_sem")
                    gender = 'f' if coref_word_gender == "female" else 'm'
                    person = 'u' if coref_word == 'speaker' else 'm' if coref_word == 'addressee' else 'a'
                    number = 'p' if morpho_sem == "pl" else 's'
                    if coref_word_gender and coref_word_gender in "anim":
                        animvalue = 'anim'
                    elif coref_word_gender and coref_word_gender in ["male/per", "male", "female/per", "per"]:
                        animvalue = 'per'
                    else:
                        animvalue = 'null'

            case, postposition = preprocess_postposition_new('pronoun', pronoun, words_info, main_verb, index_data, lang)
            if postposition != '':
                parsarg = postposition

            # ── Fix case for subject pronouns ──
            # k1/pk1 = subject → use 'subj' so morph_gen picks subject form (I not me)
            if relation in ('k1', 'pk1'):
                case = 'subj'

            if relation == 'dem' and spkview_data in ['proximal', 'distal']:
                fnoun = int(relation_head) if relation_head and relation_head.isdigit() else None
                if fnoun is not None:
                    fnoun_data = getDataByIndex(fnoun, processed_nouns, index=0)
                    if fnoun_data:
                        case = fnoun_data[3]
                        if spkview_data == 'distal':
                            number = fnoun_data[5]

            if relation == "k7p":
                gender = "0"
                person = "0"
                number = "0"
                animvalue = "null"
            if relation == "k5":
                gender = "0"
                person = "0"
                number = "0"
                animvalue = "null"

            # ── Direct word override — bypass sheet for known cases ──
            # This ensures correct pronoun regardless of sheet lookup result
            if lang == 'en':
                if term == 'speaker':
                    if relation in ('k1', 'pk1'):
                        word = 'we' if number == 'p' else 'I'
                    elif relation in ('k2', 'k4', 'k4a', 'jk1'):
                        word = 'us' if number == 'p' else 'me'
                    elif relation == 'r6':
                        word = 'our' if number == 'p' else 'my'
                    else:
                        word = get_matching_word_from_sheet(term, number, gender, person, animvalue, spkview_data, relation, sheet_url)

                elif term in ['wyax', 'apanA'] and relation == 'r6':
                    # his / her / its for the possessive. An explicit male/female
                    # marking (which may sit in the gender OR the animacy/semcat
                    # slot) implies a personal possessor -> his/her. Only fall back
                    # to 'its' when the referent is plural-neutral or genuinely
                    # inanimate/unspecified.
                    av = str(animvalue).lower()
                    inanimate = av in ['null', 'nonanim', 'inanim', 'nonan']
                    # Honorific/respect plural: 'pl' is grammatical (Hindi honorific),
                    # not semantic — use singular pronoun in English
                    is_respect_plural = number == 'p' and 'respect' in str(spkview_data)
                    if number == 'p' and not is_respect_plural:
                        word = 'their'
                    elif (gender in ['f', 'female'] or 'female' in av) and not inanimate:
                        word = 'her'
                    elif (gender in ['m', 'male'] or ('male' in av and 'female' not in av)) and not inanimate:
                        word = 'his'
                    else:
                        word = 'its'

                else:
                    word = get_matching_word_from_sheet(term, number, gender, person, animvalue, spkview_data, relation, sheet_url)
            else:
                word = get_matching_word_from_sheet(term, number, gender, person, animvalue, spkview_data, relation, sheet_url)

            POSSESSIVE_PRONOUNS = {'its', 'his', 'her', 'their', 'my', 'our', 'your', 'whose'}
            if word in POSSESSIVE_PRONOUNS:
                parsarg = 'pos'
                if pronoun[0] in processed_postpositions_dict:
                    processed_postpositions_dict[pronoun[0]] = None

            processed_pronouns.append((index, word, category, case, gender, number, person, parsarg, fnum, relation_head, relation))

    return processed_pronouns





def process_others(other_words):
    '''Process other words. Right now being processed as noun with default gnp'''
    processed_others = []
    for word in other_words:
        gender = 'm'
        number = 's'
        person = 'a'
        processed_others.append((word[0], clean(word[1]), 'other', gender, number, person))
    return processed_others

def process_verbs(verbs_data, seman_data, gnp_data, depend_data, sentence_type, spkview_data, 
                  processed_nouns, processed_pronouns, index_data, words_info, 
                  k1_not_need, lang, reprocess=False):
    '''
    Functionality:
        1. In the list of verbs data, identify
            a) if it is complex predicate - it is appended in processed_nouns
            b) if verb_type == 'nonfinite': - process the concept and append in processed_verbs
            c) otherwise process main verb and auxiliary verbs and append in respective lists
    Parameters:
         verbs_data: List of verbs data
         seman_data: Semantic data row of USR
         depend_data: Dependency data row of USR
         sentence_type: Sentence type
         spkview_data: Speaker's view data row of USR
         processed_nouns: List of processed_nouns
         processed_pronouns: List of processed_pronouns
         index_data: Index information from USR
         words_info: List of USR info word-wise
         k1_not_need: Boolean indicating if k1 is required
         lang: Language identifier
         reprocess: Boolean; for first-time processing, it is False. In case of reprocessing, it is True.
    Returns:
        List of processed_verbs and processed_auxverbs
    '''
    processed_verbs = []
    processed_auxverbs = []
    verb_dict={}
    nonfinite_dict={}

    for concept_data in verbs_data:
        concept = Concept(index=concept_data[0], term=concept_data[1], dependency=concept_data[4])
        verb_type = identify_verb_type(concept)
        

        if verb_type == 'nonfinite':
            verb,nonfinite_dict = process_nonfinite_verb(
                concept, seman_data, gnp_data, depend_data, sentence_type, 
                processed_nouns, processed_pronouns, index_data, words_info, k1_not_need
            )
            processed_verbs.append(to_tuple(verb))
            if nonfinite_dict:
                old_key, old_value = next(iter(nonfinite_dict.items()))  # get first key-value pair

                # Build new key and tuple
                new_key = old_key + 0.3
                new_tuple = (
                    f'{new_key}',
                    old_value if isinstance(old_value, str) else old_value[1],
                    'v', 'm', 's', 'a', None, 'o', 'nf'
                )

            # Replace verb_dict with only the new entry
                nonfinite_dict = {new_key: new_tuple}

        else:
            main_verbs,verb_dict ,aux_verbs= process_verb(
                concept, seman_data, gnp_data, depend_data, sentence_type, 
                spkview_data, processed_nouns, processed_pronouns, index_data, 
                k1_not_need, lang ,reprocess
            )

            # Ensure both main_verbs and aux_verbs are iterable
            if isinstance(main_verbs, list):
                for verb in main_verbs:
                    if verb:
                        processed_verbs.append(to_tuple(verb))
            elif main_verbs:
                processed_verbs.append(to_tuple(main_verbs))

            if isinstance(aux_verbs, list):
                for aux in aux_verbs:
                    if aux:
                        processed_auxverbs.append(to_tuple(aux))
            elif aux_verbs:
                processed_auxverbs.append(to_tuple(aux_verbs))

    return processed_verbs, processed_auxverbs ,verb_dict , nonfinite_dict


def process_auxiliary_verbs(verb: Verb, index_data, concept, spkview_data, sentence_type, lang) -> [Verb]:
    concept_term = concept.term
    concept_index = concept.index
    HAS_SHADE_DATA = False
    auxiliary_term_tam = []
    auxiliary_verb_terms = ''

    # Check for shade data
    for i, data in enumerate(spkview_data):
        if data and 'shade' in data and concept_index == index_data[i]:
            term = clean(data.split(':')[1])
            tam = identify_default_tam_for_main_verb(concept_term)
            HAS_SHADE_DATA = True
            break

    # if HAS_SHADE_DATA:
    #     if term == 'jA' and tam == 'yA':
    #         tam = 'yA1'   # to generate gayA from jA-yA
    #     auxiliary_term_tam.append((term, tam))
    #     verb = set_main_verb_tam_zero(verb)

    # Identify auxiliary verb terms
    if sentence_type[1:] not in ("fragment", "title", "heading", "term") and '-' in concept_term:
        auxiliary_verb_terms = identify_auxiliary_verb_terms(concept_term)

    # Special passive case handling
    if (len(auxiliary_verb_terms) > 2 and 'pass' in sentence_type and
        auxiliary_verb_terms[1] not in repository.constant.aux_exception_case):
        combined = auxiliary_verb_terms[0] + auxiliary_verb_terms[1]
        auxiliary_verb_terms = [combined] + auxiliary_verb_terms[2:]

    # Clear any previous aux
    auxiliary_term_tam = []
    failed = False

    try:
        for v in auxiliary_verb_terms:
            aux_results = auxmap(v, lang)  # ✅ This now returns a list
            if not aux_results:
                failed = True
                break
            for (term, root, tam) in aux_results:
                auxiliary_term_tam.append((root, tam))
    except Exception as e:
        failed = True

    # Try combined if any failed
    if failed:
        auxiliary_term_tam = []
        full_combined = "_".join(auxiliary_verb_terms)
        combos_to_try = [full_combined]

        if len(auxiliary_verb_terms) >= 2:
            combos_to_try += [
                "_".join(auxiliary_verb_terms[:2]),
                "_".join(auxiliary_verb_terms[1:])
            ]

        for combo in combos_to_try:
            try:
                aux_results = auxmap(combo, lang)
                if aux_results:
                    for (term, root, tam) in aux_results:
                        auxiliary_term_tam.append((root, tam))
                    failed = False
                    break
            except Exception as e:
                log(f"Error in auxiliary mapping for: {combo}, error: {e}")

        if failed:
            log(f"All auxiliary combinations failed: {combos_to_try}")
            auxiliary_term_tam = []

    # Final assembly of auxiliary verbs
    return [
        create_auxiliary_verb(index, term, tam, verb)
        for index, (term, tam) in enumerate(auxiliary_term_tam)
    ]

def process_dep_rbks(concept, words_info, processed_nouns, processed_pronouns):
    finalData = []
    k1_exists, k1_index = find_match_with_same_head(concept.index, 'k1', words_info, index=4)
    k3_exists, k3_index = find_match_with_same_head(concept.index, 'k3', words_info, index=4)
    if k1_exists:
        case = 'o'
        ppost = 'ke xvArA'

        for i in range(len(processed_nouns)):
            data = processed_nouns[i]
            data_index = data[0]
            if data_index == k1_index:
                temp = list(data)
                temp[3] = case
                temp[8] = ppost
                processed_nouns[i] = tuple(temp)
                update_ppost_dict(data_index, ppost)

    elif k3_exists:
        case = 'o'
        ppost = 'ke xvArA'

        for i in range(len(processed_nouns)):
            data = processed_nouns[i]
            data_index = data[0]
            if data_index == k3_index:
                temp = list(data)
                temp[3] = case
                temp[8] = ppost
                processed_nouns[i] = tuple(temp)
                update_ppost_dict(data_index, ppost)

def process_verb(concept: Concept, seman_data, gnp_data, dependency_data, sentence_type, spkview_data, processed_nouns, processed_pronouns,index_data,k1_not_need,lang,reprocessing):
    """
    concept pattern: 'main_verb' - 'TAM for main verb' _Aux_verb+tam...
    Example 1:
    kara_1-wA_hE_1
    main verb - kara,  main verb tam: wA, Aux -hE with TAM hE (identified from tam mapping file)

    Example 2:
    kara_1-yA_1
    main verb - kara,  main verb tam: yA,

    Example 3:
    kara_1-0_rahA_hE_1
    main verb - kara,  main verb tam: 0, Aux verb -rahA with TAM hE, Aux -hE with TAM hE (identified from tam mapping file)

    Example 4:
    kara_1-0_sakawA_hE_1
    main verb - kara,  main verb tam: 0, Aux verb -saka with TAM wA, Aux -hE with TAM hE (identified from tam mapping file)

    *Aux root and Aux TAM identified from auxiliary mapping File
    """
    # if process_main_verb(concept, seman_data, dependency_data, sentence_type, processed_nouns, processed_pronouns, reprocessing):
    
    verb,verb_dict = process_main_verb(concept, seman_data, gnp_data, dependency_data, sentence_type, processed_nouns, processed_pronouns,index_data, reprocessing,k1_not_need,lang)
    auxiliary_verbs = process_auxiliary_verbs(verb,index_data, concept, spkview_data,sentence_type,lang)
    # Assume verb_dict already has at least one item
    if verb_dict:
        old_key, old_value = next(iter(verb_dict.items()))  # get first key-value pair

        # Build new key and tuple
        new_key = old_key + 0.3
        new_tuple = (
            f'{new_key}',
            old_value if isinstance(old_value, str) else old_value[1],
            'v', 'm', 's', 'a', None, 'o', 'krya'
        )

    # Replace verb_dict with only the new entry
        verb_dict = {new_key: new_tuple}

    
    
    return verb,verb_dict, auxiliary_verbs
    # else:
    #     return None

def process_nonfinite_verb(concept, seman_data,gnp_data, depend_data, sentence_type, processed_nouns, processed_pronouns,index_data, words_info,k1_not_need):
    '''
    >>process_nonfinite_verb([], [()],[()])
    '''
    gender = 'm'

    number = 's'
    person = 'a'
    verb = Verb()
    verb.index = concept.index
    # is_cp = is_CP(concept.term)
    # if is_cp: #only CP_head as nonfinite verb
    #     draft_concept = concept.term.split('+')[1]
    #     verb.term  = clean(draft_concept)
    # else:
    verb.term = clean(concept.term)
    ind=index_data.index(verb.index)
    verb.type = 'nonfinite'
    verb.tam = ''
    
    relation = concept.dependency.strip().split(':')[1]
    relation_head = concept.dependency.strip().split(':')[0]
    # if relation == 'rbks':
        # process_dep_rbks(concept, words_info, processed_nouns, processed_pronouns)
    if relation in ['rpk','rsk','rblsk','rblak','rblpk','rbks','rvks']:
        # Suppress 'while'/'after' connector for rsk/rpk when the nonfinite verb
        # already has a dependent with 'rp' relation (which produces 'via [place]').
        # In that case, 'via' already conveys the full meaning — adding 'while'
        # on top is redundant and wrong.
        # e.g. ho_12 (rsk→verb) with kASI (rp→ho_12) → 'via kāśī' is enough;
        # suppress the 'while' from ho_12's rsk relation.
        has_rp_dependent = any(
            ':'.join(str(wi[4]).split(':')[1:]) == 'rp' and
            str(wi[4]).split(':')[0] == str(verb.index)
            for wi in words_info
            if len(wi) > 4 and wi[4] and ':' in str(wi[4])
        )
        if has_rp_dependent and relation in ('rsk', 'rpk', 'rblsk'):
            nonfinite_dict = {}  # suppress connector word — 'via' from rp covers it
        else:
            nonfinite_dict = get_additional_word(relation, ind)
    if 'causative' in gnp_data[ind] and verb.term[-1]=='a':
        verb.term = verb.term[:-1] + 'A'

    verb.tam = set_tam_for_nonfinite(relation)
    # 'wawCIlAxi' (habitual/agentive participle, e.g. 'jāne vālī') → present-participle
    # -ing form, even when carried on a head-merging relation like rbks.
    if 'wawCIlAxi' in str(gnp_data[ind]):
        verb.tam = 'ing'
    full_tam = verb.tam
    # if getVerbGNP_new(verb.term, full_tam, is_cp, seman_data, depend_data, sentence_type, processed_nouns, processed_pronouns):
    gender, number, person = getVerbGNP_new(verb.term, full_tam,verb.index, seman_data, depend_data, sentence_type, processed_nouns, processed_pronouns,index_data,k1_not_need)
    verb.gender = gender
    verb.number = number
    verb.person = person
    verb.case = 'o' # to be updated - agreement with following noun
    verb.relation_head = relation_head
    verb.relation = relation
    log(f'{verb.term} processed as nonfinite verb with index {verb.index} gen:{verb.gender} num:{verb.number} case:{verb.case}, and tam:{verb.tam} and relatiion_head:{relation_head} and relation:{relation} ')
    return verb ,nonfinite_dict
    # else:
    #     return None

# def process_main_verb(concept: Concept, seman_data, gnp_data, dependency_data, sentence_type, processed_nouns, processed_pronouns, index_data, reprocessing, k1_not_need, lang):
#     verb = Verb()
#     verb.type = "main"
#     verb.index = concept.index
#     verb.term = identify_main_verb(concept.term)
#     full_tam = ''
    
#     if sentence_type[1:] not in ("fragment", "title", "heading", "term"):
#         full_tam = identify_complete_tam_for_verb(concept.term)
#         verb.tam = identify_default_tam_for_main_verb(concept.term)

#         if verb.term == 'hE' and verb.tam in ('pres', 'past'):
#             alt_tam = {'pres': 'hE', 'past': 'WA'}
#             alt_root = {'pres': 'hE', 'past': 'WA'}
#             verb.term = alt_root[verb.tam]
#             verb.tam = alt_tam[verb.tam]

#         if verb.term == 'jA' and verb.tam == 'yA':
#             verb.tam = 'yA1'

#         ind = index_data.index(verb.index)

#         # Handle causative or doublecausative
#         if gnp_data[ind] in ('causative', 'doublecausative'):
#             new_verb_term, is_english_causative = identify_causative(verb.term, gnp_data, ind, lang)

#             # Duplicate verb before modifying it
#             verb1 = Verb()
#             for attr in ['case', 'category', 'gender', 'index', 'number', 'person', 'tam', 'term', 'type']:
#                 setattr(verb1, attr, getattr(verb, attr, None))

#             # Generate a new unique index for verb1
#             used_indices = set(index_data)
#             new_index = 1
#             while new_index in used_indices:
#                 new_index += 1
#             verb1.index = new_index
       
#             if gnp_data[ind] == "causative":
#                 verb1.term = "make"
#                 verb.tam = None
#                 verb.type = None

#             verbs_to_return = [verb, verb1]

#             # If double causative, create verb2
#             if gnp_data[ind] == 'doublecausative':
#                 verb2 = Verb()
#                 for attr in ['case', 'category', 'gender', 'index', 'number', 'person', 'tam', 'term', 'type']:
#                     setattr(verb2, attr, getattr(verb, attr, None))

#                 # Assign new index to verb2
#                 new_index2 = new_index + 1
#                 while new_index2 in used_indices:
#                     new_index2 += 1
#                 verb2.index = new_index2
#                 verb1.term = "make"
#                 verb1.tam = None
#                 verb1.type = None
#                 # Set verb2 properties
#                 verb2.term = "ask"
#                 verb2.tam = verb.tam  # Take original tam
#                 verb2.type = verb.type  # Take original type

#                 # Clear tam and type from original verb
#                 verb.tam = None
#                 verb.type = None

#                 # Update return list
#                 verbs_to_return.append(verb2)

#             # Get GNP info for all verbs
#             gender, number, person = getVerbGNP_new(
#                 concept.term, full_tam, verb.index, seman_data, dependency_data,
#                 sentence_type, processed_nouns, processed_pronouns, index_data, k1_not_need
#             )

#             # Apply same GNP to verb1 and verb2
#             verb.gender, verb.number, verb.person = gender, number, person
#             verb1.gender, verb1.number, verb1.person = gender, number, person
#             if gnp_data[ind] == 'doublecausative':
#                 verb2.gender, verb2.number, verb2.person = gender, number, person

#             return verbs_to_return

#     # Normal case: only one verb
#     verb.gender, verb.number, verb.person = getVerbGNP_new(
#         concept.term, full_tam, verb.index, seman_data, dependency_data,
#         sentence_type, processed_nouns, processed_pronouns, index_data, k1_not_need
#     )
#     return verb
# def identify_causative(verb, gnp_data, ind, lang):
#     if lang == 'hi':
#         try:
#             with open(repository.constant.CAUSATIVE_MAP_FILE, 'r') as file:
#                 for line in file:
#                     parts = line.strip().split(',')
#                     if len(parts) == 3 and parts[0] == verb and parts[1] == gnp_data[ind]:
#                         return parts[2], False  # Hindi match found
#         except FileNotFoundError:
#             print("Causative mapping file not found for Hindi.")
#     elif lang == 'en':
#         return verb, True  # English: no change to verb, but mark as causative

#     return verb, False  # Default fallback
import importlib

def process_main_verb(concept: Concept, seman_data, gnp_data, dependency_data,
                      sentence_type, processed_nouns, processed_pronouns,
                      index_data, reprocessing, k1_not_need, lang):
    """
    Process the main verb with language-specific rules.
    """
    try:
        lang_module = importlib.import_module(f'language_rules.{lang}')
        lang_rules = getattr(lang_module, 'VERB_RULES', {})
    except ImportError:
        print(f"No language rules found for '{lang}'")
        lang_rules = {}

    default_tam = lang_rules.get('default_tam', 'base')
    special_verbs = lang_rules.get('special_verbs', {})
    causative_rules = lang_rules.get('causative', {})
    verb_dict = {}

    if '+' in concept.term:
        concept_term = concept.term
        concept_term = concept_term.split("+")[0].split("_")[0]
        verb_dict = {concept.index: concept_term}

    verb = Verb()
    verb.type = "main"
    verb.index = concept.index
    verb.term = identify_main_verb(concept.term)
    full_tam = ''

    verbs_to_return = []

    if sentence_type[1:] not in ("fragment", "title", "heading", "term"):
        full_tam = identify_complete_tam_for_verb(concept.term)
        verb.tam = identify_default_tam_for_main_verb(concept.term)

        if verb.term in special_verbs:
            verb_info = special_verbs[verb.term].get(verb.tam)
            if verb_info:
                verb.term = verb_info['root']
                verb.tam = verb_info['tam']

        ind = index_data.index(verb.index)

        if gnp_data[ind] in ('causative', 'doublecausative'):
            verbs_to_return = handle_causative(
                verb, gnp_data, ind, index_data, causative_rules, lang
            )

            gender, number, person = getVerbGNP_new(
                concept.term, full_tam, verb.index, seman_data, dependency_data,
                sentence_type, processed_nouns, processed_pronouns, index_data, k1_not_need
            )

            for v in verbs_to_return:
                v.gender, v.number, v.person = gender, number, person

            return verbs_to_return, verb_dict  # ✅ FIXED HERE

    print("verb:", type(verb))
    print("verb_dict:", type(verb_dict))

    verb.gender, verb.number, verb.person = getVerbGNP_new(
        concept.term, full_tam, verb.index, seman_data, dependency_data,
        sentence_type, processed_nouns, processed_pronouns, index_data, k1_not_need
    )

    return verb, verb_dict  # ✅ Consistent return type

def handle_causative(original_verb, gnp_data, ind, index_data, causative_rules, lang):
    """Generate causative or double-causative verbs based on language rules."""
    verbs = []
    
    # Duplicate original verb
    verb1 = duplicate_verb(original_verb)
    used_indices = set(index_data)

    # Assign new unique index
    new_index = 1
    while new_index in used_indices:
        new_index += 1
    verb1.index = new_index

    if gnp_data[ind] == "causative":
        verb1.term = causative_rules.get('default_causative_verb', {})
        original_verb.tam = None
        original_verb.type = None
        verbs = [original_verb, verb1]

    elif gnp_data[ind] == "doublecausative":
        verb1.term = causative_rules.get('double_causative_verb', {})
        original_verb.tam = None
        original_verb.type = None

        verb2 = duplicate_verb(original_verb)
        new_index2 = new_index + 1
        while new_index2 in used_indices:
            new_index2 += 1
        verb2.index = new_index2

        verb2.term = causative_rules.get('default_causative_verb', {})
        verb2.tam = original_verb.tam
        verb2.type = original_verb.type

        verbs = [original_verb, verb1, verb2]

    return verbs
def duplicate_verb(verb):
    verb_copy = Verb()
    for attr in ['case', 'category', 'gender', 'index', 'number', 'person', 'tam', 'term', 'type']:
        setattr(verb_copy, attr, getattr(verb, attr, None))
    return verb_copy

def get_attr(item, attr_name):
    """Safely get an attribute from object or dict, and reject methods like list.index."""
    if isinstance(item, dict):
        val = item.get(attr_name)
    else:
        val = getattr(item, attr_name, None)

    if callable(val):
        raise TypeError(f"{attr_name} is a method, not a value: {val}")
    return val


def extract_main_verb(verb_input):
    """If input is a list of verbs, extract the one with type=='main' or return the first."""
    if isinstance(verb_input, list):
        for verb in verb_input:
            if get_attr(verb, 'type') == 'main':
                return verb
        return verb_input[0]  # fallback
    return verb_input  # already a single Verb object


def create_auxiliary_verb(index, term, tam, main_verb_input):
    main_verb = extract_main_verb(main_verb_input)

    verb = Verb()

    main_index = get_attr(main_verb, 'index')
    if not isinstance(main_index, (int, float)):
        raise TypeError(f"Expected numeric index, got: {main_index}")

    verb.index = main_index + (index + 1) / 10
    verb.gender = get_attr(main_verb, 'gender')
    verb.number = get_attr(main_verb, 'number')
    verb.person = get_attr(main_verb, 'person')
    verb.term = term
    verb.tam = tam

    if verb.term == 'cAha':
        verb.person = 'm_h'

    verb.type = 'auxiliary'

    log(f'{verb.term} processed as auxiliary verb with index {verb.index} gen:{verb.gender} num:{verb.number} and tam:{verb.tam}')
    return verb


def process_adjectives(adjectives, gnp_data1, index_data, processed_nouns, processed_verbs):
    """
    Process adjectives as tuples with grammatical attributes.

    Args:
        adjectives (list): List of adjectives as tuples (index, word, category, case, gender, number, relation).
        gnp_data1 (list): GNP-related data.
        index_data (list): Index mapping data.
        processed_nouns (list): Processed noun data.
        processed_verbs (list): Processed verb data.

    Returns:
        list: Processed adjectives with updated attributes.
    """
    processed_adjectives = []
    default_gender, default_number, default_person, default_case = get_default_GNP()

    # Determine the index of 'kqwpft' if it exists
    ind_kqwpft = gnp_data1.index('kqwpft') if 'kqwpft' in gnp_data1 else None

    for adjective in adjectives:
        index = adjective[0]
        adj = clean(adjective[1])
        if len(adj) > 1:
            adj = adj.replace(" ", "")

        category = 'adj'
        tam = ''
        rel_concept = int(adjective[4].strip().split(':')[0]) if ':' in adjective[4] else -1  # Related noun/verb
        relation = (adjective[4].strip().split(':')[1] if ':' in adjective[4] else '')

        # Determine associated concept data based on relation type
        if relation == 'k1s':
            if adj == 'kim':
                adj = 'kEsA'
            rel_concept_data = getDataByIndex(rel_concept, processed_verbs)
        else:
            rel_concept_data = getDataByIndex(rel_concept, processed_nouns)

        # Extract GNP case attributes
        if not rel_concept_data:
            log(f'Associated noun/verb not found for adjective {adjective[1]}. Using default values.')
            gender, number, person, case = default_gender, default_number, default_person, default_case
        else:
            gender, number, person, case = get_gnpcase_from_concept(rel_concept_data)
            if relation == 'k1s':
                case = 'd'

        # Special case for 'kim' with 'krvn' relation
        if adj == 'kim' and relation == 'krvn':
            adj = 'kEsA'
        if adj == 'kim' and relation == 'mod':
            adj = "Which"

        # Find tags and process based on category
        tags = find_tags_from_dix_as_list(adj)
        for tag in tags:
            if tag.get('cat') == 'v':
                if relation in ('rvks', 'rbks'):
                    category = 'vj'
                    tam = 'adj_yA_huA' if relation == 'rbks' else 'adj_wA_huA'
                if ind_kqwpft is not None and index == index_data[ind_kqwpft]:
                    category = 'vj'
                    tam = 'adj_yA_huA'
                break

        # Append processed adjective with or without TAM
        if tam:
            adjective = (index, adj, category, case, gender, number, tam ,rel_concept,relation)
            processed_adjectives.append(adjective)
            log(f'{adjective[1]} processed as adjective with case:{case}, gender:{gender}, number:{number}, tam:{tam},rel_concept:{rel_concept},relation:{relation}')
        else:
            adjective = (index, adj, category, case, gender, number,rel_concept,relation)
            processed_adjectives.append(adjective)
            log(f'{adjective[1]} processed as adjective with case:{case}, gender:{gender}, number:{number},rel_concept:{rel_concept},relation:{relation}')

    return processed_adjectives


def process_kim(index, index_data, relation, anim, gnp,case, pronoun, words_info, main_verb, processed_pronouns, processed_indeclinables, processed_nouns,lang):

    term = get_root_for_kim(relation, anim,gnp,case,)
    if term == 'kyoM':
        processed_indeclinables.append((index, term, 'indec'))
    else:
        category = 'p'
        case = 'o'
        parsarg = 0
        case, postposition = preprocess_postposition_new('pronoun', pronoun, words_info, main_verb, index_data,lang)
        if postposition != '':
            parsarg = postposition

        fnum = None
        gender, number, person = extract_gnp(pronoun)

        if "r6" in pronoun[4]:
            fnoun = int(pronoun[4][0])
            fnoun_data = getDataByIndex(fnoun, processed_nouns, index=0)
            gender = fnoun_data[4]  # To-ask
            fnum = number = fnoun_data[5]
            case = fnoun_data[3]
            if term == 'apanA':
                parsarg = '0'

        if term in ('kahAz'):
            parsarg = 0
        relation_head = pronoun[4].strip().split(':')[0] if pronoun[4] and ':' in pronoun[4] else ''
        processed_pronouns.append((pronoun[0], term, category, case, gender, number, person, parsarg, fnum, relation_head, relation))
        # processed_pronouns.append((pronoun[0], term, category, case, gender, number, person, parsarg, fnum, relation_head, relation))
        log(f'kim processed as pronoun with term: {term} case:{case} par:{parsarg} gen:{gender} num:{number} per:{person} fnum:{fnum}')
    return processed_pronouns, processed_indeclinables

def get_root_for_kim(relation, anim, gnp,case,lang="hi"):
    # kOna is root for - kisakA, kisakI, kisake, kinakA, kinake, kinakI, kOna, kisa, kisane, kise, kisako,
    # kisase, kisake, kisameM, kisameM_se, isapara, kina, inhoMne, kinheM, kinako, kinase, kinpara, kinake, kinameM, kinameM_se, kisI, kisa
    # if gnp=='pl':
    #     number='p'
    # else:
    #     number='s'
    animate = ['anim', 'per']
    if relation in ('k2p', 'k7p'):
        return 'kahAz'
    elif relation == 'k5' :
        return 'kahAz'
    elif relation == 'k7t':
        return 'kaba'
    elif relation == 'rh' :
        return 'kyoM'
    elif relation == 'rt' : #generate kisa
        return 'kOna'
    elif relation == 'krvn': #generate kEse
        return 'kEsA'
    elif relation == 'k1s':
        return 'kEsA'
    elif relation=='dem' and gnp=='' and case=='o':
        return 'kis'
    elif relation=='dem' and gnp=='pl' and case=='o':
        return 'kin'
    elif anim not in animate:
        return 'kyA'
    elif anim in animate:
        return 'kOna'
    elif relation =='k1' or relation =='k2':
        return 'kyA'
    else:
        return 'kim'
    


def get_root_for_kim(relation, anim, gnp, case, lang="en"):
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQBDA4xq199DZQwuwS5g5XHXNUTud_zvZ6O-kGEcPqj7yRe9bpv8k7BRb32f2hcYbB0OFWEhyJCJm9V/pub?gid=0&single=true&output=csv"
    response = requests.get(url)
    data_rows = list(csv.DictReader(StringIO(response.text)))

    for row in data_rows:
        sheet_relation = row['relation'].strip()
        sheet_anim = row['anim'].strip()
        value = row['value'].strip()

        if sheet_relation != relation:
            continue

        if sheet_anim == '-':
            return value
        elif sheet_anim == 'anim/per' and anim in ['anim', 'per']:
            return value
        elif sheet_anim == '!anim/per' and anim not in ['anim', 'per']:
            return value

    return "kim"  # Default fallback if nothing matches


def process_yax(index1, index_data, relation, anim, gnp,case, pronoun, words_info, main_verb, processed_pronouns, processed_indeclinables, processed_nouns,lang):
                
    term = get_root_for_yax(relation, anim,gnp,case,)
    # if term == 'kyoM':
    #     processed_indeclinables.append((index, term, 'indec'))
    # else:
    category = 'p'
    case = 'o'
    parsarg = 0
    case, postposition = preprocess_postposition_new('pronoun', pronoun, words_info, main_verb, index_data,lang)
    if postposition != '':
        parsarg = postposition

    fnum = None
    gender, number, person = extract_gnp(pronoun)

    # if "r6" in pronoun[4]:
    #     fnoun = int(pronoun[4][0])
    #     fnoun_data = getDataByIndex(fnoun, processed_nouns, index=0)
    #     gender = fnoun_data[4]  # To-ask
    #     fnum = number = fnoun_data[5]
    #     case = fnoun_data[3]
    #     if term == 'apanA':
    #         parsarg = '0'

    if term in ('jahAz'):
        parsarg = 0
    relation_head = pronoun[4].strip().split(':')[0] if pronoun[4] and ':' in pronoun[4] else ''
    processed_pronouns.append((pronoun[0], term, category, case, gender, number, person, parsarg, fnum, relation_head, relation))
    # processed_pronouns.append((pronoun[0], term, category, case, gender, number, person, parsarg, fnum, relation_head, relation))
    log(f'yax processed as pronoun with term: {term} case:{case} par:{parsarg} gen:{gender} num:{number} per:{person} fnum:{fnum}')
    return processed_pronouns, processed_indeclinables

def get_root_for_yax(relation, anim, gnp,case):
    # kOna is root for - kisakA, kisakI, kisake, kinakA, kinake, kinakI, kOna, kisa, kisane, kise, kisako,
    # kisase, kisake, kisameM, kisameM_se, isapara, kina, inhoMne, kinheM, kinako, kinase, kinpara, kinake, kinameM, kinameM_se, kisI, kisa
    # if gnp=='pl':
    #     number='p'
    # else:
    #     number='s'
    animate = ['anim', 'per']
    if relation in ('k2p', 'k7p'):
        return 'jahAz'
    elif relation == 'k5' :
        return 'jahAz'
    elif relation == 'k7t':
        return 'jaba'
    # elif relation == 'rh' :
    #     return 'kyoM'
    elif relation == 'rt' : #generate kisa
        return 'jo'
    # elif relation == 'krvn': #generate kEse
    #     return 'kEsA'
    # elif relation == 'k1s':
    #     return 'kEsA'
    elif relation=='dem' and gnp=='' and case=='o':
        return 'jisa'
    elif relation=='dem' and gnp=='pl' and case=='o':
        return 'jina'
    elif anim not in animate:
        return 'jo'
    elif anim in animate:
        return 'jo'
    elif relation =='k1' or relation =='k2':
        return 'jo'
    else:
        return 'jo'
