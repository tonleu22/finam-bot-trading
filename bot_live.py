import requests
import pandas as pd
import time
from datetime import datetime, timedelta

BASE_URL = "https://iss.moex.com/iss"

# Paramètres gagnants du backtest
FAST = 5
SLOW = 20

# Actions à surveiller
TICKERS = ["SBER", "GAZP", "LKOH", "ROSN", "GMKN", "NVTK", "TATN"]

# Mémoire des derniers signaux (pour ne pas répéter)
last_signals = {}


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


def check_signal(ticker):
    df = get_history(ticker, days=60)
    if df is None or len(df) < SLOW + 2:
        return

    df["SMA_FAST"] = df["CLOSE"].rolling(FAST).mean()
    df["SMA_SLOW"] = df["CLOSE"].rolling(SLOW).mean()

    last = df.iloc[-1]
    prev = df.iloc[-2]

    if pd.isna(last["SMA_FAST"]) or pd.isna(last["SMA_SLOW"]):
        return

    price = last["CLOSE"]
    fast = last["SMA_FAST"]
    slow = last["SMA_SLOW"]
    prev_fast = prev["SMA_FAST"]
    prev_slow = prev["SMA_SLOW"]

    # Détection du croisement
    signal = None
    if prev_fast <= prev_slow and fast > slow:
        signal = "🟢 ACHAT"
    elif prev_fast >= prev_slow and fast < slow:
        signal = "🔴 VENTE"

    # On n'affiche que si c'est un nouveau signal (pas répété)
    if signal and last_signals.get(ticker) != signal:
        last_signals[ticker] = signal
        print(f"\n{'='*55}")
        print(f"🚨 SIGNAL {signal} sur {ticker} !")
        print(f"   Prix : {price:.2f} RUB")
        print(f"   SMA {FAST} : {fast:.2f}  |  SMA {SLOW} : {slow:.2f}")
        print(f"   Heure : {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'='*55}")
    elif not signal:
        # Reset quand il n'y a plus de signal
        last_signals[ticker] = None


def main():
    print("🤖 Bot de trading en direct — Actions russes")
    print(f"   Stratégie : SMA {FAST}/{SLOW}")
    print(f"   Actions   : {', '.join(TICKERS)}")
    print(f"   Cycle     : toutes les 30 secondes")
    print("=" * 55)
    print("Appuie sur Ctrl+C pour arrêter.\n")

    cycle = 0
    while True:
        cycle += 1
        print(f"\n🔄 Cycle #{cycle} — {datetime.now().strftime('%H:%M:%S')}")

        for ticker in TICKERS:
            check_signal(ticker)

        print(f"   ✅ {len(TICKERS)} actions vérifiées. "
              f"Prochain cycle dans 30s...")
        time.sleep(30)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Bot arrêté. À bientôt !")