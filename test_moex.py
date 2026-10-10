import requests

# L'API MOEX ISS est publique, pas besoin de token
BASE_URL = "https://iss.moex.com/iss"

def get_price(ticker):
    """Récupère le prix actuel d'une action sur la MOEX."""
    url = f"{BASE_URL}/engines/stock/markets/shares/boards/TQBR/securities/{ticker}.json"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # On extrait les données de la section "marketdata"
        columns = data["marketdata"]["columns"]
        rows = data["marketdata"]["data"]
        
        if not rows or not rows[0]:
            print(f"⚠️  Aucune donnée pour {ticker}")
            return None
        
        # On transforme en dictionnaire pour lire par nom de colonne
        market = dict(zip(columns, rows[0]))
        
        last_price = market.get("LAST")
        if last_price is None:
            print(f"⚠️  Pas de prix disponible pour {ticker}")
            return None
        
        print(f"📈 {ticker} : {last_price} RUB")
        return last_price
        
    except Exception as e:
        print(f"❌ Erreur pour {ticker} : {type(e).__name__} → {e}")
        return None


def main():
    print("🇷🇺 Récupération des cours des actions russes (MOEX)")
    print("-" * 50)
    
    # Quelques grandes actions russes
    tickers = ["SBER", "GAZP", "LKOH", "ROSN", "GMKN", "NVTK", "TATN"]
    
    for ticker in tickers:
        get_price(ticker)
    
    print("-" * 50)
    print("✅ Terminé")


if __name__ == "__main__":
    main()