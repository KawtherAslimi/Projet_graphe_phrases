import os
import sqlite3
import networkx as nx
from pyvis.network import Network
from collections import defaultdict
import webbrowser
import random
from collections import defaultdict
import re

TOP_N_MOTS = 80       
NB_POINTS_FIN = 5    
NB_PHRASES = 5        

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "..", "db", "phrases.db")

ARTICLES_SOURCES = {"le", "la", "les", "l", "un", "une", "des"}

def phrases_utiles_depuis_base():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT text FROM phrases")
    result = [row[0].strip().lower() for row in cursor.fetchall()]
    conn.close()
    return result

def get_mot_id(mot):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM mots WHERE mot = ?", (mot,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else None

def construire_graphe_pondere(top_n=TOP_N_MOTS, nb_points=NB_POINTS_FIN):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT mot_source_id, mot_cible_id, poids FROM transitions")
    transitions_brutes = cursor.fetchall()

    frequence_mots = defaultdict(int)
    for source, cible, poids in transitions_brutes:
        frequence_mots[source] += poids
        frequence_mots[cible] += poids

    cursor.execute("SELECT id, mot FROM mots")
    id_vers_mot = {m_id: mot for m_id, mot in cursor.fetchall()}

    mots_tries = sorted(frequence_mots.items(), key=lambda x: -x[1])
    top_ids = [m_id for m_id, _ in mots_tries if m_id in id_vers_mot][:top_n]
    mots_selectionnes = set(top_ids)

    sources_articles = {
        m_id for m_id, mot in id_vers_mot.items() 
        if mot.lower() in ARTICLES_SOURCES and m_id in mots_selectionnes
    }

    max_id_existant = max(id_vers_mot.keys(), default=9999)
    ids_fin_phrase = list(range(max_id_existant + 1, max_id_existant + 1 + nb_points))
    for pid in ids_fin_phrase:
        id_vers_mot[pid] = "•" 

    cursor.execute("SELECT text FROM phrases")
    phrases = [row[0].strip().lower() for row in cursor.fetchall()]

    nouvelles_transitions = []
    for i, phrase in enumerate(phrases):
        mots = phrase.split()
        if len(mots) >= 2:
            dernier_mot = mots[-1]
            cursor.execute("SELECT id FROM mots WHERE mot = ?", (dernier_mot,))
            resultat = cursor.fetchone()
            if resultat:
                id_dernier_mot = resultat[0]
                id_fin = ids_fin_phrase[i % len(ids_fin_phrase)]
                nouvelles_transitions.append((id_dernier_mot, id_fin, 1))

    toutes_transitions = transitions_brutes + nouvelles_transitions
    transitions_filtrees = [
        (s, t, w) for s, t, w in toutes_transitions
        if id_vers_mot.get(t, "") not in ARTICLES_SOURCES
        and (s in mots_selectionnes or s in ids_fin_phrase)
        and (t in mots_selectionnes or t in ids_fin_phrase)
    ]

    conn.close()
    return transitions_filtrees, id_vers_mot, mots_selectionnes, sources_articles, ids_fin_phrase


