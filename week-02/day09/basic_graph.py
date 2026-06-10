from langgraph.graph import StateGraph
from typing import TypedDict

# 1. Define state

class State(TypedDict):
    question : str
    search_result : str
    analysis : str
    answer : str


# 2. Define nodes 

def search_node(state : State) -> dict:
    return  {"search_result": f"Information about {state['question']}"}

def analyse_node(state : State) -> dict:
    return  {"analysis": f"Analyzed: {state['search_result']}"}

def answer_node(state: State) -> dict:
    context = state['analysis'] if state['analysis'] else state['search_result']
    return {"answer": f"Final answer -> {context}"}


# 3. Router function  

def should_analyse(state : State) -> dict:
    if "complex" in state["question"].lower():
        return "analyse"

    return "answer"

# 4. Build Graph

graph = StateGraph(State)

graph.add_node("search", search_node)
graph.add_node("analyse", analyse_node)
graph.add_node("answer", answer_node)

graph.add_conditional_edges("search",should_analyse)
graph.add_edge("analyse", "answer")

graph.set_entry_point("search")
graph.set_finish_point("answer")

app = graph.compile()

# 4. Run
result = app.invoke({
    "question": "complex LangGraph architecture",
    "search_result": "", "analysis": "", "answer": ""})
print("Test 1:", result['answer'])

result = app.invoke({
    "question": "what is LangGraph",
    "search_result": "", "analysis": "", "answer": ""})
print("Test 2:", result['answer'])