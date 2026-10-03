#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validateur du registre des contributions — Apport Commun.

Contrôle automatique d'une entrée de registre, conformément à
04-operationnel/registre-schema.md (contrôles 1 à 8 et 11).

Usage :
    python outils/valider.py                    # contrôle toutes les entrées
    python outils/valider.py registre/2026/10/APP-202610-001.md
    python outils/valider.py --auto-test        # jeu d'essai, sans écrire dans le registre

Dépendances : aucune. Bibliothèque standard uniquement.
Code de sortie : 0 si tout est conforme, 1 sinon.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

COEFF_QUALITE = (0.5, 1.5)
COEFF_RARETE = (0.8, 1.5)
COEFF_PLAFOND = {1.0, 0.5}
TOLERANCE = 0.01

CHAMPS_OBLIGATOIRES = [
    "id", "schema", "statut", "declaree_le", "validee_le", "contributeur",
    "action", "resume", "preuves", "parrains", "validateurs",
    "bareme_version", "points_base", "coefficient_qualite",
    "coefficient_rarete", "coefficient_plafond", "unites", "indice",
    "contestation",
]
CHAMPS_FACULTATIFS = {"amendements"}
STATUTS = {"validee", "contestee", "annulee"}

RE_ID = re.compile(r"^([A-Z]{2,6})-(\d{4})(\d{2})-(\d{3})$")
RE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RE_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")


# --------------------------------------------------------------------------
# Lecture du fichier
# --------------------------------------------------------------------------

def lire_entree(chemin):
    with open(chemin, "r", encoding="utf-8") as f:
        texte = f.read()
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", texte, re.S)
    if not m:
        raise ValueError("bloc d'en-tete manquant ou mal ferme (--- au debut et --- seul sur une ligne)")
    return analyser_entete(m.group(1))


def analyser_entete(bloc):
    """Analyse le bloc d'en-tete. Gere les listes simples, les listes d'objets
    en tirets et les listes en ligne [a, b]."""
    donnees = {}
    cle_courante = None
    objet_courant = None
    for brut in bloc.splitlines():
        if not brut.strip() or brut.lstrip().startswith("#"):
            continue
        indent = len(brut) - len(brut.lstrip(" "))
        ligne = brut.strip()

        if indent == 0 and ":" in ligne:
            cle, _, valeur = ligne.partition(":")
            cle = cle.strip()
            valeur = valeur.strip()
            if valeur == "":
                donnees[cle] = [] if cle != "indice" else {}
                cle_courante = cle
                objet_courant = None
            else:
                donnees[cle] = valeur
                cle_courante = None
                objet_courant = None
            continue

        if cle_courante is None:
            continue

        if ligne.startswith("- "):
            contenu = ligne[2:].strip()
            if ":" in contenu:
                c, _, v = contenu.partition(":")
                objet_courant = {c.strip(): v.strip()}
                donnees[cle_courante].append(objet_courant)
            else:
                donnees[cle_courante].append(contenu)
                objet_courant = None
            continue

        if ":" in ligne and objet_courant is not None:
            c, _, v = ligne.partition(":")
            objet_courant[c.strip()] = v.strip()
            continue

        if ":" in ligne and isinstance(donnees.get(cle_courante), dict):
            c, _, v = ligne.partition(":")
            donnees[cle_courante][c.strip()] = v.strip()

    for cle in list(donnees):
        v = donnees[cle]
        if isinstance(v, str) and v.startswith("[") and v.endswith("]"):
            interieur = v[1:-1].strip()
            donnees[cle] = [x.strip().strip('"').strip("'") for x in interieur.split(",") if x.strip()]
    return donnees


def nombre(valeur):
    if valeur is None:
        return None
    if isinstance(valeur, (int, float)):
        return float(valeur)
    t = str(valeur).strip().strip('"').strip("'").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


# --------------------------------------------------------------------------
# Contrôles
# --------------------------------------------------------------------------

