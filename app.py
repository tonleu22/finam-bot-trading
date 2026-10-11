import os
import json
import time
import csv
import requests
import pandas as pd
import xml.etree.ElementTree as ET
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

CONSENSUS_MODE = True
RESUME_HEURE = 20
BRIEFING_HEURE = 9

# News RSS Finam
NEWS_URL = "https://www.finam.ru/analysis/conews/rsspoint/"
NEWS_CACHE_SECONDS = 1800
_news_cache = {"sentiment": None, "timestamp": 0}

TICKERS = ["SBER", "GAZP", "LKOH", "ROSN", "GMKN", "NVTK", "TATN"]

TG_TOKEN = os.getenv("TELEGRAM_TOKEN")
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GIGA_KEY = os.getenv("GIGACHAT_KEY")

PORTFOLIO_FILE = "portefeuille_ia.json"
DISCUSSIONS_FILE = "discussions.log"
TRADES_FILE = "trades.csv"
RESUME_FILE = "dernier_resume.txt"
BRIEFING_FILE = "dernier_briefing.txt"


# === TELEGRAM ===
def send_telegram(message):
    if not TG_TOKEN or not TG_CHAT_ID:
        print("⚠️ Telegram non configuré")
        return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    try:
        r = requests.post(
            url,
            data={"chat_id": TG_CHAT_ID, "text": message, "parse_mode": "HTML"},
            timeout=10,
        )
        if r.status_code != 200:
            print(f"⚠️ Erreur Telegram : {r.status_code}")
    except Exception as e:
        print(f"⚠️ Telegram erreur : {e}")


# === LOGS ===
def log_discussion(texte):
    with open(DISCUSSIONS_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*60}\n")
        f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"{'='*60}\n")
        f.write(texte + "\n")


def log_trade(ticker, action, prix, quantite, pnl_pct=None, montant=None):
    fichier_existe = os.path.exists(TRADES_FILE)
    with open(TRADES_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not fichier_existe:
            writer.writerow(["Date", "Ticker", "Action", "Prix", "Quantite", "Montant", "PnL_%"])
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ticker,
            action,
            f"{prix:.2f}",
            f"{quantite:.2f}" if quantite else "",
            f"{montant:.2f}" if montant else "",
            f"{pnl_pct:.2f}" if pnl_pct is not None else "",
        ])


# === GIGACHAT ===
def ask_gigachat(prompt):
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


def parse_avis_ia(texte):
    if not texte:
        return "INCONNU"
    texte_lower = texte.lower()
    if "acheter" in texte_lower or "achat" in texte_lower:
        return "ACHETER"
    if "vendre" in texte_lower or "vente" in texte_lower:
        return "VENDRE"
    if "attendre" in texte_lower or "neutre" in texte_lower:
        return "ATTENDRE"
    return "INCONNU"


# === NEWS ===
def get_news(limit=10):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        r = requests.get(NEWS_URL, headers=headers, timeout=15)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        items = root.findall(".//item")
        news = []
        for item in items[:limit]:
            title = item.findtext("title", default="")
            if title:
                news.append(title)
        return news
    except Exception as e:
        print(f"❌ Erreur RSS : {e}")
        return []


def get_news_sentiment():
    global _news_cache
    maintenant = time.time()

    if _news_cache["sentiment"] and (maintenant - _news_cache["timestamp"]) < NEWS_CACHE_SECONDS:
        print("📰 Sentiment des news (cache)")
        return _news_cache["sentiment"]

    print("🌐 Récupération des news Finam...")
    news = get_news(limit=10)
    if not news:
        return "News indisponibles."

    titres = "\n".join([f"- {n}" for n in news])
    prompt = f"""Tu es un analyste financier sur le marché russe.

Voici les dernières actualités :

{titres}

En UNE PHRASE, donne le sentiment global du marché : POSITIF, NÉGATIF ou NEUTRE.
Puis une phrase courte d'explication.

Format attendu :
SENTIMENT : [POSITIF/NÉGATIF/NEUTRE] - [explication courte]
"""

    sentiment = ask_gigachat(prompt)
    _news_cache["sentiment"] = sentiment
    _news_cache["timestamp"] = maintenant

    print(f"📰 Sentiment : {sentiment[:120]}...")
    return sentiment


