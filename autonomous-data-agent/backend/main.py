import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from routes.datasets import router
from routes.agent import router as agent_router
from routes.ml import router as ml_router

load_dotenv(Path(__file__).resolve().parent / ".env", override=False)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)

app = FastAPI(title="DataAgent AI · Phase 3", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","), allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
app.include_router(router)
app.include_router(agent_router)
app.include_router(ml_router)

@app.exception_handler(Exception)
async def unexpected_error(request: Request, error: Exception):
    logging.exception("Dataset request failed", exc_info=error)
    return JSONResponse(status_code=500, content={"detail": "The dataset could not be processed. Please try a smaller file or check the server logs."})
