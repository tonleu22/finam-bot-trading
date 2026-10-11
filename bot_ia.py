import os
import json
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
from gigachat import GigaChat

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
GIGA_KEY = os.getenv("GIGACHAT_KEY")

PORTFOLIO_FILE = "portefeuille_ia.json"
DISCUSSIONS_FILE = "discussions.log"


def send_telegram(message):
    if not TG_TOKEN or not TG_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": TG_CHAT_ID, "text": message}, timeout=10)
    except Exception as e:
        print(f"⚠️ Telegram : {e}")


def log_discussion(texte):
    """Enregistre une discussion dans le fichier log."""
    with open(DISCUSSIONS_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*60}\n")
        f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"{'='*60}\n")
        f.write(texte + "\n")


def ask_gigachat(prompt):
    """Demande l'avis de GigaChat sur une situation de trading."""
    try:
        with GigaChat(
            credentials=GIGA_KEY,
            model="GigaChat-2",
            verify_ssl_certs=False,
        ) as giga:
            response = giga.chat(prompt)
            return response.choices[0].message.content
    except Exception as e:
        return f"❌ Erreur GigaChat : {e}"


def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"capital": INITIAL_CAPITAL, "positions": {}, "historique": []}


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


def construire_prompt(ticker, prix, fast, slow, signal, historique_prix):
    """Construit le prompt pour GigaChat."""
    dernieres_prix = ", ".join([f"{p:.2f}" for p in historique_prix[-10:]])
    return f"""Tu es un analyste de trading. Voici les données d'une action russe :

Action : {ticker}
Prix actuel : {prix:.2f} RUB
Moyenne mobile rapide (SMA {FAST}) : {fast:.2f}
Moyenne mobile lente (SMA {SLOW}) : {slow:.2f}
Signal technique : {signal}
10 derniers prix : {dernieres_prix}

Réponds en 2 phrases maximum, en français :
1. Ton avis sur ce signal (ACHETER, VENDRE, ou ATTENDRE)
2. Une justification courte
"""


def check_signals_ia(p):
    """Vérifie les signaux et consulte GigaChat."""
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

        # Si pas de signal, on continue
        if not achat and not vente:
            continue

        signal_str = "ACHAT" if achat else "VENTE"

        # --- CONSULTATION DE L'IA ---
        print(f"\n🧠 Consultation de GigaChat pour {ticker} ({signal_str})...")
        prompt = construire_prompt(
            ticker, prix, fast, slow, signal_str,
            list(df["CLOSE"].values)
        )
        avis_ia = ask_gigachat(prompt)
        print(f"🤖 GigaChat : {avis_ia}")

        # Enregistrer la discussion
        log_discussion(
            f"📊 SIGNAL : {signal_str} sur {ticker}\n"
            f"   Prix : {prix:.2f} RUB\n"
            f"   SMA {FAST} : {fast:.2f} | SMA {SLOW} : {slow:.2f}\n\n"
            f"🧠 PROMPT envoyé à GigaChat :\n{prompt}\n\n"
            f"🤖 RÉPONSE de GigaChat :\n{avis_ia}"
        )

        # Message Telegram
        msg = (
            f"🧠 Signal {signal_str} sur {ticker}\n"
            f"Prix : {prix:.2f} RUB\n\n"
            f"🤖 GigaChat dit :\n{avis_ia}"
        )
        send_telegram(msg)

        # --- DÉCISION ---
        # Le bot suit le signal technique (SMA) pour l'instant,
        # mais on enregistre l'avis de l'IA pour analyse

        # --- POSITION EXISTANTE ---
        if ticker in p["positions"]:
            pos = p["positions"][ticker]

            if prix < pos["prix_achat"] * (1 - STOP_LOSS):
                montant = pos["quantite"] * prix * (1 - COMMISSION)
                p["capital"] += montant
                pnl = (prix - pos["prix_achat"]) / pos["prix_achat"] * 100
                p["historique"].append({
                    "date": datetime.now().isoformat(),
                    "ticker": ticker, "action": "STOP-LOSS",
                    "prix": prix, "pnl_pct": pnl, "avis_ia": avis_ia[:100],
                })
                print(f"   🛑 STOP-LOSS {ticker} ({pnl:+.2f}%)")
                send_telegram(f"🛑 STOP-LOSS {ticker} : {pnl:+.2f}%")
                del p["positions"][ticker]

            elif vente:
                montant = pos["quantite"] * prix * (1 - COMMISSION)
                p["capital"] += montant
                pnl = (prix - pos["prix_achat"]) / pos["prix_achat"] * 100
                p["historique"].append({
                    "date": datetime.now().isoformat(),
                    "ticker": ticker, "action": "VENTE",
                    "prix": prix, "pnl_pct": pnl, "avis_ia": avis_ia[:100],
                })
                print(f"   🔴 VENTE {ticker} ({pnl:+.2f}%)")
                del p["positions"][ticker]

        # --- NOUVELLE POSITION ---
        elif achat and p["capital"] > 1000:
            montant = p["capital"] * 0.2
            quantite = (montant * (1 - COMMISSION)) / prix
            p["capital"] -= montant
            p["positions"][ticker] = {
                "quantite": quantite, "prix_achat": prix,
            }
            p["historique"].append({
                "date": datetime.now().isoformat(),
                "ticker": ticker, "action": "ACHAT",
                "prix": prix, "pnl_pct": None, "avis_ia": avis_ia[:100],
            })
            print(f"   🟢 ACHAT {ticker} ({quantite:.2f} actions)")
            send_telegram(f"🟢 ACHAT {ticker} à {prix:.2f}")

    return prix_actuels


def afficher_portefeuille(p):
    print(f"\n💰 Portefeuille")
    print(f"   Capital liquide : {p['capital']:,.2f} RUB")
    total = p["capital"]
    for ticker, pos in p["positions"].items():
        valeur = pos["quantite"] * pos["prix_achat"]
        total += valeur
        print(f"   🟢 {ticker} : {pos['quantite']:.2f} actions @ {pos['prix_achat']:.2f}")
    pnl = (total - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100
    emoji = "🟢" if pnl >= 0 else "🔴"
    print(f"   {emoji} Total : {total:,.2f} RUB ({pnl:+.2f}%)")


def main():
    p = load_portfolio()

    print("🧠 Bot IA — SMA 5/20 + GigaChat")
    print(f"   Capital : {INITIAL_CAPITAL:,} RUB")
    print(f"   Cycle : {CYCLE_SECONDS}s")
    print("=" * 55)

    send_telegram("🧠 Bot IA démarré (SMA + GigaChat)")

    cycle = 0
    while True:
        cycle += 1
        print(f"\n🔄 Cycle #{cycle} — {datetime.now().strftime('%H:%M:%S')}")

        try:
            check_signals_ia(p)
            afficher_portefeuille(p)
            save_portfolio(p)
        except Exception as e:
            print(f"❌ Erreur : {e}")

        print(f"   Prochain cycle dans {CYCLE_SECONDS}s...")
        time.sleep(CYCLE_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Bot IA arrêté.")
        send_telegram("👋 Bot IA arrêté.")