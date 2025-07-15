from google import genai
from google.genai import types

# Initialize the client
client = genai.Client(
    vertexai=True,
    project="aime-hello-world",
    location="us-central1",
)

# Choose your model
model = "gemini-1.5-pro-002"

# Simple text prompt
response = client.models.generate_content(
    model=model,
    contents=[
        "Hello from Vertex AI using google-genai SDK!"
    ],
)

print(response.text, end="")
