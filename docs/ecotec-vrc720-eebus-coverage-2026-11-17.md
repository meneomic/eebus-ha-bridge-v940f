# ecoTEC gaz + VRC 720 + VR 940f — couverture EEBUS exhaustive (17 novembre 2026)

## Objectif et méthode

Exposer dans Home Assistant **toutes les valeurs et commandes réellement
disponibles via EEBUS SHIP/SPINE**, en séparant :

- **Observé sur l'ecoTEC** : fonction annoncée dans le dump SPINE du 16/11/2026
  ou donnée présente dans les diagnostics Home Assistant.
- **Lu** : une valeur valide a effectivement traversé bridge → gRPC → HA.
- **Écriture annoncée** : opération `w` publiée par le périphérique ; cela ne
  remplace pas un test supervisé de commande.
- **Non annoncé** : absent du dump ecoTEC, ou use case `available=false`.
- **À investiguer** : données sous-jacentes / métadonnées non encore lues,
  données myVAILLANT **cloud** ou fonction négociée sans abonnement établi.

**Ne pas utiliser** `docs/vr940-function-inventory.md` comme inventaire de la
chaudière gaz : ce document concerne une **aroTHERM plus** (pompe à chaleur),
avec `HeatPumpAppliance`, `Compressor`, `DHWCircuit` et d'autres fonctions
qu'on n'a pas observées ici.

## Chaîne et stabilité vérifiées

- ecoTEC gaz, régulation sensoCOMFORT VRC 720, passerelle VR 940f.
- Home Assistant Core 2026.11.1, intégration EEBUS 0.18.0 avec correctifs
  Python de la PR #5 localement installés, bridge Vaillant Preview 0.18.1.
- Une seule instance SHIP 4712 / gRPC 50051, identité de pairing préservée.
- Diagnostic du soir 16/11 : `connected=true`, `room_heating=available`,
  `DEVICE_READINESS_READY`, `recovery.attempts=0`, `streams.primary.running=1`,
  `done=0`, `reconnects=0`, révisions HA/bridge = **108/108**
  (progression confirmée depuis 95/95), événements perdus = 0.
- PR #5 : durcissement reconnexion HA ; PR #6 : période bornée de découverte
  pour watchdog Go. **La PR #6 n'est pas déployée**. Ne pas fusionner ou
  redémarrer la chaudière dans le cadre d'une collecte read-only.

## Inventaire d'entités SPINE observées (dump 16/11, adresses relatives)

| Adresse | EntityType | Fonctions pertinentes |
|---|---|---|
| `0` | DeviceInformation | NodeManagement/special, DeviceClassification/server |
| `1`, `2` | CEM | Generic/client (aucune télémétrie serveur de chaudière) |
| `3` | HeatingCircuit | DeviceClassification/server |
| `3:1` | HeatingZone | DeviceClassification/server |
| `3:1:1` | HVACRoom | Measurement/server (`3:1:1:11`), Setpoint/server (`3:1:1:18`), HVAC/server (`3:1:1:9`), DeviceClassification/server (`3:1:1:4`) |
| `4` | TemperatureSensor | Measurement/server (`4:11`) |

**Fonctions d'écriture signalées sur l'ecoTEC :** `setpointListData` et
`hvacSystemFunctionListData`, toutes deux sur `3:1:1`. Il n'y a pas de
preuve d'autres fonctions `write` dans le dump fourni. Ce n'est pas un
permis de tester automatiquement une consigne ou un mode.

## Couverture Home Assistant — mesurée et actionnable

| Information / commande | Source SPINE | Statut actuel | Étape suivante |
|---|---|---|---|
| Température ambiante RDC | MRT, HVACRoom/Measurement | **Lue** (19 puis 20 °C) | Préserver fraîcheur et unités |
| Température extérieure | MOT, TemperatureSensor/Measurement | **Lue** (9 puis 7,5 °C) | Préserver fraîcheur et unités |
| Consigne chauffage | CRHT, HVACRoom/Setpoint | **Lue, écriture annoncée** (18 °C, 5–30 °C, pas 0,5 °C) | Test d'écriture réversible **supervisé** seulement |
| Mode chauffage | CRHSF/MRHSF, HVACRoom/HVAC | **Lu, écriture annoncée** (auto/on/off) | Valider sémantique VRC 720 Prog./Manuel/Off |
| Nom de zone | DeviceClassification/userData sur HeatingZone | **Lu auparavant : « Rdc »**, puis `null` après reload HA | P1 : diagnostiquer disparition, stabiliser métadonnée sans inventer de label |
| Données de classification / modèle | DeviceInformation/DeviceClassification | Fonction annoncée, **`device_info=null`** | P1 : lecture/cache réessayable avec limites, sans identifier le propriétaire |
| Contraintes et relations HVAC/consigne | Description / relation Setpoint, HVAC | Fonctions lisibles annoncées | P2 : exposer relations dans diagnostics avant création d'entités |
| Autres mesures sur `HVACRoom`/`TemperatureSensor` | `measurementDescriptionListData` et valeurs | **Deux valeurs prouvées** (pièce/ext.) | P1 : inventaire descriptif de chaque measurement ID, scope, unité, état de lecture |
| ECS : température/consigne/mode/boost | DHWCircuit absent, DHW use cases non annoncés | **Non exposé dans la capture** | Ne pas créer de commandes ECS factices ; surveiller évolution de firmware |
| État brûleur / `hvac_action`, pression d'eau, codes défaut | Aucune fonction serveur correspondante prouvée | **Non confirmé EEBUS** | Comparer séparément à myVAILLANT/eBUS, ne pas imputer au bridge |
| Températures départ/retour, courbe de chauffe, débit gaz/énergie gaz | Aucune valeur présente dans diagnostics | **Non confirmé EEBUS** | Recenser chaque description SPINE ; ne pas inférer de courbe, de puissance ou de pression |
| LPC/MPC, heartbeat distant, OHPCF/compresseur | Capabilities `unsupported/remote_not_advertised` | **Non annoncé** pour cet appareil | Pas d'entités de contrôle charge ni de pseudo-compresseur gaz |
| Flux d'énergie réseau (MGCP), PV (VAPD), batterie (VABD) | CEM Generic/client + use cases consumer `available=true` | **Advertisés côté consommation**, pas de preuve d'abonnement | P3 optionnel : tester binding + `subscribe` après app commissioning ; ne pas promettre optimisation d'une chaudière gaz |

