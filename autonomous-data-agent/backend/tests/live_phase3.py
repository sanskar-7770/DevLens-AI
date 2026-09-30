"""Opt-in real Gemini + local Phase 3 verification. Writes incremental evidence."""
import argparse
import json
from pathlib import Path
import httpx

parser=argparse.ArgumentParser();parser.add_argument('--base-url',default='http://127.0.0.1:8000');parser.add_argument('--agent',action='store_true');args=parser.parse_args()
root=Path(__file__).resolve().parents[2];target=root/'data/phase3-live-results.json';results=[]
def save(label,response):
    data=response.json();results.append({'test':label,'http':response.status_code,'response':data})
    target.write_text(json.dumps(results,indent=2),encoding='utf-8')
    if isinstance(data,dict):print(label,response.status_code,data.get('status',''),data.get('tools_used',''),data.get('answer',data.get('detail','')),flush=True)
    else: print(label,response.status_code,flush=True)
    return data
with httpx.Client(base_url=args.base_url,timeout=175) as c:
    datasets={}
    for filename in ['agent_developer_activity.csv','phase3_developer_synthetic.csv','phase3_housing_synthetic.csv']:
        p=root/'data'/filename
        data=save('Upload '+filename,c.post('/api/upload',files={'file':(filename,p.read_bytes())}));datasets[filename]=data['dataset_id']
    sample=datasets['agent_developer_activity.csv'];demo=datasets['phase3_developer_synthetic.csv'];housing=datasets['phase3_housing_synthetic.csv']
    for section in ['overview','preview','quality','statistics','correlations','visualizations']:
        save('Phase 1 '+section,c.get(f'/api/dataset/{sample}/{section}'))
    for ds,tool,cols in [(sample,'regression',['issue_resolution_hours']),(sample,'feature_importance',['issue_resolution_hours']),(sample,'classification',['build_success']),(demo,'classification',['build_success']),(demo,'clustering',[]),(demo,'anomaly_detection',[]),(housing,'regression',['sale_price'])]:
        save('Direct '+tool+' '+','.join(cols),c.post('/api/ml/analyze',json={'dataset_id':ds,'tool':tool,'columns':cols}))
    save('Phase 2 local average',c.post('/api/agent/analyze',json={'dataset_id':sample,'query':'What is average commits?'}))
    save('Phase 1 after ML',c.get(f'/api/dataset/{sample}/statistics'))
    if args.agent:
        session=None
        for q in ['Predict issue_resolution_hours.','What factors matter most for predicting issue_resolution_hours?','Can we predict build_success?','Find similar groups of developers.','Find unusual developer activity.','What is average commits?','Are commits related to bugs_reported?','Analyze issue resolution time over time.']:
            save('Agent '+q,c.post('/api/agent/analyze',json={'dataset_id':demo,'query':q}))
        for q in ['Predict issue_resolution_hours.','Which factor matters most?','Show me the top five.','Compare those across teams.']:
            r=save('Follow-up '+q,c.post('/api/agent/analyze',json={'dataset_id':demo,'query':q,'session_id':session}))
            session=r.get('session_id',session)
