import requests
import pandas as pd
from datetime import datetime, timedelta

BASE_URL = "https://iss.moex.com/iss"

# ⚙️ PARAMÈTRES CORRIGÉS : 5/20 (comme le bot live)
INITIAL_CAPITAL = 100_000
FAST = 5
SLOW = 20


def get_history(ticker, days=365):
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


def backtest(ticker, fast=FAST, slow=SLOW):
    """Backtest avec les paramètres 5/20."""
    df = get_history(ticker, days=365)

    if df is None or len(df) < slow + 5:
        print(f"⚠️  Pas assez de données pour {ticker}")
        return

    df["SMA_FAST"] = df["CLOSE"].rolling(fast).mean()
    df["SMA_SLOW"] = df["CLOSE"].rolling(slow).mean()

    capital = INITIAL_CAPITAL
    position = 0
    buy_price = 0
    trades = []

    for i in range(1, len(df)):
        row = df.iloc[i]
        prev = df.iloc[i - 1]

        if pd.isna(row["SMA_FAST"]) or pd.isna(row["SMA_SLOW"]):
            continue

        # Croisement HAUSSIER → achat
        if (prev["SMA_FAST"] <= prev["SMA_SLOW"]
                and row["SMA_FAST"] > row["SMA_SLOW"]
                and position == 0):
            position = capital / row["CLOSE"]
            buy_price = row["CLOSE"]
            trades.append(("ACHAT", row["TRADEDATE"], row["CLOSE"]))
            capital = 0

        # Croisement BAISSIER → vente
        elif (prev["SMA_FAST"] >= prev["SMA_SLOW"]
                and row["SMA_FAST"] < row["SMA_SLOW"]
                and position > 0):
            capital = position * row["CLOSE"]
            pnl = (row["CLOSE"] - buy_price) / buy_price * 100
            trades.append(("VENTE", row["TRADEDATE"], row["CLOSE"], f"{pnl:+.2f}%"))
            position = 0

    # Valeur finale
    if position > 0:
        final_value = position * df.iloc[-1]["CLOSE"]
    else:
        final_value = capital

    gain = final_value - INITIAL_CAPITAL
    gain_pct = gain / INITIAL_CAPITAL * 100

    print(f"\n📊 {ticker}")
    print(f"   Capital initial : {INITIAL_CAPITAL:,.0f} RUB")
    print(f"   Capital final   : {final_value:,.0f} RUB")
    print(f"   Gain            : {gain:+,.0f} RUB ({gain_pct:+.2f}%)")
    print(f"   Nombre de trades : {len(trades)}")

    for t in trades:
        if len(t) == 4:
            print(f"      {t[0]:6} le {t[1]} à {t[2]:.2f} → {t[3]}")
        else:
            print(f"      {t[0]:6} le {t[1]} à {t[2]:.2f}")


def main():
    print(f"🇷🇺 Backtest de la stratégie SMA {FAST}/{SLOW}")
    print("=" * 55)

    tickers = ["SBER", "GAZP", "LKOH", "ROSN", "GMKN", "NVTK", "TATN"]
    for ticker in tickers:
        backtest(ticker)

    print("\n" + "=" * 55)
    print("✅ Backtest terminé")


if __name__ == "__main__":
    main()