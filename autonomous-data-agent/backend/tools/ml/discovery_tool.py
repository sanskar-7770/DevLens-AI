import numpy as np
from sklearn.cluster import KMeans
from sklearn.ensemble import IsolationForest
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from .data_preparation_tool import prepare, preprocessor, friendly, Unsuitable


def discover(df,types,task,columns):
    b=prepare(df,types,task,columns)
    if len(b['features'])<2: raise Unsuitable('Choose at least two usable inputs to compare records. For one numeric column, use the existing unusual-value check.')
    Z=preprocessor(b['X']).fit_transform(b['X'])
    unique=len(np.unique(Z,axis=0))
    if unique<3: raise Unsuitable('There are too few different records to discover useful groups or unusual combinations.')
    warnings=list(b['warnings']);groups=[];records=[];scores=[];factors=[]
    if task=='clustering':
        best=None
        for k in range(2,min(6,unique-1,len(Z)-1)+1):
            model=KMeans(n_clusters=k,random_state=42,n_init=5,max_iter=150)
            labels=model.fit_predict(Z)
            score=float(silhouette_score(Z,labels,sample_size=min(800,len(Z)),random_state=42))
            scores.append({'groups':k,'silhouette':score})
            if best is None or score>best[0]: best=(score,labels,k)
        score,labels,k=best
        for group in range(k):
            rows=b['work'].iloc[np.flatnonzero(labels==group)];details=[]
            for c in b['features']:
                if types[c]=='numerical':
                    value=float(rows[c].mean());overall=float(b['work'][c].mean());scale=float(b['work'][c].std())
                    if np.isfinite(value) and np.isfinite(scale) and scale>0: details.append((abs(value-overall)/scale,f"{friendly(c)} averages {value:.3g}, compared with {overall:.3g} across analyzed records."))
            details.sort(reverse=True)
            groups.append({'name':f'Group {group+1}','count':len(rows),'description':[t for _,t in details[:3]] or ['Grouped using the available input categories.']})
        names=[f'Group {i+1}' for i in labels]
        summary=f"This experiment divided {len(Z)} records into {k} groups with similar inputs."
        takeaway='Compare the measured group characteristics below to decide whether these groups are useful for your question.'
        reliability='Groups are descriptive suggestions, not known real-world categories. The number of groups was chosen by comparing separation within this dataset.'
        if score<.25:warnings.append('The groups overlap substantially in this experiment. Treat the boundaries as tentative.')
        technical={'algorithm':'K-Means','groups':k,'silhouette':score,'candidates':scores,'parameters':{'n_init':5,'max_iter':150}}
        facts=[summary]+[f"{g['name']}: {g['count']} records. "+' '.join(g['description']) for g in groups]
        chart_title='Visual view of the discovered groups'
        chart_summary={'kind':'bar','title':'Records in each group','x_label':'Group','y_label':'Records','data':[{'x':g['name'],'y':g['count']} for g in groups]}
    else:
        model=IsolationForest(n_estimators=100,max_samples=min(256,len(Z)),contamination='auto',random_state=42,n_jobs=1)
        labels=model.fit_predict(Z);risk=-model.score_samples(Z)
        unusual=labels==-1;count=int(unusual.sum());names=['Unusual' if x else 'Typical' for x in unusual]
        summary=f"{count} of {len(Z)} records have combinations of inputs that stand out in this experiment."
        takeaway='These records are not necessarily incorrect. Review their context before deciding whether any action is needed.'
        reliability='No known unusual-record labels were supplied, so this is an exploratory screen, not a measured detection accuracy or a probability of wrongdoing.'
        order=np.argsort(-risk);positions=[i for i in order if unusual[i]][:10]
        numeric=[c for c in b['features'] if types[c]=='numerical'][:6]
        for i in positions:
            row=b['work'].iloc[i]
            records.append({'row':int(b['work'].index[i])+1,'values':{c:row[c] for c in numeric}})
        for c in numeric:
            normal=b['work'].loc[~unusual,c].mean();odd=b['work'].loc[unusual,c].mean()
            if np.isfinite(normal) and np.isfinite(odd): groups.append({'name':friendly(c),'count':count,'description':[f"Flagged records average {odd:.3g}; remaining records average {normal:.3g}."]})
        facts=[summary,takeaway]+[g['name']+': '+g['description'][0] for g in groups[:3]]
        technical={'algorithm':'Isolation Forest','flagged':count,'parameters':{'n_estimators':100,'max_samples':min(256,len(Z)),'contamination':'auto'},'top_scores':[float(risk[i]) for i in positions]}
        chart_title='Where unusual records appear'
        chart_summary={'kind':'bar','title':'Records to review','x_label':'Result','y_label':'Records','data':[{'x':'Typical','y':len(Z)-count},{'x':'Unusual','y':count}]}
    projection=PCA(n_components=2,random_state=42).fit_transform(Z) if Z.shape[1]>=2 else np.column_stack([Z[:,0],np.zeros(len(Z))])
    indices=np.sort(np.random.default_rng(42).choice(len(Z),size=min(500,len(Z)),replace=False))
    chart={'kind':'groups','title':chart_title,'x_label':'Visual position','y_label':'Visual position','data':[{'x':float(projection[i,0]),'y':float(projection[i,1]),'group':names[i]} for i in indices]}
    warnings.append('The visual map compresses many inputs into two directions and may hide differences. At most 500 records are shown; group counts use all analyzed records.')
    technical.update({'projection':'2D PCA for visualization only; fitted after grouping/scoring','used_rows':len(Z),'source_rows':b['original_rows'],'features':b['features'],'excluded':b['excluded'],'seed':42})
    return {'kind':'ml','task':task,'target':None,'suitable':True,'title':'Find Similar Groups' if task=='clustering' else 'Find Unusual Records','summary':summary,'takeaway':takeaway,'reliability':reliability,'warnings':warnings,'factors':factors,'charts':[chart,chart_summary],'groups':groups,'records':records,'technical':technical,'facts':facts,'suggestions':['Compare the discovered patterns across a category column.','Show the average of a numeric input.','Which records should I investigate next?']}
