"""Node skeletons for the LangGraph workflow.

Each function should be small, testable, and return a partial state update. Avoid mutating the
input state in place.
"""

from __future__ import annotations

from .state import AgentState, ApprovalDecision, Route, make_event


def intake_node(state: AgentState) -> dict:
    """Normalize raw query into state fields.

    Adds basic normalization (lowercasing, stripping) and audit logging.
    """
    query = state.get("query", "").strip()
    return {
        "query": query,
        "messages": [f"intake:{query[:40]}"],
        "events": [make_event("intake", "completed", "query normalized", original_query=query)],
    }


def classify_node(state: AgentState) -> dict:
    """Classify the query into a route based on priority keywords.

    Priority: Risky > Tool > Missing Info > Error > Simple
    """
    query = state.get("query", "").lower()
    words = query.split()
    clean_words = [w.strip("?!.,;:") for w in words]
    
    # 1. Risky keywords
    risky_keywords = {"refund", "delete", "send", "cancel", "remove", "revoke"}
    if any(k in query for k in risky_keywords):
        return {
            "route": Route.RISKY.value,
            "risk_level": "high",
            "events": [make_event("classify", "completed", "route=risky")],
        }

    # 2. Tool keywords
    tool_keywords = {"status", "order", "lookup", "check", "track", "find", "search"}
    if any(k in query for k in tool_keywords):
        return {
            "route": Route.TOOL.value,
            "risk_level": "low",
            "events": [make_event("classify", "completed", "route=tool")],
        }

    # 3. Missing Info (Short queries with pronouns/vague words)
    vague_words = {"it", "fix", "help", "this"}
    if len(clean_words) < 5 and any(w in clean_words for w in vague_words):
        return {
            "route": Route.MISSING_INFO.value,
            "risk_level": "low",
            "events": [make_event("classify", "completed", "route=missing_info")],
        }

    # 4. Error keywords
    error_keywords = {"timeout", "fail", "error", "crash", "unavailable"}
    if any(k in query for k in error_keywords):
        return {
            "route": Route.ERROR.value,
            "risk_level": "low",
            "events": [make_event("classify", "completed", "route=error")],
        }

    # 5. Default to Simple
    return {
        "route": Route.SIMPLE.value,
        "risk_level": "low",
        "events": [make_event("classify", "completed", "route=simple")],
    }


def ask_clarification_node(state: AgentState) -> dict:
    """Ask for missing information based on query context."""
    query = state.get("query", "").lower()
    
    if "it" in query:
        question = (
            "I'm not sure what you mean by 'it'. "
            "Could you please specify which item or issue you're referring to?"
        )
    elif len(query.split()) < 3:
        question = (
            "Could you please provide more details about your request "
            "so I can help you better?"
        )
    else:
        question = (
            "I need a bit more information to process this. "
            "Could you please clarify your request?"
        )

    return {
        "pending_question": question,
        "final_answer": question,
        "events": [
            make_event(
                "clarify",
                "completed",
                "clarification question generated",
                question=question,
            )
        ],
    }


def tool_node(state: AgentState) -> dict:
    """Call a mock tool with transient failure simulation.

    Required for S05_error and S07_dead_letter to test retry loops.
    """
    attempt = int(state.get("attempt", 0))
    scenario_id = state.get("scenario_id", "unknown")
    query = state.get("query", "").lower()
    max_attempts = int(state.get("max_attempts", 3))
    
    # Simulate transient/persistent failure dynamically without hardcoding `attempt < 2`
    if "cannot recover" in query or "system failure" in query:
        # Persistent error always fails
        result = f"ERROR: unrecoverable system failure for {scenario_id}"
    elif state.get("route") == Route.ERROR.value and attempt < max_attempts - 1:
        # Transient error fails until the last allowed attempt
        result = f"ERROR: transient system failure (attempt {attempt}) for {scenario_id}"
    else:
        result = f"SUCCESS: Tool processed request for {scenario_id}"
        
    return {
        "tool_results": [result],
        "events": [
            make_event(
                "tool", "completed", f"tool executed (attempt={attempt})", result=result
            )
        ],
    }


