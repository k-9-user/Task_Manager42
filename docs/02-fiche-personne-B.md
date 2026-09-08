# 🅱️ Fiche de travail — Personne B (PM + Backend projets/tâches)

> Se référer en permanence à `00-contrat-commun.md` pour les routes API, le schéma DB et les variables d'env.

## Modules dont tu es responsable
- ✅ Web — User interaction / cœur métier (projets + tâches) — contribue au Major "Web frameworks"
- ✅ GDPR — Minor
- 🎁 **Notification system — Minor (module bonus, marge de sécurité)**
- ✅ Coordination (PM) : backlog GitHub Issues, sync d'équipe

## Structure de fichiers à créer

```
backend/app/models/project.py
backend/app/models/project_member.py
backend/app/models/task.py
backend/app/schemas/project.py
backend/app/schemas/task.py
backend/app/routers/projects.py
backend/app/routers/tasks.py
backend/app/routers/gdpr.py
backend/app/models/notification.py
backend/app/schemas/notification.py
backend/app/routers/notifications.py
backend/tests/test_projects.py
backend/tests/test_tasks.py
```

## Semaine 1 — Setup + PM

- [ ] Créer le backlog GitHub Issues à partir des 4 fiches
- [ ] Planifier 2 syncs hebdo (mardi + vendredi, 15-20 min)
- [ ] `backend/app/models/project.py`, `project_member.py`, `task.py` (cf contrat commun section 1)
- [ ] Attendre que A ait livré `database.py` + `user.py` avant de tester tes modèles

## Semaine 2 — CRUD Projets

- [ ] `backend/app/schemas/project.py`
- [ ] `backend/app/routers/projects.py` : `GET/POST /api/projects`, `GET/PUT/DELETE /api/projects/{id}`
- [ ] `POST/DELETE /api/projects/{id}/members` (ajout/retrait de membres avec rôle owner/editor/viewer)
- [ ] **Prévenir D dès que les projets sont testables**

## Semaine 3 — CRUD Tâches

- [ ] `backend/app/schemas/task.py`
- [ ] `backend/app/routers/tasks.py` : `GET/POST /api/projects/{id}/tasks`, `PUT/DELETE /api/tasks/{id}`
- [ ] Gérer les statuts todo/in_progress/done et l'assignation à un membre
- [ ] Vérifier les permissions (un viewer ne peut pas modifier une tâche)
- [ ] `backend/tests/test_projects.py`, `test_tasks.py`

## Semaine 4 — GDPR + module bonus + README

- [ ] `backend/app/routers/gdpr.py` : `GET /api/gdpr/export`, `DELETE /api/gdpr/account`
- [ ] 🎁 **Module bonus — Notification system** (à faire si le reste est fini en avance, sinon skip sans risque) :
  - [ ] `backend/app/models/notification.py` (cf contrat commun)
  - [ ] `backend/app/schemas/notification.py`
  - [ ] `backend/app/routers/notifications.py` : `GET /api/notifications`, `PUT /api/notifications/{id}/read`, `PUT /api/notifications/read-all`
  - [ ] Créer une notification automatiquement dans `tasks.py` quand une tâche est assignée ou change de statut (juste un insert en DB à chaque action existante, pas de nouvelle logique complexe)
  - [ ] Prévenir D dès que c'est testable pour la petite pastille "non lues" dans la Navbar
- [ ] Rédiger dans `README.md` : Team Information, Project Management, Modules (avec justifications)
- [ ] Aider C sur l'intégration recherche/export si besoin (dépend des mêmes tables)

## Checklist de fin

- [ ] Un utilisateur peut créer un projet, inviter des membres avec des rôles
- [ ] Un utilisateur peut créer/modifier/assigner/supprimer des tâches
- [ ] Les permissions par rôle sont bien respectées (viewer en lecture seule)
- [ ] Export GDPR fonctionnel, suppression de compte avec confirmation
- [ ] 🎁 (si fait) Les notifications se créent automatiquement et sont marquables comme lues
- [ ] README à jour avec toutes les sections obligatoires

## Dépendances envers les autres
- Besoin de `database.py` + `user.py` de A (fin semaine 1)
- Besoin du JWT de A pour protéger tes routes (semaine 2)

## Ce que les autres attendent de toi
- **D attend `projects.py` et `tasks.py`** dès semaine 2-3 pour ses pages
- **C a besoin du modèle `task.py`** pour brancher attachments/recherche/export
