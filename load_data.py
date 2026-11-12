import re
import pandas as pd
import sqlite3

# 1. EXTRACT: read the CSV into a DataFrame
df = pd.read_csv("DataCoSupplyChainDataset.csv", encoding="latin-1")

# 2. TRANSFORM (a): tidy column names
df.columns = (df.columns.str.strip().str.lower()
              .str.replace(r"[^a-z0-9]+", "_", regex=True).str.strip("_"))

# 2. TRANSFORM (b): drop columns we don't need (errors="ignore" = skip any that don't exist)
drop_cols = ["customer_email", "customer_password", "product_description", "product_image"]
df = df.drop(columns=drop_cols, errors="ignore")

# 2. TRANSFORM (c): clean extra spaces in every text column
def clean_text(value):
    if isinstance(value, str):
        return re.sub(r"\s+", " ", value).strip()
    return value

for col in df.select_dtypes(include="object").columns:
    df[col] = df[col].map(clean_text)

# 3. LOAD: write into the SQLite database
conn = sqlite3.connect("supply_chain.db")
df.to_sql("orders", conn, if_exists="replace", index=False)
conn.close()

print("Loaded", len(df), "rows,", len(df.columns), "columns")