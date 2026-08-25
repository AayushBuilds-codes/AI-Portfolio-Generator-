
# AI Resume to Portfolio Generator

This Flask application accepts a TXT, PDF, or image resume, extracts its text with Gemini when needed, and generates standard and premium HTML portfolios.

## Setup on Windows

1. Open Command Prompt in this folder:
   ```bat
   cd /d "C:\Users\aayus\OneDrive\Bootcamp\Portfolio Generator"
   ```
2. Create and activate a virtual environment:
   ```bat
   py -m venv .venv
   .venv\Scripts\activate
   ```
3. Install dependencies:
   ```bat
   python -m pip install -r requirements.txt
   ```
4. Create a Gemini API key at [Google AI Studio](https://aistudio.google.com/app/apikey). Put the key in a file named `.env` in this folder:
   ```dotenv
   GEMINI_API_KEY=AIza-your-key-here
   ```

Use a Google AI Studio API key, not an OAuth access token, an OpenAI key, or a Google Cloud service-account token. The key normally starts with `AIza`. Never commit `.env` or share the key.

## Run

Start the web server from this folder:
```bat
python server.py
```

Open http://127.0.0.1:5000/ in your browser. Do not open `templates/upload.html` directly. Uploading a TXT file works locally; PDF and image uploads require a valid Gemini key for OCR. You can verify Gemini access before uploading with:
```bat
python check_models.py
```

After generation, use the links on the page or open `/portfolio` and `/portfolio_advanced`.
