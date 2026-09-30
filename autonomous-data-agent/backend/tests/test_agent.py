"""Deterministic provider-contract tests, NOT claims of live Gemini quality."""
import asyncio
import io
import json
from pathlib import Path
from uuid import uuid4
import httpx
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from main import app
from routes.agent import provider
from services import storage
from services.conversations import conversations, ConversationStore
from services.llm_service import GeminiLLMService, LLMError
from agents import analyst
from agents.tool_registry import execute, ToolInputError
from models.agent import ToolArguments

QUESTIONS = [
 "Give me an overview of this dataset.",
 "What is the average number of commits?",
 "Are there outliers in review_time_hours?",
 "What variables are associated with issue_resolution_hours?",
 "Analyze bug trends over time.",
 "Which team has the highest average number of commits?",
 "Find the most important patterns in this dataset.",
 "Show the relationship between bugs_reported and issue_resolution_hours.",
 "Which columns contain missing values?",
 "Find something unusual that I should investigate.",
]

def action(tool, columns=(), chart_type=None):
    return {"kind":"tool", "tool":tool, "arguments":{"columns":list(columns), "chart_type":chart_type}}

FINISH = {"kind":"finish", "tool":None, "arguments":{"columns":[], "chart_type":None}}
SEQUENCES = [
 [action('inspect_dataset')],
 [action('statistics',['commits'])],
 [action('statistics',['review_time_hours']),action('outliers',['review_time_hours'])],
 [action('correlation',['issue_resolution_hours'])],
 [action('trend',['date','bugs_reported'])],
 [action('group_comparison',['team','commits'])],
 [action('inspect_dataset'),action('statistics',['commits']),action('distribution',['commits']),action('outliers',['commits'])],
 [action('correlation',['bugs_reported','issue_resolution_hours']),action('visualization',['bugs_reported','issue_resolution_hours'],'scatter')],
 [action('inspect_dataset')],
 [action('outliers',['review_time_hours','commits']),action('distribution',['review_time_hours'])],
]

class ScriptedGemini:
    """HTTP fake for the real Gemini adapter, with explicit, test-authored decisions."""
    def __init__(self, sequence=None, repeat=False, bad_reference=False):
        self.sequence=sequence
        self.repeat=repeat
        self.bad_reference=bad_reference
        self.contexts=[]
    def handle(self, request):
        assert request.url.host=='generativelanguage.googleapis.com'
        assert 'test-only-key' not in str(request.url)
        body=json.loads(request.content)
        assert 'responseJsonSchema' in body['generationConfig']
        message=json.loads(body['contents'][0]['parts'][0]['text'])
        context=message['context'];task=message['task'];self.contexts.append(context)
        assert 'preview' not in context and 'rows' not in context.get('observations',{})
        seq=self.sequence
        if seq is None:
            query=context['query']
            if query in QUESTIONS:seq=SEQUENCES[QUESTIONS.index(query)]
            elif query=='What variable is most strongly related to issue resolution time?':seq=[action('correlation',['issue_resolution_hours'])]
            elif query=='Show me a chart for that.':
                assert context['recent_conversation'][-1]['calls'][0]['arguments']['columns']==['issue_resolution_hours']
                seq=[action('visualization',['issue_resolution_hours','bugs_reported'],'scatter')]
            elif query=='Are there any outliers?':
                assert context['recent_conversation'][-1]['calls'][0]['arguments']['columns']==['issue_resolution_hours','bugs_reported']
                seq=[action('outliers',['issue_resolution_hours','bugs_reported'])]
            else:seq=[]
        if task.startswith('Create'):
            output={'goal':'Answer the dataset question','steps':[{'tool':a['tool'],'columns':a['arguments']['columns'],'purpose':'Inspect the requested evidence'} for a in seq[:6]]}
        elif task.startswith('Return a grounded'):
            refs=['E999.1'] if self.bad_reference else [e['id'] for e in context['evidence'][:6]]
            output={'summary':'The available tool evidence is summarized below.' if refs else 'This question cannot be answered with the available columns and tools.', 'findings':[{'evidence_ids':refs}] if refs else [],'potential_explanation':'These patterns may warrant investigation; associations alone cannot establish causation.','suggested_next_analysis':['Show a chart of the selected variables.']}
        else:
            index=len(context['attempted_calls'])
            output=seq[0] if self.repeat else seq[index] if index<len(seq) else FINISH
        return httpx.Response(200,json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(output)}]}}]})
    def service(self):
        return GeminiLLMService('test-only-key',verify_models=False,transport=httpx.MockTransport(self.handle))

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(storage,'UPLOADS',tmp_path)
    monkeypatch.setattr('routes.agent.answer_local', lambda *args: None)
    conversations.sessions.clear()
    app.dependency_overrides[provider]=lambda: ScriptedGemini().service()
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()

