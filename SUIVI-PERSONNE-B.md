# 🅱️ Suivi de travail — Personne B

> Feuille de route vivante : à mettre à jour au fil de l'eau. Se référer à
> `00-contrat-commun.md` (source de vérité) et `02-fiche-personne-B.md` (planning)
> pour le détail complet.

## État d'avancement

| Fichier | Statut |
|---|---|
| `backend/app/models/project.py` | ✅ fait (déplacé de la racine `backend/`) |
| `backend/app/models/project_member.py` | ✅ fait (déplacé) |
| `backend/app/models/task.py` | ✅ fait (déplacé) |
| `backend/app/schemas/project.py` | ✅ fait |
| `backend/app/schemas/task.py` | ✅ fait |
| `backend/app/schemas/common.py` | ✅ fait (pas dans la fiche d'origine, ajouté pour l'enveloppe `{success, data}`) |
| `backend/app/routers/projects.py` | 🔄 en cours |
| `backend/app/routers/tasks.py` | ⬜ à faire (semaine 3) |
| `backend/app/routers/gdpr.py` | ⬜ à faire (semaine 4) |
| `backend/tests/test_projects.py` | ⬜ à faire |
| `backend/tests/test_tasks.py` | ⬜ à faire |
| Module bonus notifications | ⬜ à faire si temps (semaine 4) |

## 🚧 Bloquants — ce qui manque pour que ça tourne réellement

- `backend/app/database.py` (A) — `Base` + une dépendance `get_db()` (session SQLAlchemy). **Hypothèse** : j'assume qu'elle s'appellera `get_db` et vivra dans `app.database` — pas écrit noir sur blanc dans la fiche de A, à confirmer.
- `backend/app/models/user.py` (A) — modèle `User`.
- `backend/app/auth/dependencies.py` (A) — `get_current_user()`, `require_admin()` (confirmé dans sa fiche, semaine 2).
- Pas de `requirements.txt` / `pyproject.toml` pour l'instant → impossible d'installer/tester réellement en local (FastAPI, SQLAlchemy, Pydantic pas installés). **Hypothèse** : Pydantic v2 (`ConfigDict`, `from_attributes`) — à confirmer une fois le fichier de deps créé (par qui ? pas assigné explicitement, probablement A).
- `backend/app/main.py` : pas assigné explicitement dans aucune fiche (ni A ni B). C'est pourtant lui qui doit enregistrer un exception handler global pour que les erreurs FastAPI (`HTTPException`) sortent au format `{"success": false, "error": "..."}` du contrat, sinon elles sortiront au format par défaut `{"detail": "..."}`. **À soulever en sync d'équipe.**

## 📥 Ce que j'attends des autres

- **A, fin semaine 1** : `docker compose up`, `database.py`, `user.py`.
- **A, semaine 2** : `auth/dependencies.py` (`get_current_user`) pour protéger mes routes projects/tasks.
- **A / équipe** : qui code `app/main.py` et l'exception handler global ? (cf bloquant ci-dessus)
- **C** : rien de bloquant pour moi, mais mon `task.py` doit rester stable côté champs — elle y accroche `attachments`/recherche/export.
- **D** : attend `projects.py` + `tasks.py` testables semaine 2-3 → **à prévenir dès que `routers/projects.py` tourne contre une vraie DB**.

## ⚠️ Incohérences / décisions à valider en groupe

1. **`description` optionnelle ou non ?** Contrat : `POST /api/projects` et `POST /api/projects/{id}/tasks` listent `description` sans `?`, mais la colonne est nullable en DB. J'ai codé les schémas avec `description` optionnelle (cohérent DB). → si le groupe veut la rendre obligatoire, corriger le contrat + `schemas/project.py` + `schemas/task.py`.
2. **Sémantique des rôles projet (owner/editor/viewer) pas détaillée dans le contrat.** J'ai décidé (à valider) :
   - `owner` : tout (éditer/supprimer le projet, gérer les membres, gérer les tâches)
   - `editor` : gérer les tâches (créer/éditer/supprimer), PAS éditer le projet ni gérer les membres
   - `viewer` : lecture seule partout
   Seule certitude explicite de la fiche : "un viewer ne peut pas modifier une tâche". Le reste (editor peut-il gérer les membres ? éditer le nom du projet ?) est une hypothèse à confirmer.