# === PORTEFEUILLE ===
def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"capital": INITIAL_CAPITAL, "positions": {}, "historique": []}


def save_portfolio(p):
    with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
        json.dump(p, f, ensure_ascii=False, indent=2)


# === DONNÉES MOEX ===
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


def construire_prompt(ticker, prix, fast, slow, signal, historique_prix, sentiment_news):
    dernieres_prix = ", ".join([f"{p:.2f}" for p in historique_prix[-10:]])
    return f"""Tu es un analyste de trading. Voici les données d'une action russe :

Action : {ticker}
Prix actuel : {prix:.2f} RUB
Moyenne mobile rapide (SMA {FAST}) : {fast:.2f}
Moyenne mobile lente (SMA {SLOW}) : {slow:.2f}
Signal technique : {signal}
10 derniers prix : {dernieres_prix}

Contexte macro (news récentes) :
{sentiment_news}

Réponds STRICTEMENT dans ce format :
1. DÉCISION : ACHETER, VENDRE ou ATTENDRE
2. JUSTIFICATION : une phrase courte (en tenant compte du contexte news)
"""


# === NOTIFICATIONS ===
def notif_achat(ticker, prix, quantite, montant, capital_restant, avis_ia, fast, slow):
    msg = (
        f"🟢 <b>ACHAT — {ticker}</b>\n\n"
        f"💰 Prix : <b>{prix:.2f} ₽</b>\n"
        f"📦 Quantité : {quantite:.2f} actions\n"
        f"💵 Montant : {montant:,.0f} ₽\n"
        f"📊 SMA {FAST} : {fast:.2f} | SMA {SLOW} : {slow:.2f}\n"
        f"🤖 IA : {avis_ia} (consensus ✅)\n"
        f"💼 Capital restant : {capital_restant:,.0f} ₽"
    )
    send_telegram(msg)


def notif_vente(ticker, prix_achat, prix_vente, quantite, pnl_pct, capital_total, avis_ia):
    gain = (prix_vente - prix_achat) * quantite
    emoji = "✅" if pnl_pct >= 0 else "❌"
    mot = "Gain" if pnl_pct >= 0 else "Perte"
    msg = (
        f"🔴 <b>VENTE — {ticker}</b>\n\n"
        f"📈 Achat : {prix_achat:.2f} ₽\n"
        f"📉 Vente : {prix_vente:.2f} ₽\n"
        f"📦 Quantité : {quantite:.2f} actions\n"
        f"{emoji} {mot} : <b>{gain:+,.0f} ₽ ({pnl_pct:+.2f}%)</b>\n"
        f"💼 Capital total : {capital_total:,.0f} ₽\n"
        f"🤖 IA : {avis_ia}"
    )
    send_telegram(msg)


def notif_stop_loss(ticker, prix_achat, prix_vente, quantite, pnl_pct, capital_total):
    perte = (prix_vente - prix_achat) * quantite
    msg = (
        f"🛑 <b>STOP-LOSS — {ticker}</b>\n\n"
        f"📈 Achat : {prix_achat:.2f} ₽\n"
        f"📉 Vente : {prix_vente:.2f} ₽\n"
        f"📦 Quantité : {quantite:.2f} actions\n"
        f"❌ Perte : <b>{perte:+,.0f} ₽ ({pnl_pct:+.2f}%)</b>\n"
        f"💼 Capital total : {capital_total:,.0f} ₽"
    )
    send_telegram(msg)


