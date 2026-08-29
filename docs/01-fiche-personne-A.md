# 🅰️ Fiche de travail — Personne A (Tech Lead + Auth/Sécurité)

> Se référer en permanence à `00-contrat-commun.md` pour les routes API, le schéma DB et les variables d'env.

## Modules dont tu es responsable
- ✅ User Management — Permissions avancées (CRUD users + rôles) — Major
- ✅ OAuth — Minor
- ✅ Health check — Minor
- ✅ HTTPS (exigence technique obligatoire)

## Structure de fichiers à créer

```
docker-compose.yml
backend/Dockerfile
frontend/Dockerfile
.env.example
backend/app/config.py
backend/app/database.py
backend/app/models/user.py
backend/alembic/  (+ alembic.ini)
backend/app/auth/security.py
backend/app/auth/oauth.py
backend/app/auth/dependencies.py
backend/app/schemas/user.py
backend/app/routers/auth.py
backend/app/routers/users.py
backend/app/routers/health.py
backend/app/utils/validators.py
backend/tests/test_auth.py
```

## Semaine 1 — Setup (bloquant pour tout le monde, priorité absolue)

- [x] Créer `docker-compose.yml` (services : backend, frontend, db, nginx)
- [x] Créer `backend/Dockerfile`, `frontend/Dockerfile`
- [x] Créer `.env.example` (cf contrat commun section 3)
- [x] Créer `backend/app/config.py`, `backend/app/database.py`
- [ ] Créer TOUS les modèles de base même si B/C les utilisent : `user.py` (le tien), et prévoir avec eux `project.py`, `task.py` (peuvent être créés par B directement, à coordonner)
- [x] Initialiser Alembic + première migration
- [ ] **Prévenir l'équipe dès que `docker compose up` fonctionne**

## Semaine 2 — Auth email/password + permissions

- [x] `backend/app/auth/security.py` : hash bcrypt/argon2, JWT
- [x] `backend/app/schemas/user.py` : register, login, response
- [x] `backend/app/routers/auth.py` : `POST /api/auth/register`, `POST /api/auth/login`
- [x] `backend/app/auth/dependencies.py` : `get_current_user()`, `require_admin()`
- [x] `GET /api/users/me`, `PUT /api/users/me`
- [ ] **Prévenir D dès que login/register est testable**

## Semaine 3 — OAuth + rôles admin

- [x] `backend/app/auth/oauth.py` : config Google OAuth
- [x] `GET /api/auth/oauth/google`
- [x] `GET /api/users` (admin, liste paginée), `PUT /api/users/{id}/role`, `DELETE /api/users/{id}`
- [x] `backend/app/utils/validators.py` : validation stricte des inputs
- [x] Vérifier que seul un admin peut changer un rôle ou supprimer un user

## Semaine 3-4 — HTTPS, Health check, sécurité finale

- [ ] Config Nginx en reverse proxy HTTPS (certificat auto-signé en local)
- [x] `backend/app/routers/health.py` : `GET /health`
- [x] Revue sécurité : CORS
- [ ] Rate limiting basique sur `/auth`
- [x] `backend/tests/test_auth.py`
- [ ] Aide à l'intégration finale

## Checklist de fin

- [x] Inscription/connexion email+password fonctionnelle
- [ ] Connexion Google OAuth fonctionnelle
- [x] Un admin peut voir/gérer tous les users, changer les rôles
- [x] Un user normal ne peut PAS accéder aux routes admin (tester le refus)
- [x] `/health` répond correctement
- [ ] HTTPS partout, zéro warning console
- [ ] Tu peux expliquer JWT, hash, et le système de rôles en détail

## Dépendances envers les autres
- Rien — tu es le point de départ

## Ce que les autres attendent de toi
- **Tous attendent `docker compose up` + `database.py` + `user.py`** fin semaine 1
- **D attend l'auth fonctionnelle** dès semaine 2
