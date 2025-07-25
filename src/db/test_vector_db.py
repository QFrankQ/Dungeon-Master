from typing import List, Dict
from qdrant_client import QdrantClient
from dotenv import load_dotenv
from google import genai
from google.genai import types
import os

load_dotenv()

QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
client_genai = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
client_qdrant = QdrantClient(api_key=QDRANT_API_KEY, host="ad28f149-0c28-45f3-85bb-e7ff19367d8c.us-east-1-0.aws.cloud.qdrant.io")

def get_embedding(text: str):
    """Get embedding for a single text"""
    result = client_genai.models.embed_content(
        model="gemini-embedding-001",
        contents=text,
        config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY", output_dimensionality=768)
    )
    return result.embeddings[0].values

def search_combat_rules(query: str, top_k: int = 3):
    """Search for combat rules using semantic similarity"""
    query_vector = get_embedding(query)
    
    search_result = client_qdrant.search(
        collection_name="COMBAT_RULES",
        query_vector=query_vector,
        limit=top_k
    )
    
    return search_result

def test_vector_db():
    """Test the vector database functionality"""
    print("🧪 Testing Vector Database Functionality\n")
    
    # Test queries
    test_queries = [
        "How does initiative work in combat?",
        "What happens when a character takes damage?",
        "How do I handle morale in battle?",
        "What are the rules for attacking?"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"Test {i}: '{query}'")
        print("-" * 50)
        
        try:
            results = search_combat_rules(query, top_k=2)
            
            if results:
                for j, hit in enumerate(results, 1):
                    print(f"  Result {j} (Score: {hit.score:.3f}):")
                    print(f"    Tags: {hit.payload.get('tags', [])}")
                    print(f"    Text: {hit.payload['text'][:200]}...")
                    print()
            else:
                print("  No results found")
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
        
        print()

if __name__ == "__main__":
    test_vector_db()