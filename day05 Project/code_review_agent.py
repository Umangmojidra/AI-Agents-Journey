# day05/code_review_agent.py

from dotenv import load_dotenv
import anthropic
import os
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from datetime import datetime

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

DAY05_PATH = os.path.dirname(os.path.abspath(__file__))

# ══════════════════════════════════════════════════════
# MCP SESSION FACTORY
# Creates a reusable MCP session for filesystem access.
# We abstract this so every agent uses the same pattern.
# ══════════════════════════════════════════════════════

def get_filesystem_server_params():
    return StdioServerParameters(
        command="npx",
        args=["@modelcontextprotocol/server-filesystem", DAY05_PATH],
        env=None
    )

def get_fetch_server_params():
    return StdioServerParameters(
        command="python",
        args=["-m", "mcp_server_fetch"],
        env=None
    )

# ══════════════════════════════════════════════════════
# MCP AGENT RUNNER
# Generic agent loop that works with any MCP session.
# Every subagent uses this — no code duplication.
# ══════════════════════════════════════════════════════

async def run_mcp_agent(
    session: ClientSession,
    system_prompt: str,
    user_message: str,
    max_turns: int = 10
) -> str:
    """
    Generic agent loop for MCP-connected agents.
    Takes an active MCP session, runs Claude with its tools,
    handles the tool loop, returns final text response.
    """
    # Get tools from MCP server
    tools_response = await session.list_tools()
    claude_tools = [
        {
            "name": t.name,
            "description": t.description,
            "input_schema": t.inputSchema
        }
        for t in tools_response.tools
    ]

    messages = [{"role": "user", "content": user_message}]
    turn = 0

    while turn < max_turns:
        turn += 1

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=system_prompt,
            tools=claude_tools,
            messages=messages
        )

        if response.stop_reason == "end_turn":
            return next(
                (b.text for b in response.content if hasattr(b, "text")), ""
            )

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []

            for block in response.content:
                if block.type == "tool_use":
                    print(f"      → MCP tool: {block.name} | {str(block.input)[:60]}...")
                    try:
                        result = await session.call_tool(
                            block.name,
                            arguments=block.input
                        )
                        output = result.content[0].text if result.content else "No output"
                    except Exception as e:
                        output = f"Tool error: {str(e)}"

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": output
                    })

            messages.append({"role": "user", "content": tool_results})

    return "Max turns reached"


# ══════════════════════════════════════════════════════
# SUBAGENT 1 — CODE FETCHER
# Gets the code from GitHub URL or local file.
# Uses fetch MCP for URLs, filesystem MCP for local files.
# ══════════════════════════════════════════════════════
async def run_code_fetcher(source: str) -> str:
    print(f"\n  [Code Fetcher] Source: {source}")

    is_url = source.startswith("http")

    if is_url:
        raw_url = source.replace(
            "github.com", "raw.githubusercontent.com"
        ).replace("/blob/", "/")

        server_params = get_fetch_server_params()
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await run_mcp_agent(
                    session,
                    system_prompt="""You are a code fetcher specialist.
Your only job is to fetch code from URLs and return the raw content.
Do not analyse, do not comment. Just fetch and return the code exactly as-is.""",
                    user_message=f"Fetch the raw code from this URL and return it exactly as-is: {raw_url}"
                )
    else:
        # ── Read local file with plain Python — fast, no MCP overhead ──
        with open(source, "r", encoding="utf-8") as f:
            result = f.read()
        print(f"  [Code Fetcher] Read local file directly")

    print(f"  [Code Fetcher] Done — fetched {len(result)} characters")
    return result

# ══════════════════════════════════════════════════════
# SUBAGENT 2A — BUG DETECTIVE
# Specialist: finds only bugs and logic errors.
# Focused system prompt = better findings.
# ══════════════════════════════════════════════════════

async def run_bug_detective(code: str, filename: str) -> str:
    """Finds bugs, logic errors, null pointer issues, edge cases."""
    print(f"\n  [Bug Detective] Analysing {filename}...")

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system="""You are a bug detection specialist with 10 years of experience.
Your ONLY job is to find bugs, logic errors, and runtime issues.

Look specifically for:
- Null/None pointer dereferences
- Off-by-one errors
- Division by zero risks
- Unhandled exceptions
- Incorrect comparisons
- Logic flow errors
- Missing edge case handling

Format your findings EXACTLY like this for each bug:
BUG_001 | Line X | <severity: CRITICAL/HIGH/MEDIUM/LOW> | <description>

Do not suggest improvements. Do not check security. Only find bugs.""",
        messages=[{
            "role": "user",
            "content": f"Find all bugs in this code from file '{filename}':\n\n```python\n{code}\n```"
        }]
    )

    result = response.content[0].text
    print(f"  [Bug Detective] Found findings — {len(result)} chars")
    return result


# ══════════════════════════════════════════════════════
# SUBAGENT 2B — QUALITY REVIEWER
# Specialist: finds only code quality issues.
# ══════════════════════════════════════════════════════

async def run_quality_reviewer(code: str, filename: str) -> str:
    """Checks code quality, naming, structure, best practices."""
    print(f"\n  [Quality Reviewer] Analysing {filename}...")

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system="""You are a code quality specialist focused on clean code principles.
Your ONLY job is to find code quality issues.

Look specifically for:
- Poor variable/function naming
- Functions doing too many things (single responsibility)
- Missing type hints
- Missing docstrings
- Code duplication
- Poor readability
- Non-pythonic patterns (use enumerate, list comprehensions etc)
- Magic numbers/indices

Format your findings EXACTLY like this:
QUALITY_001 | Line X | <severity: HIGH/MEDIUM/LOW> | <description>

Do not find bugs. Do not check security. Only quality issues.""",
        messages=[{
            "role": "user",
            "content": f"Review code quality in this file '{filename}':\n\n```python\n{code}\n```"
        }]
    )

    result = response.content[0].text
    print(f"  [Quality Reviewer] Found findings — {len(result)} chars")
    return result


