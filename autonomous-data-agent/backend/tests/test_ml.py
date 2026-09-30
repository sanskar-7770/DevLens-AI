import io
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LinearRegression
from main import app
from services import storage
from services.conversations import conversations
from routes.agent import provider
from tools.dataset_inspector import detect_column_types
from tools.ml.data_preparation_tool import prepare, preprocessor, Unsuitable, infer_task
from tools.ml.service import run_ml
from agents.tool_registry import execute, TOOLS, ToolInputError
from models.agent import ToolArguments
from tests.test_agent import ScriptedGemini, action

@pytest.fixture
def housing():
    rng=np.random.default_rng(42);n=180
    area=rng.uniform(30,220,n);age=rng.integers(1,65,n)
    return pd.DataFrame({'record_id':range(n),'area':area,'age':age,'region':rng.choice(['North','South','West'],n),'price':area*1800-age*800+rng.normal(0,16000,n)})

@pytest.fixture
def outcomes(housing):
    frame=housing.drop(columns='price').copy()
    rng=np.random.default_rng(7)
    frame['renewed']=np.where(frame.area+rng.normal(0,60,len(frame))>65,'yes','no')
    return frame


def test_regression_baseline_importance_and_integrity(housing):
    original=housing.copy(deep=True);types=detect_column_types(housing)
    result=run_ml('regression',housing,types,['price'])
    assert result['suitable'],result
    t=result['technical'];assert len(t['comparisons'])==2 and t['metrics']['mae']<t['baseline']['mae']
    assert set(t['train_row_positions']).isdisjoint(t['test_row_positions'])
    assert t['train_rows']+t['test_rows']==len(housing)
    assert 'price' not in t['features'] and 'record_id' not in t['features']
    assert len(result['suggestions'])>=2 and result['charts'][0]['kind']=='scatter'
    assert result['factors'][0]['column']=='area'
    pd.testing.assert_frame_equal(housing,original)
    json.dumps(result,allow_nan=False)


def test_classification_imbalance_matrix(outcomes):
    r=run_ml('classification',outcomes,detect_column_types(outcomes),['renewed']);assert r['suitable'],r
    t=r['technical'];assert t['split']=='stratified random'
    assert sum(map(sum,t['outcomes']['matrix']))==t['test_rows']
    assert {'accuracy','precision','recall','f1'}<=set(t['metrics'])
    assert 'Most records' in ' '.join(r['warnings'])
    assert len(t['comparisons'])==2 and t['baseline']['accuracy']>0


def test_leakage_only_training_data(housing):
    housing['answer_copy']=housing.price
    housing['transformed']=housing.price*3+8
    housing['empty']=np.nan
    types=detect_column_types(housing);b=prepare(housing,types,'regression',['price'])
    assert {'answer_copy','transformed','empty','record_id'}<=set(b['excluded'])
    assert b['excluded']['transformed']=='almost exactly mirrors the outcome'
    changed=housing.copy();changed.loc[b['test_idx'],'price']*=100
    b2=prepare(changed,types,'regression',['price']);assert b2['features']==b['features']
    assert b2['excluded']==b['excluded']


def test_preprocess_fits_training_only(housing):
    housing.loc[0:15,'area']=np.nan
    b=prepare(housing,detect_column_types(housing),'regression',['price'])
    prep=preprocessor(b['X']);prep.fit(b['X'].loc[b['train_idx']])
    columns=b['X'].select_dtypes(include='number').columns
    np.testing.assert_allclose(prep.named_transformers_['numeric'].named_steps['impute'].statistics_,b['X'].loc[b['train_idx'],columns].median())
    X=b['X'].loc[b['test_idx']].copy();cat=X.select_dtypes(exclude='number').columns[0];X[cat]='never-seen'
    assert np.isfinite(prep.transform(X)).all()


def test_time_split_and_datetime(housing):
    housing['date']=pd.date_range('2025-01-01',periods=len(housing)).astype(str)
    b=prepare(housing,detect_column_types(housing),'regression',['price'])
    assert b['split']=='chronological'
    assert housing.loc[b['train_idx'],'date'].max()<housing.loc[b['test_idx'],'date'].min()
    assert any('_dayofweek' in c for c in b['X'])