def controler(chemin, donnees, tous_les_ids):
    erreurs = []

    def err(num, message):
        erreurs.append(f"[controle {num}] {message}")

    # 9 — champs obligatoires et champs inconnus
    for champ in CHAMPS_OBLIGATOIRES:
        if champ not in donnees:
            err(9, f"champ obligatoire absent : {champ}")
    for champ in donnees:
        if champ not in CHAMPS_OBLIGATOIRES and champ not in CHAMPS_FACULTATIFS:
            err(9, f"champ inconnu : {champ}")

    if "schema" in donnees and str(donnees["schema"]).strip() != "1":
        err(9, f"version de schema inconnue : {donnees['schema']} (attendu : 1)")

    if "statut" in donnees and str(donnees["statut"]).strip() not in STATUTS:
        err(9, f"statut invalide : {donnees['statut']}")

    # 3 — bornes des coefficients
    cq = nombre(donnees.get("coefficient_qualite"))
    cr = nombre(donnees.get("coefficient_rarete"))
    cp = nombre(donnees.get("coefficient_plafond"))
    pb = nombre(donnees.get("points_base"))
    un = nombre(donnees.get("unites"))

    if cq is None:
        err(3, "coefficient_qualite illisible")
    elif not (COEFF_QUALITE[0] - 1e-9 <= cq <= COEFF_QUALITE[1] + 1e-9):
        err(3, f"coefficient_qualite hors bornes : {cq} (attendu 0,5 a 1,5)")
    if cr is None:
        err(3, "coefficient_rarete illisible")
    elif not (COEFF_RARETE[0] - 1e-9 <= cr <= COEFF_RARETE[1] + 1e-9):
        err(3, f"coefficient_rarete hors bornes : {cr} (attendu 0,8 a 1,5)")
    if cp is None:
        err(3, "coefficient_plafond illisible")
    elif cp not in COEFF_PLAFOND:
        err(3, f"coefficient_plafond invalide : {cp} (attendu 1.0 ou 0.5)")

    # 1 — formule des unites
    if None not in (pb, cq, cr, cp, un):
        attendu = pb * cq * cr * cp
        if abs(attendu - un) > TOLERANCE:
            err(1, f"unites incoherentes : {un} declare, {round(attendu, 4)} calcule "
                   f"({pb} x {cq} x {cr} x {cp})")
        if un < 0:
            err(1, "unites negatives")

    # 2 — indice
    indice = donnees.get("indice")
    if not isinstance(indice, dict):
        err(2, "bloc indice absent ou mal forme")
    else:
        c, v, e = (nombre(indice.get(k)) for k in ("c", "v", "e"))
        i = nombre(indice.get("i"))
        for nom, val in (("c", c), ("v", v), ("e", e)):
            if val is None or not (0 <= val <= 100):
                err(2, f"indice.{nom} hors bornes (attendu 0 a 100) : {indice.get(nom)}")
        if None not in (c, v, e, i):
            attendu_i = 0.55 * c + 0.25 * v + 0.20 * e
            if abs(attendu_i - i) > 0.05:
                err(2, f"indice.i incoherent : {i} declare, {round(attendu_i, 2)} calcule")

    # 4 — nombre de validateurs (regime 2 voix sur 3 en phase 0)
    validateurs = donnees.get("validateurs")
    if not isinstance(validateurs, list) or len(validateurs) < 2:
        err(4, f"au moins 2 validateurs requis (trouve : "
               f"{len(validateurs) if isinstance(validateurs, list) else 0})")
        validateurs = validateurs if isinstance(validateurs, list) else []
    for idx, val in enumerate(validateurs, 1):
        if not isinstance(val, dict):
            err(4, f"validateur {idx} mal forme")
            continue
        for champ in ("pseudo", "role", "note_qualite", "justifie_le"):
            if champ not in val:
                err(4, f"validateur {idx} : champ {champ} manquant")
        nq = nombre(val.get("note_qualite"))
        if nq is None or not (COEFF_QUALITE[0] - 1e-9 <= nq <= COEFF_QUALITE[1] + 1e-9):
            err(4, f"validateur {idx} : note_qualite hors bornes ({val.get('note_qualite')})")
        if val.get("justifie_le") and not RE_DATE.match(str(val["justifie_le"])):
            err(4, f"validateur {idx} : justifie_le au format AAAA-MM-JJ attendu")

    # 5 — conflits d'interets
    contributeur = str(donnees.get("contributeur", "")).strip()
    parrains = donnees.get("parrains")
    parrains = parrains if isinstance(parrains, list) else []
    parrains = [str(p).strip() for p in parrains]
    pseudos_val = [str(v.get("pseudo", "")).strip() for v in validateurs if isinstance(v, dict)]

    if not contributeur:
        err(5, "contributeur vide")
    for idx, p in enumerate(pseudos_val, 1):
        if p and p == contributeur:
            err(5, f"le validateur {idx} ({p}) est le contributeur lui-meme")
        if p and p in parrains:
            err(5, f"le validateur {idx} ({p}) est aussi parrain de la contribution")
    if len(set(pseudos_val)) != len(pseudos_val):
        err(5, "un meme validateur apparait deux fois")
    if len(set(parrains)) != len(parrains):
        err(5, "un meme parrain apparait deux fois")

    # 6 — nombre de parrains
    if len(parrains) < 1:
        err(6, "au moins 1 parrain requis")

    # 7 — format et unicite de l'identifiant
    ident = str(donnees.get("id", "")).strip()
    m = RE_ID.match(ident)
    if not m:
        err(7, f"identifiant mal forme : {ident} (attendu PREFIXE-AAAAMM-NNN)")
    elif ident in tous_les_ids:
        err(7, f"identifiant deja present dans le registre : {ident}")

    # 8 — coherence identifiant / chemin / date de validation
    if m:
        prefixe, annee, mois = m.group(1), m.group(2), m.group(3)
        morceaux = os.path.normpath(chemin).split(os.sep)
        if len(morceaux) >= 3:
            if morceaux[-2] != mois or morceaux[-3] != annee:
                err(8, f"chemin {os.sep.join(morceaux[-3:])} incoherent avec l'identifiant "
                       f"{annee}/{mois}")
            if morceaux[-1] != ident + ".md":
                err(8, f"nom de fichier {morceaux[-1]} different de l'identifiant {ident}.md")
        validee = str(donnees.get("validee_le", "")).strip()
        if validee and re.match(r"^\d{4}-\d{2}-\d{2}$", validee):
            if validee[:4] != annee or validee[5:7] != mois:
                err(8, f"validee_le ({validee}) hors du mois de l'identifiant ({annee}-{mois})")

    # 8 bis — dates et preuves
    for champ in ("declaree_le", "validee_le"):
        valeur = str(donnees.get(champ, "")).strip()
        if valeur and not RE_DATE.match(valeur):
            err(8, f"{champ} au format AAAA-MM-JJ attendu (trouve : {valeur})")
    declaree = str(donnees.get("declaree_le", "")).strip()
    validee = str(donnees.get("validee_le", "")).strip()
    if RE_DATE.match(declaree) and RE_DATE.match(validee):
        if dt.date.fromisoformat(validee) < dt.date.fromisoformat(declaree):
            err(8, "validee_le anterieure a declaree_le")

    preuves = donnees.get("preuves")
    if not isinstance(preuves, list) or not preuves:
        err(8, "au moins une preuve requise")
    else:
        for idx, p in enumerate(preuves, 1):
            if not isinstance(p, dict) or not p.get("url"):
                err(8, f"preuve {idx} : url manquante")
                continue
            sha = p.get("sha256")
            if not sha:
                err(8, f"preuve {idx} : sha256 manquant (obligatoire pour une preuve "
                       f"en ligne, impossible a verifier sans lui)")
            elif not RE_SHA256.match(str(sha).strip()):
                err(8, f"preuve {idx} : sha256 mal forme (64 caracteres hexadecimaux attendus)")

    # 11 — bareme existant et entree non modifiee
    bareme = str(donnees.get("bareme_version", "")).strip()
    if bareme:
        chemin_bareme = os.path.join(RACINE, "bareme", f"{bareme}.md")
        if not os.path.exists(chemin_bareme):
            err(11, f"bareme_version {bareme} sans fichier bareme/{bareme}.md")
    erreurs.extend(controler_immutabilite(chemin))

    return erreurs


