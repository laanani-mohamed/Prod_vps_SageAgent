-- Structure d'un schéma client : les 11 tables Sage chargées par l'ETL.
-- Le fichier ne nomme aucun schéma : les tables sont créées dans le search_path de la session.
--
-- Exécution :
--   * Dashboard Ops → Onboarding → « Créer le schéma d'un client »
--     (services/onboarding.py : CREATE SCHEMA + SET LOCAL search_path + ce fichier, en une transaction)
--   * En ligne de commande (une seule transaction, arrêt à la première erreur) :
--       psql -1 -v ON_ERROR_STOP=1 -c 'CREATE SCHEMA "nouveau_client"' \
--            -c 'SET search_path TO "nouveau_client"' -f create_client_schema.sql
--
-- Différences avec le script d'origine (schéma public) :
--   - VARCHAR d'au moins 50 caractères (69 conservés), pour ne pas rejeter une valeur Sage plus longue
--   - F_DOCENTETE.DO_Escompte et F_ARTSTOCK.AS_MontSto (attendues par l'ETL, map_data/reference/columns_order_number.py)
--   - clé de F_DOCENTETE = (DO_Domaine, DO_Type, DO_Piece), et clés étrangères de F_DOCLIGNE / F_REGLECH alignées
--   - index idx_artstock_ar_ref et idx_docligne_ar_ref_domaine_date

--------- Creation des tables ---------
CREATE TABLE F_COMPTET (
    CT_Num VARCHAR(50),
    CT_Intitule VARCHAR(69),
    CT_Type INTEGER,
    CG_NumPrinc VARCHAR(50),
    CT_Qualite VARCHAR(50),
    CT_Contact VARCHAR(50),
    CT_Adresse VARCHAR(50),
    CT_Complement VARCHAR(50),
    CT_Ville VARCHAR(50),
    CT_CodeRegion VARCHAR(50),
    CT_Identifiant VARCHAR(50),
    CT_Telephone VARCHAR(50),
    CT_Telecopie VARCHAR(50),
    CT_Email VARCHAR(69),
    CT_Site VARCHAR(69),
    CO_No BIGINT,
    CBCREATION DATE,
    CT_Sommeil INTEGER
);

CREATE TABLE F_COLLABORATEUR (
    CO_No BIGINT,
    CO_Nom VARCHAR(50),
    CO_Prenom VARCHAR(50),
    CO_Fonction VARCHAR(50),
    CO_Vendeur INTEGER,
    CO_Acheteur INTEGER,
    CO_Telephone VARCHAR(50),
    CO_Telecopie VARCHAR(50),
    CO_Email VARCHAR(69),
    CO_Matricule VARCHAR(50)
);

CREATE TABLE F_FAMILLE (
    FA_CodeFamille VARCHAR(50),
    FA_Type INTEGER,
    FA_Intitule VARCHAR(69),
    FA_UniteVen INTEGER,
    FA_SuiviStock INTEGER,
    FA_Central VARCHAR(50)
);

CREATE TABLE F_ARTICLE (
    AR_Ref VARCHAR(50),
    AR_Design VARCHAR(69),
    FA_CodeFamille VARCHAR(50),
    AR_UniteVen INTEGER,
    AR_PrixAch DOUBLE PRECISION,
    AR_PrixVen DOUBLE PRECISION,
    AR_PrixTTC INTEGER,
    AR_SuiviStock INTEGER,
    AR_CodeBarre VARCHAR(50),
    AR_PUNet DOUBLE PRECISION,
    AR_CoutStd DOUBLE PRECISION,
    AR_Type INTEGER,
    AR_Nature INTEGER,
    AR_SOMMEIL INTEGER
);

CREATE TABLE F_ARTSTOCK (
    AR_ref VARCHAR(50),
    as_qtesto DOUBLE PRECISION,
    DE_NO INTEGER,
    AS_MontSto DOUBLE PRECISION
);

CREATE TABLE F_LOTSERIE (
    AR_Ref VARCHAR(50),
    LS_NoSerie VARCHAR(50),
    LS_Peremption DATE,
    LS_Qte DOUBLE PRECISION,
    LS_LotEpuise INTEGER,
    LS_QteRestant DOUBLE PRECISION,
    DE_NO INTEGER
);

CREATE TABLE P_UNITE (
    U_Intitule VARCHAR(50),
    cbIndice INTEGER
);

CREATE TABLE F_DOCENTETE (
    DO_Domaine INTEGER,
    DO_Piece VARCHAR(50),
    DO_Date timestamp,
    DO_Ref VARCHAR(50),
    DO_Tiers VARCHAR(50),
    CO_No BIGINT,
    DO_TotalHT DOUBLE PRECISION,
    DO_TotalHTNet DOUBLE PRECISION,
    DO_TotalTTC DOUBLE PRECISION,
    DO_MontantRegle DOUBLE PRECISION,
    DO_Escompte INTEGER,
    DO_Type INTEGER
);

CREATE TABLE F_DOCLIGNE (
    DO_Domaine INTEGER,
    DO_Type INTEGER,
    CT_Num VARCHAR(50),
    DO_Piece VARCHAR(50),
    DL_PieceBC VARCHAR(50),
    DL_PieceBL VARCHAR(50),
    DO_Date DATE,
    DL_DateBC DATE,
    DL_DateBL DATE,
    DL_Ligne BIGINT,
    DO_Ref VARCHAR(50),
    AR_Ref VARCHAR(50),
    DL_Design VARCHAR(69),
    DL_Qte DOUBLE PRECISION,
    DL_QteBC DOUBLE PRECISION,
    DL_QteBL DOUBLE PRECISION,
    DL_PrixUnitaire DOUBLE PRECISION,
    CO_No BIGINT,
    DL_PrixRU DOUBLE PRECISION,
    DL_CMUP DOUBLE PRECISION,
    DL_PUTTC DOUBLE PRECISION,
    DL_No BIGINT,
    DL_Valorise INTEGER,
    DL_NonLivre INTEGER,
    DL_MontantHT DOUBLE PRECISION,
    DL_MontantTTC DOUBLE PRECISION,
    PF_Num VARCHAR(50),
    DL_DateDE DATE,
    DL_QteDE DOUBLE PRECISION,
    DL_MontantHTNet DOUBLE PRECISION,
    DL_MontantTTCNet DOUBLE PRECISION
);

CREATE TABLE F_REGLECH (
    RG_No BIGINT,
    DR_No BIGINT,
    DO_Domaine INTEGER,
    DO_Type INTEGER,
    DO_Piece VARCHAR(50),
    RC_Montant DOUBLE PRECISION,
    RG_TypeReg INTEGER
);

CREATE TABLE F_DEPOT (
    DE_NO INTEGER,
    DE_Intitule VARCHAR(50)
);

--------- PRIMARY KEYS ---------
ALTER TABLE F_COMPTET ADD PRIMARY KEY (CT_Num);
ALTER TABLE F_COLLABORATEUR ADD PRIMARY KEY (CO_No);
ALTER TABLE F_FAMILLE ADD PRIMARY KEY (FA_CodeFamille);
ALTER TABLE F_ARTICLE ADD PRIMARY KEY (AR_Ref);
ALTER TABLE P_UNITE ADD PRIMARY KEY (cbIndice);
ALTER TABLE F_DEPOT ADD PRIMARY KEY (DE_NO);
ALTER TABLE F_DOCENTETE ADD PRIMARY KEY (DO_Domaine, DO_Type, DO_Piece);

--------- FOREIGN KEYS ---------
ALTER TABLE F_COMPTET ADD CONSTRAINT fk_comptet_collab FOREIGN KEY (CO_No) REFERENCES F_COLLABORATEUR(CO_No);

ALTER TABLE F_FAMILLE ADD CONSTRAINT fk_famille_unite FOREIGN KEY (FA_UniteVen) REFERENCES P_UNITE(cbIndice);

ALTER TABLE F_ARTICLE ADD CONSTRAINT fk_article_famille FOREIGN KEY (FA_CodeFamille) REFERENCES F_FAMILLE(FA_CodeFamille);
ALTER TABLE F_ARTICLE ADD CONSTRAINT fk_article_unite FOREIGN KEY (AR_UniteVen) REFERENCES P_UNITE(cbIndice);

ALTER TABLE F_ARTSTOCK ADD CONSTRAINT fk_artstock_article FOREIGN KEY (AR_ref) REFERENCES F_ARTICLE(AR_Ref);
ALTER TABLE F_ARTSTOCK ADD CONSTRAINT fk_artstock_depot FOREIGN KEY (DE_NO) REFERENCES F_DEPOT(DE_NO);

ALTER TABLE F_LOTSERIE ADD CONSTRAINT fk_lotserie_article FOREIGN KEY (AR_Ref) REFERENCES F_ARTICLE(AR_Ref);
ALTER TABLE F_LOTSERIE ADD CONSTRAINT fk_lotserie_depot FOREIGN KEY (DE_NO) REFERENCES F_DEPOT(DE_NO);

ALTER TABLE F_DOCENTETE ADD CONSTRAINT fk_docentete_tiers FOREIGN KEY (DO_Tiers) REFERENCES F_COMPTET(CT_Num);
ALTER TABLE F_DOCENTETE ADD CONSTRAINT fk_docentete_collab FOREIGN KEY (CO_No) REFERENCES F_COLLABORATEUR(CO_No);

ALTER TABLE F_DOCLIGNE ADD CONSTRAINT fk_docligne_tiers FOREIGN KEY (CT_Num) REFERENCES F_COMPTET(CT_Num);
ALTER TABLE F_DOCLIGNE ADD CONSTRAINT fk_docligne_collab FOREIGN KEY (CO_No) REFERENCES F_COLLABORATEUR(CO_No);
ALTER TABLE F_DOCLIGNE ADD CONSTRAINT fk_docligne_docentete
    FOREIGN KEY (DO_Domaine, DO_Type, DO_Piece) REFERENCES F_DOCENTETE(DO_Domaine, DO_Type, DO_Piece);
ALTER TABLE F_DOCLIGNE ADD CONSTRAINT fk_docligne_article FOREIGN KEY (AR_Ref) REFERENCES F_ARTICLE(AR_Ref);

ALTER TABLE F_REGLECH ADD CONSTRAINT fk_reglech_piece
    FOREIGN KEY (DO_Domaine, DO_Type, DO_Piece) REFERENCES F_DOCENTETE(DO_Domaine, DO_Type, DO_Piece);

--------- INDEX ---------
CREATE INDEX idx_artstock_ar_ref ON F_ARTSTOCK (AR_ref);
CREATE INDEX idx_docligne_ar_ref_domaine_date ON F_DOCLIGNE (AR_Ref, DO_Domaine, DO_Date DESC);
