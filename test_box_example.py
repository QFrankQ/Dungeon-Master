from pydantic import BaseModel
from pydantic_ai.models.gemini import GeminiModel
from pydantic_ai.providers.google_gla import GoogleGLAProvider
from pydantic_ai import Agent
import os
import json
from dotenv import load_dotenv



from pydantic_ai import Agent, NativeOutput

# Load environment variables from .env file
load_dotenv()
MODEL_NAME = 'gemini-1.5-flash'

class Box(BaseModel):
    width: int
    height: int
    depth: int
    units: str

class Fruit(BaseModel):
    name: str
    color: str


class Vehicle(BaseModel):
    name: str
    wheels: int

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
model = GeminiModel(
        MODEL_NAME, provider=GoogleGLAProvider(api_key=GEMINI_API_KEY)
    )
        
# agent = Agent(
#     model,
#     output_type=[Box, str], 
#     system_prompt=(
#         "Extract me the dimensions of a box, "
#         "if you can't extract all data, ask the user to try again."
#     ),
# )

# result = agent.run_sync('The box is 10x20x30')
# print(result.output)
# #> Please provide the units for the dimensions (e.g., cm, in, m).

# result = agent.run_sync('The box is 10x20x30 cm', message_history=result.all_messages())
# print(result)
# print(type(result.output))
# print(result.output)

# # Print JSON with proper indentation
# json_data = json.loads(result.all_messages_json())
# print(json.dumps(json_data, indent=2))
# #> width=10 height=20 depth=30 units='cm'



agent = Agent(
    model,
    output_type=NativeOutput(
        [Vehicle], 
        name='Fruit_or_vehicle',
        description='Return a fruit or vehicle.'
    ),
)
result = agent.run_sync('What is a Ford Explorer?')
print(repr(result.output))
print(result)
print(type(result.output))
print(result.output)
json_data = json.loads(result.all_messages_json())
print(json.dumps(json_data, indent=2))
#> Vehicle(name='Ford Explorer', wheels=4)