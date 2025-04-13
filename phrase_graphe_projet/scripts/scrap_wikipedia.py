import requests
from bs4 import BeautifulSoup
import sqlite3
from utils import nettoyer_texte, contient_nom_propre
import time
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "..", "db", "phrases.db")

PAGES_WIKIPEDIA = [
    "https://fr.wikipedia.org/wiki/Intelligence_artificielle",
    "https://fr.wikipedia.org/wiki/Démocratie",
    "https://fr.wikipedia.org/wiki/Philosophie"
]

def extraire_texte_article(url):
    try:
        r = requests.get(url)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "html.parser")
        contenu = soup.find("div", {"id": "mw-content-text"})
        return contenu.get_text(separator=" ", strip=True) if contenu else ""
    except Exception as e:
        print(f"    [ERREUR extraction] {e}")
        return ""

def inserer_dans_bdd(titre, source, url, phrases):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR IGNORE INTO articles (title, source, url, content)
            VALUES (?, ?, ?, ?)
        """, (titre, source, url, "\n".join(phrases)))

        cursor.execute("SELECT id FROM articles WHERE url = ?", (url,))
        article_id = cursor.fetchone()[0]

        for phrase in phrases:
            cursor.execute("INSERT INTO phrases (article_id, text) VALUES (?, ?)", (article_id, phrase))

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"    [ERREUR BDD] {e}")

def scraper_wikipedia():
    print(f"[✓] {len(PAGES_WIKIPEDIA)} pages Wikipédia à traiter.")

    for i, lien in enumerate(PAGES_WIKIPEDIA):
        print(f"[{i+1}/{len(PAGES_WIKIPEDIA)}] {lien}")
        try:
            r = requests.get(lien)
            soup = BeautifulSoup(r.content, "html.parser")
            titre_tag = soup.find("h1")
            titre = titre_tag.text.strip() if titre_tag else "Sans titre"

            texte = extraire_texte_article(lien)
            phrases_brutes = nettoyer_texte(texte)

            phrases_filtrees = [p for p in phrases_brutes if contient_nom_propre(p)]

            phrases_filtrees = [p for p in phrases_filtrees if 4 <= len(p.split()) <= 20]

            phrases_filtrees = phrases_filtrees[:100]

            if phrases_filtrees:
                inserer_dans_bdd(titre, "Wikipédia", lien, phrases_filtrees)
                print(f"    → {len(phrases_filtrees)} phrases insérées.")
            else:
                print("    → Aucune phrase retenue.")

            time.sleep(1.5)

        except Exception as e:
            print(f"    [ERREUR général] {e}")

if __name__ == "__main__":
    scraper_wikipedia()
