# day2_memory.py
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
                    "description": "Search query. Example: 'latest AI startups in Hyderabad 2025'"
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
    return f"Search results for '{query}': Found 3 relevant articles. Key finding: Significant activity in this area in 2025."

def run_tool(tool_name: str, tool_input: dict) -> str:
    if tool_name == "calculate":
        return calculate(tool_input["expression"])
    elif tool_name == "get_weather":
        return get_weather(tool_input["city"])
    elif tool_name == "search_web":
        return search_web(tool_input["query"])
    return f"Unknown tool: {tool_name}"

# ── STRATEGY 1: Sliding Window ─────────────────────────────────────────────
def sliding_window(messages: list, max_messages: int = 6) -> list:
    """Keep only the last N messages. Fast, zero cost, loses old context."""
    if len(messages) > max_messages:
        dropped = len(messages) - max_messages
        print(f"  [Sliding window] Dropped {dropped} old messages")
        return messages[-max_messages:]
    return messages

# ── STRATEGY 2: Summarisation ──────────────────────────────────────────────
def summarise_messages(messages: list) -> list:
    """Compress old messages into a summary. Preserves meaning, costs one API call."""
    if len(messages) < 4:
        return messages

    # Summarise everything except the last 2 messages
    to_summarise = messages[:-2]
    recent = messages[-2:]

    print(f"  [Summariser] Compressing {len(to_summarise)} messages into summary...")

    history_text = ""
    for msg in to_summarise:
        if isinstance(msg["content"], str):
            history_text += f"{msg['role'].upper()}: {msg['content']}\n"
        elif isinstance(msg["content"], list):
            for block in msg["content"]:
                if isinstance(block, dict) and block.get("type") == "text":
                    history_text += f"{msg['role'].upper()}: {block['text']}\n"

    summary_response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=300,
        messages=[{
            "role": "user",
            "content": f"Summarise this conversation in 3-5 bullet points, preserving all key facts and decisions:\n\n{history_text}"
        }]
    )

    summary = summary_response.content[0].text
    print(f"  [Summariser] Summary: {summary[:100]}...")

    # Replace old messages with summary + keep recent messages
    compressed = [
        {"role": "user", "content": f"[Previous conversation summary]\n{summary}"},
        {"role": "assistant", "content": "Understood. I have the context from our previous conversation."}
    ] + recent

    return compressed

# ── STRATEGY 3: Scratchpad Pattern ─────────────────────────────────────────
SCRATCHPAD_SYSTEM = """You are a helpful AI assistant with access to tools.

Before answering any complex question, use your scratchpad to think step by step:
<scratchpad>
- Break down what the user is asking
- Identify which tools you need and in what order  
- Plan your approach before executing
</scratchpad>

Always show your reasoning inside <scratchpad> tags before taking action.
This helps you stay organised across long multi-turn conversations."""

# ── AGENT WITH SELECTABLE MEMORY STRATEGY ──────────────────────────────────
def run_agent(
    conversation: list,
    user_message: str,
    strategy: str = "none",  # "none", "sliding", "summarise"
    max_turns: int = 10,
    use_scratchpad: bool = False
) -> list:

    print(f"\n  USER: {user_message}")
    conversation.append({"role": "user", "content": user_message})

    turn = 0
    while turn < max_turns:
        turn += 1

        # Apply memory strategy before each API call
        working_messages = conversation.copy()
        if strategy == "sliding":
            working_messages = sliding_window(working_messages, max_messages=6)
        elif strategy == "summarise" and len(conversation) > 6:
            working_messages = summarise_messages(working_messages)

        system = SCRATCHPAD_SYSTEM if use_scratchpad else None

        kwargs = {
            "model": "claude-opus-4-5",
            "max_tokens": 1024,
            "tools": tools,
            "messages": working_messages
        }
        if system:
            kwargs["system"] = system

        response = client.messages.create(**kwargs)

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    print(f"  CLAUDE: {block.text[:200]}...")
            conversation.append({"role": "assistant", "content": response.content})
            break

        if response.stop_reason == "tool_use":
            conversation.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = run_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })
            conversation.append({"role": "user", "content": tool_results})

    return conversation