def controler_immutabilite(chemin):
    """Controle 11 — une entree deja validee ne peut evoluer que par 'amendements'."""
    try:
        rel = os.path.relpath(chemin, RACINE).replace(os.sep, "/")
        commits = subprocess.run(
            ["git", "log", "--format=%H", "--", rel],
            cwd=RACINE, capture_output=True, text=True, timeout=20,
        )
        if commits.returncode != 0:
            return []
        lignes = [l for l in commits.stdout.splitlines() if l.strip()]
        if len(lignes) <= 1:
            return []  # cree une seule fois : rien a comparer
        premier = lignes[-1]
        diff = subprocess.run(
            ["git", "diff", f"{premier}..HEAD", "--", rel],
            cwd=RACINE, capture_output=True, text=True, timeout=20,
        )
        if diff.returncode != 0 or not diff.stdout.strip():
            return []
        champs_touches = set()
        for ligne in diff.stdout.splitlines():
            if ligne.startswith(("+", "-")) and not ligne.startswith(("+++", "---")):
                contenu = ligne[1:].strip()
                if ":" in contenu:
                    champs_touches.add(contenu.split(":", 1)[0].strip())
        hors_amendements = {c for c in champs_touches if c != "amendements"}
        if hors_amendements:
            return [f"[controle 11] entree modifiee hors 'amendements' : "
                    f"{', '.join(sorted(hors_amendements))}"]
    except (subprocess.SubprocessError, OSError):
        return []
    return []


