# probe_vertex.py
import vertexai
from langchain_google_vertexai import ChatVertexAI

vertexai.init(project="aime-hello-world", location="us-central1")
llm = ChatVertexAI(
    model="gemini-2.0-flash-001",
    response_mime_type="text/plain",
    temperature=0.1,
    max_output_tokens=32,
)
msg = llm.invoke("Return literally: OK.")
print("CONTENT:", repr(getattr(msg, "content", None)))
print("RAW:", msg)