# ══════════════════════════════════════════════════════
# SUBAGENT 2C — SECURITY SCANNER
# Specialist: finds only security vulnerabilities.
# ══════════════════════════════════════════════════════

async def run_security_scanner(code: str, filename: str) -> str:
    """Scans for security vulnerabilities, exposed secrets, injection risks."""
    print(f"\n  [Security Scanner] Analysing {filename}...")

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system="""You are a security specialist focused on application security.
Your ONLY job is to find security vulnerabilities.

Look specifically for:
- Hardcoded secrets, API keys, passwords
- SQL injection vulnerabilities
- Path traversal vulnerabilities
- Weak cryptography (MD5, SHA1 for passwords)
- Missing input validation
- Insecure direct object references
- Exposed sensitive data

Format your findings EXACTLY like this:
SEC_001 | Line X | <severity: CRITICAL/HIGH/MEDIUM/LOW> | <description>

Do not find bugs. Do not check quality. Only security issues.""",
        messages=[{
            "role": "user",
            "content": f"Scan for security vulnerabilities in '{filename}':\n\n```python\n{code}\n```"
        }]
    )

    result = response.content[0].text
    print(f"  [Security Scanner] Found findings — {len(result)} chars")
    return result


# ══════════════════════════════════════════════════════
# SUBAGENT 3 — REPORT WRITER
# Takes all findings, formats structured markdown report,
# saves it to disk via filesystem MCP.
# ══════════════════════════════════════════════════════
async def run_report_writer(
    filename: str,
    code: str,
    bug_findings: str,
    quality_findings: str,
    security_findings: str
) -> tuple:
    """Formats all findings into a structured report and saves to disk."""
    print(f"\n  [Report Writer] Generating report...")

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system="""You are a technical report writing specialist.
Format code review findings into a clean, structured markdown report.
Be specific, actionable, and concise.
Use emojis for visual clarity: 🐛 bugs, ⚠️ quality, 🔒 security, ✅ summary.""",
        messages=[{
            "role": "user",
            "content": f"""Create a professional code review report for: {filename}
Date: {datetime.now().strftime("%Y-%m-%d %H:%M")}

Bug findings:
{bug_findings}

Quality findings:
{quality_findings}

Security findings:
{security_findings}

Format as a complete markdown report with:
1. Header with filename, date, overall risk level
2. Executive summary (2-3 sentences)
3. 🐛 Bugs section with each finding
4. ⚠️ Code Quality section
5. 🔒 Security section
6. ✅ Top 3 priority fixes
7. Overall scores table"""
        }]
    )

    report_content = response.content[0].text

    # ── Write file with plain Python — no MCP needed ──
    # MCP is for when Claude needs to decide what to read/write
    # When YOU know exactly what to write, just use Python directly
    report_filename = f"review_{filename.replace('.py', '')}_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
    report_path = os.path.join(DAY05_PATH, report_filename)

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    print(f"  [Report Writer] Report saved: {report_filename}")
    return report_content, report_filename

# ══════════════════════════════════════════════════════
# COORDINATOR
# Orchestrates the full pipeline.
# Sequential where needed, parallel where possible.
# ══════════════════════════════════════════════════════

async def run_code_review(source: str):
    """
    Full coordinator pipeline:
    1. Fetch code (sequential — must happen first)
    2. Bug + Quality + Security analysis (parallel — independent)
    3. Write report (sequential — needs all findings)
    """
    print(f"\n{'='*55}")
    print(f"AI CODE REVIEW AGENT")
    print(f"Source: {source}")
    print(f"{'='*55}")

    filename = source.split("/")[-1].split("\\")[-1]

    # ── STEP 1: Fetch code (sequential) ───────────────
    print(f"\n[Coordinator] Step 1 — Fetching code...")
    code = await run_code_fetcher(source)

    if not code or len(code) < 10:
        print("[Coordinator] Failed to fetch code — aborting")
        return

    # ── STEP 2: Run all 3 analysts in PARALLEL ─────────
    print(f"\n[Coordinator] Step 2 — Running parallel analysis...")
    print(f"  Launching: Bug Detective + Quality Reviewer + Security Scanner simultaneously")

    bug_findings, quality_findings, security_findings = await asyncio.gather(
        run_bug_detective(code, filename),
        run_quality_reviewer(code, filename),
        run_security_scanner(code, filename)
    )

    print(f"\n[Coordinator] All 3 analysts complete")

    # ── STEP 3: Write report (sequential) ─────────────
    print(f"\n[Coordinator] Step 3 — Writing report...")
    report_content, report_filename = await run_report_writer(
        filename,
        code,
        bug_findings,
        quality_findings,
        security_findings
    )

    print(f"\n{'='*55}")
    print(f"REVIEW COMPLETE")
    print(f"Report saved: {report_filename}")
    print(f"{'='*55}")
    print(f"\n{report_content}")

    return report_content


# ══════════════════════════════════════════════════════
# ENTRY POINT
# Test with local file first, then GitHub URL
# ══════════════════════════════════════════════════════

if __name__ == "__main__":

    # Test 1: Local file review
    local_file = os.path.join(DAY05_PATH, "sample_code.py")
    asyncio.run(run_code_review(local_file))

    # Test 2: GitHub file review (your own repo)
    # Replace with any real Python file from GitHub
    # asyncio.run(run_code_review(
    #     "https://github.com/yourusername/yourrepo/blob/main/yourfile.py"
    # ))