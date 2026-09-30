"""Opt-in real Gemini smoke suite. Requires a running configured backend; consumes API quota.
From backend: python tests/live_agent_smoke.py --base-url http://127.0.0.1:8000
"""
import argparse
import json
from pathlib import Path
import httpx

QUERIES = [
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

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',default='http://127.0.0.1:8000')
    args=parser.parse_args()
    with httpx.Client(base_url=args.base_url,timeout=175) as client:
        status=client.get('/api/agent/status');status.raise_for_status()
        if not status.json()['configured']:
            raise SystemExit('Configure GEMINI_API_KEY in backend/.env and restart the backend before running live tests.')
        sample=Path(__file__).resolve().parents[2]/'data/agent_developer_activity.csv'
        response=client.post('/api/upload',files={'file':(sample.name,sample.read_bytes())});response.raise_for_status()
        dataset_id=response.json()['dataset_id']; results=[]
        for query in QUERIES:
            response=client.post('/api/agent/analyze',json={'dataset_id':dataset_id,'query':query})
            response.raise_for_status();result=response.json()
            assert result['iterations']<=6
            assert all(e['id'] for e in result['evidence'])
            results.append(result)
            print(query, '=>', result['status'], ', '.join(result['tools_used']))
        session=None
        for query in ['What variable is most strongly related to issue resolution time?','Show me a chart for that.','Are there any outliers?']:
            response=client.post('/api/agent/analyze',json={'dataset_id':dataset_id,'query':query,'session_id':session})
            response.raise_for_status();result=response.json();session=result['session_id'];results.append(result)
            print('Follow-up:',query,'=>',result['status'],', '.join(result['tools_used']))
        target=Path(__file__).resolve().parents[2]/'data/live-agent-results.json'
        target.write_text(json.dumps(results,indent=2),encoding='utf-8')
        print('Saved results for semantic review. Transport success alone does not establish answer quality.')

if __name__=='__main__':main()
