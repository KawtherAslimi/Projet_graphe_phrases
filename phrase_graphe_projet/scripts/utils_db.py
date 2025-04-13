import sqlite3
import os

CHEMIN_DB = os.path.join("db", "phrases.db")

def inserer_phrases(phrases, source="", url=""):
    """
    Insère une liste de phrases dans la base de données
    """
    conn = sqlite3.connect(CHEMIN_DB)
    curseur = conn.cursor()
    for phrase in phrases:
        curseur.execute(
            "INSERT INTO phrases (phrase, source, url) VALUES (?, ?, ?)",
            (phrase, source, url)
        )
    conn.commit()
    conn.close()
    print(f" {len(phrases)} phrases insérées depuis {source}")