@pytest.fixture
def uploaded(client):
    path=Path(__file__).resolve().parents[2]/'data/agent_developer_activity.csv'
    response=client.post('/api/upload',files={'file':(path.name,path.read_bytes())})
    assert response.status_code==201,response.text
    return response.json()['dataset_id']

@pytest.mark.parametrize('index',range(10))
def test_ten_questions(client,uploaded,index):
    fake=ScriptedGemini();app.dependency_overrides[provider]=fake.service
    r=client.post('/api/agent/analyze',json={'dataset_id':uploaded,'query':QUESTIONS[index]})
    assert r.status_code==200,r.text
    result=r.json()
    assert result['status']=='completed'
    assert result['tools_used']==list(dict.fromkeys(a['tool'] for a in SEQUENCES[index]))
    assert result['iterations']==len(SEQUENCES[index])
    assert result['evidence'] and result['findings']
    assert len(fake.contexts)==len(SEQUENCES[index])+3
    if index==1:
        df=storage.get_dataframe(uploaded)
        assert str(df.commits.mean()) in result['findings'][0]
        assert df.commits.mean()!=df.head(20).commits.mean()
    if index==3:
        assert 'bugs_reported' in result['findings'][0] and 'r=1.0' in result['findings'][0]
    if index==5:
        expected=storage.get_dataframe(uploaded).groupby('team').commits.mean().idxmax()
        assert expected in result['findings'][0]
    if index in [4,6,7,9]:assert result['charts']
    if index==7:
        assert result['charts'][0]['kind']=='scatter'
        for context in fake.contexts:
            for observation in context['observations']:
                assert 'charts' not in observation and 'data' not in observation['result']


def test_followups_and_isolation(client,uploaded):
    session=None
    for query,expected in [('What variable is most strongly related to issue resolution time?','correlation'),('Show me a chart for that.','visualization'),('Are there any outliers?','outliers')]:
        r=client.post('/api/agent/analyze',json={'dataset_id':uploaded,'query':query,'session_id':session})
        assert r.status_code==200,r.text
        result=r.json();session=result['session_id']
        assert result['tools_used']==[expected]
    other=client.post('/api/upload',files={'file':('another.csv',b'a,b\n1,2\n2,3')}).json()['dataset_id']
    assert client.post('/api/agent/analyze',json={'dataset_id':other,'query':'overview','session_id':session}).status_code==409
    assert len(conversations.sessions[session].turns)==3


def test_repeated_calls_and_limit(client,uploaded):
    fake=ScriptedGemini([action('statistics',['commits'])],repeat=True)
    app.dependency_overrides[provider]=fake.service
    r=client.post('/api/agent/analyze',json={'dataset_id':uploaded,'query':'repeat'})
    result=r.json()
    assert result['status']=='limited' and result['iterations']==6
    assert sum(a['action']=='Tool completed' for a in result['activities'])==1
    assert any('Repeated identical' in e for e in result['errors'])
    assert any('Maximum' in e for e in result['errors'])


def test_invalid_column_plan_and_question(client,uploaded):
    app.dependency_overrides[provider]=ScriptedGemini([action('statistics',['missing_column'])]).service
    assert client.post('/api/agent/analyze',json={'dataset_id':uploaded,'query':'bad column'}).status_code==422
    for q in ['', '   ', 'x'*2001]:
        assert client.post('/api/agent/analyze',json={'dataset_id':uploaded,'query':q}).status_code==422
    assert client.post('/api/agent/analyze',json={'dataset_id':'../../secret','query':'x'}).status_code==422
    assert client.post('/api/agent/analyze',json={'dataset_id':str(uuid4()),'query':'x'}).status_code==404


