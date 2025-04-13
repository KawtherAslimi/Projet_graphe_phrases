import os
import sqlite3
import random
import networkx as nx
from collections import defaultdict

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "..", "db", "phrases.db")

MOTS_INTERDITS = {
    "nbsp", "quot", "lt", "gt", "→", "←", "ref", "wikidata",
    "suivant", "précédent", "description", "displaystyle",
    "page", "voir", "source", "article", "lien", "consulter"
}


def construire_graphe(min_usage=3, max_usage=500):
    """
    Construit un graphe orienté Markov en ne gardant que les mots dont la somme des poids
    (entrants + sortants) est entre 'min_usage' et 'max_usage'. Cela réduit fortement le
    nombre de nœuds et permet des phrases plus cohérentes.
    """
    G = nx.DiGraph()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT mot_source_id, mot_cible_id, poids FROM transitions")
    all_transitions = cursor.fetchall()

    usage = defaultdict(int)
    for source, cible, poids in all_transitions:
        usage[source] += poids
        usage[cible] += poids

    cursor.execute("SELECT id, mot FROM mots")
    all_mots = cursor.fetchall()

 
    mots_valides = set()
    for id_mot, mot in all_mots:
        if (mot 
            and mot.strip() 
            and mot not in MOTS_INTERDITS 
            and min_usage <= usage[id_mot] <= max_usage):
            mots_valides.add(id_mot)

    for id_mot in mots_valides:
        
        pass  

    dict_mots = {id_m: m for (id_m, m) in all_mots}
    for id_mot in mots_valides:
        G.add_node(id_mot, label=dict_mots[id_mot])

    aretes_ajoutees = 0
    for source, cible, poids in all_transitions:
        if source in mots_valides and cible in mots_valides:
            G.add_edge(source, cible, weight=poids)
            aretes_ajoutees += 1

    conn.close()

    print(f"[INFO] Nœuds retenus (usage entre {min_usage} et {max_usage}) : {len(G.nodes)}")
    print(f"[INFO] Arêtes retenues (après filtrage) : {aretes_ajoutees}")

    return G


def generer_phrase(G, longueur_max=15):
    """
    Génère une phrase aléatoire à partir du graphe G.
    - Choisit un nœud de départ parmi ceux qui sont valides (au hasard).
    - Sélectionne le prochain mot parmi les successeurs (tirage aléatoire pondéré).
    - S'arrête si on atteint un mot interdit ou n'a plus de successeurs.
    - Retourne la phrase (minimum 4 mots), sinon "[Aucune phrase générée]".
    """
    if G.number_of_nodes() == 0:
        return "[Erreur] Le graphe est vide."

    noeuds_depart = [
        n for n in G.nodes
        if G.nodes[n]["label"] not in MOTS_INTERDITS
    ]
    if not noeuds_depart:
        return "[Erreur] Aucun nœud de départ valide."

    courant = random.choice(noeuds_depart)
    phrase = [G.nodes[courant]["label"]]

    for _ in range(longueur_max - 1):
        voisins = list(G.successors(courant))
        if not voisins:
            break
        poids = [G[courant][v]["weight"] for v in voisins]
        courant = random.choices(voisins, weights=poids)[0]
        mot = G.nodes[courant]["label"]
        if mot in MOTS_INTERDITS or mot == ".":
            break
        phrase.append(mot)

    phrase_str = " ".join(phrase)
    phrase_str = phrase_str.capitalize().strip() + "."

    return phrase_str if len(phrase) >= 4 else "[Aucune phrase générée]"

def debug_phrase(G, phrase):
    """
    Affiche le chemin complet d'une phrase dans le graphe avec détails des transitions
    Retourne None si la phrase n'est pas trouvée
    """
    mots = phrase.lower().split()
    if not mots:
        return None

    dict_mots_inverse = {v: k for k, v in G.nodes(data='label')}
    ids = [dict_mots_inverse.get(mot, None) for mot in mots]
    
    if None in ids:
        print(f"Mot manquant: {mots[ids.index(None)]}")
        return None

    chemin_valide = True
    details = []
    
    for i in range(len(ids)-1):
        source = ids[i]
        cible = ids[i+1]
        
        if G.has_edge(source, cible):
            poids = G[source][cible]['weight']
            details.append(f"{G.nodes[source]['label']} → {G.nodes[cible]['label']} ({poids})")
        else:
            chemin_valide = False
            details.append(f"{G.nodes[source]['label']} → {G.nodes[cible]['label']} (ABSENT)")
    
    print(f"\n🔍 Debug phrase: '{phrase}'")
    print("Chemin complet:")
    print("\n".join(details))
    print(f"Validité: {' COMPLET' if chemin_valide else ' INCOMPLET'}")
    
    return chemin_valide

if __name__ == "__main__":
    G = construire_graphe(min_usage=3, max_usage=300)

    print("\n Génération de 5 phrases...\n")
    for _ in range(5):
        print("→", generer_phrase(G))
