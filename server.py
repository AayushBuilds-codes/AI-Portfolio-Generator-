import os
import sys
import json
import mimetypes
from werkzeug.utils import secure_filename
from flask import Flask, request, jsonify, render_template, send_from_directory, session, redirect, url_for
from dotenv import load_dotenv
from google.genai import types

# Load environment variables
load_dotenv()

# Import the existing portfolio generation logic from main.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from main import get_gemini_client, get_portfolio_json_from_gemini, generate_html_portfolio
except ImportError:
    print("Warning: Could not import get_portfolio_json_from_gemini and generate_html_portfolio from main.py")

template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, static_url_path='/static', static_folder='.', template_folder=template_dir)
app.secret_key = os.environ.get('SECRET_KEY', 'ai-portfolio-generator-secret-key-12983')

# Configure upload constraints
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'webp'}
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB limit

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

import traceback

@app.errorhandler(Exception)
def handle_exception(e):
    """Return HTML traceback on 500 errors for debugging."""
    return f"<h1>Internal Server Error (Traceback)</h1><pre>{traceback.format_exc()}</pre>", 500

@app.route('/')
def index():
    """Renders the main upload dashboard."""
    res = []
    base_path = os.path.dirname(os.path.abspath(__file__))
    for root, dirs, files in os.walk(base_path):
        for f in files:
            res.append(os.path.relpath(os.path.join(root, f), base_path))
    return f"<h1>Debug Files</h1><pre>" + "\n".join(res) + f"</pre><br>template_dir: {template_dir}"

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handles resume upload and extracts text using Gemini API or direct reading."""
    if 'resume_file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400
    
    file = request.files['resume_file']
    
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Unsupported file type. Please upload a TXT, PDF, or Image file.'}), 400

    filename = secure_filename(file.filename)
    ext = filename.rsplit('.', 1)[1].lower()
    
    try:
        # Read the file contents as bytes
        file_bytes = file.read()
        if not file_bytes:
            return jsonify({'error': 'The uploaded file is empty.'}), 400
        
        # If it's a plain text file, decode it directly
        if ext == 'txt':
            try:
                extracted_text = file_bytes.decode('utf-8')
            except UnicodeDecodeError:
                # Try fallback encoding
                extracted_text = file_bytes.decode('latin-1')
        else:
            # For PDF and Image files, send to Gemini API for OCR / Extraction
            client = get_gemini_client()
            
            # Determine appropriate mime-type
            if ext == 'pdf':
                mime_type = 'application/pdf'
            elif ext == 'png':
                mime_type = 'image/png'
            elif ext in ['jpg', 'jpeg']:
                mime_type = 'image/jpeg'
            elif ext == 'webp':
                mime_type = 'image/webp'
            else:
                mime_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'

            print(f"Sending file to Gemini API (mime_type: {mime_type})...")
            
            # Request Gemini 2.5 Flash to extract text
            # gemini-2.5-flash is highly optimized for document analysis and OCR
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[
                    types.Part.from_bytes(
                        data=file_bytes,
                        mime_type=mime_type,
                    ),
                    "Extract and transcribe all the text from this resume file exactly as written. Keep the original structure and content, but format it clearly as plain text. Do not add any introduction, explanations, or markdown formatting. Just return the extracted text."
                ]
            )
            
            extracted_text = (response.text or '').strip()
            
        if not extracted_text:
            return jsonify({'error': 'Failed to extract any text from the file.'}), 400

        # Save the extracted text to resume.txt (as requested)
        try:
            with open(os.path.join(app.root_path, "resume.txt"), "w", encoding="utf-8") as f:
                f.write(extracted_text)
        except OSError as e:
            print(f"Warning: Could not write resume.txt (read-only filesystem on Vercel): {e}")
            
        return jsonify({
            'success': True,
            'filename': filename,
            'extracted_text': extracted_text
        })
        
    except RuntimeError as e:
        print(f"Error during file processing: {e}")
        return jsonify({'error': str(e)}), 502
    except Exception as e:
        print(f"Error during file processing: {e}")
        return jsonify({'error': f"Error processing file: {str(e)}"}), 500

@app.route('/generate', methods=['POST'])
def generate_portfolio():
    """Generates the portfolio HTML files using the extracted resume text."""
    data = request.get_json()
    if not data or 'resume_text' not in data:
        return jsonify({'error': 'No resume text provided.'}), 400
        
    resume_text = data['resume_text'].strip()
    
    if not resume_text:
        return jsonify({'error': 'Resume text is empty.'}), 400
        
    try:
        # 1. Update resume.txt with the final text (in case user edited it on UI)
        try:
            with open(os.path.join(app.root_path, "resume.txt"), "w", encoding="utf-8") as f:
                f.write(resume_text)
        except OSError as e:
            print(f"Warning: Could not write resume.txt (read-only filesystem on Vercel): {e}")
            
        # 2. Request JSON structure from Gemini
        print("Sending resume text to Gemini to generate structured portfolio JSON...")
        json_response = get_portfolio_json_from_gemini(resume_text)
        
        # 3. Parse JSON
        portfolio_dict = json.loads(json_response)
        
        # Store in session for on-the-fly rendering fallback
        session['portfolio_data'] = portfolio_dict
        
        # 4. Generate standard and advanced html pages
        print("Rendering HTML templates...")
        generate_html_portfolio(portfolio_dict)
        
        return jsonify({
            'success': True,
            'message': 'Portfolios generated successfully!'
        })
        
    except json.JSONDecodeError as e:
        print(f"Gemini did not return valid JSON: {e}")
        return jsonify({'error': 'Gemini API failed to return structured JSON. Please try again.'}), 500
    except RuntimeError as e:
        print(f"Error generating portfolio: {e}")
        return jsonify({'error': str(e)}), 502
    except Exception as e:
        print(f"Error generating portfolio: {e}")
        return jsonify({'error': f"Error during generation: {str(e)}"}), 500

@app.route('/portfolio')
def view_portfolio():
    """Serves the standard portfolio page."""
    directory = "/tmp" if "VERCEL" in os.environ else app.root_path
    filepath = os.path.join(directory, 'portfolio.html')
    
    if not os.path.exists(filepath):
        portfolio_data = session.get('portfolio_data')
        if portfolio_data:
            try:
                generate_html_portfolio(portfolio_data)
            except Exception as e:
                print(f"Error regenerating standard portfolio: {e}")
                return "Portfolio file not found and regeneration failed.", 404
        else:
            return redirect(url_for('index'))
            
    return send_from_directory(directory, 'portfolio.html')

@app.route('/portfolio_advanced')
def view_portfolio_advanced():
    """Serves the advanced/premium portfolio page."""
    directory = "/tmp" if "VERCEL" in os.environ else app.root_path
    filepath = os.path.join(directory, 'portfolio_advanced.html')
    
    if not os.path.exists(filepath):
        portfolio_data = session.get('portfolio_data')
        if portfolio_data:
            try:
                generate_html_portfolio(portfolio_data)
            except Exception as e:
                print(f"Error regenerating advanced portfolio: {e}")
                return "Advanced portfolio file not found and regeneration failed.", 404
        else:
            return redirect(url_for('index'))
            
    return send_from_directory(directory, 'portfolio_advanced.html')

if __name__ == '__main__':
    # Run server on port 5000
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting server on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=True)
