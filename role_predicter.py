# Load libraries
from joblib import dump, load
import pandas
#from sklearn.linear_model import LogisticRegression

def get_roles(model, data):
# Load dataset
#cols = (29, 35, 36)
    cols = (4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 22, 24, 25, 26, 27, 29, 30, 31, 32, 33, 34, 35, 36)
    LR = load(model)
    rd2l_set = pandas.read_csv(data, usecols=cols)
    rd2l_set = rd2l_set[rd2l_set['Role']!=2]
    rd2l_X = rd2l_set.values[:, :len(cols)-1]
    rd2l_Y = rd2l_set.values[:, len(cols)-1]
    rd2l_predictions = LR.predict(rd2l_X)
    return rd2l_predictions