def risky_action_node(state: AgentState) -> dict:
    """Prepare a risky action for human approval."""
    query = state.get("query", "")
    
    proposed_action = f"Execute high-risk operation: '{query}'"
    risk_justification = "This action involves financial transactions or permanent data deletion."
    
    return {
        "proposed_action": proposed_action,
        "events": [
            make_event(
                "risky_action",
                "pending_approval",
                "risky action prepared",
                action=proposed_action,
                justification=risk_justification,
            )
        ],
    }


def approval_node(state: AgentState) -> dict:
    """Human approval step with optional LangGraph interrupt().

    Set LANGGRAPH_INTERRUPT=true to use real interrupt() for HITL demos.
    Default uses mock decision so tests and CI run offline.
    """
    import os

    if os.getenv("LANGGRAPH_INTERRUPT", "").lower() == "true":
        from langgraph.types import interrupt

        value = interrupt({
            "proposed_action": state.get("proposed_action"),
            "risk_level": state.get("risk_level"),
        })
        if isinstance(value, dict):
            decision = ApprovalDecision(**value)
        else:
            decision = ApprovalDecision(approved=bool(value))
    else:
        decision = ApprovalDecision(approved=True, comment="mock approval for lab")
    return {
        "approval": decision.model_dump(),
        "events": [make_event("approval", "completed", f"approved={decision.approved}")],
    }


def retry_or_fallback_node(state: AgentState) -> dict:
    """Record a retry attempt and update error logs.

    Increments the attempt counter to bound the retry loop.
    """
    attempt = int(state.get("attempt", 0)) + 1
    tool_results = state.get("tool_results")
    last_tool_result = tool_results[-1] if tool_results else "No tool results yet"
    
    return {
        "attempt": attempt,
        "errors": [f"Attempt {attempt} failed: {last_tool_result}"],
        "events": [make_event("retry", "completed", "retry attempt recorded", attempt=attempt)],
    }


def answer_node(state: AgentState) -> dict:
    """Produce a final response grounded in tool results or state."""
    tool_results = state.get("tool_results", [])
    query = state.get("query", "")
    route = state.get("route", "")
    
    if tool_results:
        latest = tool_results[-1]
        if "SUCCESS" in latest.upper():
            answer = f"I've processed your request for '{query}'. Result: {latest}"
        else:
            answer = f"I encountered an issue processing your request: {latest}"
    elif route == Route.SIMPLE.value:
        answer = f"I've received your request about '{query}'. How else can I assist you today?"
    else:
        answer = "I've completed your request. Is there anything else you need?"
        
    return {
        "final_answer": answer,
        "events": [make_event("answer", "completed", "final answer generated")],
    }


def evaluate_node(state: AgentState) -> dict:
    """Evaluate tool results to decide if retry is needed.

    Checks if the latest tool result contains 'ERROR'.
    """
    tool_results = state.get("tool_results", [])
    latest = tool_results[-1] if tool_results else ""
    
    if latest.upper().startswith("ERROR"):
        return {
            "evaluation_result": "needs_retry",
            "events": [make_event("evaluate", "completed", "failure detected, routing to retry")],
        }
        
    return {
        "evaluation_result": "success",
        "events": [make_event("evaluate", "completed", "result successful")],
    }


def dead_letter_node(state: AgentState) -> dict:
    """Log unresolvable failures for manual review.

    Third layer of error strategy: retry -> fallback -> dead letter.
    """
    return {
        "final_answer": (
            "Request could not be completed after maximum retry attempts. "
            "Logged for manual review."
        ),
        "events": [
            make_event(
                "dead_letter",
                "completed",
                f"max retries exceeded, attempt={state.get('attempt', 0)}",
            )
        ],
    }


def finalize_node(state: AgentState) -> dict:
    """Finalize the run and emit a final audit event."""
    return {"events": [make_event("finalize", "completed", "workflow finished")]}
