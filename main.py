import os
import sys
import json
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

# Import the NEW officially supported Google GenAI SDK
from google import genai

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Always load the project's .env, even when the server is started elsewhere.
load_dotenv(os.path.join(BASE_DIR, ".env"))


def get_gemini_client():
    """Create a Gemini client using an API key from the environment."""
    api_key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is missing. Create a Gemini API key in Google AI Studio "
            "and add it to .env."
        )

    if api_key.startswith(("ya29.", "1//", "Bearer ")):
        raise RuntimeError(
            "GEMINI_API_KEY contains an OAuth access token. Use a Gemini API key "
            "from https://aistudio.google.com/app/apikey instead."
        )

    if not api_key.startswith("AIza"):
        raise RuntimeError(
            "GEMINI_API_KEY does not look like a Google AI Studio API key. "
            "Create a key at https://aistudio.google.com/app/apikey and replace "
            "the value in .env."
        )

    return genai.Client(api_key=api_key)

def read_and_clean_resume(filepath=None):
    """Reads the resume file and cleans blank lines and extra spaces."""
    filepath = filepath or os.path.join(BASE_DIR, "resume.txt")
    try:
        with open(filepath, "r", encoding="utf-8") as file:
            raw_text = file.read()
            
        if not raw_text.strip():
            print("Error: resume.txt is empty.")
            sys.exit(1)
            
        # Clean up unnecessary spaces and blank lines
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        cleaned_text = "\n".join(lines)
        
        if len(cleaned_text) < 50:
            print("Error: resume.txt is too short to be a valid resume.")
            sys.exit(1)
            
        return cleaned_text
    except FileNotFoundError:
        print(f"Error: The file '{filepath}' was not found. Please create it.")
        sys.exit(1)

def get_portfolio_json_from_gemini(resume_text):
    """Sends the resume to Gemini using the new SDK and requests structured JSON."""
    client = get_gemini_client()
    
    # gemini-2.0-flash is the standard fast model
    model_name = "gemini-2.5-flash"

    prompt = f"""
    You are an expert portfolio generator. Extract information from the provided resume text and format it into a structured JSON response.
    
    STRICT RULES:
    1. Use ONLY the information provided in the resume. DO NOT invent, assume, or hallucinate skills, experiences, projects, dates, or links.
    2. If information for a specific field is missing, use an empty string "", an empty list [], or null as appropriate.
    3. Output exactly and ONLY valid JSON. Do not include markdown formatting like ```json or ```. Do not provide any conversational text.
    4. Keep the professional summary concise and factual.

    REQUIRED JSON SCHEMA:
    {{
      "Name": "string",
      "Headline": "string",
      "Professional Summary": "string",
      "Skills": ["string"],
      "Education": [{{"degree": "string", "institution": "string", "year": "string"}}],
      "Experience": [{{"title": "string", "company": "string", "duration": "string", "responsibilities": ["string"]}}],
      "Projects": [{{"title": "string", "description": "string", "technologies": ["string"]}}],
      "Achievements": ["string"],
      "Contact": {{"email": "string", "phone": "string", "linkedin": "string", "github": "string"}}
    }}

    RESUME TEXT:
    {resume_text}
    """

    try:
        # Call the model using the new syntax
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )

        response_text = (response.text or "").strip()
        if not response_text:
            raise RuntimeError("Gemini returned an empty response.")

        # Clean potential markdown wrapping if Gemini ignores instructions
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        return response_text.strip()

    except Exception as e:
        raise RuntimeError(f"Gemini API request failed: {e}") from e

def generate_html_portfolio(portfolio_data):
    """Uses Jinja2 template to generate HTML from JSON data."""
    try:
        # Load the Jinja2 environment
        env = Environment(loader=FileSystemLoader(BASE_DIR))
        
        # 1. Render standard portfolio
        template_standard = env.get_template('template.html')
        html_out_standard = template_standard.render(data=portfolio_data)
        with open(os.path.join(BASE_DIR, "portfolio.html"), "w", encoding="utf-8") as f:
            f.write(html_out_standard)
        print("Success! Generated portfolio.html")
        
        # 2. Render advanced portfolio
        template_advanced = env.get_template('template_advanced.html')
        html_out_advanced = template_advanced.render(data=portfolio_data)
        with open(os.path.join(BASE_DIR, "portfolio_advanced.html"), "w", encoding="utf-8") as f:
            f.write(html_out_advanced)
        print("Success! Generated portfolio_advanced.html")
        
    except Exception as e:
        raise RuntimeError(f"Error generating HTML: {e}") from e

if __name__ == "__main__":
    print("1. Reading and cleaning resume...")
    resume_text = read_and_clean_resume()
    
    print("2. Sending to Gemini API (this may take a few seconds)...")
    json_response = get_portfolio_json_from_gemini(resume_text)
    
    print("3. Parsing JSON data...")
    try:
        portfolio_dict = json.loads(json_response)
    except json.JSONDecodeError as e:
        print("Error: Gemini did not return valid JSON.")
        print(f"Raw output was:\n{json_response}")
        sys.exit(1)
        
    print("4. Generating HTML portfolio...")
    generate_html_portfolio(portfolio_dict)