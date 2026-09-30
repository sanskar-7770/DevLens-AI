"""Validated public state and provider output contracts; no hidden reasoning fields."""
from typing import Any, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator

ToolName = Literal["inspect_dataset", "column_info", "statistics", "correlation", "outliers", "distribution", "categories", "trend", "group_comparison", "visualization", "ml_suitability", "regression", "classification", "clustering", "anomaly_detection", "feature_importance", "model_evaluation"]

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class AnalyzeRequest(StrictModel):
    dataset_id: UUID
    query: str = Field(min_length=1, max_length=2000)
    session_id: UUID | None = None

    @field_validator("query")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Enter an analytical question.")
        return value.strip()

class ToolArguments(StrictModel):
    columns: list[str] = Field(max_length=20)
    chart_type: Literal["histogram", "bar", "line", "scatter", "heatmap"] | None

class PlanStep(StrictModel):
    tool: ToolName
    columns: list[str] = Field(max_length=20)
    purpose: str = Field(max_length=200)

class AnalysisPlan(StrictModel):
    goal: str = Field(max_length=500)
    steps: list[PlanStep] = Field(max_length=6)

class Action(StrictModel):
    kind: Literal["tool", "finish"]
    tool: ToolName | None
    arguments: ToolArguments

class FindingDraft(StrictModel):
    evidence_ids: list[str] = Field(min_length=1, max_length=10)

class AnswerDraft(StrictModel):
    summary: str = Field(max_length=1200)
    findings: list[FindingDraft] = Field(max_length=8)
    potential_explanation: str = Field(max_length=1200)
    suggested_next_analysis: list[str] = Field(max_length=4)

class Evidence(StrictModel):
    id: str
    tool: str
    text: str

class Activity(StrictModel):
    action: str
    status: Literal["completed", "failed", "stopped"]
    tool: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    summary: str = ""

class AgentState(StrictModel):
    insights: list[dict[str, Any]] = Field(default_factory=list)
    dataset_id: str
    session_id: str
    user_query: str
    dataset_metadata: dict[str, Any] = Field(default_factory=dict)
    analysis_plan: AnalysisPlan | None = None
    current_step: str = "initializing"
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    observations: list[dict[str, Any]] = Field(default_factory=list)
    generated_charts: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    final_answer: str = ""
    iteration_count: int = 0
    status: Literal["running", "completed", "limited", "insufficient", "failed"] = "running"
    errors: list[str] = Field(default_factory=list)
    activities: list[Activity] = Field(default_factory=list)

class AnalyzeResponse(StrictModel):
    insights: list[dict[str, Any]] = Field(default_factory=list)
    source: Literal["local", "gemini"] = "gemini"
    model: str | None = None
    status: str
    dataset_id: str
    session_id: str
    query: str
    plan: list[PlanStep]
    activities: list[Activity]
    tools_used: list[str]
    iterations: int
    execution_seconds: float
    answer: str
    findings: list[str]
    evidence: list[Evidence]
    potential_explanation: str
    suggested_next_analysis: list[str]
    charts: list[dict[str, Any]]
    errors: list[str]


class MLRequest(StrictModel):
    dataset_id: UUID
    tool: Literal["ml_suitability", "regression", "classification", "clustering", "anomaly_detection", "feature_importance", "model_evaluation"]
    columns: list[str] = Field(default_factory=list, max_length=20)
    session_id: UUID | None = None
