# 📋 Fiche Concept — donner un nom ou Task Manager (ft_transcendence)


## 1. En une phrase

> Une application web de gestion de projets et de tâches en équipe, où plusieurs
> utilisateurs collaborent en temps réel sur des projets partagés, avec des rôles,
> une API publique pour les intégrations externes, et une gestion complète de
> leurs données personnelles.

## 2. Pourquoi ce projet ? 

Le sujet impose de créer une **application web complète, multi-utilisateurs**, avec
frontend + backend + base de données. Un gestionnaire de tâches a été choisi car :

- C'est un concept **universellement compréhensible** (pas besoin d'expliquer des règles complexes)
- Il se prête naturellement à une **vraie collaboration multi-utilisateurs** (plusieurs personnes sur un même projet, ce qui est une exigence obligatoire du sujet)
- Il permet de couvrir des modules variés et cohérents (permissions, API publique, recherche, fichiers) **sans dépendances techniques lourdes** (pas de temps réel critique comme un jeu ou un chat)
- C'est un type d'application "réel" avec de la valeur pratique.

## 3. Le concept fonctionnel — comment ça marche pour un utilisateur

### Parcours utilisateur type

1. **Inscription / Connexion** — un utilisateur crée un compte (email + mot de passe, ou via Google OAuth)
2. **Création d'un projet** — il crée un projet (ex: "Refonte site web"), devient automatiquement "owner"
3. **Invitation de membres** — il invite ses collègues avec un rôle : `owner` (contrôle total), `editor` (peut créer/modifier des tâches), `viewer` (lecture seule)
4. **Gestion des tâches** — dans le projet, les membres créent des tâches avec un titre, une description, une échéance, et les assignent à quelqu'un
5. **Suivi de l'avancement** — chaque tâche a un statut : `todo` → `in_progress` → `done`, visible sous forme de tableau (board) façon Kanban
6. **Pièces jointes** — on peut attacher un fichier à une tâche (ex: une maquette, un cahier des charges)
7. **Recherche** — on peut rechercher une tâche par mot-clé, filtrer par statut ou par projet
8. **Notifications** *(bonus)* — l'utilisateur est notifié quand une tâche lui est assignée ou change de statut
9. **Export de données** — à tout moment, un utilisateur peut exporter ses données (conformité GDPR) ou les supprimer

### Les deux profils d'utilisateurs

| Profil | Ce qu'il peut faire |
|---|---|
| **Utilisateur normal** | Gérer ses projets, ses tâches, son profil |
| **Administrateur** | Tout ce qu'un utilisateur normal peut faire + gérer tous les comptes (voir/modifier/supprimer), changer les rôles |

---

## 4. Architecture technique — vue d'ensemble

```
┌─────────────┐        HTTPS         ┌──────────────┐        ┌────────────┐
│   Frontend   │ ───────────────────▶ │   Backend    │ ─────▶ │  Database  │
│  React + JS  │ ◀─────────────────── │   FastAPI    │ ◀───── │ PostgreSQL │
└─────────────┘      JSON (REST)      └──────────────┘        └────────────┘
                                              │
                                              │ clé API
                                              ▼
                                     ┌──────────────────┐
                                     │ Intégrations      │
                                     │ externes (API pub)│
                                     └──────────────────┘
```

- **Frontend** (React) : interface utilisateur, appelle le backend en HTTPS via des requêtes REST
- **Backend** (FastAPI) : logique métier, authentification, validation, accès à la base de données
- **Base de données** (PostgreSQL) : stockage persistant (users, projects, tasks, etc.)
- **API publique** : un tiers externe (autre développeur) peut interagir avec les tâches via une clé API, sans passer par l'interface web

## 5. Pourquoi cette stack technique ? (à savoir justifier)

| Choix | Justification |
|---|---|
| **React** | Framework frontend le plus répandu, écosystème riche, composants réutilisables faciles à structurer (utile pour le module design system) |
| **FastAPI** | Framework backend Python léger, performant, génère automatiquement la documentation API (Swagger) — utile pour le module "API publique documentée" |
| **PostgreSQL** | SGBD relationnel robuste, gère bien les relations complexes (users ↔ projects ↔ tasks) |
| **SQLAlchemy (ORM)** | Évite d'écrire du SQL brut, sécurise contre les injections SQL, accélère le développement |
| **Docker** | Garantit que l'application tourne à l'identique sur toutes les machines, déploiement en une commande |
| **JWT** | Authentification stateless, standard de l'industrie, fonctionne bien avec une API publique par clé |

