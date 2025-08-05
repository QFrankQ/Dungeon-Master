from typing import List, Dict
from qdrant_client import QdrantClient
from dotenv import load_dotenv
from google import genai
from google.genai import types
import os

load_dotenv()

class VectorService:
    """Service for vector database operations and embedding generation"""
    
    def __init__(self):
        self.qdrant_api_key = os.getenv("QDRANT_API_KEY")
        self.google_api_key = os.getenv("GEMINI_API_KEY")
        
        if not self.qdrant_api_key or not self.google_api_key:
            raise ValueError("Missing required API keys: QDRANT_API_KEY and/or GEMINI_API_KEY")
        
        self.client_genai = genai.Client(api_key=self.google_api_key)
        self.client_qdrant = QdrantClient(
            api_key=self.qdrant_api_key, 
            host="ad28f149-0c28-45f3-85bb-e7ff19367d8c.us-east-1-0.aws.cloud.qdrant.io"
        )
    
    def get_embedding(self, text: str) -> List[float]:
        """Get embedding for a single text"""
        result = self.client_genai.models.embed_content(
            model="gemini-embedding-001",
            contents=text,
            config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY", output_dimensionality=768)
        )
        return result.embeddings[0].values
    
    def search_combat_rules(self, query: str, top_k: int = 3) -> List[Dict]:
        """Search for combat rules using semantic similarity"""
        try:
            query_vector = self.get_embedding(query)
            
            search_result = self.client_qdrant.query_points(
                collection_name="COMBAT_RULES",
                query=query_vector,
                limit=top_k
            )
            
            # Format results for easier consumption
            formatted_results = []
            for hit in search_result.points:
                formatted_results.append({
                    'score': hit.score,
                    'text': hit.payload['text'],
                    'tags': hit.payload.get('tags', []),
                    'id': hit.id
                })
            
            return formatted_results
            
        except Exception as e:
            print(f"Error searching combat rules: {e}")
            return []

# Global instance for easy import
vector_service = VectorService()