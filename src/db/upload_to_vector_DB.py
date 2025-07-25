from typing import List, Dict
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from dotenv import load_dotenv
from google import genai
import json
import pickle
import os
import requests
load_dotenv()

QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

# def search_qdrant(query, top_k=3):
#     query_vec = embed_text([query])[0]
#     hits = client_qdrant.search(
#         collection_name=COLLECTION_NAME,
#         query_vector=query_vec,
#         limit=top_k
#     )
#     return [hit.payload["text"] for hit in hits]


if __name__ == "__main__":
    

    client = QdrantClient(api_key=QDRANT_API_KEY, host="ad28f149-0c28-45f3-85bb-e7ff19367d8c.us-east-1-0.aws.cloud.qdrant.io")

    # (Optional) create collection
    collection_name = "COMBAT_RULES"
    if client.collection_exists(collection_name):
        client.delete_collection(collection_name)
    
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=768, distance=Distance.COSINE)
    )

    # Load embedded data
    with open("db/combat_rules_embedded.pkl", "rb") as f:
        items = pickle.load(f)

    points = [
        PointStruct(
            id=i,
            vector=item["embedding"][0].values,
            payload={
                "text": item["text"],
                "tags": item["tags"]
            }
        )
        for i, item in enumerate(items)
    ]

    client.upsert(collection_name=collection_name, points=points)
