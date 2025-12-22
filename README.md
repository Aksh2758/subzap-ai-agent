# 🏆 SubZap 2.0: AI Financial Agent

SubZap is an **Agentic AI Financial Firewall**. It connects to your raw bank statements, uses Large Language Models (LLMs) to "clean" messy transaction data, and autonomously hunts for "Zombie Subscriptions" (forgotten recurring charges) that drain your finances.

![alt text](<Screenshot 2025-12-22 191713.png>)

## 🚀 What's New in v2.0?
The project has migrated from a Hackathon prototype to a **Production-Grade Application**:
- **📄 Universal Ingestion Engine:** Drag-and-drop PDF parsing for Indian Bank Statements (HDFC, SBI, UPI, etc.).
- **🧹 Twin-Column Intelligence:** Stores both the *Raw Bank Text* (for refunds) and *AI-Cleaned Merchant Names* (for analytics).
- **📊 Interactive Dashboard:** Visual spending breakdown using Altair charts.
- **⚡ The "Forever Free" Stack:** Migrated from AlloyDB to **Supabase** and **Gemini 2.5 Flash** for zero-cost maintenance.

---

## 🛠️ Tech Stack

| Component | Technology | Description |
| :--- | :--- | :--- |
| **Brain** | **Google Gemini 2.5 Flash** | Used for PDF extraction, Text-to-SQL generation, and financial auditing. |
| **Database** | **Supabase (PostgreSQL)** | Cloud-hosted Postgres with Vector support. Replaces AlloyDB. |
| **Frontend** | **Streamlit** | Python-based UI for dashboards and chat. |
| **Backend** | **Python** | Logic for PDF parsing (`pypdf`) and AI orchestration. |
| **Hosting** | **Google Cloud Run** | Serverless deployment container. |

---

## 🌟 Key Features

### 1. 📂 Intelligent PDF Ingestion
Unlike standard regex parsers, SubZap uses **Gemini 2.5** to read PDF text like a human.
- It identifies **Date**, **Amount**, and **Description** regardless of the bank format.
- It automatically removes "Terms & Conditions" garbage text.
- It detects **Payment Modes** (UPI vs Card vs Cash).

### 2. 🤖 Agentic SQL Generation
Users can ask questions in natural language. The Agent converts English to SQL in real-time.
> *"How much did I spend on Zomato vs Swiggy last month?"*
> `SELECT SUM(amount) FROM transactions WHERE merchant_name ILIKE '%zomato%' ...`

### 3. 🕵️‍♂️ Price Audit Agent
The agent scans recurring payments and compares them against known market rates (e.g., Netflix India Pricing) to detect if you are overpaying due to price hikes.

---

## ⚙️ Local Setup Guide

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/subzap-ai.git
cd subzap-ai
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Set up Environment Variables
Create a `.env` file in the root directory and add your keys:
```ini
# Get this from Google AI Studio (Free)
GEMINI_API_KEY="your_google_gemini_key"

# Get this from Supabase (Connect -> URI)
# IMPORTANT: Select "Session Pooler" (Port 6543) for IPv4 support
DATABASE_URL="postgresql://postgres:[PASSWORD]@aws-0-ap-south-1.pooler.supabase.com:6543/postgres"
```

### 4. Initialize Database
Run the following SQL in your Supabase SQL Editor to create the smart table:
```sql
CREATE TABLE transactions (
    id SERIAL PRIMARY KEY,
    date DATE,
    merchant_name TEXT,       -- Clean name (e.g., "Netflix")
    raw_description TEXT,     -- Original text (e.g., "POS 1234 NETFLIX MUMBAI")
    payment_mode TEXT,        -- e.g., "UPI", "Card", "Cash"
    amount DECIMAL(10, 2),
    category TEXT,
    CONSTRAINT unique_txn UNIQUE (date, raw_description, amount) -- Prevents duplicates
);
```

### 5. Run the App
```bash
streamlit run main.py
```

---

## 📸 Screenshots

### 📊 Analytics Dashboard
![alt text](image.png)

### 🤖 Agentic Audit
![alt text](<Screenshot 2025-12-22 191633.png>)


---

## 🏆 Acknowledgements
Built for the **Google Cloud Build & Blog Marathon**.
Special thanks to the Google Developer Groups for the recognition! 🚀