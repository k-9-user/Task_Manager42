# Projet réuni — dossier "tous"

Fusion du travail des 4 personnes (A, B, C, D). Le code source est complet et
testé de bout en bout (voir "Reste à faire" pour ce qui n'est pas fini côté
frontend).

## Pourquoi chacun doit refaire son installation(sans utilisation de docker pour les tests)

`.venv/`, `node_modules/` et `.env` **ne sont pas dans le dépôt** (voir
`.gitignore`) — c'est normal, ne les commitez pas non plus :

- **`.venv/` et `node_modules/`** : ce sont des dépendances installées, pas
  du code écrit par nous. Elles sont énormes (des centaines de Mo), liées à
  la machine (binaires compilés pour votre OS/architecture), et surtout
  **100% reproductibles** — `requirements.txt` et `package-lock.json`
  épinglent des versions exactes, donc `pip install` / `npm install` chez
  vous installe exactement les mêmes versions que chez les autres, juste
  stockées localement.
- **`.env`** : contient de vrais secrets (`JWT_SECRET` sert à signer les
  tokens de connexion — s'il est committé, n'importe qui peut forger un
  token valide pour n'importe quel compte). Chaque environnement peut aussi
  avoir des valeurs différentes (URL de DB, etc.). D'où `.env.example`
  (gabarit, committé, sans vrai secret) vs `.env` (vos vraies valeurs,
  jamais committé — `cp .env.example .env` puis modifiez).

## Prérequis

- Python 3.12+
- Node **≥ 20** (le frontend utilise Vite 8 / React Router 7, qui plantent
  au démarrage sur Node 18 — `node --version` pour vérifier, sinon passez
  par [nvm](https://github.com/nvm-sh/nvm))
- PostgreSQL (local, ou un conteneur Docker jetable, cf plus bas)

## Installation

```bash
cd tous
cp .env.example .env
# éditez .env : JWT_SECRET doit faire 32+ caractères aléatoires

cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cd ../frontend
npm install
```

## Compiler / vérifier que ça build

```bash
# Backend : vérifie juste que tout le code est syntaxiquement valide
cd tous/backend && source .venv/bin/activate
python3 -m py_compile app/*.py app/*/*.py alembic/env.py tests/*.py

# Frontend : build de prod, échoue si erreur de compilation
cd tous/frontend
npm run build
```

## Lancer les tests automatisés (~190 tests)

Les tests de la partie C (attachments/search/export_import/api_key/rate_limiter)
sont autonomes (SQLite en mémoire). Ceux de la partie B (projects/tasks/gdpr/
notifications) ont besoin d'une vraie Postgres de test, séparée de la DB de dev :

```bash
docker run -d --name tm-test-db \
  -e POSTGRES_DB=taskmanager_test \
  -e POSTGRES_USER=user -e POSTGRES_PASSWORD=password \
  -p 5432:5432 postgres:17-alpine

cd tous/backend
source .venv/bin/activate

export DATABASE_URL="postgresql://user:password@localhost:5432/taskmanager_test"
export JWT_SECRET="dev_secret_key_for_local_testing_only_32ch"
export TEST_DATABASE_URL="$DATABASE_URL"

alembic revision --autogenerate -m "initial schema"
alembic upgrade head

pytest tests/ -v
```

Nettoyage ensuite : `docker rm -f tm-test-db`.

## Lancer l'app pour tester à la main

```bash
# Backend (nécessite une vraie Postgres accessible via DATABASE_URL — voir
# .env, ou réutilisez tm-test-db ci-dessus pour une démo rapide)
cd tous/backend && source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
# → http://localhost:8000/docs (Swagger)

# Frontend
cd tous/frontend
npm run dev
# → http://localhost:5173
```

Ou tout d'un coup avec Docker (`db` + `backend` + `frontend` seulement — le
service `nginx` du `docker-compose.yml` n'a pas de config, ignorez-le) :

```bash
docker compose up --build db backend frontend
```

## Reste à faire

### Retours des tests de Kheira — expérience utilisateur

- **Dashboard à revoir entièrement** : actuellement pas assez lisible. Sur
  le tableau de bord, chaque projet doit vraiment apparaître avec son nom,
  un détail rapide, et son statut (au lieu de l'affichage minimal actuel).
- **Page projet** : besoin d'un environnement visuel plus sympa à l'ouverture
  d'un projet, avec :
  - un vrai suivi type conversation/messages sur le projet
  - une vue claire de l'avancement (étapes, progression) plutôt que juste la
    liste brute des tâches
- **Messages d'erreur d'authentification trop vagues** : ex. mot de passe
  trop court (minimum 12 caractères côté backend) renvoie juste "Invalid
  request", impossible de savoir pourquoi sans deviner. Il faut soit
  afficher le vrai détail de validation, soit des messages
  clairs par cas (mot de passe trop court, email invalide, etc.), et
  idéalement une validation côté frontend avant l'envoi.

### Bugs / manques déjà identifiés (à corriger ou vérifier)

- Aucune donnée réelle affichée nulle part n'a encore de design dédié — le
  frontend actuel est fonctionnel mais très brut (formulaires sans style
  particulier, pas de retours visuels de chargement/succès élaborés).
- `frontend/src/assets/components/` : bac à sable de composants (Nicolas),
  jamais intégré à l'app réelle — à trier (récupérer ce qui est utile pour
  le nouveau dashboard, supprimer le reste).
- Le service `nginx` de `docker-compose.yml` n'a pas de configuration
  (aucun `nginx.conf` fourni) 
