import spacy
import re

# Chargement du modèle français de spaCy
nlp = spacy.load("fr_core_news_sm")

def contient_nom_propre(phrase):
    """
    Vérifie si une phrase contient un nom propre (personne, organisation, lieu, etc.)
    """
    doc = nlp(phrase)
    for ent in doc.ents:
        if ent.label_ in ["PER", "LOC", "ORG", "MISC"]:
            return True
    return False

def nettoyer_texte(texte):
    """
    Nettoie le texte brut et le découpe en phrases significatives.
    """
    texte = texte.lower()
    texte = re.sub(r"[^a-zàâçéèêëîïôûùüÿœæ .!?]", " ", texte)  # conserve . ! ?
    texte = re.sub(r"\s+", " ", texte).strip()

    # Découpage en phrases
    phrases = re.split(r"[.!?]\s*", texte)

    # Filtrage des phrases : minimum 4 mots
    phrases_nettoyees = [p.strip().capitalize() for p in phrases if len(p.strip().split()) > 3]

    return phrases_nettoyees

def decouper_en_phrases(texte):
    """
    Transforme un texte en liste de listes de mots avec un point final, uniquement si la phrase est assez longue.
    """
    phrases = re.split(r"[.!?]\s*", texte)
    phrases_tokenisées = []

    for phrase in phrases:
        mots = phrase.strip().split()
        if len(mots) >= 6:
            phrases_tokenisées.append(mots + ['.'])

    return phrases_tokenisées
