import streamlit as st
import pandas as pd
import psycopg2
import google.generativeai as genai
import os
from dotenv import load_dotenv
from pdf_parser import extract_transactions_from_pdf # Import our new parser

# --- 1. CONFIGURATION ---
load_dotenv()

if not os.getenv("GEMINI_API_KEY") or not os.getenv("DATABASE_URL"):
    st.error("❌ Missing keys in .env file")
    st.stop()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# --- 2. DATABASE CONNECTION ---
def get_db_connection():
    try:
        return psycopg2.connect(os.getenv("DATABASE_URL"))
    except Exception as e:
        st.error(f"❌ DB Error: {e}")
        return None

# --- 3. AI ENGINE (UPDATED FOR NEW COLUMNS) ---
def ask_gemini_to_write_sql(user_question):
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
    You are a PostgreSQL expert analyzing financial data.
    Convert the user's request into a SQL query.
    
    Table: 'transactions'
    Columns: 
    - date (date)
    - merchant_name (text) -> The clean name (e.g. 'Zomato')
    - raw_description (text) -> Full text with IDs (e.g. 'UPI-123-ZOMATO')
    - payment_mode (text) -> 'UPI', 'Card', 'Cash'
    - amount (decimal)
    - category (text)
    
    Rules: 
    1. Return ONLY the raw SQL code.
    2. Use ILIKE for search.
    3. If user asks for "Subscriptions", look for repeating 'merchant_name'.
    4. If user asks for "Transaction ID" or "Details", select 'raw_description'.
    5. If user asks about UPI vs Card, check 'payment_mode'.
    
    User Question: {user_question}
    """
    response = model.generate_content(prompt)
    return response.text.replace("```sql", "").replace("```", "").strip()

def ask_gemini_to_explain(user_question, data_summary):
    model = genai.GenerativeModel('gemini-2.5-flash')
    prompt = f"""
    User Question: {user_question}
    Data Found: {data_summary}

    Act as 'SubZap', a financial advisor.
    - If finding subscriptions, highlight the monthly cost.
    - If showing details, mention the Payment Mode or IDs if relevant.
    - Be concise.
    """
    response = model.generate_content(prompt)
    return response.text

# --- 4. FRONTEND UI ---
st.set_page_config(page_title="SubZap 2.0", page_icon="💳", layout="wide")

st.markdown("""
<style>
    .stButton>button {width: 100%; border-radius: 8px; height: 3em;}
    [data-testid="stMetricValue"] {font-size: 24px;}
</style>
""", unsafe_allow_html=True)

st.title("💳 SubZap 2.0: Smart Financial Agent")

# --- SIDEBAR: UPLOAD & METRICS ---
with st.sidebar:
    st.header("📂 Import Data")
    uploaded_file = st.file_uploader("Upload Bank Statement (PDF)", type=["pdf"])
    
    if uploaded_file is not None:
        if st.button("Process & Save to DB"):
            with st.spinner("⚡ Speed Processing..."):
                # 1. Extract (Limit to 1 page inside pdf_parser.py for speed testing)
                new_data = extract_transactions_from_pdf(uploaded_file)
                
                if new_data:
                    conn = get_db_connection()
                    cur = conn.cursor()
                    
                    # PREPARE DATA FOR BULK INSERT (Much Faster!)
                    # We create a list of tuples: [(date, merchant, raw, mode, amount, category), ...]
                    data_tuples = [
                        (
                            row['date'],
                            row['merchant_name'],
                            row.get('raw_description', row['merchant_name']),
                            row.get('payment_mode', 'Unknown'),
                            row['amount'],
                            row['category']
                        )
                        for row in new_data
                    ]

                    query = """
                        INSERT INTO transactions 
                        (date, merchant_name, raw_description, payment_mode, amount, category) 
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (date, raw_description, amount) DO NOTHING
                    """

                    try:
                        # 🚀 THE SPEED TRICK: executemany
                        # Sends all data in ONE network packet instead of 50
                        cur.executemany(query, data_tuples)
                        conn.commit()
                        st.success(f"✅ FAST Upload: Added {len(data_tuples)} records instantly!")
                        
                        # Close connection immediately
                        cur.close()
                        conn.close()
                        
                        # Wait 1 sec so user sees the success message, then refresh
                        import time
                        time.sleep(1) 
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Database Error: {e}")
                else:
                    st.error("Could not parse PDF. Try a clearer file.")
    
    st.divider()
    
    # Financial Snapshot
    conn = get_db_connection()
    if conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*), SUM(amount) FROM transactions")
        res = cur.fetchone()
        count = res[0]
        total_spend = f"₹{res[1]:,.0f}" if res[1] else "₹0"
        conn.close()
    else:
        count = 0
        total_spend = "₹0"

    col1, col2 = st.columns(2)
    col1.metric("Transactions", count)
    col2.metric("Total Spend", total_spend)

    st.subheader("⚡ Quick Questions")
    if st.button("🔍 Find Subscriptions"):
        st.session_state.prompt = "Identify recurring monthly subscriptions based on Merchant Name."
    if st.button("💳 UPI vs Card Usage"):
        st.session_state.prompt = "How much did I spend using UPI vs Credit Card?"
    if st.button("🧾 Show Zomato Details"):
        st.session_state.prompt = "Show me the Raw Descriptions for all Zomato transactions."

# --- CHAT UI ---
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "I can track your subscriptions and payment modes. Ask away!"}]

# Handle button clicks
if "prompt" in st.session_state and st.session_state.prompt:
    user_input = st.session_state.prompt
    del st.session_state.prompt
else:
    user_input = None

# Display History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# User Input
if prompt := st.chat_input("Ask about subscriptions, UPI, or refunds...") or user_input:
    final_prompt = user_input if user_input else prompt
    st.session_state.messages.append({"role": "user", "content": final_prompt})
    with st.chat_message("user"):
        st.markdown(final_prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        placeholder.markdown("🧠 **Thinking...**")
        
        try:
            # 1. SQL
            sql = ask_gemini_to_write_sql(final_prompt)
            
            # 2. DB
            conn = get_db_connection()
            df = pd.read_sql_query(sql, conn)
            conn.close()
            
            # 3. Explain
            if df.empty:
                response = "No matching records found."
            else:
                data_str = df.to_string(index=False)
                response = ask_gemini_to_explain(final_prompt, data_str)
                
                with st.expander("View Data & SQL"):
                    st.code(sql, language='sql')
                    st.dataframe(df) # Shows all columns including raw_description
            
            placeholder.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})

        except Exception as e:
            st.error(f"Error: {e}")