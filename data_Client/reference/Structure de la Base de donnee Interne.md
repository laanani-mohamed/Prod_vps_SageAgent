## TABLES

| N° | TABLE | DESCRIPTION |
|---|---|---|
| 1 | F_COMPTET | Comptes Tiers: Clients et Fournisseur |
| 2 | F_COLLABORATEUR | Fichier des collaborateurs. |
| 3 | F_FAMILLE | Fichier principal des familles |
| 4 | F_ARTICLE | Fichier principal des articles. |
| 5 | F_ARTSTOCK | Fichier principale de stock article |
| 6 | F_LOTSERIE | fichier des articles Lots serie |
| 7 | P_UNITE | Unités de vente. Contient 30 unités. |
| 8 | F_DOCENTETE | Entêtes de document |
| 9 | F_DOCLIGNE | Lignes de document |
| 10 | F_REGLECH | Fichier des liens entre règlements et échéances. |
| 11 | F_DEPOT | Liste des depots |

## 1- F_COMPTET

| Nom | Signification | Type de données | Domaine de validité | LIAISON |
|---|---|---|---|---|
| CT_Num | Numéro compte tiers | Chaîne Alphanumérique Maj. | 17 caractères max. |
| CT_Intitule | Intitulé | Chaîne de caractères | 69 caractères max. |
| CT_Type | Type | Numérique : Entier | 0 à 3  0 = Client  1 = Fournisseur  2 = Salarié 3 = Autre |
| CG_NumPrinc | N° compte général principal | Chaîne Alphanumérique Maj. | 13 caractères max. |
| CT_Qualite | Qualité | Chaîne de caractères | 17 caractères max. |
| CT_Contact | Contact | Chaîne de caractères | 35 caractères max. |
| CT_Adresse | Adresse | Chaîne de caractères | 35 caractères max. |
| CT_Complement | Complément adresse | Chaîne de caractères | 35 caractères max. |
| CT_Ville | Ville | Chaîne de caractères | 35 caractères max. |
| CT_CodeRegion | Code région | Chaîne de caractères | 25 caractères max. |
| CT_Identifiant | Identifiant ICE | Chaîne de caractères | 25 caractères max. |
| CT_Telephone | Téléphone | Chaîne de caractères | 21 caractères max. |
| CT_Telecopie | Télécopie | Chaîne de caractères | 21 caractères max. |
| CT_Email | Adresse Email | Chaîne de caractères | 69 caractères max. |
| CT_Site | Nom du Site | Chaîne de caractères | 69 caractères max. |
| CO_No | Collaborateur | Numérique : Entier long |  | F_COLLABORATEUR |
| CBCREATION | Date de creation | Date |
| CT_Sommeil | En sommeil | Numérique : Entier |

## 2- F_COLLABORATEUR

| Nom | Signification | Type de données | Domaine de validité |
|---|---|---|---|
| CO_No | Numéro interne | Numérique : Entier long | Compteur |
| CO_Nom | Nom | Chaîne de caractères | 35 caractères max. |
| CO_Prenom | Prénom | Chaîne de caractères | 35 caractères max. |
| CO_Fonction | Fonction | Chaîne de caractères | 35 caractères max. |
| CO_Vendeur | Vendeur | Numérique : Entier | 0 à 1  0 = Non  1 = Oui |
| CO_Acheteur | Acheteur | Numérique : Entier | 0 à 1  0 = Non  1 = Oui |
| CO_Telephone | Numéro de téléphone | Chaîne de caractères | 21 caractères max. |
| CO_Telecopie | Numéro de télécopie | Chaîne de caractères | 21 caractères max. |
| CO_Email | Adresse Email | Chaîne de caractères | 69 caractères max. |
| CO_Matricule | Matricule | Chaîne Alphanumérique Maj. | 10 caractères max. |

## 3- F_FAMILLE

| Nom | Signification | Type de données | Domaine de validité | LIAISON |
|---|---|---|---|---|
| FA_CodeFamille | Code famille | Chaîne Alphanumérique Maj. | 10 caractères max. |
| FA_Type | Type (Détail, Total, Central) | Numérique : Entier | 0 à 2  0 = Détail  1 = Total  2 = Centralisateur |
| FA_Intitule | Intitulé de la famille | Chaîne de caractères | 69 caractères max. |
| FA_UniteVen | Unité de vente | Numérique : Entier | 1 à 30 (valeur indice Boite déroulante) | F_UNITE |
| FA_SuiviStock | Suivi en stock (oui, non) | Numérique : Entier | 0 à 5  0 = Aucun  1 = Sérialisé  2 = CMUP  3 = FIFO  4 = LIFO  *5 = Par lot |
| FA_Central | Code de famille centralisatrice | Chaîne Alphanumérique Maj. | 10 caractères max. |

## 4- F_ARTICLE

