import json
from dataclasses import dataclass
from typing import List, Optional

from google import genai
from google.genai import types
from google.cloud import bigquery
from serpapi import GoogleSearch


@dataclass
class Patent:
    pub_num: str
    title: str
    snippet: str
    pdf_link: str



bq_client = bigquery.Client(project="aime-hello-world")
genai_client = genai.Client(project="aime-hello-world", location="us-west1", vertexai=True)

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

def generate_prompt(prompt: str, params: str, matches: int, max: int = 200, min: int = 10):
    if params == "":
        return prompt
    
    fix = "too high, provide a more specific" if matches > 200 else "too low, provide a less specific" if matches < min else "a not satisfactory"

    return f"""
    Previously, you generated the group of synonyms {params}, which was {fix} group of synonyms.
    {prompt}
    """

def build_prompt(l: list):
    quoted_groups = [[f'"{w}"' for w in group] for group in l]

    return " AND ".join(f"({' OR '.join(group)})" for group in quoted_groups)


def fetch_matches(max_pages = 1, max_tries = 5):
    tries = 0
    old_output = ""
    matches = 0

    while True:

        reprompt = False

        synonym_prompt = f"""
        Generate groups of synonyms to use for patent prior-art searching.
        Each group should contain 3 closely related terms that could be used interchangeably.
        Groups should collectively capture:
        - What is built (the invention itself)
        - How it works or what processes it performs
        - Key technical details or domain-specific terms that a patent examiner would care about

        Return the result as a nested JSON array in which each inner array is a group of synonyms.
        """

        prompt = generate_prompt(synonym_prompt, old_output, matches)

        synonym_schema = {
            "type": "object",
            "properties": {
                "synonym_groups": {
                    "type": "array",
                    "items": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": 3
                    }
                }
            },
            "required": ["synonym_groups"]
        }


        sy = call_LLM(genai_client, model_name=model, content=multimedia_content(prompt, src), conf=response_schema(synonym_schema))
        if sy is None:
            print("keyword LLM call failed.")
            quit()

        query = build_prompt(sy["synonym_groups"])

        pubs: list[Patent] = []

        for page in range(1, max_pages + 1):
            params = {
                "engine": "google_patents",
                "q": query,
                "api_key": "c1399ae2d3bedfc7239371b16e0cb5650465fbc58220f7843606525644f7b468",
                "page": page
            }
            search = GoogleSearch(params)
            results = search.get_dict()

            if 10 > (matches := results.get("search_information", {}).get("total_results", -1)) or matches > 200:

                old_output = str(sy)
                tries+=1
                reprompt = True
                print(f"The query {query} generated {matches} results, reprompting for accuracy\n\n")
                break

            if "organic_results" not in results or not results["organic_results"]:
                print(f"No results on page {page}, stopping early.")
                return pubs
            print(f"query success, matched {matches} patents")
            for pub in results["organic_results"]:
                pubs.append(
                    Patent(
                        pub.get("publication_number", "no publication number available"),
                        pub.get("title", "no title available"),
                        pub.get("snippet", "no snippet available"),
                        pub.get("pdf", "no pdf available")
                    )
                )
        if not reprompt:
            return pubs
        if tries >= max_tries:
            return None
        

def compare_novelty(prospect: Patent, potential_match: Patent):
    ...


pubs = fetch_matches()