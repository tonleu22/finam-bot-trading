import requests
import pandas as pd
from datetime import datetime, timedelta

BASE_URL = "https://iss.moex.com/iss"


def get_history(ticker, days=60):
    """Récupère l'historique des cours sur N jours."""
    # Date de fin = aujourd'hui, date de début = il y a N jours
    end = datetime.now()
    start = end - timedelta(days=days)

    url = (
        f"{BASE_URL}/history/engines/stock/markets/shares/boards/TQBR/"
        f"securities/{ticker}.json"
        f"?from={start.strftime('%Y-%m-%d')}"
        f"&till={end.strftime('%Y-%m-%d')}"
    )

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        columns = data["history"]["columns"]
        rows = data["history"]["data"]

        if not rows:
            return None

        df = pd.DataFrame(rows, columns=columns)
        # On garde seulement la date et le cours de clôture
        df = df[["TRADEDATE", "CLOSE"]].dropna()
        df["CLOSE"] = df["CLOSE"].astype(float)
        df = df.sort_values("TRADEDATE").reset_index(drop=True)
        return df

    except Exception as e:
        print(f"❌ Erreur pour {ticker} : {type(e).__name__} → {e}")
        return None


def analyse(ticker, fast=9, slow=30):
    """Calcule les SMA et génère un signal."""
    df = get_history(ticker, days=90)

    if df is None or len(df) < slow:
        print(f"⚠️  Pas assez de données pour {ticker}")
        return

    # Calcul des moyennes mobiles
    df["SMA_FAST"] = df["CLOSE"].rolling(window=fast).mean()
    df["SMA_SLOW"] = df["CLOSE"].rolling(window=slow).mean()

    last = df.iloc[-1]
    prev = df.iloc[-2]

    price = last["CLOSE"]
    sma_fast = last["SMA_FAST"]
    sma_slow = last["SMA_SLOW"]
    prev_fast = prev["SMA_FAST"]
    prev_slow = prev["SMA_SLOW"]

    # Détection du croisement
    signal = "⚪ Neutre (attendre)"
    if prev_fast <= prev_slow and sma_fast > sma_slow:
        signal = "🟢 ACHAT (croisement haussier)"
    elif prev_fast >= prev_slow and sma_fast < sma_slow:
        signal = "🔴 VENTE (croisement baissier)"

    print(f"\n📊 {ticker}")
    print(f"   Prix actuel : {price:.2f} RUB")
    print(f"   SMA {fast}     : {sma_fast:.2f}")
    print(f"   SMA {slow}    : {sma_slow:.2f}")
    print(f"   Signal      : {signal}")


def main():
    print("🇷🇺 Analyse technique des actions russes (SMA 9/30)")
    print("=" * 55)

    tickers = ["SBER", "GAZP", "LKOH", "ROSN", "GMKN", "NVTK", "TATN"]
    for ticker in tickers:
        analyse(ticker)

    print("\n" + "=" * 55)
    print("✅ Analyse terminée")


if __name__ == "__main__":
    main()