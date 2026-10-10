import asyncio
import os
from dotenv import load_dotenv
from finam_trade_api import Client, TokenManager

# Charge le fichier .env
load_dotenv()

TOKEN = os.getenv("FINAM_TOKEN")
ACCOUNT_ID = os.getenv("FINAM_ACCOUNT_ID")

print(f"Token chargé : {TOKEN[:12]}..." if TOKEN else "❌ Token manquant")
print(f"Compte : {ACCOUNT_ID}")
print("-" * 50)


async def test_connexion():
    try:
        # Initialisation du client
        client = Client(TokenManager(TOKEN))
        await client.access_tokens.set_jwt_token()
        print("✅ Authentification réussie")

        # Récupérer les infos du compte
        account_info = await client.account.get_account_info(ACCOUNT_ID)
        print(f"✅ Infos du compte : {account_info}")

        # Récupérer les positions
        positions = await client.account.get_positions(ACCOUNT_ID)
        print(f"✅ Positions : {positions}")

    except Exception as e:
        print(f"❌ Erreur : {type(e).__name__} → {e}")


if __name__ == "__main__":
    asyncio.run(test_connexion())