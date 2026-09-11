# 📐 CONTRAT COMMUN — Task Manager (à valider ensemble AVANT de coder)

⚠️ Ce document est la **source de vérité**. Toute modification doit être discutée en groupe
et mise à jour ici, sinon le travail des 4 personnes ne s'assemblera pas à la fin.

Stack : **FastAPI (Python) + React (JS) + PostgreSQL + Docker**

---

## 1. Schéma de base de données

### Table `users`
| Champ | Type | Contrainte |
|---|---|---|
| id | UUID | PK |
| email | string | unique, not null |
| password_hash | string | nullable (null si OAuth only) |
| oauth_provider | string | nullable ("google", "github", null) |
| oauth_id | string | nullable |
| username | string | unique, not null |
| role | enum | "admin", "user" — default "user" |
| avatar_url | string | default = avatar par défaut |
| created_at | timestamp | auto |
| updated_at | timestamp | auto |

### Table `projects`
| Champ | Type | Contrainte |
|---|---|---|
| id | UUID | PK |
| name | string | not null |
| description | text | nullable |
| owner_id | UUID | FK → users.id |
| created_at | timestamp | auto |

### Table `project_members`
| Champ | Type | Contrainte |
|---|---|---|
| id | UUID | PK |
| project_id | UUID | FK → projects.id |
| user_id | UUID | FK → users.id |
| role | enum | "owner", "editor", "viewer" |

### Table `tasks`
| Champ | Type | Contrainte |
|---|---|---|
| id | UUID | PK |
| project_id | UUID | FK → projects.id |
| title | string | not null |
| description | text | nullable |
| status | enum | "todo", "in_progress", "done" — default "todo" |
| assignee_id | UUID | FK → users.id, nullable |
| due_date | date | nullable |
| created_at | timestamp | auto |
| updated_at | timestamp | auto |

### Table `attachments`
| Champ | Type | Contrainte |
|---|---|---|
| id | UUID | PK |
| task_id | UUID | FK → tasks.id |
| file_url | string | not null |
| file_name | string | not null |
| uploaded_by | UUID | FK → users.id |
| created_at | timestamp | auto |

### Table `api_keys` (pour le module API publique)
| Champ | Type | Contrainte |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | FK → users.id |
| key | string | unique, généré |
| created_at | timestamp | auto |

### Table `notifications` (module bonus)
| Champ | Type | Contrainte |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | FK → users.id (destinataire) |
| type | enum | "task_assigned", "task_status_changed", "project_invite" |
| content | text | not null |
| related_task_id | UUID | FK → tasks.id, nullable |
| related_project_id | UUID | FK → projects.id, nullable |
| read | boolean | default false |
| created_at | timestamp | auto |

**👉 Responsable : Personne A (semaine 1, jour 1-2). Validation groupe avant de continuer.**
**👉 Table `notifications` : à créer par Personne B en semaine 4 (module bonus).**

---

## 2. Contrat des routes API REST

Toutes les routes sous préfixe `/api`. Format de réponse JSON standard :
```json
// Succès
{ "success": true, "data": { ... } }
// Erreur
{ "success": false, "error": "message d'erreur" }
```

### Auth & Users — Owner : A
| Méthode | Route | Body | Réponse |
|---|---|---|---|
| POST | `/api/auth/register` | `{email, username, password}` | `{user, token}` |
| POST | `/api/auth/login` | `{email, password}` | `{user, token}` |
| GET | `/api/auth/oauth/google` | — | redirect |
| GET | `/api/users/me` | header `Authorization: Bearer <token>` | `{user}` |
| PUT | `/api/users/me` | `{username?, avatar?}` | `{user}` |
| GET | `/api/users` | admin only, query `?page=&limit=` | `{users: [], total}` |
| PUT | `/api/users/{id}/role` | admin only, `{role}` | `{user}` |
| DELETE | `/api/users/{id}` | admin only | `{success}` |
| GET | `/health` | — | `{status: "ok", db: "ok"}` |