def count_tokens(messages: list) -> int:
    """Ask Claude how many tokens a message list would consume."""
    response = client.messages.count_tokens(
        model="claude-opus-4-5",
        tools=tools,
        messages=messages
    )
    return response.input_tokens

def smart_agent(conversation: list, user_message: str, token_limit: int = 2000) -> list:
    """Agent that checks token count, auto-summarises, and handles the full tool loop."""
    conversation.append({"role": "user", "content": user_message})

    print(f"\n  USER: {user_message}")

    turn = 0
    max_turns = 10

    while turn < max_turns:
        turn += 1

        # Check tokens BEFORE sending to API
        tokens = count_tokens(conversation)
        print(f"  [Token check] Turn {turn} — {tokens} tokens")

        if tokens > token_limit:
            print(f"  [Token check] Over {token_limit} limit — triggering summarisation")
            conversation = summarise_messages(conversation)
            tokens_after = count_tokens(conversation)
            print(f"  [Token check] After summarisation: {tokens_after} tokens")
        else:
            print(f"  [Token check] Under limit — no summarisation needed")

        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1024,
            tools=tools,
            messages=conversation
        )

        # Claude finished — extract and print final answer
        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    print(f"  CLAUDE: {block.text[:200]}...")
            conversation.append({"role": "assistant", "content": response.content})
            break

        # Claude wants tools — run them and loop back
        if response.stop_reason == "tool_use":
            conversation.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"  [Tool] {block.name} → {block.input}")
                    result = run_tool(block.name, block.input)
                    print(f"  [Result] {result}")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            conversation.append({"role": "user", "content": tool_results})

    return conversation

# ── TESTS ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":

    # TEST 1: Basic memory — does Claude remember across turns?
    print("\n" + "="*55)
    print("TEST 1: Conversation Memory")
    print("="*55)
    convo = []
    convo = run_agent(convo, "My name is Umang and I am an AI engineer from Hyderabad.")
    convo = run_agent(convo, "What is 450 * 12?")
    convo = run_agent(convo, "What is my name and where am I from?")  # Tests memory
    print(f"\nTotal messages in history: {len(convo)}")

    # TEST 2: Sliding window — watch it drop old messages
    print("\n" + "="*55)
    print("TEST 2: Sliding Window Strategy")
    print("="*55)
    convo2 = []
    convo2 = run_agent(convo2, "My favourite city is Hyderabad.", strategy="sliding")
    convo2 = run_agent(convo2, "What is 10 * 10?", strategy="sliding")
    convo2 = run_agent(convo2, "What is 20 * 20?", strategy="sliding")
    convo2 = run_agent(convo2, "What is 30 * 30?", strategy="sliding")
    convo2 = run_agent(convo2, "What is my favourite city?", strategy="sliding")  # May forget!
    print(f"\nTotal messages in history: {len(convo2)}")

    # TEST 3: Scratchpad — watch Claude think before acting
    print("\n" + "="*55)
    print("TEST 3: Scratchpad Pattern")
    print("="*55)
    convo3 = []
    convo3 = run_agent(
        convo3,
        "Search for AI startups in Hyderabad, then check weather there, then calculate total funding if 5 startups each need 75000 dollars.",
        use_scratchpad=True
    )
    # TEST 4: Smart Token-Aware Agent
    print("\n" + "="*55)
    print("TEST 4: Smart Token-Aware Agent")
    print("="*55)
    convo4 = []
    convo4 = smart_agent(convo4, "My name is Umang, I am an AI engineer from Hyderabad, I love building RAG pipelines and my target salary is 10 LPA.")
    convo4 = smart_agent(convo4, "Search for ML Engineer roles in Hyderabad.")
    convo4 = smart_agent(convo4, "Calculate 10 LPA in monthly salary.")
    convo4 = smart_agent(convo4, "What is my name and what do I do?")