import requests
import pandas as pd
import time
import json
import os
import csv
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# === CONFIGURATION ===
BASE_URL = "https://iss.moex.com/iss"
FAST = 5
SLOW = 20
INITIAL_CAPITAL = 100_000
COMMISSION = 0.0005
STOP_LOSS = 0.05
CYCLE_SECONDS = 300

TICKERS = ["SBER", "GAZP", "LKOH", "ROSN", "GMKN", "NVTK", "TATN"]

TG_TOKEN = os.getenv("TELEGRAM_TOKEN")
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

PORTFOLIO_FILE = "portefeuille.json"
TRADES_FILE = "trades.csv"


def send_telegram(message):
    """Envoie un message sur Telegram."""
    if not TG_TOKEN or not TG_CHAT_ID:
        print("⚠️  Telegram non configuré")
        return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    try:
        r = requests.post(
            url,
            data={"chat_id": TG_CHAT_ID, "text": message},
            timeout=10,
        )
        if r.status_code != 200:
            print(f"⚠️  Erreur Telegram : {r.status_code}")
    except Exception as e:
        print(f"⚠️  Telegram erreur : {e}")


def log_trade(ticker, action, prix, quantite, pnl_pct=None):
    """Enregistre un trade dans le fichier CSV."""
    fichier_existe = os.path.exists(TRADES_FILE)
    with open(TRADES_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not fichier_existe:
            writer.writerow(["Date", "Ticker", "Action", "Prix", "Quantite", "PnL_%"])
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ticker,
            action,
            f"{prix:.2f}",
            f"{quantite:.2f}" if quantite else "",
            f"{pnl_pct:.2f}" if pnl_pct is not None else "",
        ])


def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "capital": INITIAL_CAPITAL,
        "positions": {},
        "historique": [],
    }


def save_portfolio(p):
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
        print(f"❌ {ticker} : {e}")
        return None


def afficher_portefeuille(p, prix_actuels=None):
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
    return total_valeur, total_pnl


def check_signals(p):
    """Vérifie les signaux et envoie les alertes Telegram."""
    prix_actuels = {}

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

        achat = prev_fast <= prev_slow and fast > slow
        vente = prev_fast >= prev_slow and fast < slow

        # --- POSITION EXISTANTE ---
        if ticker in p["positions"]:
            pos = p["positions"][ticker]

            # Stop-loss
            if prix < pos["prix_achat"] * (1 - STOP_LOSS):
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
                msg = (
                    f"🛑 STOP-LOSS sur {ticker}\n"
                    f"Prix : {prix:.2f} RUB\n"
                    f"PnL : {pnl:+.2f}%"
                )
                print(f"\n   🛑 STOP-LOSS sur {ticker} à {prix:.2f} ({pnl:+.2f}%)")
                send_telegram(msg)
                log_trade(ticker, "STOP-LOSS", prix, pos["quantite"], pnl)
                del p["positions"][ticker]

            # Vente
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
                msg = (
                    f"🔴 VENTE de {ticker}\n"
                    f"Prix : {prix:.2f} RUB\n"
                    f"PnL : {pnl:+.2f}%"
                )
                print(f"\n   🔴 VENTE de {ticker} à {prix:.2f} ({pnl:+.2f}%)")
                send_telegram(msg)
                log_trade(ticker, "VENTE", prix, pos["quantite"], pnl)
                del p["positions"][ticker]

        # --- NOUVELLE POSITION ---
        elif achat and p["capital"] > 1000:
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
            msg = (
                f"🟢 ACHAT de {ticker}\n"
                f"Prix : {prix:.2f} RUB\n"
                f"Quantité : {quantite:.2f} actions\n"
                f"Montant : {montant:,.0f} RUB"
            )
            print(f"\n   🟢 ACHAT de {ticker} à {prix:.2f} ({quantite:.2f} actions)")
            send_telegram(msg)
            log_trade(ticker, "ACHAT", prix, quantite)

    return prix_actuels


def main():
    p = load_portfolio()

    print("🤖 Bot de trading — Actions russes")
    print(f"   Stratégie : SMA {FAST}/{SLOW}")
    print(f"   Capital initial : {INITIAL_CAPITAL:,} RUB")
    print(f"   Cycle : toutes les {CYCLE_SECONDS} secondes")
    print("=" * 55)

    send_telegram(
        "🤖 Bot de trading démarré\n"
        f"Stratégie : SMA {FAST}/{SLOW}\n"
        f"Capital : {INITIAL_CAPITAL:,} RUB"
    )

    print("Appuie sur Ctrl+C pour arrêter.\n")

    cycle = 0
    while True:
        cycle += 1
        print(f"\n🔄 Cycle #{cycle} — {datetime.now().strftime('%H:%M:%S')}")

        try:
            prix_actuels = check_signals(p)
            afficher_portefeuille(p, prix_actuels)
            save_portfolio(p)
        except Exception as e:
            print(f"❌ Erreur dans le cycle : {e}")

        print(f"   Prochain cycle dans {CYCLE_SECONDS}s...")
        time.sleep(CYCLE_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Bot arrêté.")
        send_telegram("👋 Bot de trading arrêté.")