import requests
import pandas as pd
from datetime import datetime, timedelta

BASE_URL = "https://iss.moex.com/iss"

INITIAL_CAPITAL = 100_000
COMMISSION = 0.0005   # 0.05% par trade (frais MOEX)
STOP_LOSS = 0.05      # -5% → on vend automatiquement


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


def backtest(ticker, fast, slow):
    """Backtest avec paramètres personnalisés + stop-loss + commissions."""
    df = get_history(ticker, days=365)

    if df is None or len(df) < slow + 5:
        return None

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

        # STOP-LOSS : si on a une position et que le prix chute de -5%
        if position > 0 and row["CLOSE"] < buy_price * (1 - STOP_LOSS):
            capital = position * row["CLOSE"] * (1 - COMMISSION)
            pnl = (row["CLOSE"] - buy_price) / buy_price * 100
            trades.append(("STOP", row["TRADEDATE"], row["CLOSE"], pnl))
            position = 0
            continue

        # Croisement HAUSSIER → achat
        if (prev["SMA_FAST"] <= prev["SMA_SLOW"]
                and row["SMA_FAST"] > row["SMA_SLOW"]
                and position == 0):
            position = (capital * (1 - COMMISSION)) / row["CLOSE"]
            buy_price = row["CLOSE"]
            capital = 0
            trades.append(("ACHAT", row["TRADEDATE"], row["CLOSE"], None))

        # Croisement BAISSIER → vente
        elif (prev["SMA_FAST"] >= prev["SMA_SLOW"]
                and row["SMA_FAST"] < row["SMA_SLOW"]
                and position > 0):
            capital = position * row["CLOSE"] * (1 - COMMISSION)
            pnl = (row["CLOSE"] - buy_price) / buy_price * 100
            trades.append(("VENTE", row["TRADEDATE"], row["CLOSE"], pnl))
            position = 0

    if position > 0:
        final_value = position * df.iloc[-1]["CLOSE"] * (1 - COMMISSION)
    else:
        final_value = capital

    gain_pct = (final_value - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100
    closed = [t for t in trades if t[3] is not None]
    wins = [t for t in closed if t[3] > 0]
    win_rate = len(wins) / len(closed) * 100 if closed else 0

    return {
        "gain_pct": gain_pct,
        "trades": len(closed),
        "win_rate": win_rate,
        "final": final_value,
    }


def main():
    tickers = ["SBER", "GAZP", "LKOH", "ROSN", "GMKN", "NVTK", "TATN"]
    parametres = [(5, 20), (9, 30), (15, 50), (20, 60)]

    print("🇷🇺 Optimisation de la stratégie SMA")
    print("=" * 70)

    for fast, slow in parametres:
        print(f"\n🔧 Paramètres : SMA {fast} / SMA {slow}")
        print("-" * 70)

        total_gain = 0
        total_trades = 0
        total_wins = 0

        for ticker in tickers:
            r = backtest(ticker, fast, slow)
            if r is None:
                continue
            emoji = "🟢" if r["gain_pct"] > 0 else "🔴"
            print(f"   {emoji} {ticker:5} : {r['gain_pct']:+6.2f}%  "
                  f"({r['trades']} trades, {r['win_rate']:.0f}% gagnants)")
            total_gain += r["gain_pct"]
            total_trades += r["trades"]
            total_wins += r["win_rate"]

        moyenne = total_gain / len(tickers)
        win_moyen = total_wins / len(tickers)
        print(f"   ➡️  Moyenne : {moyenne:+.2f}%  "
              f"({total_trades} trades, {win_moyen:.0f}% gagnants)")

    print("\n" + "=" * 70)
    print("✅ Optimisation terminée")


if __name__ == "__main__":
    main()