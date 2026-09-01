morpho_seman = {
    'superl': ('before', 'sabase'),
    'comparmore': ('before', 'aXika'),
    'comparless': ('before', 'kama'),
}

TAM_DICT_FILES = {
    'hi': './repository/tam_mapping_hin.dat'


}

AUX_MAP_FILE = {
    'hi': './repository/auxillary_mapping_hin.txt'
}
# Language-specific verb rules for Hindi
VERB_RULES = {
    'default_tam': 'pres',
    'special_verbs': {
        'hE': {
            'pres': {'root': 'hE', 'tam': 'pres'},
            'past': {'root': 'WA', 'tam': 'past'}
        },
        'jA': {
            'yA': {'root': 'jA', 'tam': 'yA1'}
        }
    },
    'causative': {
        'default_causative_verb': 'karwA',
        'double_causative_verb': 'lawA',
        'mapping': {
            'karnA': 'karwA',
            'dEnA': 'dilwA'
        }
    }
}
speakers_b = [
    'jI', 'lagAwAra', 'kevala' ,'karIba','TIka','mAwra','basa','sirPa',
]
speakers_a = [
    'hI', 'BI', 'jI', 'wo','sI','ki','waka', 'lagaBaga', 'lagAwAra'
]
#hi.py
SPKVIEW_TO_WORD_MAP={}


PRONOUN_SHEET_URL = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vSTfjpzsLXhH_jhLEivp8tamMsj_Q1YtpsyGYJVYmVYRJaV51Lop2mePQOXwdr7W9AgoxkJ4ASEup2E/pub?gid=0&single=true&output=csv'

PRONOUN_TERMS = ['addressee', 'speaker', 'wyax', 'koI', 'saba', 'kim','yax','saBI']