from flask import Flask, request, jsonify, send_file
import pandas as pd, os, json, datetime
BASE_DIR = os.path.dirname(__file__)
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
CONFIG_PATH = os.path.join(BASE_DIR, "config_weights.json")
DEFAULT_CONFIG = {
  "weights": {"liquidez_corrente":30,"endividamento_total":25,"margem_ebitda":25,"roa_approx":20},
  "thresholds": {"liquidez_corrente":[1.0,1.5],"endividamento_total":[0.5,0.7],"margem_ebitda":[0.08,0.15],"roa_approx":[0.02,0.06]}
}
if not os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH,"w",encoding="utf-8") as f: json.dump(DEFAULT_CONFIG,f,ensure_ascii=False,indent=2)
def load_config():
    with open(CONFIG_PATH,"r",encoding="utf-8") as f: return json.load(f)
def intelligent_map_columns(df):
    mapping_variants = {
        "ano": ["ano","exercicio","year","periodo"],
        "ativo_circulante": ["ativo_circulante","ativo circulante","ac","current_assets","atc"],
        "ativo_nc": ["ativo_nc","ativo_nao_circulante","ativo nao circulante","non_current_assets","anc"],
        "passivo_circulante": ["passivo_circulante","passivo circulante","pc","current_liabilities","plc"],
        "passivo_nc": ["passivo_nc","passivo_nao_circulante","passivo nao circulante","non_current_liabilities","pnc"],
        "patrimonio_liquido": ["patrimonio_liquido","patrimonio liquido","pl","equity","patrimonio"],
        "receita_liquida": ["receita_liquida","receita liquida","receita","net_revenue","revenue","venda"],
        "custo_vendas": ["custo_vendas","custo vendas","cogs","cost_of_goods_sold","custo"],
        "despesas_operacionais": ["despesas_operacionais","despesas operacionais","operating_expenses","despesa"],
        "depreciacao": ["depreciacao","depreciação","depreciation","amortizacao","amortizacao"],
        "lucro_liquido": ["lucro_liquido","lucro liquido","net_income","resultado"]
    }
    df2 = df.copy()
    cols_lower = {c: c.lower().strip() for c in df2.columns}
    newcols = {}
    for canon, variants in mapping_variants.items():
        for v in variants:
            for c, cl in cols_lower.items():
                if v == cl or v in cl or cl in v:
                    newcols[c] = canon
    return df2.rename(columns=newcols)
def compute_indicators(df, config):
    df = intelligent_map_columns(df.copy())
    cols = ["ativo_circulante","ativo_nc","passivo_circulante","passivo_nc","patrimonio_liquido",
            "receita_liquida","custo_vendas","despesas_operacionais","depreciacao","lucro_liquido"]
    for c in cols:
        df[c] = pd.to_numeric(df.get(c, 0), errors="coerce").fillna(0)
    df["liquidez_corrente"] = (df["ativo_circulante"] / df["passivo_circulante"]).replace([float("inf")], 0).round(2)
    df["endividamento_total"] = ((df["passivo_circulante"] + df["passivo_nc"]) / (df["ativo_circulante"] + df["ativo_nc"])).replace([float("inf")], 0).round(2)
    df["ebitda"] = (df["receita_liquida"] - df["custo_vendas"] - df["despesas_operacionais"] + df["depreciacao"])
    df["margem_ebitda"] = (df["ebitda"] / df["receita_liquida"]).replace([float("inf")], 0).round(3)
    df["roa_approx"] = (df["lucro_liquido"] / (df["ativo_circulante"] + df["ativo_nc"])).replace([float("inf")], 0).round(3)
    weights = config.get("weights", DEFAULT_CONFIG["weights"]); thresholds = config.get("thresholds", DEFAULT_CONFIG["thresholds"])
    def score_row(row):
        score=0.0
        lc=row["liquidez_corrente"]; th_lc=thresholds["liquidez_corrente"]
        if lc>=th_lc[1]: score+=weights["liquidez_corrente"]
        elif lc>=th_lc[0]: score+=weights["liquidez_corrente"]*0.6
        else: score+=weights["liquidez_corrente"]*0.2
        et=row["endividamento_total"]; th_et=thresholds["endividamento_total"]
        if et<th_et[0]: score+=weights["endividamento_total"]
        elif et<=th_et[1]: score+=weights["endividamento_total"]*0.6
        else: score+=weights["endividamento_total"]*0.15
        me=row["margem_ebitda"]; th_me=thresholds["margem_ebitda"]
        if me>=th_me[1]: score+=weights["margem_ebitda"]
        elif me>=th_me[0]: score+=weights["margem_ebitda"]*0.6
        else: score+=weights["margem_ebitda"]*0.15
        roa=row["roa_approx"]; th_roa=thresholds["roa_approx"]
        if roa>=th_roa[1]: score+=weights["roa_approx"]
        elif roa>=th_roa[0]: score+=weights["roa_approx"]*0.6
        else: score+=weights["roa_approx"]*0.1
        return float(round(score,2))
    df["raw_score"] = df.apply(score_row, axis=1)
    max_possible = sum(weights.values())
    df["score_pct"] = (df["raw_score"] / max_possible * 100).round(1)
    def rating_from_pct(pct):
        if pct>=85: return "AA (Muito Baixo Risco)"
        if pct>=70: return "A (Baixo Risco)"
        if pct>=55: return "BBB (Moderado)"
        if pct>=40: return "BB (Atenção)"
        return "B ou inferior (Alto Risco)"
    df["rating_tecnico"] = df["score_pct"].apply(rating_from_pct)
    return df
app = Flask(__name__)
@app.route("/analyze_manual", methods=["POST"])
def analyze_manual():
    payload = request.get_json() or request.form.to_dict()
    df = pd.DataFrame([payload])
    cfg = load_config()
    df_res = compute_indicators(df, cfg)
    timestamp = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
    filename = os.path.join(UPLOAD_FOLDER, f"report_manual_{timestamp}.json")
    with open(filename,"w",encoding="utf-8") as f: json.dump({"generated_at":timestamp,"result":df_res.to_dict(orient='records')}, f, ensure_ascii=False, indent=2)
    return jsonify({"status":"ok","report": df_res.to_dict(orient="records")})
@app.route("/upload_financials", methods=["POST"])
def upload_financials():
    if "file" not in request.files: return jsonify({"status":"error","message":"Nenhum arquivo enviado"}),400
    f = request.files["file"]; fname = f.filename; save_path = os.path.join(UPLOAD_FOLDER, fname); f.save(save_path)
    try:
        if fname.lower().endswith(".csv"): df = pd.read_csv(save_path)
        else: df = pd.read_excel(save_path)
    except Exception as e:
        return jsonify({"status":"error","message":"Erro ao ler o arquivo: "+str(e)}),400
    cfg = load_config(); df_ind = compute_indicators(df, cfg)
    timestamp = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S"); filename = os.path.join(UPLOAD_FOLDER, f"report_upload_{timestamp}.json")
    with open(filename,"w",encoding="utf-8") as f: json.dump({"generated_at":timestamp,"source_file":fname,"result":df_ind.to_dict(orient='records')}, f, ensure_ascii=False, indent=2)
    return jsonify({"status":"ok","report": df_ind.to_dict(orient="records")})
@app.route("/download_report/<path:name>")
def download_report(name):
    path = os.path.join(UPLOAD_FOLDER, name); 
    if not os.path.exists(path): return "Arquivo não encontrado",404
    return send_file(path, as_attachment=True)
if __name__ == "__main__": app.run(host="0.0.0.0", port=5001, debug=True)
