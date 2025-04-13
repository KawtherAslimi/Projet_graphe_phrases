import sqlite3
import os
import re

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "db", "phrases.db")

def est_mot_francais(mot: str) -> bool:
    """
    Vérifie qu'un mot est potentiellement francophone
    en excluant certaines lettres peu usitées en français (k, w, etc.).
    
    Approche simpliste :
      - Lettres [a-j, l-v, x-z] + accents [àâçéèêëîïôûùüÿœæ]
      - Apostrophe et tiret autorisés au milieu
      - Exclut donc 'k' et 'w'
    
    NB : Cela peut éliminer certains mots considérés comme
    emprunts intégrés (ex. "wagon", "week-end", "kyste"…).
    """
   
    pattern = r"^[a-jl-vx-zàâçéèêëîïôûùüÿœæ]+(?:['-][a-jl-vx-zàâçéèêëîïôûùüÿœæ]+)*$"

    return bool(re.match(pattern, mot, flags=re.IGNORECASE))

def nettoyer_phrase(phrase: str) -> str:
    """
    Nettoie une phrase en plusieurs étapes :
      - Passage en minuscules
      - Suppression des URLs
      - Suppression des nombres
      - Suppression des guillemets et caractères spéciaux
      - Suppression des symboles mathématiques, lettres grecques
      - Filtrage des mots non francophones (regex ci-dessus)
      - Normalisation des espaces et tirets
    Retourne la phrase nettoyée, ou chaîne vide si tout a été supprimé.
    """
    phrase = phrase.lower()

    phrase = re.sub(r"https?://\S+|www\.\S+", "", phrase)

    phrase = re.sub(r"\d+", "", phrase)

    phrase = re.sub(r"""[\"“”«»‘’'´`§°±©®™•…–—¬¦]""", "", phrase)

    phrase = re.sub(r"[^\w\s'-]|_", " ", phrase)
    phrase = re.sub(r"[α-ωΑ-Ω]", "", phrase, flags=re.IGNORECASE)

    phrase = re.sub(r"\s+", " ", phrase)
    phrase = phrase.strip()

    mots = phrase.split()
    mots_fr = [m for m in mots if est_mot_francais(m)]

    phrase_finale = " ".join(mots_fr)

    return phrase_finale.strip()

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT id, text FROM phrases")
    rows = cursor.fetchall()

    modifiees = 0
    supprimees = 0

    phrases_deja_vues = {}

    for row_id, texte_original in rows:
        phrase_nettoyee = nettoyer_phrase(texte_original)

        if not phrase_nettoyee:
            cursor.execute("DELETE FROM phrases WHERE id = ?", (row_id,))
            supprimees += 1
            continue

        if phrase_nettoyee in phrases_deja_vues:
            cursor.execute("DELETE FROM phrases WHERE id = ?", (row_id,))
            supprimees += 1
        else:
            phrases_deja_vues[phrase_nettoyee] = row_id

            if phrase_nettoyee != texte_original:
                cursor.execute("UPDATE phrases SET text = ? WHERE id = ?", (phrase_nettoyee, row_id))
                modifiees += 1

    conn.commit()
    conn.close()

    print(f" {modifiees} phrases modifiées.")
    print(f" {supprimees} phrases supprimées (doublons ou vides).")

if __name__ == "__main__":
    main()
