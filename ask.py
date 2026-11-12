import os, re, sqlite3, time
import pandas as pd
from google import genai
from google.genai import errors, types

MODELS = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]
DB = "supply_chain.db"
client = genai.Client(
    api_key=os.environ["GEMINI_API_KEY"],
    http_options=types.HttpOptions(
        timeout=20000,  # give up after 20 seconds
        retry_options=types.HttpRetryOptions(attempts=1),  # our own retry code handles retries
    ),
)

def get_schema():
    conn = sqlite3.connect(DB)
    cols = conn.execute("PRAGMA table_info(orders)").fetchall()
    conn.close()
    return ", ".join(f"{c[1]} ({c[2]})" for c in cols)

SCHEMA = get_schema()

PROMPT = """You are a SQL expert for a SQLite database.
Table: orders
Columns: {schema}

Notes:
- late_delivery_risk is 1 if the order was late versus its promised shipping time, else 0.
- For a late percentage use: 100.0 * SUM(late_delivery_risk) / COUNT(*).
Write ONE SQLite SELECT query that answers the question.
Return ONLY the SQL. No explanation, no markdown.- If the question cannot be answered using this table, return exactly: CANNOT_ANSWER

Question: {question}"""

def call_llm(prompt):
    for model in MODELS:
        for attempt in range(3):
            try:
                resp = client.models.generate_content(model=model, contents=prompt)
                return resp.text.strip()
            except errors.APIError as e:
                if e.code in (429, 500, 503, 504):
                    wait = 2 ** attempt
                    print(f"[{model}] busy ({e.code}), retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    print(f"[{model}] error {e.code}, trying next model")
                    break
    raise RuntimeError("Gemini is unavailable right now. Please try again in a minute.")

def question_to_sql(question):
    sql = call_llm(PROMPT.format(schema=SCHEMA, question=question))
    sql = re.sub(r"^\x60{3}(?:sql)?|\x60{3}$", "", sql, flags=re.MULTILINE).strip()
    return sql

def is_safe(sql):
    s = sql.strip().rstrip(";").lower()
    banned = ["insert", "update", "delete", "drop", "alter", "create", "attach", "pragma"]
    return (s.startswith("select") and ";" not in s
            and not any(re.search(rf"\b{w}\b", s) for w in banned))

def run_sql(sql):
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        return pd.read_sql_query(sql, conn)
    finally:
        conn.close()

def ask(question):
    try:
        sql = question_to_sql(question)
    except RuntimeError as e:
        print(e)
        return None
    print("\nSQL:", sql)
    if sql.strip().upper().startswith("CANNOT_ANSWER"):
        print("I can't answer that from this data. Try asking about orders, regions, shipping or delivery.")
        return None
    if not is_safe(sql):
        print("Blocked: only a single read-only SELECT is allowed.")
        return None
    try:
        df = run_sql(sql)
    except Exception as e:
        print("SQL error:", e)
        return None
    print(df.to_string(index=False))
    return df

if __name__ == "__main__":
    while True:
        q = input("\nAsk a question (or 'quit'): ").strip()
        if not q:
            continue  # ignore blank lines
        if q.lower() == "quit":
            break
        ask(q)
