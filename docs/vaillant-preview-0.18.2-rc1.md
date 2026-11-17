# Vaillant Preview 0.18.2 RC1 — préparation hors production

Branche dédiée : `release/vaillant-preview-0.18.2-rc1`. Cette branche
réunit **les fichiers source** des PR #5, #6 et #8, sans fusionner les PR
initiales ni modifier la branche d'add-on installée
`feat/vaillant-rc-preview`.

## Correspondance

| Source | Composants | Rôle |
|---|---|---|
| PR #5, `faf7a577` | `custom_components/eebus/coordinator.py`, `streams.py`, tests | `NOT_FOUND` ré-enregistre le SKI au prochain poll sans invalider le canal ; supervise les workers streaming |
| PR #6, `16283f71` | `internal/eebus`, `app_test.go` | Watchdog : fenêtre bornée de découverte SPINE 10 min, sans exemption pour MPC/LPC annoncés |
| PR #8, `dcc0d18e` | Proto, stubs générés Go/Python, gRPC, diagnostics, tests | Inventaire SPINE **cache-only** de fonctions, mesures, contraintes, relations HVAC et labels HeatingZone |

**La PR #8 n'exécute pas de SPINE read active.** `not_cached` indique
une fonction lisible non disponible dans le cache actuel, pas une
indisponibilité définitive.

## Sécurité

- Ne pas démarrer une deuxième instance EEBUS sur les mêmes ports 4712/50051.
- Ne pas créer de nouvelle identité/certificat. Le Preview actuel protège
  `/data/serial` et `/data/certs` et ne les efface pas lors d'une MAJ
  du conteneur. Une sauvegarde complète de l'add-on est indispensable.
- Conserver `debug_events=false`, `ship_log=false` en première vérification.
- Pas de test actif d'écriture sur la consigne ou le mode chauffage.
- Ne pas publier les dumps de diagnostics sans relire les libellés de zone.
- Preview 0.18.1 et intégration 0.18.0 + patch #5 restent en service tant
  que le candidat n'a pas passé tests ET revue des empreintes OCI.

## Versions sans altérer l'add-on standard

- Add-on **Vaillant Preview** cible : `0.18.2` (candidat, pin digest OCI
  signé obligatoire avant bascule en version installable).
- Add-on standard : `0.18.0` **inchangé**.
- `custom_components/eebus/manifest.json` : `0.18.0` pour préserver
  la politique de version standard. Les fichiers Python du candidat sont
  distribués en **archive expérimentale distincte**, non via une release
  HACS générale. Les flux de release `v*` restent désactivés pour ce RC.

## Recette avant déploiement

1. CI combinée : Go vet + race, Python 3.14/3.15 Ruff/Mypy/pytest,
   tests gRPC cross-language, build binaire et ZIP de l'intégration.
2. Workflow image *candidat uniquement* : compilation container AMD64,
   smoke test, publication sous un tag unique lié au commit, signature
   keyless Cosign via GitHub OIDC, récupération du **digest SHA256 exact**.
3. Reporter ce digest figé dans le `Dockerfile` Preview ; adapter son
   `fetch-verified-preview.sh` à l'identité **exacte** du workflow
   de branche RC ; mettre le `config.yaml` du Preview à `0.18.2`.
4. Faire passer la validation de packaging du conteneur, avec
   `cosign verify` *avant* extraction du binaire. Aucun tag de release.
5. Lors d'une fenêtre de maintenance explicite, sauvegarder HA + add-on
   Preview (y compris données), noter la révision Go et le hash de
   `/data/serial` et du certificat **sans en exposer les contenus**.
   Sauvegarder aussi les fichiers Python avant mise à jour.
6. Installer d'abord le paquet Python compatible en conservant le patch #5,
   puis mettre à jour uniquement le Preview. Observer READY, stream
   `running=1, done=0`, révisions HA/bridge et l'inventaire.
7. **Rollback** : restaurer fichiers Python et add-on Preview 0.18.1 depuis
   sauvegarde préalable ou ancienne configuration/digest, en conservant
   exactement le répertoire `/data` et donc le SKI. Ne **jamais**
   réinstaller l'add-on standard en parallèle.

Aucune étape de ce document n'autorise un déploiement automatique.