def generer_phrase_depuis_graphe(dict_mots, transitions, mots_sources, ids_point, mots_valides, max_longueur=25):
    graphe = defaultdict(list)
    contexte = defaultdict(lambda: defaultdict(int))
    triplets = defaultdict(int)

    for s, t, w in transitions:
        if s in mots_valides and t in mots_valides:
            graphe[s].append((t, w))
            contexte[s][t] += w
            
            for transition in transitions:
                if transition[0] == t:
                    triplets[(s, t, transition[1])] += 1

    def choisir_suivant(mot_actuel, historique, niveau=0):
        if niveau > 2 or mot_actuel not in graphe:
            return None
            
        poids_contextuels = []
        total = 0
        for t, w in graphe[mot_actuel]:
            score = w
            if len(historique) >= 2:
                score += triplets.get((historique[-2], mot_actuel, t), 0) * 2
            if t in historique[-3:]:
                score = max(1, score // 2)
            poids_contextuels.append(score)
            total += score

        if total == 0:
            return choisir_suivant(mot_actuel, historique, niveau+1)

        choix = random.choices(
            [t for t, _ in graphe[mot_actuel]],
            weights=poids_contextuels,
            k=1
        )[0]
        return choix

    for _ in range(10): 
        try:
            mot_courant = random.choices(
                list(mots_sources),
                weights=[sum(w for _, w in graphe[m]) for m in mots_sources]
            )[0]
            
            historique = [mot_courant]
            phrase = [dict_mots[mot_courant].capitalize()]
            force_min = random.randint(8, 12)  

            for _ in range(max_longueur):
                suivant = choisir_suivant(mot_courant, historique)
                if not suivant or suivant in ids_point:
                    if len(phrase) >= force_min:
                       
                        ponctuation = random.choice(['.', '.', '?', '!', '...'])
                        phrase[-1] += ponctuation
                        return ' '.join(phrase).replace(' ,', ', ')
                    continue
                
                mot = dict_mots[suivant].lower()
                
                if mot in {'le', 'la', 'les', 'un', 'une', 'des'} and len(phrase) > 1:
                    phrase.append(mot)
                else:
                    if phrase[-1][-1] in ('s', 'x') and mot.endswith(('s', 'x')):
                        mot = mot[:-1]
                    phrase.append(mot)

                historique.append(suivant)
                mot_courant = suivant

                if len(phrase) >= force_min and random.random() < 0.3:
                    break

            phrase_finale = ' '.join(phrase)
            phrase_finale = re.sub(r'\s+([,;.!?])', r'\1', phrase_finale)
            phrase_finale = phrase_finale[0].upper() + phrase_finale[1:]
            
            if len(phrase_finale.split()) >= 6:
                return phrase_finale

        except Exception as e:
            continue

    return "[Échec de génération après plusieurs tentatives]"

def export_en_html():
    transitions, dict_mots, mots_valides, mots_sources, ids_point = construire_graphe_pondere()

    net = Network(height="800px", width="100%", directed=True, bgcolor="#ffffff", font_color="#000000")
    net.force_atlas_2based()

    for node_id in mots_valides:
        mot = dict_mots[node_id]
        color = "#55dd55" if node_id in mots_sources else "#7bc9ff"
        net.add_node(node_id, label=mot, title=f"Mot : {mot}", color=color, size=20)

    for id_point in ids_point:
        net.add_node(id_point, label=".", title="Fin de phrase", color="#ff6666", shape="dot", size=25)

    poids_sortants = defaultdict(int)
    for s, t, w in transitions:
        if (s in mots_valides or s in ids_point) and (t in mots_valides or t in ids_point):
            poids_sortants[s] += w

    for s, t, w in transitions:
        if (s in mots_valides or s in ids_point) and (t in mots_valides or t in ids_point):
            proba = w / poids_sortants[s] if poids_sortants[s] else 0
            label = f"{proba:.2f}"
            net.add_edge(s, t, label=label, title=f"Poids: {w}, Proba: {label}", arrows="to")

    phrases = phrases_utiles_depuis_base()
    for i, phrase in enumerate(phrases):
        mots = phrase.strip().split()
        if len(mots) >= 2:
            dernier = mots[-1]
            mot_id = get_mot_id(dernier)
            if mot_id and mot_id in mots_valides:
                id_point = ids_point[i % len(ids_point)]
                net.add_edge(mot_id, id_point, label="1.00", title="Fin de phrase", arrows="to")

    print("\n Phrases générées automatiquement :\n")
    phrases_generees = []
    for _ in range(NB_PHRASES):
        phrase = generer_phrase_depuis_graphe(dict_mots, transitions, mots_sources, ids_point, mots_valides)
        phrases_generees.append(phrase)
        print("•", phrase)

    with open("phrases_generees.txt", "w", encoding="utf-8") as f:
        for p in phrases_generees:
            f.write(p + "\n")

    print("\n Les phrases ont été enregistrées dans 'phrases_generees.txt'")

    output_file = "graphe_interactif.html"
    net.write_html(output_file, notebook=False, open_browser=False)
    print(f"\n Graphe interactif généré → {output_file}")
    webbrowser.open('file://' + os.path.realpath(output_file))

if __name__ == "__main__":
    export_en_html()
