import requests
import pandas as pd
import time
import json
import os
from datetime import datetime, timedelta

BASE_URL = "https://iss.moex.com/iss"

# Paramètres de la stratégie
FAST = 5
SLOW = 20
INITIAL_CAPITAL = 100_000
COMMISSION = 0.0005
STOP_LOSS = 0.05

TICKERS = ["SBER", "GAZP", "LKOH", "ROSN", "GMKN", "NVTK", "TATN"]

# Fichier de sauvegarde du portefeuille
PORTFOLIO_FILE = "portefeuille.json"


def load_portfolio():
    """Charge le portefeuille depuis le fichier, ou le crée."""
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "capital": INITIAL_CAPITAL,
        "positions": {},   # ticker -> {"quantite": x, "prix_achat": y}
        "historique": [],  # liste des trades
    }


def save_portfolio(p):
    """Sauvegarde le portefeuille dans le fichier."""
    with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
        json.dump(p, f, ensure_ascii=False, indent=2)


def get_history(ticker, days=60):
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
            return None
        df = pd.DataFrame(rows, columns=columns)
        df = df[["TRADEDATE", "CLOSE"]].dropna()
        df["CLOSE"] = df["CLOSE"].astype(float)
        df = df.sort_values("TRADEDATE").reset_index(drop=True)
        return df
    except Exception as e:
        return None


def afficher_portefeuille(p, prix_actuels=None):
    """Affiche l'état du portefeuille."""
    print(f"\n💰 Portefeuille")
    print(f"   Capital liquide : {p['capital']:,.2f} RUB")

    total_valeur = p["capital"]
    for ticker, pos in p["positions"].items():
        prix = prix_actuels.get(ticker) if prix_actuels else pos["prix_achat"]
        if prix is None:
            prix = pos["prix_achat"]
        valeur = pos["quantite"] * prix
        pnl = (prix - pos["prix_achat"]) / pos["prix_achat"] * 100
        emoji = "🟢" if pnl >= 0 else "🔴"
        print(f"   {emoji} {ticker:5} : {pos['quantite']:.2f} actions "
              f"@ {pos['prix_achat']:.2f} → {prix:.2f} ({pnl:+.2f}%)")
        total_valeur += valeur

    print(f"   ────────────────────────────")
    total_pnl = (total_valeur - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100
    emoji = "🟢" if total_pnl >= 0 else "🔴"
    print(f"   {emoji} Valeur totale : {total_valeur:,.2f} RUB ({total_pnl:+.2f}%)")


def check_signals(p):
    """Vérifie les signaux et met à jour le portefeuille."""
    prix_actuels = {}
    signaux = []

    for ticker in TICKERS:
        df = get_history(ticker, days=60)
        if df is None or len(df) < SLOW + 2:
            continue

        df["SMA_FAST"] = df["CLOSE"].rolling(FAST).mean()
        df["SMA_SLOW"] = df["CLOSE"].rolling(SLOW).mean()

        last = df.iloc[-1]
        prev = df.iloc[-2]

        if pd.isna(last["SMA_FAST"]) or pd.isna(last["SMA_SLOW"]):
            continue

        prix = last["CLOSE"]
        prix_actuels[ticker] = prix

        fast = last["SMA_FAST"]
        slow = last["SMA_SLOW"]
        prev_fast = prev["SMA_FAST"]
        prev_slow = prev["SMA_SLOW"]

        # Détection des croisements
        achat = prev_fast <= prev_slow and fast > slow
        vente = prev_fast >= prev_slow and fast < slow

        # --- GESTION DES POSITIONS ---
        if ticker in p["positions"]:
            pos = p["positions"][ticker]

            # Stop-loss
            if prix < pos["prix_achat"] * (1 - STOP_LOSS):
                # Vente forcée
                montant = pos["quantite"] * prix * (1 - COMMISSION)
                p["capital"] += montant
                pnl = (prix - pos["prix_achat"]) / pos["prix_achat"] * 100
                p["historique"].append({
                    "date": datetime.now().isoformat(),
                    "ticker": ticker,
                    "action": "STOP-LOSS",
                    "prix": prix,
                    "pnl_pct": pnl,
                })
                print(f"\n   🛑 STOP-LOSS sur {ticker} à {prix:.2f} ({pnl:+.2f}%)")
                del p["positions"][ticker]

            # Signal de vente
            elif vente:
                montant = pos["quantite"] * prix * (1 - COMMISSION)
                p["capital"] += montant
                pnl = (prix - pos["prix_achat"]) / pos["prix_achat"] * 100
                p["historique"].append({
                    "date": datetime.now().isoformat(),
                    "ticker": ticker,
                    "action": "VENTE",
                    "prix": prix,
                    "pnl_pct": pnl,
                })
                print(f"\n   🔴 VENTE de {ticker} à {prix:.2f} ({pnl:+.2f}%)")
                del p["positions"][ticker]

        # --- OUVERTURE DE POSITION ---
        elif achat and p["capital"] > 1000:
            # On investit 20% du capital par position (max 5 positions)
            montant = p["capital"] * 0.2
            quantite = (montant * (1 - COMMISSION)) / prix
            p["capital"] -= montant
            p["positions"][ticker] = {
                "quantite": quantite,
                "prix_achat": prix,
            }
            p["historique"].append({
                "date": datetime.now().isoformat(),
                "ticker": ticker,
                "action": "ACHAT",
                "prix": prix,
                "pnl_pct": None,
            })
            print(f"\n   🟢 ACHAT de {ticker} à {prix:.2f} "
                  f"({quantite:.2f} actions)")

    return prix_actuels, signaux


def main():
    p = load_portfolio()

    print("🤖 Bot de trading — Actions russes")
    print(f"   Stratégie : SMA {FAST}/{SLOW}")
    print(f"   Capital initial : {INITIAL_CAPITAL:,} RUB")
    print(f"   Actions   : {', '.join(TICKERS)}")
    print("=" * 55)
    print("Appuie sur Ctrl+C pour arrêter.\n")

    cycle = 0
    while True:
        cycle += 1
        print(f"\n🔄 Cycle #{cycle} — {datetime.now().strftime('%H:%M:%S')}")

        prix_actuels, _ = check_signals(p)
        afficher_portefeuille(p, prix_actuels)
        save_portfolio(p)

        print(f"   Prochain cycle dans 30s...")
        time.sleep(30)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Bot arrêté. Portefeuille sauvegardé.")