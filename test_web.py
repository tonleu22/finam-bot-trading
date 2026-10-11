import requests
import xml.etree.ElementTree as ET

# URL du flux RSS des nouvelles de Finam
URL = "https://www.finam.ru/analysis/conews/rsspoint/"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

try:
    print(f"🌐 Connexion à {URL}...")
    r = requests.get(URL, headers=headers, timeout=15)
    r.raise_for_status()
    print(f"✅ Flux RSS récupéré ({len(r.text)} caractères)")

    # Analyse du XML
    root = ET.fromstring(r.content)

    # Le format RSS utilise la balise <item> pour chaque actualité
    items = root.findall(".//item")

    print(f"\n📰 {len(items)} nouvelles trouvées :\n")

    # Affichage des 10 premières
    for i, item in enumerate(items[:10], 1):
        title = item.findtext("title", default="(sans titre)")
        # On peut aussi récupérer la date
        pub_date = item.findtext("pubDate", default="")
        print(f"  {i}. {title}")
        if pub_date:
            print(f"      📅 {pub_date}")

except Exception as e:
    print(f"❌ Erreur : {type(e).__name__} → {e}")