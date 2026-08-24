import os
from dotenv import load_dotenv
from google import genai

# Load the API key
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

# Connect to Google
client = genai.Client(api_key=api_key)

print("Your API key has access to these models:")
try:
    for model in client.models.list():
        # We only want to print models that generate text
        if "generateContent" in model.supported_actions:
            print(f"- {model.name}")
except Exception as e:
    print(f"Error checking models: {e}")