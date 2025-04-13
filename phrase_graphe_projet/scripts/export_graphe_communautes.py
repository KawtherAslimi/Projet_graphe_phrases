import os
import sqlite3
import networkx as nx
import community.community_louvain as community_louvain
from pyvis.network import Network
from collections import defaultdict
import json
import webbrowser
from math import log

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "..", "db", "phrases.db")

MIN_COOC = 2          
MIN_WORD_LENGTH = 4   
MIN_COMM_SIZE = 5     
PALETTE_SIZE = 10    

STOPWORDS = {
    "le", "la", "les", "de", "des", "un", "une", "et", "à", "en",
    "dans", "pour", "au", "aux", "du", "ce", "cette", "par", "sur",
    "est", "son", "ses", "qui", "que", "ont", "pas", "avec"
}

THEMATIQUES = {
    "politique": ["réglementation", "parlement", "présidentiel", "démocratie", "constitution"],
    "technologie": ["auto", "généré", "données", "robotique", "automatique"],
    "philosophie": ["philosophique", "raisonnement", "pensée", "classique", "œuvre"],
    "histoire": ["époque", "siècle", "france", "développement", "essor"]
}

def get_phrases_generees():
    """
    Récupère toutes les phrases dans la table 'phrases',
    et filtre par longueur de 6 à 25 mots (exemple).
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT text FROM phrases")
    phrases = [row[0].strip().lower() for row in cursor.fetchall()]
    conn.close()
    return [p for p in phrases if 6 <= len(p.split()) <= 25]

def get_id_to_mot():
    """
    Récupère l'ensemble des mots depuis la table 'mots'
    et retourne deux mappings : id_to_mot et mot_to_id,
    en filtrant ceux qui sont trop courts ou dans STOPWORDS.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, mot FROM mots")
    raw = cursor.fetchall()
    conn.close()

    id_to_mot = {}
    for row_id, mot in raw:
        if (len(mot) >= MIN_WORD_LENGTH) and (mot not in STOPWORDS) and mot.isalpha():
            id_to_mot[row_id] = mot
    
    mot_to_id = {mot: row_id for row_id, mot in id_to_mot.items()}
    return id_to_mot, mot_to_id

def calculer_poids_tfidf(cooccurrence, total_phrases):
    """
    Calcule un TF-IDF simplifié :
    - cooccurrence[(a, b)] = nombre de phrases où a & b coapparaissent
    - idf basé sur le log(total_phrases / freq).
    """
    df = defaultdict(int)
    for (a, b) in cooccurrence:
        df[(a, b)] += 1

    weighted = {}
    from math import log
    for pair, count in cooccurrence.items():
        idf = log(total_phrases / (1 + df[pair]))
        weighted[pair] = count * idf
    
    return weighted

def detecter_thematique(mots):
    """
    Détecte le thème dominant d'une liste de mots
    en s'appuyant sur le dictionnaire THEMATIQUES.
    """
    scores = defaultdict(int)
    for theme, keywords in THEMATIQUES.items():
        for kw in keywords:
            if kw in mots:
                scores[theme] += 1

    if scores:
        return max(scores.items(), key=lambda x: x[1])[0]
    return "autre"

def construire_graphe_cooccurrence():
    """
    Construit un graphe NON orienté basé sur la cooccurrence de mots dans les phrases.
    Applique un TF-IDF simplifié et conserve les liens >= MIN_COOC.
    """
    phrases = get_phrases_generees()
    total_phrases = len(phrases)

    id_to_mot, mot_to_id = get_id_to_mot()

    G = nx.Graph()
    cooccurrence = defaultdict(int)
    frequences = defaultdict(int)

    for phrase in phrases:
        mots = [m for m in phrase.split() if m in mot_to_id]
        ids = [mot_to_id[mot] for mot in mots]
        for unique_id in set(ids):
            frequences[unique_id] += 1

        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = sorted((ids[i], ids[j]))
                cooccurrence[(a, b)] += 1

    weighted_cooc = calculer_poids_tfidf(cooccurrence, total_phrases)

    for (a, b), poids in weighted_cooc.items():
        if poids >= MIN_COOC:
            G.add_edge(a, b, weight=poids, raw_count=cooccurrence[(a, b)])

    nx.set_node_attributes(G, {nid: mot for nid, mot in id_to_mot.items()}, "label")
    nx.set_node_attributes(G, frequences, "freq")

    return G, id_to_mot

