#!/usr/bin/env python3
"""confidential.py -- contrat de confidentialite.

Regle de fer 5 : resumes/metadonnees only. Allowlist ALLOWED_FIELDS + scrub NER/regex.

CONTRAT (arbitrage 2026-07-15). La copie GELEE `FROZEN_ALLOWED_FIELDS` EST la source de verite :
le moteur se suffit a lui-meme, aucun skill cible n'est requis pour le faire tourner. Brancher un
skill cible reel est OPTIONNEL : renseigner `AMELIORE_ALLOWLIST_MEMORY` (chemin absolu vers le
`memory.py` de la cible) fait alors importer SON allowlist et la confronter a la copie gelee.
  - aucun chemin fourni  -> cas NOMINAL : on tourne sur la copie gelee, anti-drift sans objet ;
  - chemin fourni        -> l'allowlist importee doit egaler la copie gelee, sinon la cible a
    change son contrat en douce : ALERTE, a re-valider consciemment.

Ce module expose :
  - filter_allowlist() : le filtre utilise par le check G1 `subset_of_allowlist` ;
  - scrub() / clean_interaction() : le scrub PII (implemente plus bas, exerce par la demo).
"""
from __future__ import annotations

import importlib.util
import os
import re
import unicodedata
from pathlib import Path

# Copie GELEE au 2026-07-03. SOURCE DE VERITE du moteur (cf. contrat en tete de module) :
# c'est elle qui tourne par defaut, et la reference contre laquelle on confronte une cible branchee.
FROZEN_ALLOWED_FIELDS = frozenset({
    "run_id", "timestamp", "langue", "registre", "angles_types",
    "options_proposees", "top3_sorties", "top10_sorties", "choisi_par_user",
    "score_top1", "score_lisibilite", "degraded",
})

# Branchement OPTIONNEL d'un skill cible reel : chemin absolu vers son memory.py.
# Non renseigne (cas nominal) -> on tourne sur la copie gelee.
_ENV_TARGET_MEMORY = "AMELIORE_ALLOWLIST_MEMORY"


def _find_target_memory() -> Path | None:
    """Chemin du memory.py de la cible branchee, ou None si aucune cible n'est branchee."""
    env_path = os.environ.get(_ENV_TARGET_MEMORY)
    if env_path and Path(env_path).exists():
        return Path(env_path)
    return None


