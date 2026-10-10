import json
import os
from datetime import datetime
from flask import Flask, render_template, jsonify

app = Flask(__name__)

PORTFOLIO_FILE = "portefeuille.json"
INITIAL_CAPITAL = 100_000


def load_portfolio():
    if not os.path.exists(PORTFOLIO_FILE):
        return {"capital": INITIAL_CAPITAL, "positions": {}, "historique": []}
    with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


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

    return render_template(
        "dashboard.html",
        capital=p["capital"],
        positions=positions_detail,
        total_valeur=total_valeur,
        pnl=pnl,
        pnl_pct=pnl_pct,
        historique=list(reversed(p["historique"][-20:])),  # 20 derniers trades
        now=datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    )


@app.route("/api/portfolio")
def api_portfolio():
    return jsonify(load_portfolio())


if __name__ == "__main__":
    print("🌐 Dashboard démarré sur http://localhost:5000")
    print("   Appuie sur Ctrl+C pour arrêter")
    app.run(debug=True, host="0.0.0.0", port=5000)