### Projects & Tasks — Owner : B
| Méthode | Route | Body | Réponse |
|---|---|---|---|
| GET | `/api/projects` | — | `{projects: []}` |
| POST | `/api/projects` | `{name, description}` | `{project}` |
| GET | `/api/projects/{id}` | — | `{project, members, tasks}` |
| PUT | `/api/projects/{id}` | `{name?, description?}` | `{project}` |
| DELETE | `/api/projects/{id}` | — | `{success}` |
| POST | `/api/projects/{id}/members` | `{user_id, role}` | `{member}` |
| DELETE | `/api/projects/{id}/members/{user_id}` | — | `{success}` |
| GET | `/api/projects/{id}/tasks` | query `?status=&page=` | `{tasks: [], total}` |
| POST | `/api/projects/{id}/tasks` | `{title, description, assignee_id?, due_date?}` | `{task}` |
| PUT | `/api/tasks/{id}` | `{title?, status?, assignee_id?, due_date?}` | `{task}` |
| DELETE | `/api/tasks/{id}` | — | `{success}` |
| GET | `/api/gdpr/export` | — | fichier JSON téléchargeable |
| DELETE | `/api/gdpr/account` | `{confirm: true}` | `{success}` |
| GET | `/api/notifications` | query `?unread_only=` | `{notifications: [], total}` |
| PUT | `/api/notifications/{id}/read` | — | `{notification}` |
| PUT | `/api/notifications/read-all` | — | `{success}` |

### API publique, recherche, fichiers, export — Owner : C
| Méthode | Route | Body | Réponse |
|---|---|---|---|
| GET | `/api/v1/public/tasks` | header `X-API-Key` | `{tasks: []}` (rate limited) |
| POST | `/api/v1/public/tasks` | header `X-API-Key`, `{project_id, title}` | `{task}` |
| PUT | `/api/v1/public/tasks/{id}` | header `X-API-Key`, `{status?}` | `{task}` |
| DELETE | `/api/v1/public/tasks/{id}` | header `X-API-Key` | `{success}` |
| GET | `/api/v1/public/projects` | header `X-API-Key` | `{projects: []}` |
| GET | `/api/search/tasks` | query `?q=&status=&project_id=&page=&limit=` | `{tasks: [], total}` |
| POST | `/api/tasks/{id}/attachments` | multipart file | `{attachment}` |
| DELETE | `/api/attachments/{id}` | — | `{success}` |
| GET | `/api/export?format=json\|csv` | — | fichier téléchargeable |
| POST | `/api/import` | multipart file | `{imported_count}` |

**👉 Toute nouvelle route doit être ajoutée ici AVANT d'être codée.**

---

## 3. Variables d'environnement (`.env.example`)

```env
# Backend
DATABASE_URL=postgresql://user:password@db:5432/taskmanager
JWT_SECRET=change_me
JWT_EXPIRATION=3600
OAUTH_GOOGLE_CLIENT_ID=
OAUTH_GOOGLE_CLIENT_SECRET=
CORS_ORIGINS=http://localhost:5173
UPLOAD_DIR=/app/uploads
MAX_UPLOAD_SIZE_MB=10

# Frontend
VITE_API_URL=http://localhost:8000
```

**👉 Responsable : Personne A, jour 1.**

---

## 4. Convention de nommage & Git

- **Branches** : une branche longue par personne — `A`, `B`, `C`, `D` — plus
  deux branches communes : `commun-test` (intégration/tests de l'équipe) et
  `commune-final` (dernier push avant le rendu scolaire)
- **Commits** : `[SCOPE] description` (ex: `[auth] add JWT token generation`)
- Merge régulier de sa branche perso vers `commun-test` pour tester ensemble
- `commune-final` : uniquement au moment du rendu, à partir de `commun-test` validé

---

## 5. Récapitulatif des points visés

| Catégorie | Module | Type | Pts | Owner |
|---|---|---|---|---|
| Web | Framework frontend + backend | Major | 2 | D + A |
| Web | ORM | Minor | 1 | A |
| Web | API publique | Major | 2 | C |
| Web | Recherche avancée | Minor | 1 | C |
| Web | File upload | Minor | 1 | C |
| User Management | Permissions avancées | Major | 2 | A |
| User Management | OAuth | Minor | 1 | A |
| Accessibilité | Multilingue | Minor | 1 | D |
| Data & Analytics | Export/import | Minor | 1 | C |
| Data & Analytics | GDPR | Minor | 1 | B |
| Devops | Health check | Minor | 1 | A |
| **Sous-total (obligatoire)** | | | **14** | |
| 🎁 Web | Notification system | Minor | 1 | B |
| 🎁 Web | PWA | Minor | 1 | D |
| 🎁 Accessibilité | Navigateurs additionnels | Minor | 1 | D |
| 🎁 Web | Custom design system | Minor | 1 | D |
| **Total avec marge** | | | **17-18** | |

⚠️ Les modules 🎁 sont des bonus de sécurité — à faire en priorité 2, seulement une fois
les 14 points obligatoires solides et démontrables. Un module non fonctionnel = 0 point,
donc mieux vaut 14 points 100% fiables que 17 points bancals.

## 6. Checklist de validation du contrat (à faire ensemble, jour 1)

- [ ] Schéma DB validé par les 4
- [ ] Routes API validées par les 4
- [ ] `.env.example` créé par A
- [ ] Convention Git comprise par tous
