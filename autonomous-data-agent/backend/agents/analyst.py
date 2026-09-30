"""A bounded plan → act → observe → re-plan loop over real DataFrames."""
import asyncio
import json
import logging
import re
import time
from starlette.concurrency import run_in_threadpool
from models.agent import AgentState, Activity, AnalyzeResponse
from agents.planner import create_plan
from agents.tool_registry import catalog, execute, ToolInputError
from agents.evidence import facts, provider_result
from services.llm_service import LLMError

logger = logging.getLogger("dataagent.agent")
MAX_ITERATIONS = 6
TOTAL_TIMEOUT_SECONDS = 150


def compact_context(state, history):
    return {"query": state.user_query, "metadata": state.dataset_metadata, "recent_conversation": history,
            "tools": catalog(), "plan": state.analysis_plan.model_dump() if state.analysis_plan else None,
            "attempted_calls": state.tool_calls, "observations": state.observations,
            "evidence": [e.model_dump() for e in state.evidence], "errors": state.errors,
            "iterations_remaining": MAX_ITERATIONS-state.iteration_count}


def qualitative(text):
    # Reject invented numerical claims in prose; exact facts are rendered separately.
    if re.search(r"\d", text):
        return "See the verified tool evidence below for numerical findings."
    if re.search(r"\b(causes?|caused|proves?|proven|because of|due to)\b", text, re.I):
        return "The available analysis describes associations and cannot establish causation."
    return text


