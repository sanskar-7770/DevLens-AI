import time
import logging
from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool
from models.agent import MLRequest, AnalyzeResponse, ToolArguments, Activity
from services.storage import get_report, get_dataframe
from services.conversations import conversations
from agents.tool_registry import execute, ToolInputError
from agents.evidence import facts, provider_result

router=APIRouter(prefix="/api/ml",tags=["Predictions and patterns"])
logger=logging.getLogger("dataagent.ml")

@router.post('/analyze',response_model=AnalyzeResponse)
async def analyze_ml(request: MLRequest):
    start=time.monotonic();dataset_id=str(request.dataset_id)
    report=await run_in_threadpool(get_report,dataset_id)
    df=await run_in_threadpool(get_dataframe,dataset_id)
    types={c['name']:c['type'] for c in report['overview']['column_info']}
    sid,history=conversations.acquire(dataset_id,str(request.session_id) if request.session_id else None)
    turn=None
    try:
        args=ToolArguments(columns=request.columns,chart_type=None)
        output=await run_in_threadpool(execute,request.tool,args,df,types)
        card=output['result'];evidence=facts(request.tool,card,1)
        status='completed' if card['suitable'] else 'insufficient'
        query=card['title']+(': '+str(card['target']) if card['target'] else '')
        turn={'query':query,'answer':card['summary'],'calls':[{'tool':request.tool,'arguments':args.model_dump()}],'evidence':[e.model_dump() for e in evidence],'status':status,'ml_context':provider_result(output)}
        logger.info('ml_completed dataset=%s tool=%s status=%s duration=%.2f',dataset_id,request.tool,status,time.monotonic()-start)
        return AnalyzeResponse(source='local',status=status,dataset_id=dataset_id,session_id=sid,query=query,plan=[],activities=[Activity(action='Checked data and prepared results',status='completed',tool=request.tool)],tools_used=[request.tool],iterations=1,execution_seconds=round(time.monotonic()-start,2),answer=card['summary'],findings=card['facts'],evidence=evidence,potential_explanation='',suggested_next_analysis=card['suggestions'],charts=[],errors=[],insights=[card])
    except ToolInputError as error:
        raise HTTPException(422,str(error)) from None
    except Exception:
        logger.warning('ml_failed dataset=%s tool=%s',dataset_id,request.tool)
        raise HTTPException(422,'We could not complete this experiment. Try fewer columns or another outcome.') from None
    finally:
        conversations.release(sid,turn)
