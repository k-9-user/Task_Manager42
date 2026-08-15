# 🅲️ Fiche de travail — Personne C (API publique, recherche, fichiers, export)

> Se référer en permanence à `00-contrat-commun.md` pour les routes API, le schéma DB et les variables d'env.

## Modules dont tu es responsable
- ✅ Web — API publique (clé sécurisée, rate limiting, doc, 5 endpoints) — Major
- ✅ Web — Recherche avancée — Minor
- ✅ Web — File upload — Minor
- ✅ Data & Analytics — Export/import — Minor

## Structure de fichiers à créer

```
backend/app/models/attachment.py
backend/app/models/api_key.py
backend/app/routers/public_api.py
backend/app/routers/search.py
backend/app/routers/attachments.py
backend/app/routers/export_import.py
backend/app/auth/api_key_auth.py
backend/app/utils/rate_limiter.py
backend/tests/test_public_api.py
```

## Semaine 1 — Modèles + attente

- [ ] `backend/app/models/attachment.py`, `api_key.py` (cf contrat commun section 1)
- [ ] Étudier une lib de rate limiting (ex: `slowapi` pour FastAPI)
- [ ] Attendre que A ait livré `database.py`, et que B ait livré `task.py`/`project.py`

## Semaine 2 — API publique

- [ ] `backend/app/auth/api_key_auth.py` : génération + vérification de clé API (header `X-API-Key`)
- [ ] `backend/app/routers/public_api.py` :
  - `GET/POST /api/v1/public/tasks`
  - `PUT/DELETE /api/v1/public/tasks/{id}`
  - `GET /api/v1/public/projects`
- [ ] `backend/app/utils/rate_limiter.py` : limite de requêtes par clé API
- [ ] Documentation Swagger (générée automatiquement par FastAPI, vérifier qu'elle est complète)

## Semaine 3 — Recherche + fichiers

- [ ] `backend/app/routers/search.py` : `GET /api/search/tasks` avec filtres (statut, projet) + pagination
- [ ] `backend/app/routers/attachments.py` :
  - `POST /api/tasks/{id}/attachments` (upload multipart, validation type/taille)
  - `DELETE /api/attachments/{id}`
- [ ] Stockage fichiers dans `backend/app/static/uploads/` (cf `UPLOAD_DIR` du `.env`)

## Semaine 4 — Export/Import

- [ ] `backend/app/routers/export_import.py` :
  - `GET /api/export?format=json|csv`
  - `POST /api/import` (upload + validation + insertion en base)
- [ ] `backend/tests/test_public_api.py` (tester la clé API, le rate limiting)
- [ ] Tests de la recherche et de l'upload de fichiers

## Checklist de fin

- [ ] Un développeur externe peut utiliser l'API publique avec une clé API et respecte le rate limiting
- [ ] La doc Swagger est claire et à jour (`/docs`)
- [ ] La recherche de tâches fonctionne avec filtres + pagination
- [ ] Un fichier peut être uploadé sur une tâche, prévisualisé/téléchargé, supprimé
- [ ] Export JSON/CSV et import fonctionnels avec validation des données
- [ ] Tu peux expliquer comment le rate limiting et l'auth par clé API fonctionnent

## Dépendances envers les autres
- Besoin de `database.py` de A (fin semaine 1)
- Besoin de `task.py`/`project.py` de B (semaine 2)

## Ce que les autres attendent de toi
- **D attend `search.py` et `attachments.py`** en semaine 3 pour ses pages Search et pièces jointes
