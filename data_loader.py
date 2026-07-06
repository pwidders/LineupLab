import pandas as pd

def load_excel(file):
    xls = pd.ExcelFile(file)

    hitters = pd.read_excel(xls, 'Hitters')
    pitchers = pd.read_excel(xls, 'Pitchers')
    stacks = pd.read_excel(xls, 'Stackbuilder')

    return hitters, pitchers, stacks