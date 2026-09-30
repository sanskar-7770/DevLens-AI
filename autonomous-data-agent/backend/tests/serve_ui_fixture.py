"""Manual UI test server only. Never used by main.py or production configuration.
Run from backend: python -m uvicorn tests.serve_ui_fixture:fixture_app --port 8001
Serves the real production frontend build with a scripted Gemini HTTP transport.
This verifies rendering and orchestration, not live provider intelligence.
"""
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from main import app
from routes.agent import provider
from tests.test_agent import ScriptedGemini

app.dependency_overrides[provider] = lambda: ScriptedGemini().service()
app.mount("/", StaticFiles(directory=Path(__file__).resolve().parents[2]/"frontend/dist", html=True), name="ui-test")
fixture_app = app
