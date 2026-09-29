import logging
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from routes.datasets import router

app = FastAPI(title="DataAgent AI · Phase 1", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","), allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
app.include_router(router)

@app.exception_handler(Exception)
async def unexpected_error(request: Request, error: Exception):
    logging.exception("Dataset request failed", exc_info=error)
    return JSONResponse(status_code=500, content={"detail": "The dataset could not be processed. Please try a smaller file or check the server logs."})
