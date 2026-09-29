from fastapi import APIRouter, File, UploadFile, HTTPException
from starlette.concurrency import run_in_threadpool
from models.responses import Overview
from services.storage import MAX_BYTES, save_dataset, get_report

router = APIRouter(prefix="/api")

@router.get("/health")
def health():
    return {"status": "ok", "phase": 1}

@router.post("/upload", response_model=Overview, status_code=201)
async def upload(file: UploadFile = File(...)):
    try:
        content = await file.read(MAX_BYTES+1)
        if len(content) > MAX_BYTES: raise HTTPException(413, "Maximum upload size is 25 MB.")
        return await run_in_threadpool(save_dataset, content, file.filename or "dataset")
    finally: await file.close()

@router.get("/dataset/{dataset_id}/overview", response_model=Overview)
def overview(dataset_id: str):
    return get_report(dataset_id)["overview"]

@router.get("/dataset/{dataset_id}/{section}")
def section(dataset_id: str, section: str):
    if section not in {"preview", "quality", "statistics", "correlations", "visualizations"}:
        raise HTTPException(404, "Unknown dataset section.")
    return get_report(dataset_id)[section]
