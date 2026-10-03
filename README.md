# Registre des contributions — Apport Commun

Ce dépôt contient le **registre public des contributions validées** du projet Apport Commun.

Une contribution validée = **un fichier**. Le fichier est à la fois l'enregistrement officiel et le reçu remis au membre.

---

## Pourquoi ce dépôt existe

Le registre est la **source de vérité** du projet. Tout le reste en est dérivé : l'annuaire des contributeurs, les reçus, les unités accumulées, et — le moment venu — la distribution du jeton.

Trois propriétés sont recherchées, dans cet ordre :

1. **Vérifiable** — n'importe qui peut contrôler qu'une entrée n'a pas été modifiée, sans faire confiance au projet.
2. **Portable** — un clone de ce dépôt suffit à reconstituer l'intégralité du registre. Aucun service en ligne n'est nécessaire pour le lire.
3. **Non réécrite** — une entrée validée n'est jamais modifiée. Les corrections passent par un champ `amendements` qui conserve l'ancienne et la nouvelle valeur.

## Organisation

```
bareme/          barème en vigueur pour chaque période (versionné, jamais modifié)
registre/        les contributions validées, une par fichier
  2026/10/APP-202610-001.md
outils/          le contrôleur automatique
```

Le chemin encode la date de validation, le nom encode l'identifiant :

| Segment | Signification |
|---|---|
| `APP` | Préfixe du projet |
| `AAAAMM` | Année et mois de **validation** |
| `NNN` | Numéro séquentiel dans le mois |

## Règles non négociables

| Règle | Raison |
|---|---|
| **Aucune donnée personnelle** — pseudonymes uniquement | Le dépôt est public et réplicable. Une donnée personnelle qui y entre ne peut plus en sortir |
| **Jamais d'adresse IP ni d'empreinte d'appareil** | Le contrôle anti-Sybil produit une décision avant l'inscription, pas une donnée conservée ici |
| **Aucune entrée modifiée après validation** | On amende, on ne réécrit pas. Un registre réécrivable ne prouve rien |
| **Les unités ne sont jamais recalculées** | Elles sont attachées au barème du jour de la validation |
| **Un commit par entrée** | L'historique du dépôt devient la chronologie du projet |
| **Aucun secret dans le dépôt** | Ni clé, ni mot de passe, ni jeton d'accès |

## Contrôler une entrée

Sans rien installer, avec Python 3.8 ou plus récent :

```bash
python outils/valider.py                    # contrôle toutes les entrées
python outils/valider.py registre/2026/10/APP-202610-001.md
python outils/valider.py --auto-test        # jeu d'essai, n'écrit rien dans le registre
```

Le contrôleur vérifie la formule des unités, l'indice de contribution, les bornes des coefficients, le nombre de validateurs, les conflits d'intérêts, le format et l'unicité des identifiants, la cohérence du chemin et des dates, la présence d'une empreinte pour chaque preuve, l'existence du barème référencé, et — si le dépôt est un dépôt Git — qu'une entrée déjà validée n'a pas été modifiée hors `amendements`.

**Une entrée qui échoue au contrôle n'est pas publiée.**

## Vérifier un reçu

Un reçu est un fichier d'entrée précédé d'un en-tête de vérification. Pour contrôler qu'un reçu correspond bien au registre :

```bash
git hash-object registre/2026/10/APP-202610-001.md
```

L'empreinte obtenue doit être identique à celle inscrite dans l'en-tête du reçu. Si elle diffère, le reçu a été altéré — ou ne correspond à aucune entrée du registre.

Cette vérification ne demande **aucun accès au dépôt** et **aucune confiance dans le projet** : c'est le seul mécanisme du dispositif qui fonctionne entièrement hors ligne.

## Ajouter une contribution

Le cycle complet, en sept étapes, est décrit dans :

> `04-operationnel/registre-modele.md` — section « Ajouter une contribution »

En résumé : déclaration → contrôle anti-Sybil → validation à **2 voix sur 3** → création de l'entrée → contrôle automatique → publication (un commit) → envoi du reçu au membre.

## Documents de référence

Ces documents vivent dans le dépôt documentaire du projet (`jeton-communautaire/`), pas ici. Ce dépôt ne contient que des données et les outils pour les contrôler.

| Sujet | Document |
|---|---|
| Schéma des données, champs, contrôles | `04-operationnel/registre-schema.md` |
| Fichier type, cycle d'ajout, réplication | `04-operationnel/registre-modele.md` |
| Qui valide, et selon quelle règle | `03-gouvernance/validation-contributions.md` |
| Points et coefficients | `02-tokenomics/preuve-de-contribution.md` |
| Pourquoi rien de personnel ici | `05-juridique/rgpd-donnees-personnelles.md` |

## État du registre

| Élément | État |
|---|---|
| Schéma des données | v1 — figé pour les entrées à venir |
| Barème en vigueur | `2026-10` |
| Entrées publiées | **0** — le registre n'a pas encore reçu sa première contribution |
| Contrôleur automatique | `outils/valider.py` — opérationnel, auto-testé (11 cas) |
| Archive complète (bundle) | **Créée et vérifiée** — `registre-apport-commun.bundle` |
| Dépôt distant (GitHub) | **Non configuré** — clé SSH à enregistrer sur le compte |
| Ancrage externe | **Non mis en place** — à décider avant la 10ᵉ entrée |
| Second clone de réplication | **Non désigné** — à désigner avant la 10ᵉ entrée |

Les deux dernières lignes sont les seules protections contre la réécriture de l'historique. Tant qu'elles ne sont pas en place, l'immuabilité du registre est une intention, pas une propriété.

## Sauvegarde et restauration

### Le bundle — archive complète, vérifiable

`registre-apport-commun.bundle` est un **fichier unique contenant l'intégralité du dépôt** : tous les commits, tous les fichiers, toutes les branches. C'est la sauvegarde à copier hors de la machine.

```bash
# Vérifier que l'archive est complète et intacte
git bundle verify registre-apport-commun.bundle

# Restaurer le registre à partir de l'archive, sur n'importe quelle machine
git clone registre-apport-commun.bundle registre-restaure
```

**À régénérer après chaque nouvelle entrée publiée** :

```bash
git bundle create registre-apport-commun.bundle --all
```

L'archive n'est jamais versionnée dans le dépôt (elle est dans `.gitignore`) : c'est un artefact dérivé, pas une donnée du registre.

### Pourquoi le bundle plutôt qu'un simple clone

Un clone suffit à répliquer, mais il transporte une arborescence de travail et des fichiers internes. Le bundle est **un seul fichier** : plus simple à copier sur un disque, à envoyer, à archiver, et **Git sait le vérifier** — `git bundle verify` répond « complete history » ou refuse le fichier. Une sauvegarde que l'outil lui-même valide vaut mieux qu'une copie dont on espère qu'elle est complète.

### Le test à faire une fois par trimestre

1. Créer un dossier vide ailleurs sur la machine.
2. Restaurer depuis le bundle : `git clone <bundle> registre-test`
3. Lancer le contrôleur sur la copie restaurée : `python outils/valider.py`
4. Vérifier que toutes les entrées passent.
5. Supprimer le dossier de test.

**Une sauvegarde jamais restaurée n'est pas une sauvegarde.** Ce test a déjà été effectué une fois : l'arborescence complète a été récupérée depuis le bundle et le contrôleur a validé l'entrée restaurée.

## Licence et réutilisation

Le registre est public. Les contributions qui y figurent appartiennent à leurs auteurs. Toute réutilisation doit citer l'identifiant de l'entrée et sa date de validation.