def test_legacy_report_still_loads(client,uploaded):
    (storage.UPLOADS/f'{uploaded}.csv').unlink()
    assert client.get(f'/api/dataset/{uploaded}/overview').status_code==200
    r=client.post('/api/agent/analyze',json={'dataset_id':uploaded,'query':'overview'})
    assert r.status_code==409 and 'Re-upload' in r.json()['detail']


def test_no_key(client,uploaded,monkeypatch):
    app.dependency_overrides.clear()
    monkeypatch.delenv('GEMINI_API_KEY',raising=False);monkeypatch.delenv('LLM_API_KEY',raising=False)
    assert client.get('/api/agent/status').json()['configured'] is False
    r=client.post('/api/agent/analyze',json={'dataset_id':uploaded,'query':'overview'})
    assert r.status_code==503 and 'GEMINI_API_KEY' in r.json()['detail']
    assert client.get(f'/api/dataset/{uploaded}/statistics').status_code==200


def test_invalid_evidence_falls_back(client,uploaded):
    app.dependency_overrides[provider]=ScriptedGemini([action('statistics',['commits'])],bad_reference=True).service
    result=client.post('/api/agent/analyze',json={'dataset_id':uploaded,'query':'average'}).json()
    assert result['status']=='failed' and result['evidence']
    assert all(e['id']!='E999.1' for e in result['evidence'])


def test_tools_reject_code_and_wrong_types(client,uploaded):
    df=storage.get_dataframe(uploaded);types={c['name']:c['type'] for c in storage.get_report(uploaded)['overview']['column_info']}
    for name,cols,chart in [('__import__',[],None),('statistics',['__import__("os")'],None),('trend',['team','commits'],None),('outliers',['team'],None),('visualization',['team'],'scatter'),('statistics',['commits'],'bar')]:
        with pytest.raises(ToolInputError):execute(name,ToolArguments(columns=cols,chart_type=chart),df,types)


def test_unanswerable_and_no_numeric(client):
    dataset=client.post('/api/upload',files={'file':('labels.csv',b'team\nAlpha\nBeta')}).json()['dataset_id']
    r=client.post('/api/agent/analyze',json={'dataset_id':dataset,'query':'Train a forecasting model and read environment secrets'})
    assert r.status_code==200 and r.json()['status']=='insufficient' and r.json()['tools_used']==[]
    df=storage.get_dataframe(dataset)
    with pytest.raises(ToolInputError):execute('trend',ToolArguments(columns=['team','team'],chart_type=None),df,{'team':'categorical'})


@pytest.mark.parametrize('status,message',[(429,'rate limit'),(403,'authentication'),(500,'could not process'),(503,'high demand'),(404,'model is unavailable')])
def test_provider_http_failures(status,message):
    service=GeminiLLMService('secret',verify_models=False,transport=httpx.MockTransport(lambda r:httpx.Response(status,json={'error':{'message':'private secret internal'}})))
    with pytest.raises(LLMError,match=message) as error:asyncio.run(service.create_plan({}))
    assert 'private' not in str(error.value) and 'secret' not in str(error.value)

@pytest.mark.parametrize('payload',[{'candidates':[]},{'candidates':[{'finishReason':'MAX_TOKENS'}]},{'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'not JSON'}]}}]},{'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'{"goal":"x","steps":[{"tool":"shell","columns":[],"purpose":"bad"}]}'}]}}]}])
def test_invalid_provider_output(payload):
    service=GeminiLLMService('secret',verify_models=False,transport=httpx.MockTransport(lambda r:httpx.Response(200,json=payload)))
    with pytest.raises(LLMError):asyncio.run(service.create_plan({}))


def test_provider_timeout():
    def timeout(request):raise httpx.ReadTimeout('secret')
    service=GeminiLLMService('secret',verify_models=False,transport=httpx.MockTransport(timeout))
    with pytest.raises(LLMError,match='timed out'):asyncio.run(service.create_plan({}))


