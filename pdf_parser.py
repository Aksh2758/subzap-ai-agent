import pypdf
import google.generativeai as genai
import json
import os
import re
from dotenv import load_dotenv

load_dotenv()

# Configure Gemini
if not os.getenv("GEMINI_API_KEY"):
    raise ValueError("GEMINI_API_KEY not found in .env")
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def extract_transactions_from_pdf(uploaded_file):
    """
    Reads a PDF and uses Gemini to extract Clean Name, Raw Text, and Payment Mode.
    """
    try:
        # 1. Read PDF Text (First 3 pages max to save token limits)
        pdf_reader = pypdf.PdfReader(uploaded_file)
        text_content = ""
        for i, page in enumerate(pdf_reader.pages):
            if i > 2: break 
            text_content += page.extract_text() + "\n"

        # 2. Ask Gemini to Parse it
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        prompt = f"""
        You are an expert Data Extraction AI. 
        I am providing raw text from a Bank Statement (HDFC, SBI, GPay, etc.).
        Extract individual spending transactions into a JSON list.

        Input Text:
        {text_content[:30000]} 

        Rules:
        1. **Merchant Name:** Extract the CLEAN name of the shop/person (e.g., "Zomato", "Starbucks", "Netflix").
        2. **Raw Description:** Keep the EXACT original text line (crucial for Transaction IDs).
        3. **Payment Mode:** Guess based on text: 'UPI', 'Card' (POS/Debit), 'Cash' (ATM), 'NetBanking'. Default to 'Other'.
        4. **Amount:** Positive float. Ignore credits/deposits.
        5. **Category:** Guess the category (Food, Travel, Utilities, etc.).
        6. **Date:** Format YYYY-MM-DD.
        
        Output Format (JSON List ONLY):
        [
            {{
                "date": "2024-10-05", 
                "merchant_name": "Starbucks", 
                "raw_description": "POS 445590 STARBUCKS COFFEE MUMBAI",
                "payment_mode": "Card",
                "amount": 250.00, 
                "category": "Food"
            }}
        ]
        """
        
        response = model.generate_content(prompt)
        
        # 3. Clean the JSON response
        cleaned_json = response.text.replace("```json", "").replace("```", "").strip()
        
        # Extract just the list part if Gemini adds extra text
        start_idx = cleaned_json.find('[')
        end_idx = cleaned_json.rfind(']') + 1
        if start_idx != -1 and end_idx != -1:
            cleaned_json = cleaned_json[start_idx:end_idx]

        transactions = json.loads(cleaned_json)
        return transactions

    except Exception as e:
        print(f"Error parsing PDF: {e}")
        return []