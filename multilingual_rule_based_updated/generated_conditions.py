# def get_ppost(datacase, cond=None, data_seman=None, root_main=None, concept_type=None):
import pandas as pd

def  get_ppost(datacase, cond=None, data_seman=None, root_main=None, concept_type=None):
    # Load the CSV from the Google Sheets URL
    url = "pre-pos - Sheet1.csv"
    df = pd.read_csv(url)

    # Build a lookup dictionary from the sheet
    ppost_map = {}
    for _, row in df.iterrows():
        keys = [k.strip() for k in str(row['datacase']).split(',')]
        for key in keys:
            ppost_map[key] = row['value']
    

    # Lookup the given data_case
    return ppost_map.get(datacase, None)  # returns None if not found