@pytest.mark.parametrize('tool',['clustering','anomaly_detection'])
def test_discovery(housing,tool):
    original=housing.copy(deep=True)
    r=run_ml(tool,housing,detect_column_types(housing),[]);assert r['suitable'],r
    assert r['charts'][0]['kind']=='groups' and len(r['charts'][0]['data'])<=500
    assert len(r['suggestions'])>=2 and 'not' in r['reliability']
    if tool=='clustering':assert sum(g['count'] for g in r['groups'])==len(housing) and 2<=len(r['groups'])<=6
    else: assert 'probability' in r['reliability']
    pd.testing.assert_frame_equal(housing,original)

@pytest.mark.parametrize('tool,target',[('regression','missing'),('classification','region')])
def test_unsuitable_small(housing,tool,target):
    r=run_ml(tool,housing.head(8),detect_column_types(housing),[target]);assert not r['suitable'] and r['technical']=={}


def test_single_class(outcomes):
    outcomes['renewed']='yes';r=run_ml('classification',outcomes,detect_column_types(outcomes),['renewed'])
    assert not r['suitable'] and 'one outcome' in r['summary']


def test_constants_and_high_cardinality(housing):
    housing['constant']=1;housing['text']=['label'+str(i) for i in range(len(housing))]
    b=prepare(housing,detect_column_types(housing),'regression',['price'])
    assert 'constant' in b['excluded'] and 'text' in b['excluded']


def test_suitability_and_alias_cache(housing):
    types=detect_column_types(housing);args=ToolArguments(columns=['price'],chart_type=None);cache={}
    r=execute('regression',args,housing,types,cache)
    assert execute('feature_importance',args,housing,types,cache) is r
    assert execute('model_evaluation',args,housing,types,cache) is r
    suitable=run_ml('ml_suitability',housing,types,['price']);assert suitable['suitable'] and 'No model' in suitable['reliability']
    assert infer_task(housing,types,'price')=='regression'
    with pytest.raises(ToolInputError):execute('regression',ToolArguments(columns=['price','price'],chart_type=None),housing,types)


def test_sample_leakage_flag():
    df=pd.read_csv(Path(__file__).resolve().parents[2]/'data/agent_developer_activity.csv')
    r=run_ml('regression',df,detect_column_types(df),['issue_resolution_hours'])
    assert r['suitable'],r
    assert 'bugs_reported' in r['technical']['excluded']
    assert r['technical']['split']=='chronological'


def test_sampling(housing,monkeypatch):
    monkeypatch.setattr('tools.ml.data_preparation_tool.MAX_ROWS',100)
    b=prepare(housing,detect_column_types(housing),'regression',['price'])
    assert len(b['work'])==100 and 'sample' in ' '.join(b['warnings'])


def test_api_and_agent_integration(housing,tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'UPLOADS',tmp_path);conversations.sessions.clear()
    with TestClient(app) as client:
        ds=client.post('/api/upload',files={'file':('housing.csv',housing.to_csv(index=False).encode())}).json()['dataset_id']
        before=client.get(f'/api/dataset/{ds}/statistics').json()
        r=client.post('/api/ml/analyze',json={'dataset_id':ds,'tool':'regression','columns':['price']})
        assert r.status_code==200,r.text
        assert r.json()['insights'][0]['suitable'] and r.json()['source']=='local'
        assert client.get(f'/api/dataset/{ds}/statistics').json()==before
        assert client.post('/api/ml/analyze',json={'dataset_id':ds,'tool':'shell','columns':[]}).status_code==422
        assert client.post('/api/ml/analyze',json={'dataset_id':ds,'tool':'regression','columns':['unknown']}).status_code==422
        fake=ScriptedGemini([action('regression',['price'])]);app.dependency_overrides[provider]=fake.service
        try:
            result=client.post('/api/agent/analyze',json={'dataset_id':ds,'query':'Predict price.'}).json()
            assert result['status']=='completed' and result['insights'][0]['task']=='regression'
            assert result['tools_used']==['regression']
            assert all('train_row_positions' not in str(c) and 'Predicted Price' not in str(c) for c in fake.contexts)
        finally:app.dependency_overrides.clear()


def test_overfit_warning_heuristics():
    from tools.ml.model_evaluation_tool import overfitting_warning
    assert overfitting_warning('regression',{'mae':1},{'mae':4})
    assert overfitting_warning('classification',{'f1':.98},{'f1':.6})
    assert not overfitting_warning('regression',{'mae':3},{'mae':3.1})


def test_classification_relabelled_leakage(outcomes):
    outcomes['proxy']=outcomes.renewed.map({'yes':'green','no':'red'})
    b=prepare(outcomes,detect_column_types(outcomes),'classification',['renewed'])
    assert 'proxy' in b['excluded']
