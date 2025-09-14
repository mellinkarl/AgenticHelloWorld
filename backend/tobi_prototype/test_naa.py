import json
from dataclasses import dataclass
from typing import List, Optional

from google import genai
from google.genai import types
from google.cloud import bigquery


@dataclass
class Patent:
    pub_num: str
    title: str
    abstract: str
    claims: List[str]
    num_matches: int


bq_client = bigquery.Client(project="aime-hello-world")
genai_client = genai.Client(project="aime-hello-world", vertexai=True)

model = "gemini-2.0-flash-lite-001"
src: str = "gs://aime-manuscripts/patent.pdf"
date: str | None = "2025-09-10"


def call_LLM(genai_client: genai.Client, model_name: str, content: types.ContentListUnionDict, conf: types.GenerateContentConfigOrDict | None = None, repeats = 5) -> dict | None:
    
    for i in range(repeats):

        output = None

        try:    

            resp = genai_client.models.generate_content(
                model=model_name,
                contents=content,
                config=conf
            )
            output = json.loads(resp.text)
        
        except Exception as e:

            print(f"LLM error: {e}")
            output = None

        if output is not None:
            break
    
    return output
    
def multimedia_content(prompt: str,uri: str, m_type: str = "application/pdf") -> list:
    return [types.Part.from_uri(file_uri=uri, mime_type=m_type), prompt]

def response_schema(schema = dict, response_type: str = "application/json") -> types.GenerateContentConfig:
    return types.GenerateContentConfig(response_schema=schema, response_mime_type=response_type)

def compare_novelty(prospect: Patent, potential_match: Patent):
    


kw_prompt="Generate 5-20 keywords regarding this manuscript to perform novelty assessment on the invention and determine if the invention is novel. Therefore, the keywords should focus on what is built, the processes for which it is built, and specific details that would be important to a patent agent in searching for similar patents. Return the keywords as an array in JSON format"
kw_schema={
                "type": "object",
                "properties": {
                    "keywords": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["keywords"]
            }

kw = call_LLM(genai_client, model_name=model, content=multimedia_content(kw_prompt, src), conf=response_schema(kw_schema))
if kw is None:
    print("keyword LLM call failed.")
    quit()
print(f"Generated keywords: {(kw := kw["keywords"])}")

query = f"""
DECLARE keywords ARRAY<STRING> DEFAULT @keywords;

WITH hits AS (
  SELECT
    p.publication_number,
    COUNT(*) AS num_matching_claims
  FROM `patents-public-data.patents.publications` p,
       UNNEST(p.claims_localized) c,
       UNNEST(keywords) kw
  WHERE LOWER(c.text) LIKE CONCAT('%', LOWER(kw), '%')
  GROUP BY p.publication_number
)

SELECT
  p.publication_number AS pub_num,
  (SELECT STRING_AGG(t.text, ' ')
     FROM UNNEST(p.title_localized) t
     WHERE t.language = 'en') AS title,
  (SELECT STRING_AGG(a.text, ' ')
     FROM UNNEST(p.abstract_localized) a
     WHERE a.language = 'en') AS abstract,
  ARRAY_AGG(cl.text ORDER BY pos) AS claims,
  h.num_matching_claims AS num_matches
FROM `patents-public-data.patents.publications` p
JOIN hits h USING (publication_number)
LEFT JOIN UNNEST(p.claims_localized) AS cl WITH OFFSET AS pos
GROUP BY pub_num, title, abstract, num_matches
ORDER BY num_matches DESC
LIMIT 10;
"""

job_config = bigquery.QueryJobConfig(
    query_parameters=[
        bigquery.ArrayQueryParameter("keywords", "STRING", kw),
        bigquery.ScalarQueryParameter("cutoff_date", "DATE", date)
    ]
)

results = bq_client.query(query, job_config=job_config).result()

for row in results:
    print(row.publication_number, row.title_localized)