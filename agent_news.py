import os
import requests
import xml.etree.ElementTree as ET
from dotenv import load_dotenv
from gigachat import GigaChat

load_dotenv()

GIGA_KEY = os.getenv("GIGACHAT_KEY")

# URL du flux RSS Finam
URL = "https://www.finam.ru/analysis/conews/rsspoint/"


def get_news(limit=10):
    """Récupère les dernières news depuis le flux RSS."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        r = requests.get(URL, headers=headers, timeout=15)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        items = root.findall(".//item")

        news = []
        for item in items[:limit]:
            title = item.findtext("title", default="")
            desc = item.findtext("description", default="")
            date = item.findtext("pubDate", default="")
            news.append({"title": title, "desc": desc, "date": date})
        return news
    except Exception as e:
        print(f"❌ Erreur RSS : {e}")
        return []


def analyser_news(news):
    """Demande à GigaChat d'analyser les news."""
    # Construire la liste des titres
    titres = "\n".join([f"- {n['title']}" for n in news])

    prompt = f"""Tu es un analyste financier spécialisé sur le marché russe.

Voici les dernières actualités financières :

{titres}

Analyse ces news et réponds STRICTEMENT dans ce format :

1. SENTIMENT GLOBAL : POSITIF, NÉGATIF ou NEUTRE
2. IMPACT MARCHÉ : une phrase courte sur l'impact attendu
3. SECTEURS À SURVEILLER : liste des secteurs concernés
4. RISQUES : un risque principal à surveiller

Sois concis et factuel.
"""

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


def main():
    print("🌐 Récupération des news Finam...")
    news = get_news(limit=10)

    if not news:
        print("❌ Aucune news récupérée.")
        return

    print(f"✅ {len(news)} news récupérées\n")
    print("📰 Titres :")
    for i, n in enumerate(news, 1):
        print(f"  {i}. {n['title']}")

    print("\n" + "=" * 55)
    print("🧠 Analyse par GigaChat...")
    print("=" * 55)

    analyse = analyser_news(news)
    print(f"\n{analyse}")

    # Sauvegarder dans un fichier
    from datetime import datetime
    with open("analyses_news.log", "a", encoding="utf-8") as f:
        f.write(f"\n{'='*60}\n")
        f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"{'='*60}\n")
        f.write(f"News analysées : {len(news)}\n")
        f.write(f"{analyse}\n")

    print(f"\n💾 Analyse sauvegardée dans analyses_news.log")


if __name__ == "__main__":
    main()