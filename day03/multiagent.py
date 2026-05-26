# day3_multiagent.py
from dotenv import load_dotenv
import anthropic
import os
import random

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ══════════════════════════════════════════════════════
# TOOLS — each subagent has only the tools it needs
# ══════════════════════════════════════════════════════

search_tools = [
    {
        "name": "search_web",
        "description": "Searches the web for information on a topic. Use maximum 3 searches then report findings.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query to look up"
                }
            },
            "required": ["query"]
        }
    }
]

calc_tools = [
    {
        "name": "calculate",
        "description": "Evaluates a mathematical expression and returns the result.",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Math expression to evaluate. Example: '1847 * 23'"
                }
            },
            "required": ["expression"]
        }
    }
]

coordinator_tools = [
    {
        "name": "run_search_agent",
        "description": "Delegates a research task to the search specialist agent. Use when the task requires finding information, researching topics, or looking up facts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Clear description of what to search for"
                }
            },
            "required": ["task"]
        }
    },
    {
        "name": "run_calculator_agent",
        "description": "Delegates a calculation task to the math specialist agent. Use when the task requires any mathematical computation or numeric analysis.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Clear description of what to calculate"
                }
            },
            "required": ["task"]
        }
    },
    {
        "name": "run_writer_agent",
        "description": "Delegates report writing to the writer specialist. Call this LAST after research and calculations are complete.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "The original user task"
                },
                "research": {
                    "type": "string",
                    "description": "Research findings from the search agent"
                },
                "calculations": {
                    "type": "string",
                    "description": "Calculation results from the calculator agent"
                }
            },
            "required": ["task", "research", "calculations"]
        }
    },
    {
        "name": "escalate_to_human",
        "description": """Escalate to a human operator when:
        - A tool has failed repeatedly and task cannot be completed
        - The task is ambiguous and needs clarification before proceeding
        - The result confidence is low and human verification is needed
        - The task involves irreversible actions
        Always prefer escalation over guessing.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why escalation is needed"
                },
                "context": {
                    "type": "string",
                    "description": "What has been done so far and what is blocking progress"
                },
                "suggested_resolution": {
                    "type": "string",
                    "description": "What the human should do to resolve this"
                }
            },
            "required": ["reason", "context", "suggested_resolution"]
        }
    }
]


# ══════════════════════════════════════════════════════
# TOOL EXECUTORS — the actual functions behind each tool
# ══════════════════════════════════════════════════════

def execute_search(query: str) -> str:
    """Stub — replace with real search API in Week 2."""
    if random.random() < 0.3:  # 30% failure rate to test retry logic
        raise Exception("Search API timeout — service unavailable")
    return f"Search results for '{query}': Significant growth and activity found in this area in 2025. Key players are emerging rapidly."

def execute_calculate(expression: str) -> str:
    try:
        result = eval(expression)
        return f"{expression} = {result}"
    except Exception as e:
        return f"CALCULATION_ERROR: {str(e)}"

def handle_escalation(reason: str, context: str, suggested_resolution: str) -> str:
    """In production: pages on-call engineer, creates ticket, sends alert."""
    print(f"\n  🚨 ESCALATION TRIGGERED")
    print(f"  Reason: {reason}")
    print(f"  Context: {context[:100]}...")
    print(f"  Suggested fix: {suggested_resolution}")
    return "ESCALATED: Human operator notified. Task paused pending review."


# ══════════════════════════════════════════════════════
# RETRY WRAPPER
# Wraps any tool call with retry logic.
# Returns (success, result) so the caller knows if it worked.
# ══════════════════════════════════════════════════════

def run_with_retry(func, *args, max_retries: int = 3) -> tuple[bool, str]:
    for attempt in range(1, max_retries + 1):
        try:
            result = func(*args)
            print(f"    [Retry] Attempt {attempt} succeeded")
            return True, result
        except Exception as e:
            print(f"    [Retry] Attempt {attempt} failed: {e}")
            if attempt == max_retries:
                return False, f"TOOL_FAILED after {max_retries} attempts: {str(e)}"
    return False, "TOOL_FAILED: Unknown error"


# ══════════════════════════════════════════════════════
# SUBAGENT 1 — Search Agent
# Specialised: only searches. Max 3 searches then reports.
# Has its own loop, its own system prompt, its own tools.
# ══════════════════════════════════════════════════════

def run_search_agent(task: str) -> str:
    print(f"\n    [Search Agent] Starting task: {task[:80]}...")
    messages = [{"role": "user", "content": task}]
    search_count = 0

    while True:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1024,
            system="""You are a search specialist. Your only job is to find information.
Rules:
- Search maximum 3 times per task
- After 3 searches, report what you found regardless of completeness
- Never calculate, never write reports — only search and report facts
- Be concise in your findings""",
            tools=search_tools,
            messages=messages
        )

        if response.stop_reason == "end_turn":
            result = next((b.text for b in response.content if hasattr(b, "text")), "")
            print(f"    [Search Agent] Complete. Searches used: {search_count}")
            return result

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []

            for block in response.content:
                if block.type == "tool_use":
                    search_count += 1
                    print(f"    [Search Agent] Search {search_count}: {block.input['query'][:60]}...")

                    success, result = run_with_retry(
                        execute_search,
                        block.input["query"],
                        max_retries=3
                    )

                    if not success:
                        result = f"SEARCH_FAILED: Could not retrieve results. {result}"

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            messages.append({"role": "user", "content": tool_results})


# ══════════════════════════════════════════════════════
# SUBAGENT 2 — Calculator Agent
# Specialised: only does math. No searching, no writing.
# ══════════════════════════════════════════════════════

def run_calculator_agent(task: str) -> str:
    print(f"\n    [Calculator Agent] Starting task: {task[:80]}...")
    messages = [{"role": "user", "content": task}]

    while True:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=512,
            system="""You are a calculation specialist. Your only job is to perform mathematical calculations accurately.
Rules:
- Only calculate, never search or write reports
- Show your working clearly
- Return precise numeric results""",
            tools=calc_tools,
            messages=messages
        )

        if response.stop_reason == "end_turn":
            result = next((b.text for b in response.content if hasattr(b, "text")), "")
            print(f"    [Calculator Agent] Complete.")
            return result

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []

            for block in response.content:
                if block.type == "tool_use":
                    print(f"    [Calculator Agent] Calculating: {block.input['expression']}")
                    result = execute_calculate(block.input["expression"])
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            messages.append({"role": "user", "content": tool_results})


# ══════════════════════════════════════════════════════
# SUBAGENT 3 — Writer Agent
# Specialised: formats findings into clean reports.
# No tools needed — pure language task.
# ══════════════════════════════════════════════════════

def run_writer_agent(task: str, research: str, calculations: str) -> str:
    print(f"\n    [Writer Agent] Formatting final report...")

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        system="""You are a report writing specialist.
Rules:
- Take raw research and calculations and format into a clean professional report
- Use markdown formatting with clear sections
- Be concise — no fluff, only relevant information
- Always include the calculations in a table format""",
        messages=[{
            "role": "user",
            "content": f"""Write a professional report for this task: {task}

Research findings:
{research}

Calculations:
{calculations}"""
        }]
    )

    result = response.content[0].text
    print(f"    [Writer Agent] Report ready — {len(result)} characters")
    return result


# ══════════════════════════════════════════════════════
# COORDINATOR
# The brain. Never does work itself.
# Only reads tasks, decides which subagents to call,
# passes results between them, assembles final answer.
# ══════════════════════════════════════════════════════

def run_coordinator(user_task: str) -> str:
    print(f"\n{'='*55}")
    print(f"COORDINATOR received: {user_task}")
    print(f"{'='*55}")

    messages = [{"role": "user", "content": user_task}]
    collected_results = {"research": "", "calculations": ""}

    turn = 0
    while turn < 10:
        turn += 1
        print(f"\n[Coordinator] Turn {turn} — deciding next action...")

        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=2048,
            system="""You are a coordinator agent. You break down tasks and delegate to specialists.

Your specialists:
- run_search_agent: finds information and research — call this FIRST for any research task
- run_calculator_agent: performs math and calculations — call after research if needed
- run_writer_agent: formats final reports — call this LAST with research + calculation results
- escalate_to_human: use when task is ambiguous, tools keep failing, or action is irreversible

Rules:
- Never do the work yourself — always delegate
- Follow the sequence: search → calculate → write
- If a task only needs one specialist, only call that one
- If you receive TOOL_FAILED or ESCALATED results, escalate to human""",
            tools=coordinator_tools,
            messages=messages
        )

        print(f"[Coordinator] Decision: {response.stop_reason}")

        if response.stop_reason == "end_turn":
            final = next((b.text for b in response.content if hasattr(b, "text")), "")
            print(f"\n{'='*55}")
            print("FINAL OUTPUT:")
            print(f"{'='*55}")
            print(final)
            return final

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []

            for block in response.content:
                if block.type == "tool_use":
                    print(f"[Coordinator] Delegating to → {block.name}")

                    if block.name == "run_search_agent":
                        result = run_search_agent(block.input["task"])
                        collected_results["research"] = result

                    elif block.name == "run_calculator_agent":
                        result = run_calculator_agent(block.input["task"])
                        collected_results["calculations"] = result

                    elif block.name == "run_writer_agent":
                        result = run_writer_agent(
                            block.input["task"],
                            block.input.get("research", collected_results["research"]),
                            block.input.get("calculations", collected_results["calculations"])
                        )

                    elif block.name == "escalate_to_human":
                        result = handle_escalation(
                            block.input["reason"],
                            block.input["context"],
                            block.input["suggested_resolution"]
                        )

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            messages.append({"role": "user", "content": tool_results})

    return "Max turns reached — task incomplete"


# ══════════════════════════════════════════════════════
# TESTS
# ══════════════════════════════════════════════════════

if __name__ == "__main__":

    # Test 1: Only needs search agent
    # run_coordinator(
    #     "Research the current state of AI startups in Hyderabad."
    # )

    # # Test 2: Only needs calculator agent
    # run_coordinator(
    #     "Calculate monthly salary for 10 LPA and convert 8.57 CGPA to percentage."
    # )

    # # Test 3: Full pipeline — all 3 subagents
    # run_coordinator(
    #     "Research AI startup funding trends in India, calculate total funding if 10 startups each raise 2 crore across 3 rounds, and write a professional report."
    # )

    # Test 4: Ambiguous task — should escalate
    run_coordinator(
        "Process the data and send it."
    )