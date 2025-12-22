import streamlit as st
import pandas as pd
import psycopg2
import google.generativeai as genai
import os
import altair as alt # For Charts
from dotenv import load_dotenv
from pdf_parser import get_pdf_pages, parse_text_chunk

# --- 1. CONFIGURATION ---
load_dotenv()
st.set_page_config(page_title="SubZap 2.0", page_icon="🏆", layout="wide")

if not os.getenv("GEMINI_API_KEY") or not os.getenv("DATABASE_URL"):
    st.error("❌ Missing keys in .env file")
    st.stop()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# --- 2. DATABASE UTILS ---
def get_db_connection():
    try:
        return psycopg2.connect(os.getenv("DATABASE_URL"))
    except Exception as e:
        st.error(f"❌ DB Error: {e}")
        return None

def get_total_metrics():
    conn = get_db_connection()
    if conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*), SUM(amount) FROM transactions")
        res = cur.fetchone()
        conn.close()
        return res[0], (res[1] if res[1] else 0)
    return 0, 0

# --- 3. AI FUNCTIONS ---
def ask_gemini_to_write_sql(user_question):
    model = genai.GenerativeModel('gemini-2.5-flash')
    prompt = f"""
    You are a PostgreSQL expert. Convert the question to SQL.
    Table: 'transactions' (date, merchant_name, raw_description, payment_mode, amount, category)
    
    Rules: 
    1. Return ONLY SQL. No markdown.
    2. Use ILIKE for text.
    3. User Question: {user_question}
    """
    response = model.generate_content(prompt)
    return response.text.replace("```sql", "").replace("```", "").strip()

def ask_gemini_to_explain(user_question, data_summary):
    model = genai.GenerativeModel('gemini-2.5-flash')
    prompt = f"""
    Act as SubZap Financial Advisor.
    User Question: {user_question}
    Data: {data_summary}
    Analyze and be helpful. Mention specific amounts in ₹.
    """
    response = model.generate_content(prompt)
    return response.text

# --- 4. UI: SIDEBAR (Upload) ---
st.title("💳 SubZap 2.0: AI Financial Agent")


with st.sidebar:
    st.header("📂 Ingestion Engine")
    uploaded_file = st.file_uploader("Upload Bank PDF", type=["pdf"])
    
    if uploaded_file and st.button("Process & Save"):
        progress_bar = st.progress(0)
        status = st.empty()
        
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Simple Page Iterator (First 5 pages)
            import pypdf
            reader = pypdf.PdfReader(uploaded_file)
            max_pages = min(len(reader.pages), 5)
            
            total_added = 0
            
            for i in range(max_pages):
                raw_text = reader.pages[i].extract_text()
                status.write(f"Scanning Page {i+1}...")
                
                # We skip the separate cleaning func for brevity here, logic matches prev
                new_data = parse_text_chunk(raw_text) # Uses imported function
                
                if new_data:
                    data_tuples = [
                        (r['date'], r['merchant_name'], r.get('raw_description', r['merchant_name']),
                         r.get('payment_mode', 'Unknown'), r['amount'], r['category'])
                        for r in new_data
                    ]
                    
                    query = """
                        INSERT INTO transactions 
                        (date, merchant_name, raw_description, payment_mode, amount, category) 
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (date, raw_description, amount) DO NOTHING
                    """
                    cur.executemany(query, data_tuples)
                    conn.commit()
                    total_added += cur.rowcount
                
                progress_bar.progress((i+1)/max_pages)
                
            cur.close()
            conn.close()
            status.empty()
            if total_added > 0:
                st.success(f"✅ Added {total_added} new transactions!")
                import time
                time.sleep(1)
                st.rerun()
            else:
                st.warning("No new unique transactions found.")
                
        except Exception as e:
            st.error(f"Error: {e}")

    st.divider()
    count, spend = get_total_metrics()
    col1, col2 = st.columns(2)
    col1.metric("Transactions", count)
    col2.metric("Total Spend", f"₹{spend:,.0f}")

