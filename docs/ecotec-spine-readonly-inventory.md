# Diagnostics SPINE en lecture seule — ecoTEC + VRC 720 + VR 940f

Ce changement ajoute `spine_inventory` au résultat `GetDeviceDiagnostics`,
ainsi qu'à l'export de diagnostics de Home Assistant. Il ne change aucune
entité HA et ne lance aucun RPC de commande vers la chaudière.

## Inventaire publié

- Chaque entité (adresse et type) et sa liste des fonctions déclarées.
- Pour chaque fonction : adresse et type de feature, droits SPINE `r/rp/w/wp`,
  et `cache_state`.
- Les caches allowlistés `Measurement/*`, `Setpoint/*`, `HVAC/*`
  sont sérialisés en JSON, sans transformation sémantique. Cela donne les
  descriptions, ID, scopes, unités, valeurs, contraintes et relations **si
  ces données ont réellement été reçues et mises en cache**.
- La donnée `deviceClassificationUserData.userLabel` des HeatingCircuit,
  HeatingZone et HVACRoom est extraite isolément et sans `UserNodeIdentification`.
- Le `zone_label` déjà mémorisé dans le registre est inclus séparément.

## Interprétation importante

`cached` = reçu et présent en cache. **Ce n'est pas une lecture fraîche
faite au moment de télécharger les diagnostics.**

`not_cached` = la fonction est annoncée comme lisible mais son contenu
n'est pas en cache ; cela **ne prouve ni absence de capacité ni erreur**.
`skipped_sensitive` = fonction volontairement exclue pour éviter d'exporter
NodeManagement, les séries d'appareils et des données non autorisées.
`not_readable` = lecture non annoncée. `invalid_cache_data` et
`oversized` signalent un problème de sérialisation/limite (32 KiB par
fonction). Le résultat est borné à 32 entités et 256 fonctions.

Les libellés utilisateurs figurent dans le diagnostic HA ; **ne pas publier
un diagnostic brut** sans revue. Le SKI complet, les séries et les certificats
ne sont pas inclus dans la réponse Go.

## Compatibilité

- Nouvelle capacité : `FEATURE_SPINE_READONLY_INVENTORY` (7).
- Le champ `DeviceOperationalDiagnostics.spine_inventory = 10` est additif.
- Un bridge plus ancien n'envoie pas ce champ : le diagnostic retourne
  `spine_inventory: null` sans impact sur les entités, les streams ou
  les commandes existants.
- Aucune capture ne se produit tant que l'intégration HA n'a pas demandé les
  diagnostics, qui sont déjà limités aux clients ayant `FEATURE_OPERATIONAL_DIAGNOSTICS`.

## Étapes suivantes

Une fois une version expérimentale testée sur l'installation, inspecter les
entrées `not_cached` avant d'envisager des **demandes SPINE read-only
explicites et bornées**. Cette PR ne prétend pas extraire de nouvelles
mesures si les données n'ont jamais été transmises par la VR 940f.
Ne pas redémarrer la chaudière ou effacer le pairing pour ce test.
