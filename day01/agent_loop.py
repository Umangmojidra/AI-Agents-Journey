# day1_agent_loop.py
from dotenv import load_dotenv
import anthropic
import os

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

tools = [
    {
        "name": "calculate",
        "description": "Performs basic math operations. Use this whenever the user asks for any calculation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Math expression to evaluate. Example: '15 * 4 + 22'"
                }
            },
            "required": ["expression"]
        }
    },
    {
        "name": "get_weather",
        "description": "Gets current weather for a city. Use this when the user asks about weather.",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "Name of the city. Example: 'Hyderabad'"
                }
            },
            "required": ["city"]
        }
    },
    {
        "name": "search_web",
        "description": "Searches the web for current information about any topic. Use this when the user asks about recent events, facts, or anything that needs research.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query. Example: 'latest AI startups in Hyderabad 2026"
                }
            },
            "required": ["query"]
        }
    }
]

def calculate(expression: str) -> str:
    try:
        result = eval(expression)
        return f"{expression} = {result}"
    except Exception as e:
        return f"Error: {str(e)}"

def get_weather(city: str) -> str:
    weather_data = {
        "hyderabad": "32°C, Partly Cloudy, Humidity: 65%",
        "bangalore": "24°C, Cloudy, Humidity: 80%",
        "mumbai": "30°C, Humid, Humidity: 85%",
    }
    return weather_data.get(city.lower(), "28°C, Clear Sky, Humidity: 55%")

def search_web(query: str) -> str:
    # Stub — returns fake search results for now
    return f"Search results for '{query}': Found 3 relevant articles about this topic. Key finding: This is a growing area with significant activity in 2025."

def run_tool(tool_name: str, tool_input: dict) -> str:
    if tool_name == "calculate":
        return calculate(tool_input["expression"])
    elif tool_name == "get_weather":
        return get_weather(tool_input["city"])
    elif tool_name == "search_web":
        return search_web(tool_input["query"])
    else:
        return f"Unknown tool: {tool_name}"

# ── THE AGENT LOOP ─────────────────────────────────────────────────────────
def run_agent(user_message: str, max_turns: int = 10):
    print(f"\n{'='*55}")
    print(f"TASK: {user_message}")
    print(f"{'='*55}")

    messages = [{"role": "user", "content": user_message}]
    turn = 0

    # Loop until Claude stops asking for tools OR we hit max_turns
    while turn < max_turns:
        turn += 1
        print(f"\n--- Turn {turn} ---")

        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1024,
            tools=tools,
            messages=messages
        )

        print(f"Stop reason: {response.stop_reason}")

        # Claude is done — final answer ready
        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    print(f"\nFINAL ANSWER:\n{block.text}")
            break

        # Claude wants to use tools
        if response.stop_reason == "tool_use":
            # Add Claude's response to message history
            messages.append({"role": "assistant", "content": response.content})

            # Process every tool Claude asked for
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"Tool called: {block.name}")
                    print(f"Input: {block.input}")

                    result = run_tool(block.name, block.input)
                    print(f"Result: {result}")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            # Send all tool results back to Claude in one message
            messages.append({"role": "user", "content": tool_results})

    else:
        print(f"\nMax turns ({max_turns}) reached — stopping agent.")

    print(f"\nTotal turns used: {turn}")


# ── TEST WITH MULTI-STEP TASKS ─────────────────────────────────────────────
if __name__ == "__main__":
    # Task 1: Needs one tool
    # run_agent("What is 2847 divided by 13, rounded to 2 decimal places?")

    # # Task 2: Needs two different tools in sequence
    # run_agent("What's the weather in Bangalore? Also calculate 450 * 12 for me.")

    # # Task 3: Watch Claude plan and use tools in the right order
    # run_agent("Search for AI startups in Hyderabad, then calculate how much funding they'd need if each startup needs 50000 dollars times 3 rounds.")

    # Test max_turns safety net
    run_agent(
        "Search for AI news. Then search for ML news. Then search for LLM news. Then search for GenAI news. Then search for deep learning news. Keep going.",
        max_turns=3
    )