| Nom | Signification | Type de données | Domaine de validité | LIAISON |
|---|---|---|---|---|
| AR_Ref | Référence de l’article | Chaîne Alphanumérique Maj. | 18 caractères |
| AR_Design | Désignation de l’article | Chaîne Alphanumérique | 69 caractères |
| FA_CodeFamille | Code de la famille à laquelle appartient la famille | Chaîne Alphanumérique Maj. | 10 caractères | F_FAMILLE |
| AR_UniteVen | Unité de vente = indice Boite déroulante | Numérique : Entier | 1 à 30 | F_UNITE |
| AR_PrixAch | Prix d’achat | Numérique : Réel double |
| AR_PrixVen | Prix de vente | Numérique : Réel double |
| AR_PrixTTC | Prix HT ou TTC | Numérique : Entier | 0 à 1  0 = HT  1 = TTC |
| AR_SuiviStock | Type de suivi du stock | Numérique : Entier | à 5  0 = Aucun  1 = Sérialisé  2 = CMUP  3 = FIFO  4 = LIFO  5 = Par lot |
| AR_CodeBarre | Code Barre | Chaîne alphanumérique | 18 caractères max. |
| AR_PUNet | Dernier prix d’achat | Numérique : Réel double |
| AR_CoutStd | Coût standard | Numérique : Réel double |
| AR_Type | Type d’article | Numérique : Entier | 0 à 3  0 = Standard  1 = Gamme  2 = Ressource prestation  3 = Ressource location |
| AR_Nature | Nature | Numérique : Entier | 0 à 3  0 = Composant  1 = Pièce détachée  2 = Produit fini  3 = Produit semi-fini |
| AR_SOMMEIL | SOMMEIL | Numérique : Entier | 0=Actif 1=En Sommeil |

## 5-F_ARTSTOCK

| Nom | Signification | Type de données | Domaine de validité | LIAISON |
|---|---|---|---|---|
| AR_ref | Référence de l’article | Chaîne Alphanumérique Maj. | 18 caractères |  F_ARTICLE |
| as_qtesto | Qte en stock | Numérique : Réel double |
| DE_NO | Numero de depot | Numérique : Entier |  | F_depot |

## 6-F_LOTSERIE

| Nom | Signification | Type de données | Domaine de validité | LIAISON |
|---|---|---|---|---|
| AR_Ref | Référence de l’article | Chaîne Alphanumérique Maj. | 18 caractères | F_ARTICLE |
| LS_NoSerie | Numéro de série/Lot de l’article si le suivi de stock l’article est sérialisé ou par lot | Chaîne de caractères | 30 caractères max. |
| LS_Peremption | Date de péremption | Date |
| LS_Qte | Qte en stock | Numérique : Réel double |
| LS_LotEpuise | Lot epuise (Oui Ou Non) | Numérique : Entier |
| LS_QteRestant | Qte en stock | Numérique : Réel double |
| DE_NO | Numero de depot | Numérique : Entier |  | F_DEPOT |

## 7-P_UNITE

| Nom | Signification | Type de données | Domaine de validité | LIAISON |
|---|---|---|---|---|
| U_Intitule | Intitulés des Unités d’achat et de vente | Chaîne de caractères | 21 caractères max. |
| cbIndice | Indice | Numérique : Entier | 1 à 30 |

## 8- F_DOCENTETE

| Nom | Signification | Type de données | Domaine de validité | LIAISON |
|---|---|---|---|---|
| DO_Domaine | Domaine du document | Numérique : Entie | 0 à 4  0 = Vente  1 = Achat  2 = Stock  3 = Ticket  4 = Document interne |
| DO_Type | Type de document | Numérique : Entier | Vente 0 à 8  0 = Devis  1 = Bon de commande  2 = Préparation de livraison  3 = Bon de livraison  4 = Bon de retour  5 = Bon d’avoir  6 = Facture  7 = Facture comptabilisée  8 = Archive   Achat de 10 à 18  10 = Demande d’achat  11 = Préparation de commande 12 = Bon de Commande  13 = Bon de livraison  14 = Bon de retour  15 = Bon d’avoir  16 = Facture  17 = Facture comptabilisée  18 = Archive  |
| DO_Piece | Numéro pièce interne | Chaîne Alphanumérique Maj. | 13 caractères max |
| DO_Date | Date du document | Date |
| DO_Ref | Numéro de pièce externe | Chaîne de caractères | 17 caractères max. |
| DO_Tiers | Client, fournisseur ou stock Pour les Clients, Fournisseurs : Code client ou fournisseur Pour un dépôt : N° interne du dépôt | Chaîne Alphanumérique Maj. | 17 caractères max. | F_COMPTET |
| CO_No | Représentant / Acheteur | Numérique : Entier long |  | F_COLLABORATEUR |
| DO_TotalHT | Total HT | Numérique : Réel double |
| DO_TotalHTNet | Total HT Net | Numérique : Réel double |
| DO_TotalTTC | Total TTC | Numérique : Réel double |
| DO_MontantRegle | Montant réglé | Numérique : Réel double |

## 9- F_DOCLIGNE

