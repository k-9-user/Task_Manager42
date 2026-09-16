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
| display_name | string | nullable, nom public distinct du username |
| status | enum | "active", "banned" — default "active" |
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
| key_hash | string | unique, not null, SHA-256 de la cle generee |
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

### Table `oauth_handoffs` (transfert navigateur interne)
| Champ | Type | Contrainte |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | FK → users.id, cascade |
| token_hash | string | unique, not null |
| expires_at | timestamp | not null, duree maximale 60 secondes |

**👉 Responsable : Personne A (semaine 1, jour 1-2). Validation groupe avant de continuer.**
**Table `notifications` : responsabilite B; livree dans la migration de fondation. Le module complet reste non valide.**

### Regles de coherence actuelles

- Les sept tables sont maintenant dans la migration initiale, notifications comprises. Enums PostgreSQL : `user_role`, `user_status`, `projectrole`, `taskstatus`, `notificationtype`.
- La premiere inscription dans une base vide devient administrateur; les suivantes deviennent `user`. Un compte banni est refuse par JWT et par cle API. Les operations admin et GDPR doivent conserver au moins un administrateur actif.
- `project_members` est la source canonique des permissions pour B et C. Un admin global sans appartenance n'a pas d'acces implicite aux projets. `owner` gere projet/membres/taches, `editor` gere les taches et fichiers, `viewer` lit seulement.
- Le createur est membre `owner`. Plusieurs membres peuvent etre `owner`; le retrait du dernier owner est refuse. Si le membre retire correspond a `projects.owner_id`, cette reference est transferee a un autre owner dans la meme operation. Il ne s'agit pas d'une nouvelle route de transfert.
- La suppression GDPR transfere un projet partage a un membre restant (priorite a un owner, puis ordre deterministe des UUID), ou supprime un projet sans autre membre. L'ordre UUID ne represente pas l'anciennete. Les assignations du compte supprime sont remises a null.
- Les FK attachments vers task/uploader sont restrictives : supprimer un parent avec des pieces jointes peut retourner **409**. Supprimer explicitement les fichiers autorises avant de retenter. La suppression d'une piece jointe commit la suppression DB avant unlink; un echec unlink est journalise comme fichier orphelin. La procedure de nettoyage reste a definir.
- Le telechargement protege des fichiers n'est pas livre. Une `file_url` n'est pas la preuve d'une route de telechargement disponible. Les cles API sont stockees uniquement sous forme de hash; la valeur brute est affichee une seule fois a l'emission ou rotation.
- Les contraintes de null explicite, la validation des assignations via import et la couverture complete des donnees GDPR restent des suivis de l'audit; ne pas les declarer resolus par ce contrat.

---

## 2. Contrat des routes API REST

Routes metier sous `/api`, sauf `/health`. Swagger : `/docs`, specification : `/openapi.json`. Format de reponse JSON standard :
```json
// Succès
{ "success": true, "data": { ... } }
// Erreur
{ "success": false, "error": "message d'erreur" }
```

Dans les tableaux, **Reponse designe le contenu de `data`**, pas l'enveloppe complete. Entites singulieres : `data.user`, `data.project`, `data.task`, `data.member`, `data.notification`, `data.attachment`. Listes : pluriel et `total` quand pagine. Suppression et marquage global : HTTP 200 avec `{ "success": true, "data": {} }`, pas de second booleen `success` dans `data`.

Exceptions : `/health` est un objet direct; demarrage et callback OAuth sont des redirections; exports sont des fichiers avec `Content-Disposition`, pas des enveloppes JSON. Le callback OAuth cree une session de transfert courte sans JWT et redirige vers `/oauth/callback`; le frontend consomme cette session une fois via `POST /api/auth/oauth/google/exchange`. Les codes HTTP restent significatifs (401 identite invalide, 403 permission/bannissement, 404 ressource non visible/absente, 409 conflit, 422 validation, 429 limitation).

### Auth & Users — Owner : A
| Méthode | Route | Body | Réponse |
|---|---|---|---|
| POST | `/api/auth/register` | `{email, username, password}` | `{user, token}` |
| POST | `/api/auth/login` | `{email, password}` | `{user, token}` |
| GET | `/api/auth/oauth/google` | — | redirect |
| GET | `/api/auth/oauth/google/callback` | callback fournisseur, session OAuth | redirect `/oauth/callback` ou `/login?oauth=...` |
| POST | `/api/auth/oauth/google/exchange` | session OAuth courte, consommee une fois | `{user, token}` |
| GET | `/api/users/me` | header `Authorization: Bearer <token>` | `{user}` |
| PUT | `/api/users/me` | `{username?, avatar?, display_name?}` | `{user}` |
| GET | `/api/users` | admin only, query `?page=&limit=` | `{users: [], total}` |
| PUT | `/api/users/{id}` | admin only, `{username?, display_name?}` | `{user}` |
| PUT | `/api/users/{id}/role` | admin only, `{role}` | `{user}` |
| PUT | `/api/users/{id}/status` | admin only, `{status, reason?}`; active/banned | `{user}` |
| DELETE | `/api/users/{id}` | admin only; conflits dernier admin/donnees liees | `{}` |
| GET | `/health` | — | `{status: "ok", db: "ok"}` |

