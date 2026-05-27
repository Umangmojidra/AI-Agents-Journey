# day04/mcp_basics.py
from dotenv import load_dotenv
import anthropic
import os
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ══════════════════════════════════════════════════════
# WHAT IS HAPPENING HERE — read before running
#
# Normal tools (Day 1-3): tools lived inside your Python file
# MCP tools: tools live in a SEPARATE PROCESS (the MCP server)
#
# Flow:
# Your script → starts filesystem MCP server as subprocess
#             → connects to it via stdio (standard input/output)
#             → asks it "what tools do you have?"
#             → gets back: read_file, write_file, list_directory, etc.
#             → passes those tools to Claude
#             → Claude calls them like normal tools
#             → MCP client sends the call to the server process
#             → server executes it on real files
#             → returns result to Claude
#
# You write zero file handling code. The MCP server handles it all.
# ══════════════════════════════════════════════════════

# Path to your day04 folder — MCP server only accesses this folder
DAY04_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)))


async def run_with_filesystem_mcp(user_task: str):
    """
    Starts the filesystem MCP server, connects to it,
    gives Claude its tools, runs the agent loop.
    """
    print(f"\n{'='*55}")
    print(f"TASK: {user_task}")
    print(f"{'='*55}")

    # ── STEP 1: Define how to start the MCP server ────
    # StdioServerParameters tells the MCP client:
    # "start this command as a subprocess and talk to it via stdio"
    server_params = StdioServerParameters(
        command="npx",
        args=[
            "@modelcontextprotocol/server-filesystem",
            DAY04_PATH  # only give Claude access to this folder
        ],
        env=None
    )

    # ── STEP 2: Start server and connect ─────────────
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:

            # Initialize the connection
            await session.initialize()

            # ── STEP 3: Discover available tools ─────
            # This is the magic of MCP — you don't hardcode tools
            # You ask the server what it provides
            tools_response = await session.list_tools()
            print(f"\n[MCP] Connected to filesystem server")
            print(f"[MCP] Available tools: {[t.name for t in tools_response.tools]}")

            # ── STEP 4: Convert MCP tools to Anthropic format ──
            # Claude expects tools in a specific format
            # MCP tools come in a different format
            # This conversion is required every time
            claude_tools = []
            for tool in tools_response.tools:
                claude_tools.append({
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema
                })

            # ── STEP 5: Run the agent loop ────────────
            messages = [{"role": "user", "content": user_task}]

            turn = 0
            while turn < 10:
                turn += 1
                print(f"\n[Agent] Turn {turn}")

                response = client.messages.create(
                    model="claude-opus-4-5",
                    max_tokens=1024,
                    system="You are a helpful agent with access to a filesystem. You can read, write, and list files. Always confirm what you've done after completing file operations.",
                    tools=claude_tools,
                    messages=messages
                )

                print(f"[Agent] Stop reason: {response.stop_reason}")

                if response.stop_reason == "end_turn":
                    final = next(
                        (b.text for b in response.content if hasattr(b, "text")), ""
                    )
                    print(f"\nFINAL ANSWER:\n{final}")
                    return final

                if response.stop_reason == "tool_use":
                    messages.append({
                        "role": "assistant",
                        "content": response.content
                    })
                    tool_results = []

                    for block in response.content:
                        if block.type == "tool_use":
                            print(f"[Agent] Tool called: {block.name}")
                            print(f"[Agent] Input: {block.input}")

                            # ── STEP 6: Execute tool via MCP ──────
                            # Instead of calling a local Python function,
                            # we send the call to the MCP server process
                            # The server executes it and returns the result
                            try:
                                result = await session.call_tool(
                                    block.name,
                                    arguments=block.input
                                )
                                # MCP returns content as a list of objects
                                tool_output = result.content[0].text if result.content else "No output"
                                print(f"[Agent] Result: {tool_output[:100]}...")

                            except Exception as e:
                                tool_output = f"Tool error: {str(e)}"
                                print(f"[Agent] Error: {e}")

                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": tool_output
                            })

                    messages.append({
                        "role": "user",
                        "content": tool_results
                    })


async def run_with_fetch_mcp(user_task: str):
    """
    Connects to the fetch MCP server.
    Lets Claude browse real URLs and extract content.
    """
    print(f"\n{'='*55}")
    print(f"TASK: {user_task}")
    print(f"{'='*55}")

    server_params = StdioServerParameters(
        command="python",
        args=["-m", "mcp_server_fetch"],
        env=None
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools_response = await session.list_tools()
            print(f"\n[MCP] Connected to fetch server")
            print(f"[MCP] Available tools: {[t.name for t in tools_response.tools]}")

            claude_tools = []
            for tool in tools_response.tools:
                claude_tools.append({
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema
                })

            messages = [{"role": "user", "content": user_task}]

            turn = 0
            while turn < 10:
                turn += 1
                print(f"\n[Agent] Turn {turn}")

                response = client.messages.create(
                    model="claude-opus-4-5",
                    max_tokens=1024,
                    system="You are a helpful agent that can fetch and read web pages. Summarise content clearly and concisely.",
                    tools=claude_tools,
                    messages=messages
                )

                print(f"[Agent] Stop reason: {response.stop_reason}")

                if response.stop_reason == "end_turn":
                    final = next(
                        (b.text for b in response.content if hasattr(b, "text")), ""
                    )
                    print(f"\nFINAL ANSWER:\n{final}")
                    return final

                if response.stop_reason == "tool_use":
                    messages.append({
                        "role": "assistant",
                        "content": response.content
                    })
                    tool_results = []

                    for block in response.content:
                        if block.type == "tool_use":
                            print(f"[Agent] Tool called: {block.name}")
                            print(f"[Agent] Input: {block.input}")

                            try:
                                result = await session.call_tool(
                                    block.name,
                                    arguments=block.input
                                )
                                tool_output = result.content[0].text if result.content else "No output"
                                print(f"[Agent] Result: {tool_output[:150]}...")

                            except Exception as e:
                                tool_output = f"Tool error: {str(e)}"
                                print(f"[Agent] Error: {e}")

                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": tool_output
                            })

                    messages.append({
                        "role": "user",
                        "content": tool_results
                    })


async def main():

    # ── TEST 1: Read a real file ───────────────────────
    print("\n" + "TEST 1: Read real file from disk")
    await run_with_filesystem_mcp(
        "Read the file called test_data.txt and tell me about this person."
    )

    # ── TEST 2: Write a real file ──────────────────────
    print("\n" + "TEST 2: Write a new file to disk")
    await run_with_filesystem_mcp(
        "Create a new file called agent_notes.txt and write this inside it: 'Day 4 complete. MCP filesystem server connected successfully. Claude can now read and write real files.'"
    )

    # ── TEST 3: List directory + read ─────────────────
    print("\n" + "TEST 3: List directory then read a file")
    await run_with_filesystem_mcp(
        "List all files in the current directory, then read test_data.txt and summarise the person's profile in one sentence."
    )

    # ── TEST 4: Fetch a real URL ───────────────────────
    print("\n" + "TEST 4: Fetch real URL content")
    await run_with_fetch_mcp(
        "Fetch the page at https://docs.anthropic.com/en/docs/about-claude/models and tell me what the latest Claude model is."
    )


if __name__ == "__main__":
    asyncio.run(main())