# --- 5. UI: TABS (The New Look) ---
tab1, tab2 = st.tabs(["📊 Analytics Dashboard", "🤖 AI Agent & Audit"])

# === TAB 1: VISUALIZATIONS ===
with tab1:
    conn = get_db_connection()
    if conn:
        # A. SPENDING BY CATEGORY (Donut Chart)
        df_cat = pd.read_sql_query("SELECT category, SUM(amount) as total FROM transactions GROUP BY category", conn)
        
        # B. MONTHLY TREND (Bar Chart)
        # Extract Month from Date
        df_trend = pd.read_sql_query("""
            SELECT TO_CHAR(date, 'YYYY-MM') as month, SUM(amount) as total 
            FROM transactions GROUP BY month ORDER BY month
        """, conn)
        conn.close()
        
        # Layout
        c1, c2 = st.columns(2)
        
        with c1:
            st.subheader("🍩 Spending by Category")
            if not df_cat.empty:
                chart_cat = alt.Chart(df_cat).mark_arc(innerRadius=50).encode(
                    theta="total",
                    color="category",
                    tooltip=["category", "total"]
                )
                st.altair_chart(chart_cat, use_container_width=True)
            else:
                st.info("No data yet.")
                
        with c2:
            st.subheader("📅 Monthly Trend")
            if not df_trend.empty:
                chart_trend = alt.Chart(df_trend).mark_bar().encode(
                    x="month",
                    y="total",
                    color=alt.value("#4c78a8"),
                    tooltip=["month", "total"]
                )
                st.altair_chart(chart_trend, use_container_width=True)
            else:
                st.info("No data yet.")
                
        # C. TOP EXPENSES TABLE
        st.subheader("💸 Top 5 Largest Expenses")
        conn = get_db_connection()
        df_top = pd.read_sql_query("SELECT date, merchant_name, amount, category FROM transactions ORDER BY amount DESC LIMIT 5", conn)
        conn.close()
        st.dataframe(df_top, use_container_width=True)

# === TAB 2: AGENT ===
with tab2:
    st.markdown("### 🕵️‍♂️ Price Audit & Chat")
    
    # 1. PRICE AUDIT BUTTON
    if st.button("⚠️ Audit My Subscriptions"):
        conn = get_db_connection()
        df_subs = pd.read_sql_query("""
            SELECT merchant_name, MAX(amount) as price, COUNT(*) as frequency 
            FROM transactions 
            GROUP BY merchant_name 
            HAVING COUNT(*) > 1 AND MAX(amount) > 50
        """, conn)
        conn.close()
        
        if not df_subs.empty:
            with st.spinner("Analyzing Market Prices..."):
                subs_text = df_subs.to_string(index=False)
                model = genai.GenerativeModel('gemini-2.5-flash')
                response = model.generate_content(f"""
                Audit these Indian subscriptions. Compare with 2024-25 market rates.
                Data: {subs_text}
                Output: Markdown Table (Service | User Pays | Market Price | Verdict).
                Highlight Overpayments.
                """)
                st.markdown(response.text)
        else:
            st.warning("No recurring subscriptions found.")

    st.divider()

    # 2. CHATBOT
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "Ask me about your spending (e.g., 'How much on Zomato?') "}]

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask SubZap..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            try:
                sql = ask_gemini_to_write_sql(prompt)
                conn = get_db_connection()
                df = pd.read_sql_query(sql, conn)
                conn.close()
                
                if df.empty:
                    resp = "No matching records found."
                else:
                    # Format amount for better reading
                    if 'amount' in df.columns:
                        df['amount'] = df['amount'].apply(lambda x: f"₹{x:,.2f}")
                        
                    data_str = df.to_string(index=False)
                    resp = ask_gemini_to_explain(prompt, data_str)
                    
                    with st.expander("See SQL & Data"):
                        st.code(sql, language="sql")
                        st.dataframe(df)
                        
                st.markdown(resp)
                st.session_state.messages.append({"role": "assistant", "content": resp})
            except Exception as e:
                st.error(f"Error: {e}")