def _import_allowlist() -> tuple[frozenset[str], str]:
    """Retourne (allowlist, source). source = 'memory.py' si une cible est branchee, 'frozen' sinon."""
    path = _find_target_memory()
    if path is None:
        return FROZEN_ALLOWED_FIELDS, "frozen"
    spec = importlib.util.spec_from_file_location("target_memory", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    imported = frozenset(getattr(mod, "ALLOWED_FIELDS", set()))
    return (imported, "memory.py") if imported else (FROZEN_ALLOWED_FIELDS, "frozen")


ALLOWED_FIELDS, ALLOWLIST_SOURCE = _import_allowlist()


def check_drift() -> tuple[bool, str]:
    """Garde anti-drift : n'a de sens que si une cible est branchee via AMELIORE_ALLOWLIST_MEMORY.
    Aucune cible = cas nominal (on tourne sur la copie gelee, qui fait foi) : rien a comparer.
    Cible branchee dont l'allowlist diverge = elle a change son contrat -> a re-valider
    consciemment, jamais en silence."""
    if ALLOWLIST_SOURCE == "frozen":
        return True, (
            f"aucune cible branchee ({_ENV_TARGET_MEMORY} non renseigne) -> copie gelee "
            f"({len(FROZEN_ALLOWED_FIELDS)} champs), qui fait foi. Rien a comparer."
        )
    if ALLOWED_FIELDS != FROZEN_ALLOWED_FIELDS:
        diff_new = sorted(ALLOWED_FIELDS - FROZEN_ALLOWED_FIELDS)
        diff_gone = sorted(FROZEN_ALLOWED_FIELDS - ALLOWED_FIELDS)
        return False, f"DRIFT allowlist : +{diff_new} -{diff_gone} -> re-valider le contrat."
    return True, f"cible branchee alignee sur la copie gelee ({len(ALLOWED_FIELDS)} champs)."


def filter_allowlist(record: dict) -> dict:
    """Ne garde que les champs de l'allowlist (le check G1 subset_of_allowlist s'appuie dessus)."""
    return {k: v for k, v in record.items() if k in ALLOWED_FIELDS}


# --- Scrub PII (patch CRITIQUE spec : scruber les NOMS, pas seulement les regex) ---------------
# Le corpus de ce moteur est fait de fils de revue, qui ne sont pas anonymes par nature : on y
# nomme des auteurs, on y colle des adresses mail, des @handles et des URL internes. Le prenom y
# est la PII la plus frequente et la seule qu'aucune regex ne rattrape -- d'ou une NER
# heuristique LEGERE (liste de prenoms), volontairement sans
# dependance lourde (un modele NER embarque ferait telecharger des poids au premier run : cout
# et surface reseau injustifies pour une ceinture de securite). Limite assumee et documentee :
# faux negatifs sur les prenoms hors liste ; un vrai modele NER = V2. La vraie defense reste
# "zero texte brut" : l'extracteur ecrit en ROLES ; ce scrub est une defense en profondeur.

_RE_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_RE_URL = re.compile(r"https?://\S+")
# URL sans schema (patch red-team #5c) : domaine.tld[/chemin], ex. forum.example/thread/214, agenda.io/u.
_RE_URL_NOSCHEME = re.compile(r"\b[\w-]+\.(?:com|net|org|io|fr|co|example|app|me|tv)\b(?:/\S*)?", re.IGNORECASE)
# @handle elargi aux . et - (patch red-team #5c) : @marc.pichon, @marc-p (on se @mentionne dans un fil de revue).
_RE_HANDLE = re.compile(r"@[\w.\-]+")


def _deaccent(s: str) -> str:
    """Retire les accents (patch red-team #5a) : 'Leïla' -> 'leila' pour matcher FIRST_NAMES."""
    return "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if not unicodedata.combining(c))

# Liste SYNTHETIQUE, volontairement courte, couvrant des initiales et des origines variees.
# Ce n'est PAS un carnet d'adresses : son seul role est d'EXERCER le scrub NER (et de rattraper
# les prenoms les plus courants au passage). Le vrai carnet ne doit jamais entrer ici -- ce fichier
# est versionne, y coller de vrais prenoms en ferait lui-meme une fuite de PII, exactement ce que
# la regle de fer 5 interdit. C'est un echantillon, pas un dictionnaire : la couverture large est
# le job d'un vrai modele NER (V2), et les prenoms hors liste sont des faux negatifs assumes.
# Minuscule pour comparaison insensible a la casse ; _deaccent gere les formes accentuees.
FIRST_NAMES = frozenset({
    "alex", "amine", "bastien", "chloe", "david", "elena", "farid", "gabriel",
    "hugo", "ines", "jonas", "karim", "leila", "marc", "nadia", "olivier",
    "priya", "rachid", "sofia", "thomas", "yuki",
})


def scrub(text: str) -> str:
    """Retire les PII d'un texte : email/URL/@handle (regex) + prenoms connus (liste).
    Ordre : email avant handle (l'email contient un @)."""
    if not text:
        return text
    t = _RE_EMAIL.sub("[EMAIL]", text)
    t = _RE_URL.sub("[URL]", t)
    t = _RE_URL_NOSCHEME.sub("[URL]", t)
    t = _RE_HANDLE.sub("[HANDLE]", t)

    def _repl(m: re.Match) -> str:
        w = m.group(0)
        return "[PRENOM]" if _deaccent(w) in FIRST_NAMES else w  # comparaison sans accent

    return re.sub(r"\b[A-Za-zÀ-ÿ]+\b", _repl, t)


def clean_interaction(record: dict) -> tuple[dict, list[str]]:
    """Pipeline d'ecriture d'une interaction : filtre allowlist -> scrub des valeurs texte.
    Retourne (record_propre, champs_droppes). Le drop est silencieux cote donnees mais RETOURNE
    pour etre loggue par l'appelant (jamais une erreur : patch data_model confidential.py)."""
    dropped = sorted(k for k in record if k not in ALLOWED_FIELDS)
    clean = {k: (scrub(v) if isinstance(v, str) else v) for k, v in record.items() if k in ALLOWED_FIELDS}
    return clean, dropped


if __name__ == "__main__":
    ok, detail = check_drift()
    print(f"source allowlist : {ALLOWLIST_SOURCE}")
    print(f"anti-drift       : {'OK' if ok else 'ALERTE'} -- {detail}")
    print(f"champs           : {sorted(ALLOWED_FIELDS)}")
    demo = {"run_id": "x", "langue": "fr",
            "registre": "direct, comme dans la revue de Marc @marc.legrand https://forge.example/mr/88ad/8821",
            "SECRET_hors_liste": "fuite"}
    clean, dropped = clean_interaction(demo)
    print(f"clean_interaction: {clean}")
    print(f"champs droppes   : {dropped}")
    raise SystemExit(0 if ok else 1)
