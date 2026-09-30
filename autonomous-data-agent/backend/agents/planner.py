from agents.tool_registry import TOOLS, validate, ToolInputError
from models.agent import ToolArguments
from services.llm_service import LLMError

async def create_plan(service, context, types):
    plan = await service.create_plan(context)
    for step in plan.steps:
        spec = TOOLS[step.tool]
        if any(c not in types for c in step.columns):
            raise LLMError("The proposed plan references an unknown column. Ask using the dataset's exact column names.", 422)
        if not spec.minimum <= len(step.columns) <= spec.maximum:
            raise LLMError("The proposed plan has invalid tool parameters. Try a more specific question.")
        if step.tool != "visualization":
            try:
                validate(step.tool, ToolArguments(columns=step.columns, chart_type=None), types)
            except ToolInputError as error:
                raise LLMError(str(error), 422) from None
        elif len(set(step.columns)) != len(step.columns):
            raise LLMError("Visualization plans must use distinct columns.", 422)
    return plan