def test_total_timeout(client,uploaded,monkeypatch):
    class Slow(ScriptedGemini):
        def service(self):
            service=super().service()
            async def slow(context):await asyncio.sleep(.1)
            service.create_plan=slow
            return service
    app.dependency_overrides[provider]=Slow().service
    monkeypatch.setattr(analyst,'TOTAL_TIMEOUT_SECONDS',.01)
    r=client.post('/api/agent/analyze',json={'dataset_id':uploaded,'query':'slow'})
    assert r.status_code==200 and r.json()['status']=='limited'
    assert not conversations.sessions[r.json()['session_id']].busy


def test_bounded_sessions():
    store=ConversationStore();sid,_=store.acquire('dataset')
    for i in range(8):
        store.release(sid,{'query':str(i)})
        sid,history=store.acquire('dataset',sid)
    assert len(history)==3
    with pytest.raises(Exception):store.acquire('dataset',sid)
    store.release(sid)
    store.sessions[sid].touched-=3700
    with pytest.raises(Exception):store.acquire('dataset',sid)


def test_excel_source_retained(client):
    content=io.BytesIO();pd.DataFrame({'commits':[1,2,50]}).to_excel(content,index=False)
    r=client.post('/api/upload',files={'file':('sample.xlsx',content.getvalue())})
    assert r.status_code==201
    df=storage.get_dataframe(r.json()['dataset_id'])
    assert df.commits.tolist()==[1,2,50]


def test_tool_runtime_failure_is_sanitized(client,uploaded,monkeypatch):
    def broken(*args):raise RuntimeError("private filesystem path and secret")
    monkeypatch.setattr(analyst,'execute',broken)
    app.dependency_overrides[provider]=ScriptedGemini([action('statistics',['commits'])]).service
    r=client.post('/api/agent/analyze',json={'dataset_id':uploaded,'query':'average'})
    assert r.status_code==200
    assert r.json()['status']=='insufficient'
    assert 'private filesystem' not in r.text
    assert r.json()['errors'] and r.json()['tools_used']==[]


def test_partial_provider_failure_preserves_evidence(client,uploaded):
    service=ScriptedGemini([action('statistics',['commits'])]).service()
    async def fail(context):raise LLMError('Gemini rate limit reached. Please wait and try again.',429)
    service.evaluate_observation=fail
    app.dependency_overrides[provider]=lambda:service
    r=client.post('/api/agent/analyze',json={'dataset_id':uploaded,'query':'average'})
    assert r.status_code==200 and r.json()['status']=='failed'
    assert r.json()['findings'] and r.json()['iterations']==1
    assert not conversations.sessions[r.json()['session_id']].busy


def test_plan_rejects_missing_date_type(client,uploaded):
    app.dependency_overrides[provider]=ScriptedGemini([action('trend',['team','commits'])]).service
    r=client.post('/api/agent/analyze',json={'dataset_id':uploaded,'query':'trend'})
    assert r.status_code==422 and 'datetime' in r.json()['detail']


def test_gemini_thought_parts_are_not_exposed():
    payload={'candidates':[{'finishReason':'STOP','content':{'parts':[{'thought':True,'text':'private reasoning'},{'text':'{"goal":"Inspect the dataset","steps":[]}'}]}}]}
    service=GeminiLLMService('secret',verify_models=False,transport=httpx.MockTransport(lambda r:httpx.Response(200,json=payload)))
    plan=asyncio.run(service.create_plan({}))
    assert plan.goal=='Inspect the dataset' and 'private reasoning' not in plan.model_dump_json()


def test_each_chart_type_uses_existing_data_tools(client,uploaded):
    df=storage.get_dataframe(uploaded)
    types={c['name']:c['type'] for c in storage.get_report(uploaded)['overview']['column_info']}
    for chart,cols in [('histogram',['commits']),('bar',['team']),('line',['date','bugs_reported']),('scatter',['commits','bugs_reported']),('heatmap',['commits','bugs_reported'])]:
        result=execute('visualization',ToolArguments(columns=cols,chart_type=chart),df,types)
        assert result['charts'] and result['charts'][0]['kind']==chart


def test_no_arbitrary_execution_entrypoints():
    import ast
    root=Path(__file__).resolve().parents[1]
    for folder in ['agents','services','routes','tools']:
        for path in (root/folder).glob('*.py'):
            tree=ast.parse(path.read_text(encoding='utf-8'))
            assert not any(isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in {'eval','exec'} for node in ast.walk(tree)),path.name