def notif_pas_consensus(ticker, signal_sma, avis_ia, prix, fast, slow):
    msg = (
        f"⚪ <b>Pas de consensus — {ticker}</b>\n\n"
        f"📊 SMA dit : {signal_sma}\n"
        f"🤖 IA dit : {avis_ia}\n"
        f"💰 Prix : {prix:.2f} ₽\n"
        f"📈 SMA {FAST} : {fast:.2f} | SMA {SLOW} : {slow:.2f}\n"
        f"→ Aucune action"
    )
    send_telegram(msg)


# === RÉSUMÉ QUOTIDIEN ===
def envoyer_resume_quotidien(p, prix_actuels):
    total_valeur = p["capital"]
    for ticker, pos in p["positions"].items():
        prix = prix_actuels.get(ticker, pos["prix_achat"])
        total_valeur += pos["quantite"] * prix

    pnl = total_valeur - INITIAL_CAPITAL
    pnl_pct = pnl / INITIAL_CAPITAL * 100

    trades_jour = []
    if os.path.exists(TRADES_FILE):
        today = datetime.now().strftime("%Y-%m-%d")
        with open(TRADES_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["Date"].startswith(today):
                    trades_jour.append(row)

    nb_gagnants = sum(1 for t in trades_jour if t.get("PnL_%") and float(t["PnL_%"]) > 0)
    nb_perdants = sum(1 for t in trades_jour if t.get("PnL_%") and float(t["PnL_%"]) < 0)
    win_rate = (nb_gagnants / len(trades_jour) * 100) if trades_jour else 0

    positions_str = ", ".join(p["positions"].keys()) if p["positions"] else "Aucune"
    emoji_pnl = "🟢" if pnl >= 0 else "🔴"

    msg = (
        f"📊 <b>RÉSUMÉ DU JOUR</b>\n\n"
        f"📈 Trades : {len(trades_jour)} "
        f"({nb_gagnants} gagnants, {nb_perdants} perdants)\n"
        f"🎯 Win rate : {win_rate:.1f}%\n"
        f"{emoji_pnl} PnL : <b>{pnl:+,.0f} ₽ ({pnl_pct:+.2f}%)</b>\n"
        f"📦 Positions ouvertes : {positions_str}\n"
        f"💼 Capital total : {total_valeur:,.0f} ₽"
    )
    send_telegram(msg)


def verifier_heure_resume():
    maintenant = datetime.now()
    aujourdhui = maintenant.strftime("%Y-%m-%d")
    heure_actuelle = maintenant.hour
    derniere_date = ""
    if os.path.exists(RESUME_FILE):
        with open(RESUME_FILE, "r") as f:
            derniere_date = f.read().strip()
    if heure_actuelle == RESUME_HEURE and derniere_date != aujourdhui:
        return True
    return False


def marquer_resume_envoye():
    with open(RESUME_FILE, "w") as f:
        f.write(datetime.now().strftime("%Y-%m-%d"))


# === BRIEFING MATINAL ===
def envoyer_briefing_news():
    """Envoie le briefing news du matin."""
    print("🌐 Briefing news du matin...")
    news = get_news(limit=10)
    if not news:
        return

    titres = "\n".join([f"• {n}" for n in news])
    prompt = f"""Tu es un analyste financier. Voici les news du jour :

{titres}

Résume en 3 points :
1. SENTIMENT GLOBAL : POSITIF, NÉGATIF ou NEUTRE
2. 2 SECTEURS À SURVEILLER
3. UN RISQUE PRINCIPAL

Sois très concis.
"""
    analyse = ask_gigachat(prompt)
    msg = (
        f"☀️ <b>BRIEFING MATINAL — Marché russe</b>\n\n"
        f"📰 <b>Top 5 news :</b>\n"
        + "\n".join([f"• {n[:80]}" for n in news[:5]])
        + f"\n\n🧠 <b>Analyse IA :</b>\n{analyse}"
    )
    send_telegram(msg)


def verifier_heure_briefing():
    maintenant = datetime.now()
    aujourdhui = maintenant.strftime("%Y-%m-%d")
    heure_actuelle = maintenant.hour
    derniere_date = ""
    if os.path.exists(BRIEFING_FILE):
        with open(BRIEFING_FILE, "r") as f:
            derniere_date = f.read().strip()
    if heure_actuelle == BRIEFING_HEURE and derniere_date != aujourdhui:
        return True
    return False


def marquer_briefing_envoye():
    with open(BRIEFING_FILE, "w") as f:
        f.write(datetime.now().strftime("%Y-%m-%d"))


# === LOGIQUE PRINCIPALE ===
def check_signals_ia(p):
    prix_actuels = {}

    # Récupérer le sentiment des news UNE FOIS par cycle
    sentiment_news = get_news_sentiment()

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

        achat_sma = prev_fast <= prev_slow and fast > slow
        vente_sma = prev_fast >= prev_slow and fast < slow

        if not achat_sma and not vente_sma:
            continue

        signal_sma = "ACHAT" if achat_sma else "VENTE"

        # --- CONSULTATION IA avec contexte news ---
        print(f"\n🧠 Consultation GigaChat pour {ticker} ({signal_sma})...")
        prompt = construire_prompt(
            ticker, prix, fast, slow, signal_sma,
            list(df["CLOSE"].values),
            sentiment_news
        )
        reponse_ia = ask_gigachat(prompt)
        avis_ia = parse_avis_ia(reponse_ia)
        print(f"🤖 GigaChat ({avis_ia}) : {reponse_ia[:150]}")

        accord = (
            (signal_sma == "ACHAT" and avis_ia == "ACHETER") or
            (signal_sma == "VENTE" and avis_ia == "VENDRE")
        )

        if CONSENSUS_MODE and not accord:
            print(f"   ⚪ PAS DE CONSENSUS → aucune action")
            log_discussion(
                f"📊 SIGNAL : {signal_sma} sur {ticker}\n"
                f"   Prix : {prix:.2f} RUB\n"
                f"   SMA {FAST} : {fast:.2f} | SMA {SLOW} : {slow:.2f}\n"
                f"   Contexte news : {sentiment_news[:150]}\n\n"
                f"🤖 RÉPONSE :\n{reponse_ia}\n\n"
                f"🎯 DÉCISION : ⚪ AUCUNE (pas de consensus)"
            )
            notif_pas_consensus(ticker, signal_sma, avis_ia, prix, fast, slow)
            continue

        # --- CONSENSUS OK ---
        print(f"   ✅ CONSENSUS → {signal_sma}")
        log_discussion(
            f"📊 SIGNAL : {signal_sma} sur {ticker}\n"
            f"   Prix : {prix:.2f} RUB\n"
            f"   SMA {FAST} : {fast:.2f} | SMA {SLOW} : {slow:.2f}\n"
            f"   Contexte news : {sentiment_news[:150]}\n\n"
            f"🤖 RÉPONSE :\n{reponse_ia}\n\n"
            f"🎯 DÉCISION : ✅ {signal_sma} (consensus)"
        )

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
                    "prix": prix, "pnl_pct": pnl, "avis_ia": avis_ia,
                })
                print(f"   🛑 STOP-LOSS {ticker} ({pnl:+.2f}%)")
                notif_stop_loss(ticker, pos["prix_achat"], prix, pos["quantite"], pnl, p["capital"])
                log_trade(ticker, "STOP-LOSS", prix, pos["quantite"], pnl)
                del p["positions"][ticker]

            elif vente_sma:
                montant = pos["quantite"] * prix * (1 - COMMISSION)
                p["capital"] += montant
                pnl = (prix - pos["prix_achat"]) / pos["prix_achat"] * 100
                p["historique"].append({
                    "date": datetime.now().isoformat(),
                    "ticker": ticker, "action": "VENTE",
                    "prix": prix, "pnl_pct": pnl, "avis_ia": avis_ia,
                })
                print(f"   🔴 VENTE {ticker} ({pnl:+.2f}%)")
                notif_vente(ticker, pos["prix_achat"], prix, pos["quantite"], pnl, p["capital"], avis_ia)
                log_trade(ticker, "VENTE", prix, pos["quantite"], pnl)
                del p["positions"][ticker]

        # --- NOUVELLE POSITION ---
        elif achat_sma and p["capital"] > 1000:
            montant = p["capital"] * 0.2
            quantite = (montant * (1 - COMMISSION)) / prix
            p["capital"] -= montant
            p["positions"][ticker] = {
                "quantite": quantite, "prix_achat": prix,
            }
            p["historique"].append({
                "date": datetime.now().isoformat(),
                "ticker": ticker, "action": "ACHAT",
                "prix": prix, "pnl_pct": None, "avis_ia": avis_ia,
            })
            print(f"   🟢 ACHAT {ticker} ({quantite:.2f} actions)")
            notif_achat(ticker, prix, quantite, montant, p["capital"], avis_ia, fast, slow)
            log_trade(ticker, "ACHAT", prix, quantite, montant=montant)

    return prix_actuels


