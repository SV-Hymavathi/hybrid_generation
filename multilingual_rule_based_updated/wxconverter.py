
# from wxconv import WXC

# def convert_to_hindi(input_list):
#     wx = WXC(order='wx2utf', lang='hin')
#     wx1 = WXC(order='utf2wx', lang='hin')
#     hindi_text_list = [wx.convert(word) for word in input_list]
#     # hindi_text_list = wx.convert(input_list)
#     return hindi_text_list

# one_markers = ["pahuMca"]
# converted_text1 = convert_to_hindi(one_markers)
# print(converted_text1)
# {'meMtala': {'rAw/a__n': ['meMtala', 'meMtaleM', 'meMtala', 'meMtaloM'], 'BIda/__n': [], 'Gar/a__n': ['meMtala', 'meMtala', 'meMtala', 'meMtaloM'], 'Karc/a__n': ['meMtala', 'meMtale', 'meMtala', 'meMtaloM'], 'kroXa/__n': [], 'calaciwr/a__n': ['meMtala', 'meMtala', 'meMtaloM', 'meMtaloM']}}

# ============================================
from wxconv import WXC

def convert_to_hindi(input_list):
    # Initialize the WXC converter for Hindi (WX to UTF)
    wx = WXC(order='wx2utf', lang='hin')
    # Convert each word in the input list from WX to UTF
    hindi_text_list = [wx.convert(word) for word in input_list]
    return hindi_text_list

def convert_one_marker(one_marker):
    # Iterate through the outer dictionary
    for key, value in one_marker.items():
        # Iterate through the inner dictionary
        for sub_key, sub_value in value.items():
            if isinstance(sub_value, list):  # Check if the value is a list
                # Convert the list of words to Hindi
                one_marker[key][sub_key] = convert_to_hindi(sub_value)
    return one_marker

# Input dictionary
one_marker = {'janmaxina': {'rAw/a__n': ['janmaxina', 'janmaxineM', 'janmaxina', 'janmaxinoM'], 'BIda/__n': [], 'Gar/a__n': ['janmaxina', 'janmaxina', 'janmaxina', 'janmaxinoM'], 'Karc/a__n': ['janmaxina', 'janmaxine', 'janmaxina', 'janmaxinoM'], 'kroXa/__n': [], 'calaciwr/a__n': ['janmaxina', 'janmaxina', 'janmaxinoM', 'janmaxinoM']}}

# Convert the values in the lists to Hindi
converted_one_marker = convert_one_marker(one_marker)

# Print the result
print(converted_one_marker)