morpho_seman = {
    'superl': ('before', 'most'),
    'comparmore': ('before', 'more'),
    'comparless': ('before', 'less'),
}


TAM_DICT_FILES = {
    'en': './repository/tam_mapping_eng.dat'
    # Add more languages as needed
}

AUX_MAP_FILE = {
    'en': './repository/auxillary_mapping_en.txt'
}
# Language-specific verb rules for English
VERB_RULES = {
    'default_tam': 'base',
    'special_verbs': {},
    'causative': {
        'default_causative_verb': 'make',
        'double_causative_verb': 'ask',
        'mapping': {}
    }
}

indeclinables = []

PRONOUN_TERMS = ['addressee', 'speaker', 'wyax',  'any', 'all', 'kim','yax','every','each','many','several','apanA','eka+xUsarA']


speakers_b = [
    'jI', 'lagAwAra', 'kevala', 'karIba', 'TIka', 'mAwra',
    'basa', 'sirPa', 'hAz', 'aura', 'lagaBaga', 'lagaBAga'
]

speakers_a = [
    'hI', 'BI', 'jI', 'wo', 'sI', 'ki', 'waka',
    'lagaBaga', 'lagAwAra', 'def'
]

SPKVIEW_TO_WORD_MAP = {
    # hI variants
    'hI_1': 'only',                  # Exclusive - only Mohan saw Rama
    'hI_2': 'really',                # Emphasis - really/certainly
    'hI_3': 'a few',                 # Intensification - a few days
    'hI_4': 'as soon as',            # Immediacy - as soon as he entered
    'hI_5': 'even',                  # Scalar/expectation - didn't even know
    'hI_6': 'only',                  # Only - only 10 days

    # BI variants
    'BI_1': 'also',                  # Additive - John too/also
    'BI_2': 'even',                  # Delimit/scalar - even John came
    'BI_3': 'any',                   # Generic/free-choice - whoever/any
    'BI_4': 'even a single',         # Emphasis under negation - not a single
    'BI_5': 'may',                   # Alternative - may win
    'BI_6': 'even while',            # Concessive - even while crying

    # wo variants
    'wo_1': 'so',                    # Aboutness/turn-taker - so, what are you upto
    'wo_2': '',                      # Agraha/request - no direct English equivalent
    'wo_3': '',                      # others

    # aura variants
    'aura_1': 'more',                # Additional - one more tea

    # kevala
    'kevala_1': 'only',              # Only - only 10 people

    # sA
    'sA_1': 'quite',                 # Modifier/intensifier - small toy puppy

    # kariba
    'karIba_1': 'nearly',            # Nearly - nearly 4 crores

    # lagaBaga / lagaBAga
    'lagaBaga_1': 'almost',          # Almost/approximate
    'lagaBAga_1': 'almost',          # Almost/approximate (alternate spelling)

    # sirPa
    'sirPa_1': 'only',               # Only - only 30% work

    # hAz
    'hAz_1': 'yes',                  # Affirmation - yes

    # TIka
    'TIka_1': 'exactly',             # Exactly

    # mAwra
    'mAwra_1': 'amount',             # Amount
    'wakarIbana_1': 'about',

    # def - article
    'def': 'the',                    # Definiteness marker
}

indeclinables_dict = {
  "waWA": "likewise",
  "paranwu": "but",
  "kinwu": "but",
  "evaM": "thus",
  "waWApi": "nevertheless",
  "wo": "then",
  "yaxi": "if",
  "awaH": "therefore",
  "kAraNa": "because",
  "waKana": "then",
  "anyaWA": "otherwise",
  "aWabA": "or",
  "Aja": "today",
  "nA": "not",
  "nahIM": "not",
  "yA": "or",
  "kilometre": "kilometer"
  
}

months = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]
days = [
    "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"
]


PRONOUN_SHEET_URL ='hindi_pronoun - Sheet1.csv'