Les chaînes `room_heating=available`, `monitoring=unsupported`, et
`dhw=unsupported` viennent des diagnostics de la **chaudière ecoTEC** :
les entités HA génériques du fork ne prouvent aucune capacité du matériel.

## Cas d'usage du dump SPINE ecoTEC (16 novembre)

- **Observés disponibles** : CRHT (configurationOfRoomHeatingTemperature),
  CRHSF (configurationOfRoomHeatingSystemFunction), MRT, MOT, MRHSF,
  MGCP (monitoringOfGridConnectionPoint), VAPD, VABD.
- **Observés non disponibles** : trois déclarations
  `visualizationOfHeatingAreaName` (HeatingCircuit/HeatingZone/HVACRoom).
  Cela n'empêche pas une lecture directe
  `deviceClassificationUserData` si ce droit est annoncé.
- **Absents sur ce profil** : DHW use cases, MPC, LPC, OHPCF,
  un compresseur ou une entité HeatPumpAppliance.

L'acteur dans le `nodeManagementUseCaseData` est celui du **VR 940f** :
pour MGCP/VAPD/VABD, il se présente comme **consommateur** de données
énergétiques externes. Cela ne prouve pas qu'il les réclamera, les affichera
ni qu'il modifiera le chauffage gaz en réponse.

## Différence avec les API cloud et le bus eBUS

Les intégrations myVAILLANT/mypyllant peuvent montrer des entités de chaudière :
pression circuit, température départ/consigne départ, courbe de chauffe,
état chauffage, défauts, ECS, énergie gaz. Ces données ne deviennent pas
automatiquement disponibles sur l'interface **EEBUS** du VR 940f.

**Échelle de preuve** : un champ en cloud n'est pas une fonction SPINE,
une fonction SPINE `r` n'est pas une valeur, et un `w` annoncé n'est
pas une commande vérifiée. Si une valeur importante reste absente après
une véritable capture des descriptions et des lectures, documenter la
limite EEBUS puis évaluer eBUS/ebusd comme source complémentaire,
indépendamment de la connexion EEBUS existante.

## Plan de travail — petites PR testables

1. **P1 : audit read-only des Measurement server** sur `HVACRoom` et
   `TemperatureSensor`, incluant description, scope, unité, état de cache,
   provenance et fraîcheur, sans appeler de méthode d'écriture. Pas de nouveau
   capteur tant qu'une valeur n'est pas mesurée et identifiée.
2. **P1 : DeviceClassification** pour stabiliser les noms et lire les
   métadonnées de chaudière/zone réellement disponibles ; vérifier le `Rdc → null`
   après rechargement HA. Rejouer une lecture uniquement lorsqu'elle est
   annoncée `r`, avec retry borné.
3. **P2 : relations HVAC/Setpoint** pour exposer les modes et limites exacts
   et préparer un support multi-zone seulement si plusieurs HVACRoom sont
   découverts. Écriture contrôlée et réversible, jamais automatique.
4. **P3 : flux HA → Vaillant MGCP/VAPD/VABD** si le VR 940f accepte les
   abonnements ; utiliser SolarEdge et le compteur réseau existants, mais
   mesurer le bénéfice réel avant de vendre cela comme optimisation.
5. **P4 : couche de données non-EEBUS**, uniquement pour les informations
   réellement absentes de SPINE ; pas de fusion implicite de sources.

## Critères de recette

- Comparaison fonction par fonction au dump de l'ecoTEC, et non à l'aroTHERM.
- `READY`, aucune perte d'événement, `streams.primary.running=1` ;
  maintenir une possibilité de rollback avant chaque changement d'add-on.
- Toute nouvelle lecture rapporte `entity/type/function/measurement ID/unit`
  et distingue `not advertised`, `not requested`, `timeout`,
  `unavailable` et `valid read`.
- Aucun certificat, SKI complet, serial, token, nom personnel, ou donnée
  de sécurité n'est publié dans GitHub ; artefacts de capture relus/redigés.
- Ne jamais modifier la chaudière, la régulation ni les consignes
  pendant une capture ou un test non expressément autorisé.
- Tester avant de fusionner ; l'installation actuelle reste la référence
  stable jusqu'à validation matérielle.

## Références

- `docs/ecotec-vrc720-observed-2026-11-15.md` (baseline matériel et cloud).
- Journal `[DISCOVERY]` ecoTEC collecté le 16/11/2026 dans le suivi du projet
  (à conserver comme artefact expurgé lors de la prochaine capture).
- Diagnostics Home Assistant EEBUS du 16/11/2026, avant/après PR #5.
- Manuel Vaillant EEBUS `0020257203_07`, §1.3.4, VRC 720 :
  https://www.vaillant.de/api/download/document/de/1383775.pdf
- `docs/vr940-function-inventory.md` : **autre matériel**, aroTHERM ;
  utile seulement pour comparer les surfaces EEBUS.
