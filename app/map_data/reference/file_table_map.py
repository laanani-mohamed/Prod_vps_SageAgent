import os

# Mapping Fichier → Table   
FILE_TABLE_MAP = {
    'F_COMPTET.txt':       'F_COMPTET',
    'F_COLLABORATEUR.txt': 'F_COLLABORATEUR',
    'F_FAMILLE.txt':       'F_FAMILLE',
    'F_ARTICLE.txt':       'F_ARTICLE',
    'F_ARTSTOCK.txt':      'F_ARTSTOCK',
    'F_LOTSERIE.txt':      'F_LOTSERIE',
    'P_UNITE.txt':         'P_UNITE',
    'F_DOCENTETE.txt':     'F_DOCENTETE',
    'F_DOCLIGNE.txt':      'F_DOCLIGNE',
    'F_REGLECH.txt':       'F_REGLECH',
    'F_DEPOT.txt':         'F_DEPOT'
}

# Ordre strict d'insertion pour respecter les Clés Étrangères (Parents avant Enfants)
INSERTION_ORDER = [
    'P_UNITE', 'F_COLLABORATEUR', 'F_COMPTET', 'F_DEPOT',
    'F_FAMILLE', 'F_ARTICLE', 'F_ARTSTOCK', 'F_LOTSERIE',
    'F_DOCENTETE', 'F_DOCLIGNE', 'F_REGLECH'
]