---

## 6. Le schéma de données expliqué simplement

```
users ──┬── owns ──▶ projects ──┬── has many ──▶ tasks ──┬── has ──▶ attachments
        │                       │                        │
        └── member_of ──────────┘                        └── assigned_to ──▶ users
```

- Un **user** peut posséder plusieurs **projects**
- Un **project** a plusieurs **members** (via la table `project_members`, avec un rôle chacun)
- Un **project** contient plusieurs **tasks**
- Une **task** peut être assignée à un **user** et avoir des **attachments**

C'est un schéma relationnel classique en **étoile autour des projets**, ce qui permet
de justifier facilement le choix d'une base de données relationnelle plutôt que NoSQL.

---

## 7. Pourquoi ces modules précisément ? (justification par catégorie)

| Module | Pourquoi il a du sens pour CE projet |
|---|---|
| **Permissions avancées** | Un gestionnaire de projets a naturellement besoin de rôles (owner/editor/viewer) et d'administration |
| **API publique** | Permet à une équipe d'intégrer le gestionnaire de tâches à d'autres outils (ex: un bot Slack qui crée des tâches) — cas d'usage réel |
| **Recherche avancée** | Indispensable dès qu'un projet a beaucoup de tâches |
| **File upload** | Une tâche a souvent besoin d'un document ou d'une maquette attachée |
| **OAuth** | Simplifie l'inscription, évite de gérer un mot de passe de plus |
| **GDPR** | Toute application qui stocke des données personnelles doit permettre l'export/suppression |
| **Multilingue** | Rend l'outil utilisable par une équipe internationale |
| **Health check** | Bonne pratique de fiabilité pour une application en production |
| **Notifications** *(bonus)* | Améliore l'expérience utilisateur sans complexité technique lourde (pas de temps réel requis, juste un flag en base) |

---

## 8. Ce qui NE fait PAS partie du projet (pour éviter les malentendus)

- ❌ Pas de chat en temps réel entre utilisateurs
- ❌ Pas de jeu ou de fonctionnalité de divertissement
- ❌ Pas de fonctionnalités IA (recommandation, LLM, etc.)

Ce choix est volontaire : il permet de **livrer un projet fiable et bien testé**
plutôt que de multiplier les fonctionnalités à risque.

---

## 9. Questions probables 

1. **"Pourquoi avoir choisi ce projet plutôt qu'un jeu ?"**
   → Moins de risque technique (pas de synchronisation temps réel critique), plus facile à tester et démontrer de façon fiable, tout en couvrant des modules variés.

2. **"Comment gérez-vous le multi-utilisateur simultané ?"**
   → Chaque requête est indépendante et authentifiée par JWT ; la base de données PostgreSQL gère nativement les accès concurrents via les transactions ; les permissions (owner/editor/viewer) évitent les conflits d'édition.

3. **"Pourquoi FastAPI plutôt que Django ou Express ?"**
   → Léger à mettre en place pour une équipe qui découvre le framework, documentation API automatique (utile pour le module API publique), performance native sur l'async.

4. **"Comment fonctionne le rate limiting de l'API publique ?"**
   → Chaque clé API est limitée à un nombre de requêtes par minute, suivi en mémoire ou en base, avec un code d'erreur 429 si dépassement.

5. **"Que se passe-t-il si deux personnes modifient la même tâche en même temps ?"**
   → Chaque `PUT /api/tasks/{id}` écrase avec les dernières valeurs envoyées (last-write-wins) ; à mentionner honnêtement comme limitation connue si pas de gestion de conflit plus poussée.

---

## 10. Résumé express 

> "Notre projet est un gestionnaire de tâches collaboratif. Les utilisateurs créent
> des projets, invitent des collègues avec des rôles différents, et organisent leur
> travail sous forme de tâches avec statuts et échéances. On a ajouté une API publique
> documentée pour permettre des intégrations externes, une recherche avancée, la
> gestion de pièces jointes, et on respecte le RGPD avec export et suppression des
> données. Techniquement, c'est un stack React/FastAPI/PostgreSQL, entièrement
> conteneurisé avec Docker, sécurisé en HTTPS avec authentification JWT et OAuth."
