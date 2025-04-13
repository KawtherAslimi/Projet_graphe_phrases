import os
import sys
import sqlite3
import subprocess
import re
from collections import Counter
from functools import lru_cache
from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException

from export_interactif import export_en_html   
from export_graphe_communautes import exporter_graphe_communautes  

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "..", "db", "phrases.db")

MOTS_INTERDITS = {
    "nbsp", "quot", "lt", "gt", "→", "←", "ref", "wikidata", "suivant",
    "précédent", "description", "displaystyle", "page", "voir", "source",
    "article", "lien", "consulter", "retrieved", "https", "isbn", "p",
    "the", "and", "of", "in", "to", "with", "as", "by", "was", "is", "an", "a"
}


@lru_cache(maxsize=10000)
def est_francais(mot):
    """Détecte si un mot est en français via langdetect."""
    try:
        return detect(mot) == "fr"
    except LangDetectException:
        return False


def vider_base_de_donnees():
    """Supprime toutes les données existantes dans les tables articles, phrases, mots, transitions."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    print(" Vidage des tables : articles, phrases, mots, transitions...")
    for table in ["articles", "phrases", "mots", "transitions"]:
        cursor.execute(f"DELETE FROM {table}")
    conn.commit()
    conn.close()
    print(" Base nettoyée avec succès.")


def remplir_mots_et_transitions(db_path):
    """
    Extrait les mots depuis la table `phrases`,
    nettoie, puis insère dans 'mots' et 'transitions' (pondération).
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print(" Nettoyage des tables 'mots' et 'transitions'...")
    cursor.execute("DELETE FROM mots")
    cursor.execute("DELETE FROM transitions")
    conn.commit()

    cursor.execute("SELECT text FROM phrases")
    lignes = [row[0] for row in cursor.fetchall() if row[0]]
    print(f" {len(lignes)} phrases récupérées depuis la table 'phrases'.")

    phrases_utiles = []
    compteur = Counter()

    for ligne in lignes:
        texte = ligne.lower()
        texte = re.sub(r"[^\wàâçéèêëîïôûùüÿœæ'-]+", " ", texte)
        texte = re.sub(r"\s+", " ", texte).strip()

        morceaux = re.split(r"\s*\.\s*", texte)
        for phrase in morceaux:
            mots = phrase.strip().split()
            mots = [m for m in mots
                    if m.isalpha()
                    and m not in MOTS_INTERDITS
                    and est_francais(m)]
            if len(mots) >= 4:
                phrases_utiles.append(mots)
                compteur.update(mots)

    print(f"\n {len(phrases_utiles)} phrases utiles conservées.")
    print(" Top 10 mots fréquents :")
    for mot, count in compteur.most_common(10):
        print(f"   {mot}: {count}")

    mots_valides = {mot for mot, count in compteur.items() if count >= 1}
    id_mots = {}
    for mot in mots_valides:
        cursor.execute("INSERT OR IGNORE INTO mots (mot, est_fin_phrase) VALUES (?, ?)", (mot, 0))
        cursor.execute("SELECT id FROM mots WHERE mot = ?", (mot,))
        id_mots[mot] = cursor.fetchone()[0]

    total = 0
    for mots in phrases_utiles:
        for i in range(len(mots) - 1):
            id_source = id_mots[mots[i]]
            id_cible = id_mots[mots[i + 1]]
            cursor.execute("""
                INSERT INTO transitions (mot_source_id, mot_cible_id, poids)
                VALUES (?, ?, 1)
                ON CONFLICT(mot_source_id, mot_cible_id)
                DO UPDATE SET poids = poids + 1
            """, (id_source, id_cible))
            total += 1

    conn.commit()
    conn.close()
    print(f"\n Transitions insérées : {total}")


def pipeline_complet():
    """Exécute toutes les étapes de traitement : scraping, nettoyage, insertion, visualisations."""
    print("\n Démarrage du pipeline complet")
    vider_base_de_donnees()

    print("\n Lancement du scraping principal (scrap_wikipedia.py)...")
    import scrap_wikipedia
    subprocess.run([sys.executable, "scrap_wikipedia.py"], check=True)

    print("\n🧹 Nettoyage des phrases (clean_phrases.py)...")
    clean_script = os.path.join(BASE_DIR, "clean_phrases.py")
    subprocess.run([sys.executable, clean_script], check=True)

    print("\n Remplissage des mots et transitions...")
    remplir_mots_et_transitions(DB_PATH)

    print("\n Export du graphe interactif (export_interactif.py)...")
    export_en_html()

    print("\n Export du graphe de communautés (Louvain)...")
    exporter_graphe_communautes()


if __name__ == "__main__":
    pipeline_complet()
