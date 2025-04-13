# creer_db.py
import sqlite3
import os

import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "..", "db", "phrases.db")

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    content TEXT,
    source TEXT,
    url TEXT UNIQUE
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS phrases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER,
    text TEXT NOT NULL,
    FOREIGN KEY(article_id) REFERENCES articles(id)
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS mots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mot TEXT UNIQUE,
    est_fin_phrase BOOLEAN DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS transitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mot_source_id INTEGER,
    mot_cible_id INTEGER,
    poids INTEGER DEFAULT 1,
    FOREIGN KEY (mot_source_id) REFERENCES mots(id),
    FOREIGN KEY (mot_cible_id) REFERENCES mots(id),
    UNIQUE (mot_source_id, mot_cible_id)
)
""")

conn.commit()
conn.close()
print(f" Base de données créée dans : {DB_PATH}")
