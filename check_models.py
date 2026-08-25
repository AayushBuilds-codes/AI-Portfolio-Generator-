import os
from dotenv import load_dotenv
from main import get_gemini_client

# Load the API key
load_dotenv()
print("Your API key has access to these models:")
try:
    client = get_gemini_client()
    for model in client.models.list():
        # We only want to print models that generate text
        if "generateContent" in model.supported_actions:
            print(f"- {model.name}")
except Exception as e:
    print(f"Error checking models: {e}")