import os
from dotenv import load_dotenv
from gigachat import GigaChat

load_dotenv()

KEY = os.getenv("GIGACHAT_KEY")

if KEY:
    print(f"Clé : {KEY[:20]}...{KEY[-10:]}")
else:
    print("❌ Clé manquante dans .env")
    exit()

print("-" * 50)

# ⚙️ MODIFICATION : On spécifie le modèle "GigaChat-2" ici
try:
    with GigaChat(
        credentials=KEY,
        model="GigaChat-2",          # <-- LA CORRECTION EST ICI
        verify_ssl_certs=False,
    ) as giga:
        response = giga.chat("Bonjour ! Réponds en une phrase courte.")
        print("✅ Connexion réussie !")
        print(f"🤖 GigaChat dit : {response.choices[0].message.content}")

except Exception as e:
    print(f"❌ Erreur : {type(e).__name__} → {e}")