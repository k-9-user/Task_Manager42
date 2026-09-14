# 🅳️ Fiche de travail — Personne D (Frontend)

> Se référer en permanence à `00-contrat-commun.md` pour les routes API — tes appels doivent matcher EXACTEMENT ce contrat.

## Modules dont tu es responsable
- ✅ Web — Framework frontend — Major (partagé avec l'équipe)
- ✅ Accessibilité — Multilingue (i18n) — Minor
- 🎁 **PWA — Minor (module bonus, marge de sécurité)**
- 🎁 **Support navigateurs additionnels — Minor (module bonus, marge de sécurité)**
- 🎁 **Custom design system (10 composants réutilisables) — Minor (module bonus, quasi gratuit si le code est déjà propre)**

## Structure de fichiers à créer

```
frontend/vite.config.js
frontend/tailwind.config.js
frontend/src/App.jsx
frontend/src/main.jsx
frontend/src/services/api.js
frontend/src/services/authService.js
frontend/src/services/projectService.js
frontend/src/services/taskService.js
frontend/src/hooks/useAuth.js
frontend/src/pages/Login.jsx
frontend/src/pages/Register.jsx
frontend/src/pages/Profile.jsx
frontend/src/pages/Projects.jsx
frontend/src/pages/ProjectDetail.jsx
frontend/src/pages/Search.jsx
frontend/src/pages/AdminUsers.jsx
frontend/src/pages/PrivacyPolicy.jsx
frontend/src/pages/TermsOfService.jsx
frontend/src/components/Navbar.jsx
frontend/src/components/Footer.jsx
frontend/src/components/TaskCard.jsx
frontend/src/components/TaskBoard.jsx
frontend/src/components/AttachmentUpload.jsx
frontend/src/components/LanguageSwitcher.jsx
frontend/src/i18n.js
frontend/public/locales/en/translation.json
frontend/public/locales/fr/translation.json
frontend/public/locales/es/translation.json
frontend/public/manifest.json
frontend/src/service-worker.js
frontend/src/components/NotificationBell.jsx
frontend/src/services/notificationService.js
```

## Semaine 1 — Setup (en parallèle de A, sans dépendance bloquante)

- [ ] `frontend/vite.config.js`, `frontend/tailwind.config.js`
- [ ] `frontend/src/App.jsx`, `frontend/src/main.jsx` (routes React Router)
- [ ] `frontend/src/services/api.js` : instance axios/fetch pointant sur `VITE_API_URL`
- [ ] Maquettes rapides validées avec l'équipe : login, profil, liste projets, détail projet (board de tâches)
- [ ] `frontend/src/components/Navbar.jsx`, `Footer.jsx` (squelette)

## Semaine 2 — Auth + Profil (dépend de A)

- [ ] `frontend/src/services/authService.js`
- [ ] `frontend/src/hooks/useAuth.js`
- [ ] `frontend/src/pages/Login.jsx`, `Register.jsx`, `Profile.jsx`
- [ ] **Ne commence cette partie qu'une fois que A a confirmé `/api/auth/*` testable**

## Semaine 3 — Projets, tâches, admin (dépend de B et A)

- [ ] `frontend/src/services/projectService.js`, `taskService.js`
- [ ] `frontend/src/pages/Projects.jsx` (liste + création)
- [ ] `frontend/src/pages/ProjectDetail.jsx` avec `frontend/src/components/TaskBoard.jsx` (colonnes todo/in progress/done)
- [ ] `frontend/src/components/TaskCard.jsx`
- [ ] `frontend/src/pages/AdminUsers.jsx` (visible seulement si rôle admin)
- [ ] **Ne commence qu'une fois que B a confirmé `/api/projects` et `/api/tasks` testables**

## Semaine 4 — Recherche, fichiers, i18n, légal, design

- [ ] `frontend/src/pages/Search.jsx` (branché sur `/api/search/tasks` de C)
- [ ] `frontend/src/components/AttachmentUpload.jsx` (branché sur `/api/tasks/{id}/attachments` de C)
- [ ] `frontend/src/i18n.js`, `frontend/public/locales/*/translation.json`
- [ ] `frontend/src/components/LanguageSwitcher.jsx`
- [ ] `frontend/src/pages/PrivacyPolicy.jsx`, `TermsOfService.jsx` (contenu réel)
- [ ] Passe de design : cohérence, responsive, test sur Firefox en plus de Chrome

## Semaine 4 (fin) — Modules bonus (si le reste est fini en avance, sinon skip sans risque)

- [ ] 🎁 **PWA** :
  - [ ] `frontend/public/manifest.json` (nom, icônes, couleurs, `display: standalone`)
  - [ ] `frontend/src/service-worker.js` (cache basique des assets statiques, mode offline simple)
  - [ ] Enregistrer le service worker dans `main.jsx`
  - [ ] Tester : le site s'installe bien depuis Chrome ("Installer l'application")

- [ ] 🎁 **Support navigateurs additionnels** :
  - [ ] Tester le site entier sur Firefox et Edge (ou Safari si dispo)
  - [ ] Corriger les incohérences CSS trouvées (flexbox/grid, fonts, etc.)
  - [ ] Documenter les limitations connues dans le README

- [ ] 🎁 **Custom design system** (si les composants sont déjà propres, il suffit de les recenser) :
  - [ ] Vérifier que tu as au moins 10 composants réutilisables (Navbar, Footer, TaskCard, TaskBoard, UserCard, Button, Input, Modal, Badge, LanguageSwitcher, NotificationBell...)
  - [ ] Extraire une palette de couleurs + typographie cohérente dans `tailwind.config.js`
  - [ ] Documenter le design system dans le README (courte section avec captures)

- [ ] 🎁 **Notifications (branché sur le module bonus de B)** :
  - [ ] `frontend/src/services/notificationService.js`
  - [ ] `frontend/src/components/NotificationBell.jsx` (pastille avec compteur non lu dans la Navbar)

## Checklist de fin

- [ ] Toutes les pages sont fonctionnelles et connectées au backend réel (pas de mock)
- [ ] Le board de tâches (drag & drop optionnel, ou simples boutons de changement de statut) fonctionne
- [ ] Le switch de langue fonctionne sur 3 langues
- [ ] Aucune erreur/warning console
- [ ] Responsive mobile + desktop, testé sur 2 navigateurs
- [ ] Footer avec liens Privacy Policy / ToS visibles partout
- [ ] 🎁 (si fait) Le site est installable en PWA et fonctionne hors ligne a minima pour le shell de l'app
- [ ] 🎁 (si fait) Le site fonctionne correctement sur Firefox + Edge, limitations documentées
- [ ] 🎁 (si fait) Au moins 10 composants réutilisables identifiés et documentés

## Dépendances envers les autres
- Attend `docker compose up` fonctionnel de A (fin semaine 1)
- Attend `/api/auth/*` testable de A (semaine 2)
- Attend `/api/projects`, `/api/tasks` testables de B (semaine 2-3)
- Attend `/api/search`, `/api/attachments` testables de C (semaine 3-4)

## Ce que les autres attendent de toi
- Rien de bloquant, mais **communique vite** si un contrat API ne matche pas ce qui a été codé côté backend — corrige-le dans `00-contrat-commun.md` en groupe
