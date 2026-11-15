# Capture des fonctions EEBUS — ecoTEC + VRC 720 + VR 940f

## But et état constaté

L'installation est appairée et contrôle localement le chauffage RDC via EEBUS,
mais l'export de diagnostics du 15 novembre 2026 indique seulement la
capacité `room_heating=available`. `dhw=unsupported` porte la raison
`remote_not_advertised`. Le journal de l'add-on amont montre des récupérations
`monitoring recovery: stale` et `EEBUS debug_events=false`.
Il ne contient **aucune** ligne `[DISCOVERY]`.

On souhaite capturer l'inventaire SPINE réel (entités, fonctionnalités,
fonctions, opérations `r/rp/w/wp` et cas d'usage) sans modifier les commandes
de chauffage, la connexion cloud existante ni l'identité EEBUS.

## Règles de sécurité

1. **Ne pas installer un deuxième bridge en parallèle.** L'add-on utilise
   le réseau de l'hôte avec SHIP TCP 4712 et gRPC 127.0.0.1:50051.
   Deux processus provoqueraient des conflits de ports et de sessions.
2. **Ne pas désinstaller l'add-on existant.** Son stockage `/data`
   contient l'identité SHIP, les certificats et le numéro de série; une
   désinstallation peut les supprimer.
3. **Ne pas importer de clef privée ni de sauvegarde complète dans GitHub.**
   Ne jamais mettre `cert.pem`, `key.pem`, `serial`, jetons ou sauvegardes
   de Home Assistant dans un dépôt ou dans une conversation.
4. La branche GitHub change uniquement l'interface de configuration de
   l'add-on : **ces options ne sont PAS présentes sur l'add-on amont en cours**.
   L'add-on du fork a une identité Supervisor distincte et donc un `/data`
   distinct : installer seulement la version du fork **ne conserve pas**
   automatiquement l'appairage.
5. Ne jamais tester une fonction déclarée `w` ou `wp` automatiquement :
   ce sont des permissions annoncées, pas une autorisation de commande.

## Préparation avant toute interruption

- Confirmer un fonctionnement chauffage stable et sauvegarder les consignes.
- Créer une sauvegarde Home Assistant complète, puis un snapshot Proxmox de la
  VM 104 avec un nom explicite et une stratégie de restauration testée.
- Identifier précisément l'ID de l'add-on installé, son emplacement des
  données et le mécanisme de restauration de **la même** identité SHIP.
  Utiliser des commandes de lecture seule pour cette inspection.
- Confirmer que la sauvegarde contient les données de l'add-on : certificat,
  clé et serial. **Vérifier la présence, ne jamais en afficher le contenu.**
- Préparer un mécanisme de rollback : redémarrage immédiat de l'add-on
  d'origine et contrôle de `room_heating` dans HA.

**Gate bloquant :** ne pas exécuter une migration de l'add-on du fork avant
d'avoir vérifié les chemins d'accès, sauvegardes et capacités de restauration
sur **ce** Home Assistant OS. Les commandes de copie dépendent de
l'environnement Supervisor exact; aucun chemin de stockage n'est supposé ici.

## Capture envisagée après validation du gate

1. Arrêter proprement le bridge existant, sans supprimer l'add-on ni ses données.
2. Lancer **un seul** bridge diagnostique en conservant exactement le certificat
   et le serial, avec `debug_events: true` et éventuellement
   `ship_log: true`; `ship_trace` reste désactivé.
3. Surveiller le rétablissement de la connexion à la VR 940f. Dans les journaux,
   conserver les lignes `[DISCOVERY]` ainsi que les événements SHIP utiles.
4. Arrêter le bridge diagnostique et restaurer le bridge stable à l'issue de
   la collecte. Vérifier la présence des capteurs / du contrôle chauffage.
5. Sur un PC (hors ligne), produire un rapport non confidentiel :

   ```bash
   python3 scripts/spine_inventory.py bridge.log --output spine-report.md
   python3 scripts/spine_inventory.py bridge.log --format json --output spine-report.json
   ```

6. Ne partager que le rapport relu; vérifier si les labels et descriptions
   contiennent des noms personnels.

## Analyse et critères d'acceptation

- Comparer le rapport à l'inventaire d'une **aroTHERM** existant dans
  `docs/vr940-function-inventory.md`, sans supposer des capacités identiques.
- Classer chaque fonction comme **annoncée / effectivement lisible /
  effectivement commandable / non disponible / non vérifiée**.
- Pour créer un capteur HA, exiger un résultat lisible et une unité mesurée
  conforme, ainsi qu'un comportement de fraîcheur documenté.
- Pour une commande, exiger une vérification distincte de sécurité et un
  essai supervisé réversible.
- Si pression, état brûleur ou températures de départ/retour n'apparaissent
  pas, envisager le bus **eBUS** séparément au lieu d'inventer des données.

## Hors périmètre

- Dépendance de fonctionnement hors Internet de la VR 940f.
- Modification de la chaudière/gaz, des paramètres de sécurité, de la
  régulation Vaillant ou des automatisations Home Assistant.
- Validation matérielle ou déploiement de la branche du fork.

Ce document est un plan de travail; **aucune collecte ni migration live n'a
encore été exécutée**.
