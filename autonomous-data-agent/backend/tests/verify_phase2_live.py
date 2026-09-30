"""Real HTTP verification; records source and actual response, never credentials."""
import argparse
import json
from pathlib import Path
import httpx

parser=argparse.ArgumentParser()
parser.add_argument('--base-url',default='http://127.0.0.1:8000')
args=parser.parse_args()
root=Path(__file__).resolve().parents[2]
results=[]
def record(label,response):
    item={'test':label,'http_status':response.status_code,'response':response.json()}
    results.append(item)
    (root/'data/phase2-verification.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    data=item['response'] if isinstance(item['response'],dict) else {}
    print(label,response.status_code,data.get('source','N/A'),data.get('answer',data.get('detail','OK')),flush=True)
    return data
with httpx.Client(base_url=args.base_url,timeout=175) as c:
    p=root/'data/agent_developer_activity.csv'
    upload=record('upload',c.post('/api/upload',files={'file':(p.name,p.read_bytes())}))
    ds=upload['dataset_id']
    for section in ['preview','statistics','quality','correlations','visualizations','overview']:
        record(section,c.get(f'/api/dataset/{ds}/{section}'))
    record('agent status',c.get('/api/agent/status'))
    for q in ['What is the average number of commits?','Which developer has the most commits?','What is the maximum number of commits?','How many rows are in this dataset?','Which columns have missing values?','Summarize the dataset.','What are the important patterns in this dataset?']:
        record(q,c.post('/api/agent/analyze',json={'dataset_id':ds,'query':q}))