### Projects & Tasks — Owner : B
| Méthode | Route | Body | Réponse |
|---|---|---|---|
| GET | `/api/projects` | — | `{projects: []}` |
| POST | `/api/projects` | `{name, description}` | `{project}` |
| GET | `/api/projects/{id}` | — | `{project, members, tasks}` |
| PUT | `/api/projects/{id}` | `{name?, description?}` | `{project}` |
| DELETE | `/api/projects/{id}` | owner; 409 si fichiers lies | `{}` |
| POST | `/api/projects/{id}/members` | `{user_id, role}` | `{member}` |
| DELETE | `/api/projects/{id}/members/{user_id}` | owner; conserve un owner | `{}` |
| GET | `/api/projects/{id}/tasks` | query `?status=&page=` | `{tasks: [], total}` |
| POST | `/api/projects/{id}/tasks` | `{title, description, assignee_id?, due_date?}` | `{task}` |
| PUT | `/api/tasks/{id}` | `{title?, status?, assignee_id?, due_date?}` | `{task}` |
| DELETE | `/api/tasks/{id}` | owner/editor; 409 si fichiers lies | `{}` |
| GET | `/api/gdpr/export` | — | fichier JSON téléchargeable |
| DELETE | `/api/gdpr/account` | `{confirm: true}`; invariant admin et FK | `{}` |
| GET | `/api/notifications` | query `?unread_only=` | `{notifications: [], total}` |
| PUT | `/api/notifications/{id}/read` | — | `{notification}` |
| PUT | `/api/notifications/read-all` | — | `{}` |

### API publique, recherche, fichiers, export — Owner : C
| Méthode | Route | Body | Réponse |
|---|---|---|---|
| POST | `/api/api-keys` | header `Authorization: Bearer <token>` | `{api_key: {id, key, created_at}}`; `key` visible une fois |
| GET | `/api/api-keys` | header `Authorization: Bearer <token>` | `{api_keys: [{id, created_at}]}` |
| DELETE | `/api/api-keys/{id}` | header `Authorization: Bearer <token>`; proprietaire | `{}` |
| POST | `/api/api-keys/{id}/rotate` | header `Authorization: Bearer <token>`; proprietaire | `{api_key: {id, key, created_at}}`; ancienne cle invalide |
| GET | `/api/v1/public/tasks` | header `X-API-Key` | `{tasks: []}` (rate limited) |
| POST | `/api/v1/public/tasks` | header `X-API-Key`, `{project_id, title}` | `{task}` |
| PUT | `/api/v1/public/tasks/{id}` | header `X-API-Key`, `{status?}` | `{task}` |
| DELETE | `/api/v1/public/tasks/{id}` | header `X-API-Key` | `{}` |
| GET | `/api/v1/public/projects` | header `X-API-Key` | `{projects: []}` |
| GET | `/api/search/tasks` | query `?q=&status=&project_id=&page=&limit=` | `{tasks: [], total}` |
| POST | `/api/tasks/{id}/attachments` | multipart file | `{attachment}` |
| DELETE | `/api/attachments/{id}` | owner/editor | `{}` |
| GET | `/api/export?format=json\|csv` | — | fichier téléchargeable |
| POST | `/api/import` | multipart file | `{imported_count}` |

**👉 Toute nouvelle route doit être ajoutée ici AVANT d'être codée.**

### Limites et fonctions differees

- Pagination users : page 1, limite 20 par defaut, maximum 100. Taches d'un projet : pages de 20. Recherche : page 1, limite 20, maximum 100; `q` facultatif, filtres status/project disponibles. **Tri configurable requis par le sujet mais non implemente**; ne pas envoyer un parametre de tri invente.
- Import JSON/CSV : multipart `file`, maximum 5 MiB et 1000 taches, insertion atomique dans des projets existants accessibles en ecriture. Il cree de nouvelles taches; ce n'est pas une restauration de sauvegarde ni une mise a jour des IDs exportes. Politique CSV/formules, null et assignations : suivis ouverts.
- Upload : multipart `file`, limite backend `MAX_UPLOAD_SIZE_MB`, types declares PDF/JPEG/PNG/CSV/texte. La limite nginx doit etre reconciliee avec l'overhead multipart. Validation client, contenu, preview, progression et recuperation protegee restent a completer.
- Notifications actuelles : assignment, changement de statut, invitation. Le module du sujet exige **toutes les creations/modifications/suppressions**, y compris les chemins public/import pertinents; matrice d'evenements et UI encore manquantes.
- Les cles API publiques sont destinees aux clients serveur/CLI. `X-API-Key` reste exclu de CORS tant qu'aucun client navigateur n'est explicitement supporte.
- Emails de confirmation GDPR, status page, sauvegardes automatiques et procedure de reprise sont des exigences non livrees. Les routes actuelles ne les impliquent pas.

