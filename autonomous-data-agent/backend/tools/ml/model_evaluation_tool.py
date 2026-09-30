import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, accuracy_score, precision_recall_fscore_support, confusion_matrix


def evaluate(task, actual, predicted, labels=None):
    if task == 'regression':
        return {'mae':float(mean_absolute_error(actual,predicted)), 'rmse':float(np.sqrt(mean_squared_error(actual,predicted))), 'r2':float(r2_score(actual,predicted)) if len(actual)>1 and np.var(actual)>0 else None}
    precision,recall,f1,_=precision_recall_fscore_support(actual,predicted,labels=labels,average='macro',zero_division=0)
    return {'accuracy':float(accuracy_score(actual,predicted)), 'precision':float(precision),'recall':float(recall),'f1':float(f1)}


def outcome_details(actual, predicted, labels):
    p,r,f,s=precision_recall_fscore_support(actual,predicted,labels=labels,zero_division=0)
    return {'labels':list(labels),'matrix':confusion_matrix(actual,predicted,labels=labels).tolist(), 'per_class':[{'label':str(label),'precision':float(p[i]),'recall':float(r[i]),'f1':float(f[i]),'support':int(s[i])} for i,label in enumerate(labels)]}


def overfitting_warning(task, train, test):
    return (task == 'regression' and test['mae'] > 2 * max(train['mae'], 1e-9)) or (task == 'classification' and train['f1'] - test['f1'] > .15)
