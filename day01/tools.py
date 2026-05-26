# day1_tools.py
from dotenv import load_dotenv
import anthropic
import os

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ── STEP 1: Define your tools ──────────────────────────────────────────────
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
    }
]

# ── STEP 2: Real functions that execute when Claude calls a tool ────────────
def calculate(expression: str) -> str:
    try:
        result = eval(expression)
        return f"Result: {expression} = {result}"
    except Exception as e:
        return f"Error: {str(e)}"

def get_weather(city: str) -> str:
    # Stub — real API later. For now returns fake data.
    weather_data = {
        "hyderabad": "32°C, Partly Cloudy, Humidity: 65%",
        "bangalore": "24°C, Cloudy, Humidity: 80%",
        "mumbai": "30°C, Humid, Humidity: 85%",
    }
    return weather_data.get(city.lower(), f"28°C, Clear Sky, Humidity: 55%")

# ── STEP 3: Tool router — maps Claude's tool_name to real function ─────────
def run_tool(tool_name: str, tool_input: dict) -> str:
    if tool_name == "calculate":
        return calculate(tool_input["expression"])
    elif tool_name == "get_weather":
        return get_weather(tool_input["city"])
    else:
        return f"Unknown tool: {tool_name}"

# ── STEP 4: Single turn — ask Claude, handle ONE tool call ────────────────
def ask_claude(user_message: str):
    print(f"\n{'='*50}")
    print(f"USER: {user_message}")
    print(f"{'='*50}")

    messages = [{"role": "user", "content": user_message}]

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        tools=tools,
        messages=messages
    )

    print(f"\nSTOP REASON: {response.stop_reason}")

    # Claude wants to use a tool
    if response.stop_reason == "tool_use":
        for block in response.content:
            if block.type == "tool_use":
                print(f"\nCLAUDE CHOSE TOOL: {block.name}")
                print(f"TOOL INPUT: {block.input}")

                # Execute the real function
                tool_result = run_tool(block.name, block.input)
                print(f"TOOL RESULT: {tool_result}")

                # Send result back to Claude for final answer
                messages.append({"role": "assistant", "content": response.content})
                messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": tool_result
                    }]
                })

                final_response = client.messages.create(
                    model="claude-opus-4-5",
                    max_tokens=1024,
                    tools=tools,
                    messages=messages
                )

                print(f"\nCLAUDE FINAL ANSWER: {final_response.content[0].text}")

    # Claude answered directly without tools
    else:
        print(f"\nCLAUDE ANSWER: {response.content[0].text}")


# ── STEP 5: Test it ────────────────────────────────────────────────────────
if __name__ == "__main__":
    ask_claude("What is 1847 * 23 + 456?")
    ask_claude("What's the weather in Hyderabad?")
    ask_claude("Who are you?")  # No tool needed — watch what happens