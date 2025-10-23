from pydantic import BaseModel

from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
import os
import dotenv
dotenv.load_dotenv()
MODEL_NAME = 'gemini-2.0-flash-lite'
class CityLocation(BaseModel):
    city: str
    country: str

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
model = GoogleModel(
    MODEL_NAME, provider=GoogleProvider(api_key=GOOGLE_API_KEY)
)
agent = Agent(model=model, output_type=CityLocation)
result = agent.run_sync('Where were the olympics held in 2012?')
print(type(result))
print(result.output)
#> city='London' country='United Kingdom'
print(result.usage())
#> RunUsage(input_tokens=57, output_tokens=8, requests=1)