| Nom | Signification | Type de données | Domaine de validité | LIAISON |
|---|---|---|---|---|
| DO_Domaine | Domaine du document | Numérique : Entier | 0 à 4  0 = Vente  1 = Achat  2 = Stock  3 = Ticket  4 = Document intern |
| DO_Type | Type de document | Numérique : Entier | Vente 0 à 8  0 = Devis  1 = Bon de commande  2 = Préparation de livraison  3 = Bon de livraison  4 = Bon de retour  5 = Bon d’avoir  6 = Facture  7 = Facture comptabilisée  8 = Archive   Achat de 10 à 18  10 = Demande d’achat  11 = Préparation de commande 12 = Bon de Commande  13 = Bon de livraison  14 = Bon de retour  15 = Bon d’avoir  16 = Facture  17 = Facture comptabilisée  18 = Archive  |
| CT_Num | Client, fournisseur ou stock  Pour les Clients, Fournisseurs : Code client ou fournisseur  Pour un dépôt : N° interne du dépôt | Chaîne Alphanumérique Maj | 17 caractères max. | F_COMPTET |
| DO_Piece | Numéro pièce interne | Chaîne Alphanumérique Maj. | 13 caractères max. |
| DL_PieceBC | N° de pièce du bon de commande | Chaîne Alphanumérique Maj. | 13 caractères max. |
| DL_PieceBL | Numéro de pièce du bon de livraison | Chaîne Alphanumérique Maj. | 13 caractères max. |
| DO_Date | Date du document | Date |
| DL_DateBC | Date du bon de commande | Date |
| DL_DateBL | Date du bon de livraison | Date |
| DL_Ligne | Numéro d’ordonnancement de la ligne dans le document | Numérique : Entier long |
| DO_Ref | N° de pièce externe | Chaîne Alphanumérique Maj. | 17 caractères max. |
| AR_Ref | Référence article | Chaîne Alphanumérique Maj. | 18 caractères max. |
| DL_Design | Désignation de la ligne | Chaîne de caractères | 69 caractères max. |
| DL_Qte | Quantités | Numérique : Réel double |
| DL_QteBC | Quantités commandées | Numérique : Réel double |
| DL_QteBL | Quantités livrées ou facturées | Numérique : Réel double |
| DL_PrixUnitaire | Prix unitaire HT | Numérique : Réel double |
| CO_No | Représentant / Acheteur | Numérique : Entier long |  | F_COLLABORATEUR |
| DL_PrixRU | Prix de revient unitaire | Numérique : Réel double |
| DL_CMUP | Coût moyen unitaire pondéré | Numérique : Réel double |
| DL_PUTTC | Prix unitaire TTC | Numérique : Réel double |
| DL_No | Numéro interne | Numérique : Entier long | Compteur |
| DL_Valorise | Valorisation de la ligne | Numérique : Entier | 0 à 1  0 = Ligne non valorisée  1 = Ligne valorisée |
| DL_NonLivre | Article Non Livré | Numérique : Entie | 0 à 1  0 = Non  1 = Oui |
| DL_MontantHT | Montant Hors Taxe | Numérique : Réel double |
| DL_MontantTTC | Montant TTC | Numérique : Réel double |
| PF_Num | Numéro projet affaire | Chaîne Alphanumérique Maj. | 9 caractères max. |
| DL_DateDE | Date du devis | Date |
| DL_QteDE | Quantité du devis | Numérique : Réel double |
| DL_MontantHT | Montant HT net de la ligne | Numérique : Réel double |
| DL_MontantTTC | Montant TTC de la ligne | Numérique : Réel double |

## 10- F_REGLECH

| Nom | Signification | Type de données | Domaine de validité | LIAISON |
|---|---|---|---|---|
| RG_No | Numéro interne du règlement | Numérique : Entier long |
| DR_No | Numéro interne de l’échéance | Numérique : Entier long |
| DO_Domaine | Domaine du document | Numérique : Entier | 0, 1 ou 3  0 = Vente  1 = Achat  3 = Ticket |
| DO_Type | Type de document | Numérique : Entier | 0 à 47  Vente 0 à 8  0 = Devis  1 = Bon de commande  2 = Préparation de livraison  3 = Bon de livraison  4 = Bon de retour  5 = Bon d’avoir  6 = Facture  7 = Facture comptabilisée  8 = Archive   Achat de 10 à 18  10 = Demande d’achat  11 = Préparation de Commande  12 = Bon de Commande  13 = Bon de livraison  14 = Bon de retour  15 = Bon d’avoir  16 = Facture  17 = Facture comptabilisée  18 = Archive   Ticket  30 = Ticket |
| DO_Piece | Numéro de pièce interne | Chaîne Alphanumérique Maj. | 13 caractères max. | F_DOCENTET |
| RC_Montant | Montant imputé sur l’échéance | Numérique : Réel double |
| RG_TypeReg | Type de règlement | Numérique : Entier | 0 à 8  0 = Règlement  1 = Acompte  2 = Fond de caisse  3 = Remise en banque  4 = Sortie de caisse  5 = Entrée en caisse  6 = Remise à 0  7 = Contrôle de caisse  8 = Bon d’achat |

## 11-F_DEPOT

| Nom | Signification | Type de données | Domaine de validité | LIAISON |
|---|---|---|---|---|
| DE_NO | Numero de depot | Numérique : Entier |
| DE_Intitule | Intitule depot | Chaîne Alphanumérique | 17 caractères max. |

