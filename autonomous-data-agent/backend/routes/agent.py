import asyncio
import logging
import os
from fastapi import APIRouter, Depends, HTTPException
from starlette.concurrency import run_in_threadpool
from models.agent import AnalyzeRequest, AnalyzeResponse
from services.storage import get_dataframe, get_report
from services.llm_service import get_llm_service, configuration, LLMError
from services.conversations import conversations
from agents.analyst import analyze
from services.local_analytics import answer_local

router = APIRouter(prefix="/api/agent", tags=["Agent"])
slots = asyncio.Semaphore(2)
logger = logging.getLogger("dataagent.agent")

def provider():
    # Resolve credentials only after local analytics has had a chance to answer.
    return get_llm_service

@router.get("/status")
def status():
    name, key, model = configuration()
    return {"provider": name, "model": model, "configured": bool(key) and name == "gemini",
            "max_iterations": 6, "history_turns": 3, "local_available": True, "fallback_model": os.getenv("GEMINI_FALLBACK_MODEL") or None}

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_dataset(request: AnalyzeRequest, service=Depends(provider)):
    if slots.locked():
        raise HTTPException(429, "Two analyses are already running. Please try again shortly.")
    async with slots:
        dataset_id = str(request.dataset_id)
        report = await run_in_threadpool(get_report, dataset_id)
        df = await run_in_threadpool(get_dataframe, dataset_id)
        session_id, history = conversations.acquire(dataset_id, str(request.session_id) if request.session_id else None)
        turn = None
        try:
            local = await run_in_threadpool(answer_local, request, df, report, session_id)
            if local is not None:
                result, turn = local
                logger.info("local_completed dataset=%s status=%s duration=%s", dataset_id, result.status, result.execution_seconds)
                return result
            if callable(service):
                service = service()
            result, turn = await analyze(request, df, report, service, session_id, history)
            return result
        except LLMError as error:
            logger.warning("agent_provider_failed dataset=%s status=%s", dataset_id, error.status_code)
            raise HTTPException(error.status_code, str(error) + " Basic statistical questions can still be answered locally.") from None
        except Exception:
            logger.warning("agent_failed dataset=%s", dataset_id)
            raise HTTPException(500, "Agent analysis failed safely. Please retry with a narrower question.") from None
        finally:
            conversations.release(session_id, turn)