def afficher_portefeuille(p, prix_actuels):
    print(f"\n💰 Portefeuille")
    print(f"   Capital liquide : {p['capital']:,.2f} RUB")
    total = p["capital"]
    for ticker, pos in p["positions"].items():
        prix = prix_actuels.get(ticker, pos["prix_achat"])
        valeur = pos["quantite"] * prix
        total += valeur
        pnl = (prix - pos["prix_achat"]) / pos["prix_achat"] * 100
        emoji = "🟢" if pnl >= 0 else "🔴"
        print(f"   {emoji} {ticker} : {pos['quantite']:.2f} @ {pos['prix_achat']:.2f} → {prix:.2f} ({pnl:+.2f}%)")
    pnl_total = (total - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100
    emoji = "🟢" if pnl_total >= 0 else "🔴"
    print(f"   {emoji} Total : {total:,.2f} RUB ({pnl_total:+.2f}%)")


def main():
    p = load_portfolio()

    mode = "CONSENSUS (SMA + IA + News)" if CONSENSUS_MODE else "SMA seule"
    print(f"🧠 Bot IA — Mode : {mode}")
    print(f"   Capital : {INITIAL_CAPITAL:,} RUB")
    print(f"   Cycle : {CYCLE_SECONDS}s")
    print(f"   Briefing matinal : {BRIEFING_HEURE}h00")
    print(f"   Résumé quotidien : {RESUME_HEURE}h00")
    print("=" * 55)

    send_telegram(
        f"🧠 <b>Bot IA démarré</b>\n"
        f"Mode : {mode}\n"
        f"Capital : {INITIAL_CAPITAL:,} ₽\n"
        f"Briefing : {BRIEFING_HEURE}h00 | Résumé : {RESUME_HEURE}h00"
    )

    cycle = 0
    while True:
        cycle += 1
        print(f"\n🔄 Cycle #{cycle} — {datetime.now().strftime('%H:%M:%S')}")

        try:
            prix_actuels = check_signals_ia(p)
            afficher_portefeuille(p, prix_actuels)
            save_portfolio(p)

            # Briefing matinal (9h)
            if verifier_heure_briefing():
                print("☀️ Envoi du briefing matinal...")
                envoyer_briefing_news()
                marquer_briefing_envoye()

            # Résumé quotidien (20h)
            if verifier_heure_resume():
                print("📊 Envoi du résumé quotidien...")
                envoyer_resume_quotidien(p, prix_actuels)
                marquer_resume_envoye()

        except Exception as e:
            print(f"❌ Erreur : {e}")
            send_telegram(f"⚠️ Erreur : {e}")

        print(f"   Prochain cycle dans {CYCLE_SECONDS}s...")
        time.sleep(CYCLE_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Bot arrêté.")
        send_telegram("👋 Bot IA arrêté.")