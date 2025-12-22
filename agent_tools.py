from duckduckgo_search import DDGS
import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def search_current_price(service_name):
    """
    1. Searches the web for the current price of a service in India.
    2. Uses Gemini to read the search results and extract a single number (float).
    """
    try:
        # 1. Search the Web (Free)
        query = f"current monthly subscription price of {service_name} in India 2025"
        results = DDGS().text(query, max_results=3)
        
        if not results:
            return None, "No search results found."

        # Combine snippets into one text block
        search_context = "\n".join([r['body'] for r in results])

        # 2. Ask Gemini to extract the price
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        I searched for the price of '{service_name}' and got these results:
        
        {search_context}
        
        Task: Extract the standard monthly price in Indian Rupees (₹).
        Rules:
        - If multiple plans exist, pick the "Standard" or "Premium" one (most common).
        - Return ONLY the number (e.g. 649).
        - If you cannot find a price, return '0'.
        """
        
        response = model.generate_content(prompt)
        price_text = response.text.strip()
        
        # Clean up string to get float
        import re
        price = re.findall(r"[-+]?\d*\.\d+|\d+", price_text)
        
        if price:
            return float(price[0]), search_context
        else:
            return 0, search_context

    except Exception as e:
        print(f"Search Error: {e}")
        return 0, str(e)