from sklearn.pipeline import Pipeline
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.dummy import DummyRegressor, DummyClassifier
from .data_preparation_tool import prepare, preprocessor, friendly
from .model_evaluation_tool import evaluate, outcome_details, overfitting_warning
from .feature_importance_tool import important_factors


def predict(df,types,task,columns):
    b=prepare(df,types,task,columns)
    X,y=b['X'],b['y']; train,test=b['train_idx'],b['test_idx']
    candidates=({'Linear Regression':LinearRegression(),'Random Forest':RandomForestRegressor(n_estimators=60,max_depth=8,min_samples_leaf=3,random_state=42,n_jobs=1)} if task=='regression' else {'Logistic Regression':LogisticRegression(max_iter=500,random_state=42),'Random Forest':RandomForestClassifier(n_estimators=60,max_depth=8,min_samples_leaf=3,random_state=42,n_jobs=1)})
    baseline=DummyRegressor(strategy='mean') if task=='regression' else DummyClassifier(strategy='most_frequent')
    labels=sorted(y.unique()) if task=='classification' else None
    baseline.fit(X.loc[train],y.loc[train]); baseline_metrics=evaluate(task,y.loc[test],baseline.predict(X.loc[test]),labels)
    comparisons=[];fitted={}
    for name, estimator in candidates.items():
        pipeline=Pipeline([('prepare',preprocessor(X)),('model',estimator)])
        pipeline.fit(X.loc[train],y.loc[train]);fitted[name]=pipeline
        comparisons.append({'name':name,'train':evaluate(task,y.loc[train],pipeline.predict(X.loc[train]),labels),'test':evaluate(task,y.loc[test],pipeline.predict(X.loc[test]),labels)})
    selected=min(comparisons,key=lambda r:r['test']['mae']) if task=='regression' else max(comparisons,key=lambda r:r['test']['f1'])
    model=fitted[selected['name']]; metrics=selected['test'];train_metrics=selected['train'];pred=model.predict(X.loc[test])
    factors,method=important_factors(model,b,task)
    warnings=list(b['warnings'])
    warnings.append('These same test records were used to compare methods, so the winning result may be optimistic. Verify it on a separate dataset before relying on it.')
    if overfitting_warning(task, train_metrics, metrics):
        warnings.append('The model learned the training data much better than it handled new data. Its predictions may therefore be less reliable on new records.')
    if (task=='regression' and (metrics['r2'] or 0)>.98) or (task=='classification' and metrics['accuracy']>.98):
        warnings.append('The test result is unusually strong. Check whether any input indirectly reveals the outcome before trusting it.')
    target=friendly(b['target']); unit=' hours' if b['target'].lower().endswith(('_hours',' hour',' hours')) else ' units of '+target
    charts=[];extra={}
    if task=='regression':
        better=metrics['mae']<baseline_metrics['mae']
        summary=f"Predictions for {target} were typically {metrics['mae']:.3g}{unit} away from the actual value in the test records."
        takeaway=f"The simple typical-value guess was {baseline_metrics['mae']:.3g}{unit} away on average. The tested model {'reduced' if better else 'did not reduce'} that difference."
        points=[{'x':float(a),'y':float(p)} for a,p in zip(y.loc[test].iloc[:200],pred[:200])]
        charts=[{'kind':'scatter','title':'Predictions compared with actual values','x_label':'Actual '+target,'y_label':'Predicted '+target,'data':points}]
        facts=[summary,takeaway,f"Learning records: {len(train)}; separate test records: {len(test)}."]
    else:
        correct=int((y.loc[test].to_numpy()==pred).sum());better=metrics['f1']>baseline_metrics['f1']
        summary=f"The model correctly predicted {correct} of {len(test)} test outcomes for {target}."
        baseline_correct=round(baseline_metrics['accuracy']*len(test))
        takeaway=f"Always guessing the most common outcome got {baseline_correct} of {len(test)} right. Across outcome types, the tested model {'performed better' if better else 'did not improve'} compared with this simple guess."
        extra=outcome_details(y.loc[test],pred,sorted(y.unique()))
        minority=y.loc[train].value_counts().idxmin(); row=next(r for r in extra['per_class'] if r['label']==minority)
        if row['support']:
            takeaway+=f" It found {row['recall']*100:.1f}% of test records with the less common training outcome '{minority}' ({row['support']} test examples)."
        charts=[{'kind':'bar','title':'How the test predictions turned out','x_label':'Test outcomes','y_label':'Records','data':[{'x':'Correct','y':correct},{'x':'Incorrect','y':len(test)-correct}]}]
        facts=[summary,takeaway]
    reliability=('The model beat the simple baseline on these held-out records. ' if better else 'This experiment did not beat the simple baseline on the comparison measure. Treat its predictions cautiously. ')+f"Only {len(test)} records were used for testing. This does not establish future accuracy or cause and effect."
    if factors and factors[0]['weight']>0: facts.append(f"{friendly(factors[0]['column'])} ranked highest among inputs used by this model; usefulness for prediction does not mean causation.")
    technical={'task':task,'target':b['target'],'selected_model':selected['name'],'selection_metric':'test MAE' if task=='regression' else 'test macro F1','metrics':metrics,'training_metrics':train_metrics,'baseline':baseline_metrics,'comparisons':comparisons,'train_rows':len(train),'test_rows':len(test),'train_row_positions':[int(i)+1 for i in train],'test_row_positions':[int(i)+1 for i in test],'split':b['split'],'seed':42,'features':b['features'],'excluded':b['excluded'],'importance_method':method,'outcomes':extra,'parameters':{'forest_trees':60,'forest_max_depth':8,'forest_min_leaf':3,'logistic_max_iterations':500},'source_rows':b['original_rows'],'used_rows':len(b['work'])}
    return {'kind':'ml','task':task,'target':b['target'],'suitable':True,'title':'Predict a Number' if task=='regression' else 'Predict an Outcome','summary':summary,'takeaway':takeaway,'reliability':reliability,'warnings':warnings,'factors':factors,'charts':charts,'groups':[],'records':[],'technical':technical,'facts':facts,'suggestions':[f"Which factors matter most for predicting {b['target']}?",f"How reliable is the prediction of {b['target']}?",'Find unusual records using several columns.']}
