# Load libraries
from joblib import dump, load
import pandas
from pandas.plotting import scatter_matrix
import matplotlib.pyplot as plt
from sklearn import model_selection
from sklearn.metrics import classification_report
from sklearn.metrics import confusion_matrix
from sklearn.metrics import accuracy_score
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.naive_bayes import GaussianNB
from sklearn.svm import SVC
import numpy as np
import os
def get_roles(model, data):
# Load dataset
    cols = (4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 22, 24, 25, 26, 27, 29, 30, 31, 32, 33, 34, 35, 36)
    if not os.path.isfile(model):
        url = 'TI_data/ti.out'    
        dataset = pandas.read_csv(url, usecols=cols)
        dataset = dataset[dataset['Role']!=2]
        array = dataset.values
        X = array[:, :len(cols)-1]
        Y = array[:, len(cols)-1]
        Y = Y.astype('int')
        LR = LogisticRegression(penalty = 'l2', solver='newton-cg', class_weight='balanced', max_iter = 10000000, multi_class = 'auto')
        LR.fit(X, Y)
        df = pandas.DataFrame([LR.coef_[0].T], columns = list(dataset)[:len(cols)-1])
        print(df)
        dump(LR, model)
    else:    
        LR = load(model)
    rd2l_data = data
    rd2l_set = pandas.read_csv(rd2l_data, usecols=cols)
    rd2l_set = rd2l_set[rd2l_set['Role']!=2]
    rd2l_X = rd2l_set.values[:, :len(cols)-1]
    rd2l_Y = rd2l_set.values[:, len(cols)-1]
    rd2l_predictions = LR.predict(rd2l_X)
    return rd2l_predictions
    print("LR RD2L %s"%accuracy_score(rd2l_Y, rd2l_predictions))
    a = confusion_matrix(rd2l_Y, rd2l_predictions)
    b = pandas.DataFrame(a)
    print(b)
    print(classification_report(rd2l_Y, rd2l_predictions))

    names = pandas.read_csv(rd2l_data)
    names = names[names['Role']!=2]
    names['predicted_role_LR'] = rd2l_predictions
    names.to_csv('rd2l_test.dat', index = False)

if __name__ == "__main__":
    get_roles('role_model.joblib', 'rd2l_fantasy.out')
