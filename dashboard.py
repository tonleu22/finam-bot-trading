import json
import os
import requests
import pandas as pd
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify

app = Flask(__name__)

PORTFOLIO_FILE = "portefeuille.json"
INITIAL_CAPITAL = 100_000
BASE_URL = "https://iss.moex.com/iss"


def load_portfolio():
    if not os.path.exists(PORTFOLIO_FILE):
        return {"capital": INITIAL_CAPITAL, "positions": {}, "historique": []}
    with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_history(ticker, days=30):
    """Récupère l'historique des prix sur N jours."""
    end = datetime.now()
    start = end - timedelta(days=days)
    url = (
        f"{BASE_URL}/history/engines/stock/markets/shares/boards/TQBR/"
        f"securities/{ticker}.json"
        f"?from={start.strftime('%Y-%m-%d')}"
        f"&till={end.strftime('%Y-%m-%d')}"
    )
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        columns = data["history"]["columns"]
        rows = data["history"]["data"]
        if not rows:
            return []
        df = pd.DataFrame(rows, columns=columns)
        df = df[["TRADEDATE", "CLOSE"]].dropna()
        df["CLOSE"] = df["CLOSE"].astype(float)
        df = df.sort_values("TRADEDATE").reset_index(drop=True)
        return df.to_dict("records")
    except Exception as e:
        print(f"❌ {ticker} : {e}")
        return []


@app.route("/")
def index():
    p = load_portfolio()

    # Calcul de la valeur totale
    total_valeur = p["capital"]
    positions_detail = []

    for ticker, pos in p["positions"].items():
        valeur = pos["quantite"] * pos["prix_achat"]
        total_valeur += valeur
        positions_detail.append({
            "ticker": ticker,
            "quantite": pos["quantite"],
            "prix_achat": pos["prix_achat"],
            "valeur": valeur,
        })

    pnl = total_valeur - INITIAL_CAPITAL
    pnl_pct = pnl / INITIAL_CAPITAL * 100

    # Tickers pour les graphiques (positions + quelques actions populaires)
    tickers_graphique = list(p["positions"].keys()) if p["positions"] else ["SBER", "GAZP"]

    return render_template(
        "dashboard.html",
        capital=p["capital"],
        positions=positions_detail,
        total_valeur=total_valeur,
        pnl=pnl,
        pnl_pct=pnl_pct,
        historique=list(reversed(p["historique"][-20:])),
        tickers_graphique=tickers_graphique,
        now=datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    )


@app.route("/api/portfolio")
def api_portfolio():
    return jsonify(load_portfolio())


@app.route("/api/historique/<ticker>")
def api_historique(ticker):
    """Renvoie l'historique des prix sur 30 jours pour un ticker."""
    data = get_history(ticker.upper(), days=30)
    return jsonify({"ticker": ticker.upper(), "data": data})


if __name__ == "__main__":
    print("🌐 Dashboard démarré sur http://localhost:5000")
    print("   Appuie sur Ctrl+C pour arrêter")
    app.run(debug=True, host="0.0.0.0", port=5000)