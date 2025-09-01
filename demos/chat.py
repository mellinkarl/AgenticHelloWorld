
from openai import OpenAI
import os
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
resp = client.responses.create(model="gpt-4o-mini", input="hello! tell me who you are.")
print(resp.output_text)
