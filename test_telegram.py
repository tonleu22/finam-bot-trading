import os
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

print(f"Token : {TOKEN[:15]}..." if TOKEN else "❌ Token manquant")
print(f"Chat ID : {CHAT_ID}")

if not TOKEN or not CHAT_ID:
    print("❌ Configuration incomplète")
    exit()

url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
data = {
    "chat_id": CHAT_ID,
    "text": "🎉 Test réussi ! Ton bot peut maintenant t'envoyer des alertes.",
}

r = requests.post(url, data=data, timeout=10)
if r.status_code == 200:
    print("✅ Message envoyé ! Vérifie ton téléphone.")
else:
    print(f"❌ Erreur : {r.status_code} → {r.text}")