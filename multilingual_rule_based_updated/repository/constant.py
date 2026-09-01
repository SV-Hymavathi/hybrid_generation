HAS_CONSTRUCTION_DATA = False
HAS_SPKVIEW_DATA = False
HAS_MORPHO_SEMANTIC_DATA = False
HAS_DISCOURSE_DATA = False
HAS_COREF = False
flag_conj = False
flag_disjunct = False
flag_span = False
flag_cp = False
flag_meas = False
flag_rate = False
flag_spatial = False
flag_waw = False
flag_cal = False
flag_xvanxva = False
flag_temporal = False
k1_not_need = False
has_changes = False
flag_temporal_spatial = False

# Declare global variables

src_sentence = []
root_words = []
index_data = []
seman_data = []
gnp_data = []
depend_data = []
discourse_data = []
spkview_data = []
scope_data = []
construction_data = []
sentence_type = []


# TAM_DICT_FILE = 'tam_mapping.dat'
TAM_DICT_FILE = './repository/tam_mapping_new.dat'
AUX_MAP_FILE = './repository/auxillary_mapping.txt'
CAUSATIVE_MAP_FILE='./repository/causative_mapping.txt'




# data lists
INDECLINABLE_WORDS = [
        'eKana','waWA','Ara','paranwu','kinwu','evaM','waWApi','kiCu',
        'wo','yaxi','wabe','awaH','kAraNa','kenanA','yeBAbe',
        'waKana','waKani','bA', 'nAhale','anyaWA', 'yaKana', 'naile',
        'yAwe','yaxi', 'aWabA','Aja','nA', 'yawa', 'yA','nahIM',]

UNITS = ['semI', 'kimI', 'mItara', 'lItara', 'kilomItara', 'kilolItara']

kriyAmUla=['viswqwa','prawIkRA','varNana']

# NON_FINITE_VERB_DEPENDENCY = ['rpk', 'rsk','rbk', 'rvks', 'rbks', 'rblpk', 'rblsk']
NON_FINITE_VERB_DEPENDENCY = ['rpk', 'rsk','rbks','rblsk','rvks','rblak','rblpk']

noun_exceptional = ['home']

ADJECTIVE_DEPENDENCY = ['card', 'mod','meas', 'ord', 'intf','rvks','rbks','k1s']
# VERBAL_ADJECTIVE = ['rvks','rbks']
PRONOUN_TERMS = ['addressee', 'speaker', 'kyA', 'Apa','wyax', 'jo', 'koI', 'kOna', 'mEM','merA', 'saba', 'vaha', 'wU', 'wuma', 'yaha', 'kim','ve','ye','yax','apanA']
# NOMINAL_VERB_DEPENDENCY = ['rt', 'rh', 'k7p', 'k7t', 'k2']
NOMINAL_VERB_DEPENDENCY = ['rt', 'rh', 'k7p','k7', 'k7t', 'k2','rblpk','rblsk','rblak','k1s']
# constants.py
# pass_list=['pass-affirmative','pass-interrogative','pass-negative sentence']
pass_list=['pass_affirmative','pass_interrogative','pass_negative','pass_yn_interrogative',
           'pass-affirmative','pass-interrogative','pass-negative','pass-yn_interrogative']
k7_postposition_list=['पर', 'को', 'में']
noun_attribute = dict()
USR_row_info = [
    'root_words', 'index_data', 'seman_data', 'gnp_data', 'depend_data',
    'discourse_data', 'spkview_data', 'scope_data'
]
nA_list = [
    'nA_paDa', 'nA_padZA', 'nA_padA', 'nA_hE', 'nA_WA', 'nA_hogA', 'nA_cAhie',
    'nA_cAhiye','cAhiye'
]

morpho_seman = ['comparmore','comparless', 'superl', 'mawupa', 'mawup','dviwva']

spkview_list_b = [
    'jI', 'lagAwAra', 'kevala' ,'karIba','TIka','mAwra','basa','sirPa',
]
spkview_list_a = [
    'hI', 'BI', 'jI', 'wo','sI','ki','waka', 'lagaBaga', 'lagAwAra'
]
kisase_k2g_verbs = ['bola', 'pUCa', 'kaha', 'nikAla', 'mAzga']
reciprocal_verbs = ['mila', 'pyAra']
kisase_k5_verbs = ['dara', 'baca', 'rakSA']
kahAz_k5_verbs = ['A', 'uga', 'gira']

discourse_dict = {
    'samuccaya': ['and'],
    'AvaSyakawApariNAma': '',
    'kAryakAraNa': ['because'],
    'pariNAma': ['therefore'],
    'viroXI_xyowaka': 'whereas',
    'viroXIxyowaka': 'whereas',           
    'vyaBicAra': ['although'],
    'viroXI': ['but'],
    'anyawara': ['or'],                    
    'anyawra': ['or'],                     
    'samuccaya x': ['besides', 'apart from this', 'along with', 'not only'],
    'arWAwa': ['in other words'],
    'uwwarakAla': ['after that'],          
    'uwwarkAla': ['after that'],          
    'kAryaxyowaka': 'so that',
    'kArya_xyowaka': 'so that',            
    'uxaharaNasvarUpa': 'for example',
    'uxAharaNasvarUpa': 'for example',
    'rcprop': 'as',                       
    'rkrl': '',                            
}

