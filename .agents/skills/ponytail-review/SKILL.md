---
name: ponytail-review
description: >-
  Audit le code ou le diff actuel pour détecter l'over-engineering, la duplication,
  et les opportunités de suppression. Utilisez ce skill quand vous voulez un regard critique
  sur du code existant.
---

# 🐴 Ponytail Review — Audit d'Over-Engineering

Analyse le code cible avec l'œil du senior dev paresseux.

## Processus d'audit

1. **Lire** le code / diff en entier avant tout jugement
2. **Identifier** chaque barreau de l'escalier qui aurait pu s'appliquer :
   - Ce code devait-il exister ? (YAGNI)
   - Une version existait déjà ailleurs dans le codebase ?
   - La stdlib ou la plateforme native couvrait ça ?
   - Une dépendance installée le faisait déjà ?
   - Pouvait-on l'écrire en une ligne ?
3. **Lister** les opportunités concrètes de suppression ou simplification
4. **Proposer** le diff minimal qui garde la même fonctionnalité

## Format de sortie

```
## Verdict
[OVER-ENGINEERED | MINIMAL | MIXED]

## Opportunités de simplification
- [ligne X-Y] : description du problème → solution proposée

## Diff suggéré (si pertinent)
```diff
- code actuel
+ code simplifié
```

## Non-Négociables respectés ?
- [ ] Validation des frontières de confiance
- [ ] Protection contre la perte de données  
- [ ] Sécurité
- [ ] Gestion d'erreurs I/O
```
