import numpy as np
from sklearn.inspection import permutation_importance


def important_factors(model, bundle, task):
    origins=bundle['origins']; totals={c:0.0 for c in bundle['features']}
    estimator=model.named_steps['model']
    if hasattr(estimator,'feature_importances_'):
        names=model.named_steps['prepare'].get_feature_names_out()
        for name,value in zip(names,estimator.feature_importances_):
            expanded=name.split('__',1)[1]
            key=next((k for k in sorted(origins,key=len,reverse=True) if expanded==k or expanded.startswith(k+'_')),None)
            if key: totals[origins[key]]+=float(value)
        method='tree impurity reduction (training data); categorical expansions aggregated'
    else:
        X=bundle['X'].loc[bundle['test_idx']].head(600);y=bundle['y'].loc[X.index]
        result=permutation_importance(model,X,y,n_repeats=3,random_state=42,n_jobs=1,scoring='neg_mean_absolute_error' if task=='regression' else 'f1_macro')
        for name,value in zip(X.columns,result.importances_mean): totals[origins[name]]+=float(value)
        method='held-out permutation importance; three repeats; date parts aggregated'
    positive=sum(max(0,v) for v in totals.values())
    ranking=[{'column':c,'weight':max(0,v)/positive if positive else 0,'raw':v} for c,v in sorted(totals.items(),key=lambda item:item[1],reverse=True)]
    return ranking, method
