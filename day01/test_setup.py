from dotenv import load_dotenv
import anthropic
import os

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

response = client.messages.create(
    model="claude-opus-4-5",
    max_tokens=100,
    messages=[{"role": "user", "content": "Say: setup complete"}]
)
print(response.content[0].text)
