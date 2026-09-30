import asyncio
import json
from pathlib import Path
import httpx
import pytest
from fastapi.testclient import TestClient
from main import app
from routes.agent import provider
from services import storage
from services.conversations import conversations
from services.llm_service import GeminiLLMService, LLMError

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'UPLOADS', tmp_path)
    conversations.sessions.clear()
    app.dependency_overrides.clear()
    def no_provider(): raise AssertionError("Local question called Gemini")
    app.dependency_overrides[provider] = lambda: no_provider
    with TestClient(app) as c: yield c
    app.dependency_overrides.clear()

@pytest.fixture
def dataset(client):
    data = b"developer,commits,pull_requests\nAda,2,1\nBo,8,3\nCy,8,\nDee,,2\n"
    return client.post('/api/upload',files={'file':('data.csv',data)}).json()['dataset_id']

@pytest.mark.parametrize('query,expected',[
    ('What is the average number of commits?','6.0'),
    ('What is the minimum commits?','2.0'),
    ('What is the maximum number of commits?','8.0'),
    ('sum of commits','18.0'),
    ('count commits','3 non-missing'),
    ('How many rows are in this dataset?','4 rows'),
    ('How many columns are in this dataset?','3 columns'),
    ('Which columns have missing values?','1 missing'),
    ('unique commits','2 distinct'),
    ('basic statistics commits','mean'),
    ('highest record commits','2 tied'),
    ('lowest record commits','1 tied'),
    ('Which developer has the most commits?','Bo'),
    ('What is the maximum number of pull requests?','3.0'),
    ('dataset column names','developer'),
    ('Summarize the dataset.','4 rows'),
])
def test_local(client,dataset,query,expected):
    r=client.post('/api/agent/analyze',json={'dataset_id':dataset,'query':query})
    assert r.status_code == 200, r.text
    d=r.json();assert d['source']=='local' and d['model'] is None
    assert expected in ' '.join(d['findings'])
    assert not conversations.sessions[d['session_id']].busy


def test_missing_identity_and_nulls(client):
    ds=client.post('/api/upload',files={'file':('x.csv',b'commits,other\n4,1\n4,2\n,3')}).json()['dataset_id']
    d=client.post('/api/agent/analyze',json={'dataset_id':ds,'query':'Which developer has the most commits?'}).json()
    assert d['status']=='insufficient' and 'no developer identity' in ' '.join(d['findings'])

@pytest.mark.parametrize('q',['mean commits for Ada','mean commits by developer','mean commits where commits > 3','mean commits and pull requests','mean imaginary','average commits excluding missing','average commits yesterday'])
def test_complex_not_misanswered(client,dataset,q):
    # The provider guard throws if dispatch reaches Gemini; this is a controlled server error, never a false local answer.
    r=client.post('/api/agent/analyze',json={'dataset_id':dataset,'query':q})
    assert r.status_code==500


def test_local_without_key(client,dataset,monkeypatch):
    app.dependency_overrides.clear()
    monkeypatch.delenv('GEMINI_API_KEY',raising=False);monkeypatch.delenv('LLM_API_KEY',raising=False)
    assert client.post('/api/agent/analyze',json={'dataset_id':dataset,'query':'mean commits'}).json()['source']=='local'
    r=client.post('/api/agent/analyze',json={'dataset_id':dataset,'query':'Find important patterns'})
    assert r.status_code==503 and 'locally' in r.json()['detail']


VALID={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps({'goal':'Inspect','steps':[]})}]}}]}

def run_service(handler, fallback=None):
    waits=[]
    async def sleep(delay):waits.append(delay)
    service=GeminiLLMService('private-key',model='primary',fallback_model=fallback,transport=httpx.MockTransport(handler),sleep=sleep)
    return service, waits

