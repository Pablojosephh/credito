import streamlit as st
import pandas as pd, requests, json, io
st.title("Streamlit - Análise Financeira (Seguro Garantia)")
st.write("Envie um arquivo CSV/XLSX ou preencha manualmente.")
uploaded = st.file_uploader("Arquivo CSV/XLSX", type=["csv","xlsx"])
if uploaded:
    try:
        if uploaded.name.lower().endswith(".csv"): df = pd.read_csv(uploaded)
        else: df = pd.read_excel(uploaded)
        st.dataframe(df.head())
        if st.button("Enviar para API (backend)"):
            files = {"file": (uploaded.name, uploaded.getvalue())}
            resp = requests.post("http://backend:5001/upload_financials", files=files, timeout=30)
            st.json(resp.json())
    except Exception as e:
        st.error(str(e))
st.subheader("Entrada manual")
with st.form("manual"):
    receita = st.number_input("receita_liquida", value=15000)
    custo = st.number_input("custo_vendas", value=9000)
    despesas = st.number_input("despesas_operacionais", value=2500)
    ativo_c = st.number_input("ativo_circulante", value=5000)
    ativo_nc = st.number_input("ativo_nc", value=7000)
    passivo_c = st.number_input("passivo_circulante", value=3000)
    passivo_nc = st.number_input("passivo_nc", value=4000)
    lucro = st.number_input("lucro_liquido", value=1200)
    submitted = st.form_submit_button("Analisar manual via API")
    if submitted:
        payload = {"receita_liquida": receita, "custo_vendas": custo, "despesas_operacionais": despesas,
                   "ativo_circulante": ativo_c, "ativo_nc": ativo_nc, "passivo_circulante": passivo_c,
                   "passivo_nc": passivo_nc, "lucro_liquido": lucro}
        resp = requests.post("http://backend:5001/analyze_manual", json=payload, timeout=30)
        st.json(resp.json())