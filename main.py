import streamlit as st
import pandas as pd
import psycopg2
import google.generativeai as genai
import os
from dotenv import load_dotenv

# --- 1. CONFIGURATION ---
load_dotenv() # Load keys from .env file

# Verify keys exist
if not os.getenv("GEMINI_API_KEY"):
    st.error("❌ GEMINI_API_KEY not found in .env file")
    st.stop()
if not os.getenv("DATABASE_URL"):
    st.error("❌ DATABASE_URL not found in .env file")
    st.stop()

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# --- 2. DATABASE CONNECTION (SUPABASE) ---
def get_db_connection():
    try:
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        return conn
    except Exception as e:
        st.error(f"❌ Database Connection Failed: {e}")
        return None

# --- 3. AI ENGINE (GEMINI API) ---
def ask_gemini_to_write_sql(user_question):
    # Use the model that is working for you (keep your 2.0 or 1.5 setting)
    model = genai.GenerativeModel('gemini-2.5-flash') 
    
    prompt = f"""
    You are a Senior PostgreSQL Data Analyst. 
    Convert the user's request into a correct, executable SQL query.
    
    Table Schema: 'transactions'
    - date (date)
    - description (text)
    - amount (decimal)
    - category (text)
    
    CRITICAL RULES:
    1. Return ONLY the raw SQL code. No markdown (```), no explanations.
    2. When asked for "highest" or "most expensive", you MUST use 'ORDER BY ... DESC LIMIT 1'.
    3. When grouping by month/category, you MUST include 'SUM(amount)' in the SELECT clause.
    4. For Month extraction, use: TO_CHAR(date, 'Month') or EXTRACT(MONTH FROM date).
    
    User Question: {user_question}
    """
    response = model.generate_content(prompt)
    return response.text.replace("```sql", "").replace("```", "").strip()

def ask_gemini_to_explain(user_question, data_summary):
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
    User Question: {user_question}
    Data Found (in Rupees ₹): 
    {data_summary}

    Act as a "SubZap" Financial Advisor. 
    Analyze the data and answer the user.
    - If you see monthly repeating charges, flag them as subscriptions.
    - Mention specific amounts in ₹.
    - Be concise and helpful.
    """
    response = model.generate_content(prompt)
    return response.text

# --- 4. FRONTEND UI ---
st.set_page_config(page_title="SubZap 2.0", page_icon="🇮🇳", layout="wide")

# Custom CSS for that "Dark Mode" look
st.markdown("""
<style>
    .stButton>button {width: 100%; border-radius: 8px; height: 3em;}
    [data-testid="stMetricValue"] {font-size: 24px;}
</style>
""", unsafe_allow_html=True)

st.title("🇮🇳 SubZap 2.0: Indian Finance Agent")
st.caption("Powered by **Supabase** & **Gemini Flash**")

# --- SIDEBAR DASHBOARD ---
with st.sidebar:
    st.header("📊 Financial Snapshot")
    
    # Live Metrics from Supabase
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*), SUM(amount) FROM transactions")
            res = cur.fetchone()
            count = res[0]
            total_spend = f"₹{res[1]:,.0f}" if res[1] else "₹0"
            conn.close()
        except:
            count = 0
            total_spend = "₹0"
    else:
        count = 0
        total_spend = "Error"

    col1, col2 = st.columns(2)
    col1.metric("Transactions", count)
    col2.metric("Total Spend", total_spend)
    
    st.divider()
    st.subheader("⚡ Quick Actions")
    if st.button("🔍 Find Hidden Subscriptions"):
        st.session_state.prompt_input = "Identify recurring monthly subscriptions and calculate the monthly cost."
    if st.button("🍔 Food & Zomato Spending"):
        st.session_state.prompt_input = "How much did I spend on Zomato, Swiggy, and Food?"
    if st.button("📈 Most Expensive Month"):
        st.session_state.prompt_input = "Which month had the highest spending?"

# --- CHAT INTERFACE ---
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Namaste! 🙏 I have analyzed your transactions. Ask me about your spending!"}]

# Handle Quick Actions
if "prompt_input" in st.session_state and st.session_state.prompt_input:
    user_input = st.session_state.prompt_input
    del st.session_state.prompt_input
else:
    user_input = None

# Display Chat
for message in st.session_state.messages:
    avatar = "🤖" if message["role"] == "assistant" else "👤"
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])

# User Input
if prompt := st.chat_input("Ask about your finances...") or user_input:
    final_prompt = user_input if user_input else prompt
    st.session_state.messages.append({"role": "user", "content": final_prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(final_prompt)

    with st.chat_message("assistant", avatar="🤖"):
        msg_placeholder = st.empty()
        msg_placeholder.markdown("🧠 **Thinking...**")
        
        try:
            # 1. Gemini writes SQL
            sql = ask_gemini_to_write_sql(final_prompt)
            
            # 2. Run SQL on Supabase
            conn = get_db_connection()
            df = pd.read_sql_query(sql, conn)
            conn.close()
            
            # 3. Explain Results
            if df.empty:
                response = "I searched your records but found no matching transactions."
            else:
                # Format currency for cleaner reading
                df_display = df.copy()
                if 'amount' in df_display.columns:
                    df_display['amount'] = df_display['amount'].apply(lambda x: f"₹{x:,.2f}")
                
                data_str = df_display.to_string(index=False)
                response = ask_gemini_to_explain(final_prompt, data_str)
                
                with st.expander("View Technical Details (SQL)"):
                    st.code(sql, language='sql')
                    st.dataframe(df)

            msg_placeholder.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})

        except Exception as e:
            st.error(f"Error: {e}")