async def analyze(request, df, report, service, session_id, history):
    started = time.monotonic()
    state = AgentState(dataset_id=str(request.dataset_id), session_id=session_id, user_query=request.query)
    overview = report['overview']
    types = {c['name']: c['type'] for c in overview['column_info']}
    state.dataset_metadata = {k: overview[k] for k in ['filename', 'rows', 'columns', 'column_info', 'type_counts']}
    state.dataset_metadata['missing'] = report['quality']['missing']
    state.activities.append(Activity(action="Understanding question", status="completed"))
    logger.info("agent_request_started dataset=%s session=%s", state.dataset_id, session_id)
    draft = None
    ml_cache = {}
    try:
        async with asyncio.timeout(TOTAL_TIMEOUT_SECONDS):
            state.current_step = "planning"
            state.analysis_plan = await create_plan(service, compact_context(state, history), types)
            state.activities.append(Activity(action="Created analysis plan", status="completed"))
            action = await service.choose_next_action(compact_context(state, history))
            seen = set()
            for iteration in range(1, MAX_ITERATIONS+1):
                if action.kind == "finish":
                    if action.tool is not None or action.arguments.columns or action.arguments.chart_type:
                        raise LLMError("Gemini returned an invalid finish action.")
                    state.status = "completed" if state.evidence else "insufficient"
                    break
                state.iteration_count = iteration
                state.current_step = "executing_tool"
                name = action.tool
                args = action.arguments
                signature = json.dumps([name, args.model_dump()], sort_keys=True)
                state.tool_calls.append({"tool": name, "arguments": args.model_dump()})
                logger.info("tool_invoked dataset=%s tool=%s iteration=%s", state.dataset_id, name, iteration)
                try:
                    if signature in seen:
                        raise ToolInputError("Repeated identical tool call blocked; choose a different analysis or finish.")
                    seen.add(signature)
                    output = await run_in_threadpool(execute, name, args, df, types, ml_cache)
                    state.observations.append({"iteration": iteration, "tool": name, "arguments": args.model_dump(), "result": provider_result(output)})
                    state.evidence.extend(facts(name, output['result'], iteration))
                    if isinstance(output['result'], dict) and output['result'].get('kind') == 'ml':
                        card = output['result']
                        if card['task'] != 'ml_suitability':
                            state.insights = [r for r in state.insights if not (r['task'] == 'ml_suitability' and r['target'] == card['target'])]
                        if card not in state.insights: state.insights.append(card)

                    for chart in output.get('charts', []):
                        if chart not in state.generated_charts:
                            state.generated_charts.append(chart)
                    state.activities.append(Activity(action="Tool completed", status="completed", tool=name, parameters=args.model_dump(), summary="Calculated on the full retained dataset; chart sampling/aggregation follows tool limits."))
                    logger.info("tool_completed dataset=%s tool=%s iteration=%s", state.dataset_id, name, iteration)
                except ToolInputError as error:
                    state.errors.append(str(error))
                    state.activities.append(Activity(action="Tool rejected", status="failed", tool=name, summary=str(error)))
                    logger.info("tool_rejected dataset=%s tool=%s iteration=%s", state.dataset_id, name, iteration)
                except Exception:
                    message = "The selected tool could not analyze these values. Try a different column or tool."
                    state.errors.append(message)
                    state.activities.append(Activity(action="Tool failed", status="failed", tool=name, summary=message))
                    logger.warning("tool_failed dataset=%s tool=%s iteration=%s", state.dataset_id, name, iteration)
                if iteration == MAX_ITERATIONS:
                    state.status = "limited"
                    state.errors.append("Maximum of six tool attempts reached. Findings may be incomplete.")
                    break
                state.current_step = "evaluating_observation"
                action = await service.evaluate_observation(compact_context(state, history))
            state.current_step = "generating_answer"
            draft = await service.generate_final_answer(compact_context(state, history))
            available = {e.id for e in state.evidence}
            if any(ref not in available for f in draft.findings for ref in f.evidence_ids):
                raise LLMError("The generated answer cited unavailable evidence. Only verified tool results are shown.")
    except TimeoutError:
        state.errors.append("Analysis reached its time limit. Only completed tool results are shown.")
        state.status = "limited"
        draft = None
    except LLMError as error:
        if not state.evidence:
            raise
        state.errors.append(str(error))
        state.status = "failed"
        draft = None
    selected = {ref for finding in draft.findings for ref in finding.evidence_ids} if draft else set()
    evidence = [e for e in state.evidence if e.id in selected] if selected else state.evidence[:12]
    summary = qualitative(draft.summary) if draft else "Analysis stopped before a complete interpretation was available. The evidence below contains only completed calculations."
    if not state.evidence:
        summary = "I could not collect sufficient evidence to answer this question. Please name the metric or columns you want to investigate."
        if "datetime" not in types.values():
            summary += " This dataset has no usable datetime column, so trend analysis is unavailable."
        if "numerical" not in types.values():
            summary += " This dataset has no numerical columns for averages, numeric outliers, or correlations."
    if state.insights:
        summary = state.insights[-1]["summary"]
        if not state.insights[-1]["suitable"] and state.status == "completed": state.status = "insufficient"
    state.final_answer = summary
    state.current_step = "finished"
    state.activities.append(Activity(action="Analysis complete" if state.status == "completed" else "Analysis stopped", status="completed" if state.status == "completed" else "stopped", summary=state.status))
    duration = round(time.monotonic()-started, 2)
    logger.info("agent_completed dataset=%s status=%s iterations=%s duration=%s", state.dataset_id, state.status, state.iteration_count, duration)
    result = AnalyzeResponse(insights=state.insights, model=", ".join(getattr(service, "used_models", [])) or getattr(service, "model", None), status=state.status, dataset_id=state.dataset_id, session_id=session_id, query=request.query,
        plan=state.analysis_plan.steps if state.analysis_plan else [], activities=state.activities,
        tools_used=list(dict.fromkeys(o['tool'] for o in state.observations)), iterations=state.iteration_count,
        execution_seconds=duration, answer=summary, findings=[e.text for e in evidence], evidence=evidence,
        potential_explanation=qualitative(draft.potential_explanation) if draft and state.evidence else "No additional interpretation is supported by the available evidence.",
        suggested_next_analysis=state.insights[-1]["suggestions"] if state.insights else [s[:300] for s in draft.suggested_next_analysis] if draft else ["Try a narrower analytical question."],
        charts=state.generated_charts, errors=state.errors)
    # The next turn receives exact tool arguments and evidence, not raw rows or unlimited state.
    turn = {"query": request.query, "answer": summary, "calls": state.tool_calls,
            "evidence": [e.model_dump() for e in evidence], "status": state.status}
    return result, turn