# --------------------------------------------------------------------------
# Parcours et execution
# --------------------------------------------------------------------------

def lister_entrees(depart=None):
    base = os.path.join(RACINE, "registre") if depart is None else depart
    trouvees = []
    for dossier, _, fichiers in os.walk(base):
        for f in sorted(fichiers):
            if f.startswith("APP-") and f.endswith(".md"):
                trouvees.append(os.path.join(dossier, f))
    return sorted(trouvees)


def controler_fichier(chemin, tous_les_ids):
    try:
        donnees = lire_entree(chemin)
    except Exception as exc:  # noqa: BLE001
        return [f"[lecture] {exc}"]
    return controler(chemin, donnees, tous_les_ids)


def executer(chemins):
    entrees = lister_entrees()
    ids = []
    for c in entrees:
        try:
            ident = lire_entree(c).get("id")
            if ident:
                ids.append(str(ident).strip())
        except Exception:  # noqa: BLE001
            pass
    total_erreurs = 0
    for chemin in chemins:
        erreurs = controler_fichier(chemin, ids)
        rel = os.path.relpath(chemin, RACINE)
        if erreurs:
            total_erreurs += len(erreurs)
            print(f"NON CONFORME  {rel}")
            for e in erreurs:
                print(f"    {e}")
        else:
            print(f"conforme      {rel}")
    print(f"\n{len(chemins)} entree(s) controlee(s), {total_erreurs} erreur(s).")
    return 1 if total_erreurs else 0


# --------------------------------------------------------------------------
# Auto-test : jeu d'essai temporaire, hors du registre
# --------------------------------------------------------------------------