@pytest.mark.parametrize('status',[429,500,502,503,504])
def test_retries_and_verified_fallback(status,caplog):
    calls=[]
    def handler(r):
        calls.append((r.method,r.url.path))
        assert r.headers['x-goog-api-key']=='private-key'
        assert 'private-key' not in str(r.url)
        if r.method=='GET':return httpx.Response(200,json={'supportedGenerationMethods':['generateContent']})
        if 'primary:' in r.url.path:return httpx.Response(status,json={'error':{'message':'private-key must not be logged'}})
        return httpx.Response(200,json=VALID)
    service,waits=run_service(handler,'fallback')
    asyncio.run(service.create_plan({}))
    assert waits==[1,2]
    assert len([c for c in calls if c[0]=='POST'])==4
    assert service.model=='fallback' and service.used_models==['fallback']
    assert 'private-key' not in caplog.text

@pytest.mark.parametrize('status',[400,401,403,404])
def test_permanent_never_retried(status):
    calls=[]
    def handler(r):
        calls.append(r)
        if r.method=='GET':return httpx.Response(200,json={'supportedGenerationMethods':['generateContent']})
        return httpx.Response(status,json={'error':{}})
    service,waits=run_service(handler,'fallback')
    with pytest.raises(LLMError):asyncio.run(service.create_plan({}))
    assert len(calls)==2 and waits==[]

@pytest.mark.parametrize('error',[httpx.ReadTimeout,httpx.ConnectError])
def test_network_retry(error):
    calls=[]
    def handler(r):
        if r.method=='GET':return httpx.Response(200,json={'supportedGenerationMethods':['generateContent']})
        calls.append(r)
        if len(calls)<3:raise error('private-key')
        return httpx.Response(200,json=VALID)
    service,waits=run_service(handler)
    asyncio.run(service.create_plan({}))
    assert len(calls)==3 and waits==[1,2]


def test_incompatible_model_not_generated():
    calls=[]
    def handler(r):
        calls.append(r);return httpx.Response(200,json={'supportedGenerationMethods':['countTokens']})
    service,_=run_service(handler,'fallback')
    with pytest.raises(LLMError,match='does not support'):asyncio.run(service.create_plan({}))
    assert len(calls)==1


def test_provider_failure_controlled(client,dataset):
    calls=[]
    def handler(r):
        calls.append(r)
        if r.method=='GET':return httpx.Response(200,json={'supportedGenerationMethods':['generateContent']})
        return httpx.Response(503,json={'error':{'message':'private'}})
    service,waits=run_service(handler,'fallback')
    app.dependency_overrides[provider]=lambda:service
    r=client.post('/api/agent/analyze',json={'dataset_id':dataset,'query':'Find important patterns'})
    assert r.status_code==503 and 'locally' in r.json()['detail']
    assert waits==[1,2,1,2] and len([c for c in calls if c.method=='POST'])==6
    assert client.get('/api/health').status_code==200
    r=client.post('/api/agent/analyze',json={'dataset_id':dataset,'query':'mean commits'})
    assert r.status_code==200 and r.json()['source']=='local'


def test_all_missing_and_non_numeric(client):
    ds=client.post('/api/upload',files={'file':('x.csv',b'commits,team\n,A\n,B')}).json()['dataset_id']
    for q in ['mean commits','mean team']:
        d=client.post('/api/agent/analyze',json={'dataset_id':ds,'query':q}).json()
        assert d['source']=='local' and d['status']=='insufficient'


def test_local_history_and_ambiguous_columns(client):
    ds=client.post('/api/upload',files={'file':('x.csv',b'commits,Commits\n1,20\n3,40')}).json()['dataset_id']
    # Case-normalized collisions must not arbitrarily choose a metric.
    assert client.post('/api/agent/analyze',json={'dataset_id':ds,'query':'mean commits'}).status_code==500
    r=client.post('/api/agent/analyze',json={'dataset_id':ds,'query':'How many rows are in this dataset?'}).json()
    sid=r['session_id']
    assert conversations.sessions[sid].turns[-1]['answer']=='The dataset has 2 rows.'
    assert client.post('/api/agent/analyze',json={'dataset_id':ds,'query':'','session_id':sid}).status_code==422