spkview_list = ['BI_1', 'samAveSI', 'alAvA', 'awirikwa']
# --- REPLACE WITH: ---
discourse_list = [
    'samuccaya', 'AvaSyakawApariNAma', 'kAryakAraNa', 'pariNAma',
    'viroXIxyowaka', 'viroXI_xyowaka',     # both spellings
    'vyaBicAra', 'viroXI',
    'anyawra', 'anyawara',                  # both spellings
    'samuccaya x', 'samuccaya.alAvA', 'samuccaya.samAveSI', 'samuccaya.atirikta',
    'arWAwa', 'uwwarkAla', 'uwwarakAla',    # both spellings
    'kAryaxyowaka', 'kArya_xyowaka',        # both spellings
    'uxaharaNasvarUpa',
    'uxAharaNasvarUpa',
    'rcprop',                               # NEW
    'rkrl',                                 # NEW
]
# Create a dictionary to map short categories to descriptive forms
category_mapping = {
    'n': 'noun',
    'p': 'pronoun',
    'adj': 'adjective',
    'v': 'verb',
    'adv': 'adverb',
    'indec': 'indeclinable',
    # Add more mappings as needed
}

construction_list =['cp', 'conj','temporal', 'disjunct', 'span','meas', 'widthmeas', 'depthmeas','volumemeas','nc', 'distmeas', 'rate', 'timemeas', 'waw', 'calendar', 'massmeas', 'heightmeas', 'spatial','xvanxva','compound','ne']
complex_concepts = {
    "conj_1": ["op1", "op2", "op3", "op4", "op5"],
    "disjunct_1": ["op1", "op2", "op3", "op4", "op5"],
    "span_1": ["start", "end"],
    "nc_1": ["mod", "head"],
    "time_meas_1": ["count", "unit"],
    "dist_meas_1": ["count", "unit"],
    "weight_meas_1": ["count", "unit"],
    "length_meas_1": ["count", "unit"],
    "temp_meas_1": ["count", "unit"],
    "width_meas_1": ["count", "unit"],
    "depth_meas_1": ["count", "unit"],
    "height_meas_1": ["count", "unit"],
    "volume_meas_1": ["count", "unit"],
    "rate_1": ["unit_value", "unit_every"],
    "calender_1": ["component1", "component2", "component3", "component4", "component5", "component6"],
    "spatial_1": ["whole", "part"],
    "temporal_1": ["whole", "part"],
    "cp_1": ["kriyAmUla", "verbalizer"],
    "xvanxva_1": ["op1", "op2"],
    "ne_1": ["begin", "inside"]
}
# spkview_list_for_discource=['BI_1','samAveSI','alAvA','awirikwa']
exception_no_tam_sentence_type = ["fragment","term","title","heading"]
aux_exception_case = ['sakawA']
relations = [
    "card","cxnpart","dem","dur","extent","freq","intf","jk1","k1","k1s","k2","k2g","k2p","k2s","k3","k4","k4a","k5","k5prk","k7","k7a","k7p","k7t","krvn","krvnneg","main",
    "mk1","mod","neg","ord","pk1","quant","quantless","quantmore","rad","rbks","rblak","rblpk","rblsk","rcdelim","rcelab","rcloc","rcprop","rcsamAnakAla","rd",
    "re","rh","rhh","rk","rkrl","rn","rp","r6","rpk","rprop","rs","rsma","rsm","rsk","rt","ru","rv","rvks","rviroXIk1","vIpsA","vkvn",
    "rask1","rask2","rask3","rask4","rask5","rask6","rask7",
    "k1as","k2as","k3as","k4as","k5as","k7as",
]
ordering_dep_list = ['card','dem','intf','mod','ord','quant','rn','rs','r6','ru','rv','rmeas']

postpositionnew_dc_mod_season = ['kA']
#postposition_new if mod and season 'k3', 'k4', 'k5', 'k7', 'k7p', 'k7t', 'r6', 'mk1', 'jk1', 'rt'
postpositionnew_dc_mod_sea_a = ['ke']

# File: language_rules.py

# morpho_seman_mapping = {
#     'en': {
#         'superl': ('before', 'most'),
#         'comparmore': ('before', 'more'),
#         'comparless': ('before', 'less'),
#         # Add more as needed
#     },
#     'hi': {
#         'superl': ('before', 'sabase'),
#         'comparmore': ('before', 'aXika'),
#         'comparless': ('before', 'kama'),
#         # Add more as needed
#     }

# }
# lang_config = {
#     'hi': {
#         'use_def_check': False,
#         'use_gnp_rules': False,
#         'use_construction_rules': False,
#         'article_rules': None,
#         'spkview_lists': ['spkview_list_b', 'spkview_list_a'],
#         'default_before_after': {'result': 'after'}
#     },
#     'en': {
#         'use_def_check': True,
#         'use_gnp_rules': True,
#         'use_construction_rules': True,
#         'article_rules': {
#             'indef': 'a',
#             'indef_vowel': 'an'
#         },
#         'spkview_lists': ['spkview_list_b', 'spkview_list_a'],
#         'default_before_after': {'result': 'after'}
#     }
# }

    # Add other languages here
