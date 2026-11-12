import pandas as pd
import altair as alt
import streamlit as st

from ask import question_to_sql, is_safe, run_sql

st.set_page_config(page_title="Supply Chain Analytics Assistant", layout="wide")

ACCENT = "#0F5C55"
INK = "#1F1B16"
MUTED = "#6B6459"

# ---------- Styling: quiet panels, one accent, no clutter ----------
st.markdown("""
<style>
.block-container { padding-top: 2.4rem; max-width: 1150px; }
h1 { font-weight: 650; letter-spacing: -0.02em; margin-bottom: 0.2rem; }
[data-testid="stMetric"] {
    background: #FFFFFF; border: 1px solid #E7E1D8;
    border-radius: 10px; padding: 14px 18px;
}
[data-testid="stMetricLabel"] { color: #6B6459; }
#MainMenu, footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ---------- Helpers ----------
@st.cache_data
def query(sql):
    return run_sql(sql)


def bar(df, cat, val, height=None, domain=None, title=None):
    x_scale = alt.Scale(domain=domain) if domain else alt.Undefined
    base = alt.Chart(df).encode(
        y=alt.Y(f"{cat}:N", sort="-x", title=None, axis=alt.Axis(labelLimit=220)),
        x=alt.X(f"{val}:Q", title=title or val, scale=x_scale),
    )
    bars = base.mark_bar(color=ACCENT, cornerRadiusEnd=3)
    labels = base.mark_text(align="left", dx=4, color=INK).encode(
        text=alt.Text(f"{val}:Q", format=",.1f")
    )
    layered = bars + labels
    if height:
        layered = layered.properties(height=height)
    return (layered.configure_view(strokeWidth=0)
            .configure_axis(grid=False, labelColor=MUTED, titleColor=MUTED))


# ---------- Header ----------
st.title("Supply Chain Analytics Assistant")
st.caption("Ask questions about ~180K supply chain orders in plain English. "
           "An LLM writes the SQL, and the database gives the numbers.")

# ---------- KPI row ----------
k = query("""
    SELECT COUNT(*) AS orders,
           ROUND(100.0 * SUM(late_delivery_risk) / COUNT(*), 1) AS late_pct,
           ROUND(AVG(days_for_shipment_scheduled), 1) AS promised_days,
           ROUND(AVG(days_for_shipping_real), 1) AS actual_days
    FROM orders
""").iloc[0]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Orders", f"{int(k['orders']):,}")
c2.metric("Late deliveries", f"{k['late_pct']}%")
c3.metric("Avg promised days", f"{k['promised_days']}")
c4.metric("Avg actual days", f"{k['actual_days']}")

st.write("")

# ---------- Charts ----------
left, right = st.columns(2)

with left:
    st.subheader("Late deliveries by shipping mode")
    by_mode = query("""
        SELECT shipping_mode,
               ROUND(100.0 * SUM(late_delivery_risk) / COUNT(*), 1) AS late_pct
        FROM orders GROUP BY shipping_mode ORDER BY late_pct DESC
    """)
    st.altair_chart(bar(by_mode, "shipping_mode", "late_pct", height=200,
                        domain=[0, 110], title="Late (%)"))
  

with right:
    st.subheader("Late deliveries by region")
    by_region = query("""
        SELECT order_region,
               ROUND(100.0 * SUM(late_delivery_risk) / COUNT(*), 1) AS late_pct
        FROM orders GROUP BY order_region ORDER BY late_pct DESC
    """)
    st.altair_chart(bar(by_region, "order_region", "late_pct", height=520,
                        domain=[0, 70], title="Late (%)"))

st.divider()

# ---------- The assistant ----------
st.subheader("Ask the data")

examples = [
    "Which region has the most late orders?",
    "Late percentage by shipping mode",
    "Top 5 product categories by sales",
]
cols = st.columns(len(examples))
for i, ex in enumerate(examples):
    if cols[i].button(ex):
        st.session_state["q"] = ex

q = st.text_input("Your question", key="q",
                  placeholder="e.g. Which customer segment has the highest late percentage?")

if q.strip():
    with st.spinner("Writing SQL..."):
        try:
            sql = question_to_sql(q.strip())
        except RuntimeError as e:
            st.error(str(e))
            st.stop()

    if sql.strip().upper().startswith("CANNOT_ANSWER"):
        st.info("I can't answer that from this data. Try asking about orders, "
                "regions, shipping or delivery.")
        st.stop()

    st.markdown("**Generated SQL**")
    st.code(sql, language="sql")

    if not is_safe(sql):
        st.error("Blocked: only a single read-only SELECT is allowed.")
        st.stop()

    try:
        df = run_sql(sql)
    except Exception as e:
        st.error(f"SQL error: {e}")
        st.stop()

    st.dataframe(df, hide_index=True)

    # Auto-chart simple "category + number" results
    if (len(df.columns) == 2 and 1 < len(df) <= 30
            and pd.api.types.is_numeric_dtype(df.iloc[:, 1])):
        try:
            st.altair_chart(bar(df, df.columns[0], df.columns[1]))
        except Exception:
            pass