3. **`GET /api/projects` renvoie quoi ?** J'ai supposé "les projets dont je suis membre" (via `project_members`), pas "tous les projets de la DB". Cohérent avec un outil collaboratif multi-tenant, mais pas écrit explicitement dans le contrat.
4. **Réponses `DELETE` (`{success}`)** : le contrat les écrit sans le wrapper `data` habituel. J'ai codé ces routes pour renvoyer littéralement `{"success": true}` (pas `{"success": true, "data": {...}}`) — à confirmer que c'est bien voulu et pas juste une notation raccourcie dans le tableau.
5. **Owner retiré des membres = projet orphelin ?** J'ai ajouté une règle : impossible de retirer le dernier `owner` d'un projet via `DELETE /api/projects/{id}/members/{user_id}`. Pas dans le contrat, ajouté par prudence — à discuter si on préfère l'autoriser (ex: transfert de propriété à prévoir alors).

## ✅ Tests à écrire — `test_projects.py`

- [ ] `POST /api/projects` : succès (201, owner = créateur, membership owner auto-créée)
- [ ] `POST /api/projects` : `name` manquant → 422
- [ ] `GET /api/projects` : ne renvoie que les projets où je suis membre
- [ ] `GET /api/projects/{id}` : succès, contient `project` + `members` + `tasks`
- [ ] `GET /api/projects/{id}` : projet où je ne suis pas membre → 404
- [ ] `GET /api/projects/{id}` : id inexistant → 404
- [ ] `PUT /api/projects/{id}` : owner → succès ; editor/viewer → 403
- [ ] `DELETE /api/projects/{id}` : owner → succès + cascade (members, tasks supprimés) ; editor/viewer → 403
- [ ] `POST /api/projects/{id}/members` : owner ajoute un membre → succès
- [ ] `POST /api/projects/{id}/members` : editor/viewer tente d'ajouter → 403
- [ ] `POST /api/projects/{id}/members` : `user_id` inexistant → 400
- [ ] `POST /api/projects/{id}/members` : membre déjà présent → 400 (contrainte unique)
- [ ] `DELETE /api/projects/{id}/members/{user_id}` : succès
- [ ] `DELETE /api/projects/{id}/members/{user_id}` : retirer le dernier owner → refusé

## ✅ Tests à écrire — `test_tasks.py` (semaine 3, à détailler à ce moment-là)

- [ ] Création tâche : owner/editor → succès, viewer → 403
- [ ] `GET /api/projects/{id}/tasks` : filtre `?status=`, pagination `?page=`
- [ ] `PUT /api/tasks/{id}` : changer statut/assignee, permissions par rôle
- [ ] `DELETE /api/tasks/{id}` : permissions par rôle
- [ ] Assigner une tâche à un user qui n'est pas membre du projet → comportement à définir (refuser ? autoriser ?)

## 🗒️ GDPR (semaine 4) — points à trancher avant de coder

- Contenu exact de `GET /api/gdpr/export` : à définir précisément (user info, projets possédés, memberships, tâches assignées ?). Le contrat dit juste "fichier JSON téléchargeable", pas de spec de contenu.
- `DELETE /api/gdpr/account` : cascade sur projects (si owner), project_members, tasks assignées (passer `assignee_id` à `null` plutôt que supprimer la tâche ?) — à vérifier avec le schéma de A.

## 📌 À évoquer au prochain sync (mardi/vendredi)

- Qui écrit `app/main.py` + l'exception handler global `{success:false, error:...}` ?
- Confirmer `get_db()` dans `app/database.py`.
- Trancher les points 1 à 5 de la section "Incohérences" ci-dessus.
