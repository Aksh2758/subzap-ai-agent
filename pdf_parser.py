import pypdf
import google.generativeai as genai
import json
import os
import re
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def clean_text_before_ai(raw_text):
    """
    Optimization: Removes lines that definitely don't have money.
    If a line has no numbers, it's likely 'Terms & Conditions' garbage.
    Removing this speeds up Gemini by 50%.
    """
    lines = raw_text.split('\n')
    cleaned_lines = []
    for line in lines:
        # Check if line contains at least one digit (0-9)
        # We keep the line if it has a number (like date or amount)
        if any(char.isdigit() for char in line):
            cleaned_lines.append(line)
    return "\n".join(cleaned_lines)

def parse_text_chunk(text_chunk):
    """
    Sends a smaller chunk of text to Gemini for fast processing.
    """
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
        Extract financial transactions from this Bank Statement text segment.
        
        Input Text:
        {text_chunk}

        Rules:
        1. **Merchant Name:** Clean name (e.g. "Zomato", "Uber").
        2. **Raw Description:** Keep original text line.
        3. **Payment Mode:** 'UPI', 'Card', 'Cash', 'Other'.
        4. **Amount:** Positive float. Ignore credits/deposits.
        5. **Date:** YYYY-MM-DD.
        
        Output JSON List:
        [{{ "date": "2024-01-01", "merchant_name": "Name", "raw_description": "Raw", "payment_mode": "UPI", "amount": 100.0, "category": "Food" }}]
        """
        
        response = model.generate_content(prompt)
        cleaned_json = response.text.replace("```json", "").replace("```", "").strip()
        
        # Safe extraction of JSON list
        start = cleaned_json.find('[')
        end = cleaned_json.rfind(']') + 1
        if start != -1 and end != -1:
            return json.loads(cleaned_json[start:end])
        return []

    except Exception as e:
        print(f"AI Error: {e}")
        return []

def get_pdf_pages(uploaded_file):
    """
    Generator that yields one page of text at a time.
    """
    pdf_reader = pypdf.PdfReader(uploaded_file)
    for page in pdf_reader.pages:
        raw_text = page.extract_text()
        # Clean garbage text immediately to save AI time
        yield clean_text_before_ai(raw_text)