ENTREE_VALIDE = """---
id: APP-202610-001
schema: 1
statut: validee
declaree_le: 2026-10-05
validee_le: 2026-10-08
contributeur: tisseuse
action: publication_utile
resume: "Guide de lecture des regles de validation"
preuves:
  - url: https://exemple.org/guide-validation
    sha256: 4f2ac9e1b7d8035612aa47cf90e12b3d4c5e6f708192a3b4c5d6e7f8091a2b3c
parrains: [kora, nadi]
validateurs:
  - pseudo: kora
    role: conseil
    note_qualite: 1.2
    justifie_le: 2026-10-07
  - pseudo: nadi
    role: conseil
    note_qualite: 1.1
    justifie_le: 2026-10-07
bareme_version: 2026-10
points_base: 40
coefficient_qualite: 1.2
coefficient_rarete: 1.0
coefficient_plafond: 1.0
unites: 48.0
indice:
  c: 78
  v: 40
  e: 0
  i: 52.9
contestation: aucune
---

## Description

Jeu d'essai. Guide de lecture des regles de validation.
"""

CAS_A_TESTER = [
    ("unites fausses", "unites: 48.0", "unites: 55.0", 1),
    ("indice faux", "  i: 52.9", "  i: 70.0", 2),
    ("coefficient qualite hors bornes", "coefficient_qualite: 1.2", "coefficient_qualite: 2.0", 3),
    ("validateur unique", "  - pseudo: nadi\n    role: conseil\n    note_qualite: 1.1\n    justifie_le: 2026-10-07\n", "", 4),
    ("validateur = contributeur", "pseudo: kora", "pseudo: tisseuse", 5),
    ("parrain = validateur", "parrains: [kora, nadi]", "parrains: [kora, autre]", 5),
    ("aucun parrain", "parrains: [kora, nadi]", "parrains: []", 6),
    ("identifiant mal forme", "id: APP-202610-001", "id: APP-101-1", 7),
    ("preuve sans empreinte", "    sha256: 4f2ac9e1b7d8035612aa47cf90e12b3d4c5e6f708192a3b4c5d6e7f8091a2b3c\n", "", 8),
    ("bareme inexistant", "bareme_version: 2026-10", "bareme_version: 1999-01", 11),
]


def auto_test():
    print("Auto-test du validateur (jeu d'essai temporaire, hors registre)\n")
    echecs = 0

    dossier = tempfile.mkdtemp(prefix="regtest-")
    try:
        # 1. L'entree de reference doit passer
        chemin = os.path.join(dossier, "APP-202610-001.md")
        with open(chemin, "w", encoding="utf-8") as f:
            f.write(ENTREE_VALIDE)
        erreurs = controler_fichier(chemin, [])
        if erreurs:
            print("ECHEC  l'entree de reference devrait etre conforme :")
            for e in erreurs:
                print(f"    {e}")
            echecs += 1
        else:
            print("ok     entree de reference conforme")

        # 2. Chaque cas de degradation doit declencher le controle attendu
        for nom, avant, apres, controle in CAS_A_TESTER:
            contenu = ENTREE_VALIDE.replace(avant, apres)
            chemin = os.path.join(dossier, "APP-202610-001.md")
            with open(chemin, "w", encoding="utf-8") as f:
                f.write(contenu)
            erreurs = controler_fichier(chemin, [])
            detecte = any(f"[controle {controle}]" in e for e in erreurs)
            if detecte:
                print(f"ok     {nom} -> controle {controle} declenche")
            else:
                print(f"ECHEC  {nom} -> controle {controle} NON declenche ({len(erreurs)} erreur(s))")
                echecs += 1
    finally:
        shutil.rmtree(dossier, ignore_errors=True)

    print()
    if echecs:
        print(f"{echecs} cas en echec.")
        return 1
    print("Tous les cas passent.")
    return 0


def principal(argv):
    if "--auto-test" in argv:
        return auto_test()
    arguments = [a for a in argv if not a.startswith("-")]
    if arguments:
        chemins = [os.path.abspath(a) for a in arguments]
        for c in chemins:
            if not os.path.exists(c):
                print(f"fichier introuvable : {c}")
                return 1
    else:
        chemins = lister_entrees()
        if not chemins:
            print("Aucune entree dans registre/. Rien a controler.")
            return 0
    return executer(chemins)


if __name__ == "__main__":
    sys.exit(principal(sys.argv[1:]))