def fusionner_petites_communautes(partition, G):
    """
    Fusionne dans la plus grande communauté voisine celles qui sont trop petites (< MIN_COMM_SIZE).
    """
    comm_counts = defaultdict(int)
    for node, comm in partition.items():
        comm_counts[comm] += 1

    petites_comms = [comm for comm, count in comm_counts.items() if count < MIN_COMM_SIZE]

    for comm in petites_comms:
        voisins = defaultdict(int)
        nodes_in_comm = [n for n in partition if partition[n] == comm]
        for n in nodes_in_comm:
            for neighbor in G.neighbors(n):
                if partition[neighbor] != comm:
                    voisins[partition[neighbor]] += 1
        if voisins:
            nouvelle_comm = max(voisins.items(), key=lambda x: x[1])[0]
            for node in nodes_in_comm:
                partition[node] = nouvelle_comm
    return partition

def exporter_graphe_communautes():
    """
    Construit le graphe de cooccurrence, détecte les communautés via Louvain,
    fusionne les petites communautés, puis affiche via PyVis.
    """
    print("🔎 Construction du graphe de cooccurrence...")
    G, id_to_mot = construire_graphe_cooccurrence()
    print(f"   -> Graphe : {G.number_of_nodes()} nœuds, {G.number_of_edges()} arêtes.")

    print("🔎 Détection des communautés (Louvain)...")
    import community.community_louvain as community_louvain
    partition = community_louvain.best_partition(G, random_state=42)

    partition = fusionner_petites_communautes(partition, G)

    communautes = defaultdict(list)
    for node, comm in partition.items():
        communautes[comm].append(id_to_mot[node])

    net = Network(
        height="100vh",
        width="100%",
        bgcolor="#f8f9fa",
        font_color="#2c3e50",
        notebook=False,
        select_menu=True,
        filter_menu=True
    )

    net.set_options("""
    {
      "interaction": {
        "hover": true,
        "tooltipDelay": 200
      },
      "manipulation": {
        "enabled": false
      },
      "locale": "fr",
      "physics": {
        "forceAtlas2Based": {
          "gravitationalConstant": -50,
          "centralGravity": 0.02,
          "springLength": 100,
          "damping": 0.8
        },
        "minVelocity": 0.75,
        "solver": "forceAtlas2Based"
      }
    }
    """)

    palette = [
        "#4e79a7", "#f28e2b", "#e15759", "#76b7b2",
        "#59a14f", "#edc948", "#b07aa1", "#ff9da7",
        "#9c755f", "#bab0ac"
    ]

    def detecter_thematique(mots):
        """Détection simpliste de thème parmi THEMATIQUES."""
        from collections import defaultdict
        scores = defaultdict(int)
        for theme, keywords in THEMATIQUES.items():
            for kw in keywords:
                if kw in mots:
                    scores[theme] += 1
        if scores:
            return max(scores.items(), key=lambda x: x[1])[0]
        return "autre"

    print("🔎 Ajout des nœuds...")
    for node in G.nodes():
        comm = partition[node]
        mots_comm = communautes[comm]
        theme = detecter_thematique(mots_comm)
        freq_node = G.nodes[node].get("freq", 1)

        color = palette[comm % PALETTE_SIZE]
        title_info = (
            f"<b>{id_to_mot[node]}</b><br>"
            f"Communauté {comm} - {theme.capitalize()}<br>"
            f"Fréquence: {freq_node}"
        )

        net.add_node(
            node,
            label=id_to_mot[node],
            color=color,
            size=10 + min(40, freq_node * 0.3),
            title=title_info,
            group=theme
        )

    print("🔎 Ajout des arêtes...")
    for s, t, data in G.edges(data=True):
        net.add_edge(
            s,
            t,
            value=data['weight'],
            title=f"Cooccurrences: {data['raw_count']} (poids TF-IDF: {data['weight']:.2f})",
            color="rgba(120,120,120,0.4)",
            width=0.5 + data['weight'] * 0.05
        )

    output_file = os.path.join(BASE_DIR, "graphe_communautes_final.html")
    try:
        net.save_graph(output_file)
        print(f"✅ Graphe des communautés exporté → {output_file}")
        webbrowser.open(f"file://{output_file}")
    except Exception as e:
        print(f"Erreur lors de l'export: {e}")

    mod = community_louvain.modularity(partition, G)
    with open("analyse_communautes.json", "w", encoding="utf-8") as f:
        json.dump({
            "modularite": mod,
            "communautes": {
                comm: {
                    "mots": communautes[comm],
                    "theme": detecter_thematique(communautes[comm]),
                    "taille": len(communautes[comm])
                }
                for comm in communautes
            }
        }, f, indent=2, ensure_ascii=False)
    print(f"Modularité du graphe: {mod:.4f}")


if __name__ == "__main__":
    exporter_graphe_communautes()
