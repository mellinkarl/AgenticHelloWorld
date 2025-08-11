# grapha psesudo code 
```python
graph = StateGraph(schema=State)

graph.add_node("retrieve", retrieve)
graph.add_node("draft", draft_answer)
graph.add_node("critic", critic_review)

graph.add_edge("retrieve", "draft")
graph.add_edge("draft", "critic")
graph.add_conditional_edges(
    "critic",
    lambda s: "done" if s.ok else "retry",
    {"done": END, "retry": "retrieve"},
)

app = graph.compile()
result = app.invoke({"question": q})
```

# 
```