---

## 3. Variables d'environnement (`.env.example`)

```env
# Database
POSTGRES_DB=taskmanager
POSTGRES_USER=user
POSTGRES_PASSWORD=replace_with_generated_database_password

# Backend
DATABASE_URL=postgresql://user:replace_with_generated_database_password@db:5432/taskmanager
JWT_SECRET=replace_with_a_random_32_plus_character_jwt_secret
JWT_EXPIRATION=3600
OAUTH_GOOGLE_CLIENT_ID=
OAUTH_GOOGLE_CLIENT_SECRET=
OAUTH_GOOGLE_REDIRECT_URI=https://localhost:8443/api/auth/oauth/google/callback
OAUTH_SESSION_SECRET=replace_with_a_random_32_plus_character_oauth_secret
CORS_ORIGINS=https://localhost:8443
UPLOAD_DIR=/app/uploads
MAX_UPLOAD_SIZE_MB=10
FORWARDED_ALLOW_IPS=10.0.0.0/8,172.16.0.0/12,192.168.0.0/16

# Frontend
VITE_API_URL=https://localhost:8443
```

**👉 Responsable : Personne A, jour 1.**

`.env.example` a la racine est la reference complete (identifiants PostgreSQL et proxy compris). Ne pas conserver les secrets exemples. Usage **localhost uniquement**, adresse navigateur preservee `https://localhost:8443`. Les secrets restent dans `.env` ignore par Git. La confiance du certificat local est une decision explicite de l'utilisateur; aucun script ne doit modifier automatiquement le magasin de certificats de l'hote. Voir le README anglais pour setup/check/up/down/logs/ps/smoke/test et reset-db explicite.

---

## 4. Convention de nommage & Git

- **Branches** : une branche longue par personne — `A`, `B`, `C`, `D` — plus
  deux branches communes : `commun-test` (intégration/tests de l'équipe) et
  `commune-final` (dernier push avant le rendu scolaire)
- **Commits** : `[SCOPE] description` (ex: `[auth] add JWT token generation`)
- Merge régulier de sa branche perso vers `commun-test` pour tester ensemble
- `commune-final` : uniquement au moment du rendu, à partir de `commun-test` validé

Etat observe lors de l'integration : branche locale `dev`, upstream signale `origin/A`. Cette divergence avec la convention historique doit etre resolue par une **decision explicite de l'equipe** avant push. Aucun changement automatique de configuration Git; verifier branche et destination, ne pas supposer que `dev` suit `origin/dev`.

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
| Devops | Health check + status page + sauvegardes automatiques + reprise apres sinistre | Minor | 1 | A |
| **Sous-total cible (non valide)** | | | **14** | |
| 🎁 Web | Notification system | Minor | 1 | B |
| 🎁 Web | PWA | Minor | 1 | D |
| 🎁 Accessibilité | Navigateurs additionnels | Minor | 1 | D |
| 🎁 Web | Custom design system | Minor | 1 | D |
| **Total theorique avec les 4 options** | | | **18** | |

⚠️ Les modules 🎁 sont des bonus de sécurité — à faire en priorité 2, seulement une fois
les 14 points obligatoires solides et démontrables. Un module non fonctionnel = 0 point,
donc mieux vaut 14 points 100% fiables que 17 points bancals.

Precision sujet 21.1 : recherche = filtres **+ tri + pagination**; multilingue = **trois traductions completes de tous les textes visibles**; GDPR = export/suppression confirmee **+ emails de confirmation**; notifications = **tous les CUD**; navigateurs additionnels = **deux en plus de Chrome**. Le framework major ne se cumule pas ici avec les deux minors frontend/backend. Les taches collaboratives ne remplacent pas chat/profils/amis pour le major User Interaction. Ce tableau est un objectif, jamais un score acquis.

Le README racine doit etre en anglais (sujet VI, pages 27-29), avec vrais logins en premiere ligne, roles confirmes (PO/PM/Tech Lead/developpeurs), contributions, gestion de projet, stack/schema/features/modules, ressources et usage IA. Les etiquettes A/B/C/D ne remplacent pas ces informations personnelles encore a fournir.

## 6. Checklist de validation du contrat (à faire ensemble, jour 1)

- [ ] Schéma DB validé par les 4
- [ ] Routes API validées par les 4
- [ ] `.env.example` créé par A
- [ ] Convention Git comprise par tous
