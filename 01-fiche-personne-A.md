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

- [ ] Créer `docker-compose.yml` (services : backend, frontend, db, nginx)
- [ ] Créer `backend/Dockerfile`, `frontend/Dockerfile`
- [ ] Créer `.env.example` (cf contrat commun section 3)
- [ ] Créer `backend/app/config.py`, `backend/app/database.py`
- [ ] Créer TOUS les modèles de base même si B/C les utilisent : `user.py` (le tien), et prévoir avec eux `project.py`, `task.py` (peuvent être créés par B directement, à coordonner)
- [ ] Initialiser Alembic + première migration
- [ ] **Prévenir l'équipe dès que `docker compose up` fonctionne**

## Semaine 2 — Auth email/password + permissions

- [ ] `backend/app/auth/security.py` : hash bcrypt/argon2, JWT
- [ ] `backend/app/schemas/user.py` : register, login, response
- [ ] `backend/app/routers/auth.py` : `POST /api/auth/register`, `POST /api/auth/login`
- [ ] `backend/app/auth/dependencies.py` : `get_current_user()`, `require_admin()`
- [ ] `GET /api/users/me`, `PUT /api/users/me`
- [ ] **Prévenir D dès que login/register est testable**

## Semaine 3 — OAuth + rôles admin

- [ ] `backend/app/auth/oauth.py` : config Google OAuth
- [ ] `GET /api/auth/oauth/google`
- [ ] `GET /api/users` (admin, liste paginée), `PUT /api/users/{id}/role`, `DELETE /api/users/{id}`
- [ ] `backend/app/utils/validators.py` : validation stricte des inputs
- [ ] Vérifier que seul un admin peut changer un rôle ou supprimer un user

## Semaine 3-4 — HTTPS, Health check, sécurité finale

- [ ] Config Nginx en reverse proxy HTTPS (certificat auto-signé en local)
- [ ] `backend/app/routers/health.py` : `GET /health`
- [ ] Revue sécurité : CORS, rate limiting basique sur `/auth`
- [ ] `backend/tests/test_auth.py`
- [ ] Aide à l'intégration finale

## Checklist de fin

- [ ] Inscription/connexion email+password fonctionnelle
- [ ] Connexion Google OAuth fonctionnelle
- [ ] Un admin peut voir/gérer tous les users, changer les rôles
- [ ] Un user normal ne peut PAS accéder aux routes admin (tester le refus)
- [ ] `/health` répond correctement
- [ ] HTTPS partout, zéro warning console
- [ ] Tu peux expliquer JWT, hash, et le système de rôles en détail

## Dépendances envers les autres
- Rien — tu es le point de départ

## Ce que les autres attendent de toi
- **Tous attendent `docker compose up` + `database.py` + `user.py`** fin semaine 1
- **D attend l'auth fonctionnelle** dès semaine 2
