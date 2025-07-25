from typing import List, Dict
from dotenv import load_dotenv
from google import genai
import json
import os
import requests
load_dotenv()


# client = OpenAI()
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

def get_embedding(texts):
    result = client.models.embed_content(
        model="gemini-embedding-001",
        contents= texts,
        task_type="RETRIEVAL_DOCUMENT"
        )
    return result.embeddings

def prepare_docs(rules_data: Dict) -> List[Dict]:
    documents = []
    for rule in rules_data["combat_rules"][:2]:
        doc = {
            "text": f"{rule['section_title']}\n\n{rule['content']}",
            "metadata": {
                "section_title": rule["section_title"],
                "tags": rule.get("tags", [])
            }
        }
        documents.append(doc)
    return documents

if __name__ == "__main__":
    # Create collection
    # client_qdrant.recreate_collection(
    #     collection_name=COLLECTION_NAME,
    #     vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
    # )

    # Prepare and upload
    rules_data = json.load(open("db/combat_rules.json"))
    embeddings = []

    for item in rules_data["combat_rules"]:
        text = f"{item['section_title']}\n\n{item['content']}"
        emb = get_embedding(text)
        embeddings.append({
            "id": item["section_title"],  # or a hash
            "text": text,
            "tags": item["tags"],
            "embedding": emb
        })

    # Save locally
    with open("combat_rules_embedded.json", "w") as f:
        json.dump(embeddings, f)