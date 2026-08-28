#!/usr/bin/env python3
"""normalize_feedback.py -- Etape 0bis : retours bruts -> FeedbackItem[].

Chaque FORMAT de retour a un adaptateur EXPLICITE. Un format sans adaptateur ->
BlockedInputError (Scenario 3 : bloque input externe), jamais un parser invente.

A ce stade (normalisation), un FeedbackItem porte : {id, source_ref, resume,
format_origine}. Les champs `type` / `regle_cible` / `disposition` sont ajoutes par le
classificateur (Session 3), pas ici.

Garanties (patch SIM-007) :
  - COMPLETUDE : chaque unite d'entree est comptee. `n_out + n_dupes == n_in`
    (assertion dure : rien n'est perdu silencieusement).
  - DEDUP : deux retours identiques (meme source_ref + meme resume) fusionnent ;
    le compte de doublons est retourne et logge.
  - IDs uniques en sortie.

CONFIDENTIALITE : les adaptateurs extraient une REFERENCE (ancre / id) + le texte de
l'issue. Le contenu brut sensible (corpus jugement = champs contexte/fil/raw ; micro-donnees
tableur) n'est JAMAIS lu ni copie. La neutralisation/allowlist finale avant memoire est la
frontiere du module memoire (Sessions 4-5), pas ici -- mais ici on ne touche deja QUE
l'ancre et le texte d'issue.

CLI :
  python normalize_feedback.py --demo         # 2 exemples resolus (tableur + jugement)
  python normalize_feedback.py --real-jugement <path/cases.jsonl>  # normalise le vrai
      fichier et affiche UNIQUEMENT les compteurs (aucun contenu / PII imprime).
"""
from __future__ import annotations

import html.parser
import json
import sys
from pathlib import Path

# format_origine reconnus (data_model 1). Etendre ce set = ajouter un adaptateur.
# 'chat-transcript' : conversation collectee (collect_sessions.py) -> adapt_chat.py.
KNOWN_FORMATS = {"tracker-HTML", "jsonl-header-prose", "tags-binaires", "chat-transcript"}


class BlockedInputError(Exception):
    """Format sans adaptateur -> Scenario 3 (bloque input externe), stop propre."""


# --------------------------------------------------------------------------- #
# Adaptateur 1 : tracker-HTML a ancres (tableur)
# --------------------------------------------------------------------------- #
class _CommentParser(html.parser.HTMLParser):
    """Extrait les commentaires ancres : element portant class~='comment' et
    data-anchor='<case>#<section>'. Le texte de l'element = l'issue."""

    def __init__(self):
        super().__init__()
        self._in_comment = False
        self._depth = 0
        self._anchor = None
        self._buf: list[str] = []
        self.comments: list[dict] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = (a.get("class") or "").split()
        if "comment" in classes and not self._in_comment:
            self._in_comment = True
            self._depth = 1
            self._anchor = a.get("data-anchor") or a.get("data-ancre")
            self._buf = []
        elif self._in_comment:
            self._depth += 1

    def handle_endtag(self, tag):
        if self._in_comment:
            self._depth -= 1
            if self._depth == 0:
                text = " ".join(" ".join(self._buf).split())
                self.comments.append({"anchor": self._anchor, "text": text})
                self._in_comment = False
                self._anchor = None
                self._buf = []

    def handle_data(self, data):
        if self._in_comment and data.strip():
            self._buf.append(data.strip())


def adapt_tracker_html(html_str: str) -> list[dict]:
    p = _CommentParser()
    p.feed(html_str)
    items = []
    for i, c in enumerate(p.comments, 1):
        anchor = c["anchor"] or f"unknown#{i}"
        items.append({
            "id": f"cas-{i:04d}",
            "source_ref": anchor,
            "resume": c["text"],
            "format_origine": "tracker-HTML",
        })
    return items


# --------------------------------------------------------------------------- #
# Adaptateur 2 : jsonl-header-prose (corpus jugement)
# --------------------------------------------------------------------------- #
def adapt_jsonl_header_prose(jsonl_str: str) -> list[dict]:
    """Chaque ligne = 1 objet JSON. L'issue est dans le champ `header` (prose).
    Les champs `contexte` / `fil` / `raw` (les messages du fil = PII) sont IGNORES."""
    items = []
    for line in jsonl_str.splitlines():
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        cid = str(d.get("id") or f"jugement-{len(items) + 1}")
        header = (d.get("header") or "").strip()
        items.append({
            "id": cid,
            "source_ref": cid,
            "resume": header,  # issue prose seulement ; contexte/fil/raw NON lus
            "format_origine": "jsonl-header-prose",
        })
    return items


# --------------------------------------------------------------------------- #
# Adaptateur 3 : tags-binaires
# --------------------------------------------------------------------------- #
def adapt_tags(records: list[dict]) -> list[dict]:
    """1 tag {run_id, verdict[, note]} -> 1 FeedbackItem."""
    items = []
    for r in records:
        rid = str(r.get("run_id") or f"tag-{len(items) + 1}")
        verdict = r.get("verdict", "?")
        note = (r.get("note") or "").strip()
        resume = f"tag={verdict}" + (f" : {note}" if note else "")
        items.append({
            "id": f"tag-{rid}",
            "source_ref": rid,
            "resume": resume,
            "format_origine": "tags-binaires",
        })
    return items


def _adapt_chat(bundle):
    """raw = bundle de session (dict) collecte par collect_sessions.py."""
    from adapt_chat import adapt_chat
    return adapt_chat(bundle)


_ADAPTERS = {
    "tracker-HTML": lambda raw: adapt_tracker_html(raw),
    "jsonl-header-prose": lambda raw: adapt_jsonl_header_prose(raw),
    "tags-binaires": lambda raw: adapt_tags(raw),
    "chat-transcript": _adapt_chat,
}


# --------------------------------------------------------------------------- #
# Normalisation + completude + dedup
# --------------------------------------------------------------------------- #
def normalize(raw, format_origine: str) -> dict:
    if format_origine not in _ADAPTERS:
        raise BlockedInputError(
            f"format '{format_origine}' sans adaptateur -> Scenario 3 (bloque input externe). "
            f"Formats connus : {sorted(KNOWN_FORMATS)}. Ne PAS inventer un parser."
        )
    raw_items = _ADAPTERS[format_origine](raw)
    n_in = len(raw_items)

    # Dedup par (source_ref, resume) ; conserve le 1er, compte les doublons.
    seen: dict[tuple, dict] = {}
    n_dupes = 0
    for it in raw_items:
        key = (it["source_ref"], it["resume"])
        if key in seen:
            n_dupes += 1
        else:
            seen[key] = it
    items = list(seen.values())
    n_out = len(items)

    # Assertion de completude : rien perdu silencieusement.
    assert n_out + n_dupes == n_in, \
        f"COMPLETUDE VIOLEE : n_out({n_out}) + n_dupes({n_dupes}) != n_in({n_in})"
    ids = [it["id"] for it in items]
    assert len(ids) == len(set(ids)), f"IDs non uniques en sortie : {ids}"

    return {"items": items, "n_in": n_in, "n_out": n_out, "n_dupes": n_dupes,
            "format_origine": format_origine}


# --------------------------------------------------------------------------- #
# Exemples resolus (demo) + normalisation du vrai cases.jsonl (compteurs only)
# --------------------------------------------------------------------------- #
def _demo() -> int:
    print("=== Exemple resolu 1 : tracker-HTML (tableur) ===")
    tableur_html = (
        '<div class="comment" data-anchor="C21#S4">'
        "L'histogramme des durees de build s'arrete a 10 min : les builds plus longs manquent.</div>"
    )
    r1 = normalize(tableur_html, "tracker-HTML")
    print(json.dumps(r1["items"], ensure_ascii=False, indent=2))
    assert r1["n_out"] == r1["n_in"] == 1
    assert r1["items"][0]["source_ref"] == "C21#S4"

    print("\n=== Exemple resolu 2 : jsonl-header-prose (jugement) ===")
    # champs bruts synthetiques -> NON copies en sortie.
    jugement_line = json.dumps({
        "id": "jugement-12",
        "header": "La reponse fait 20 mots, trop longue -> rejetee.",
        "champ_a": "<SYNTHETIQUE, non lu>", "champ_b": "<SYNTHETIQUE, non lu>",
        "raw": "<SYNTHETIQUE, non lu>",
    }, ensure_ascii=False)
    r2 = normalize(jugement_line, "jsonl-header-prose")
    print(json.dumps(r2["items"], ensure_ascii=False, indent=2))
    assert r2["n_out"] == r2["n_in"] == 1
    assert "champ_a" not in r2["items"][0] and "raw" not in r2["items"][0]
    assert r2["items"][0]["resume"].startswith("La reponse")

    print("\n=== Dedup + completude ===")
    # Doublon reel : meme ancre + meme texte (ex. 2 commentaires identiques sur C21#S4).
    dup = '<div class="comment" data-anchor="C21#S4">derniers bins de duree manquants</div>'
    r3 = normalize(dup + dup, "tracker-HTML")
    assert r3["n_in"] == 2 and r3["n_out"] == 1 and r3["n_dupes"] == 1, r3
    print(f"n_in=2, n_out={r3['n_out']}, n_dupes={r3['n_dupes']} (completude OK)")

    print("\n=== Format inconnu -> bloque (Scenario 3) ===")
    try:
        normalize("x", "csv-maison")
        print("ERREUR : aurait du bloquer")
        return 1
    except BlockedInputError as e:
        print(f"BLOQUE proprement : {e}")

    # Compteur DERIVE de la donnee (jamais ecrit en dur) : ajouter un adaptateur a KNOWN_FORMATS
    # met cette ligne a jour tout seul, sinon elle reperime en silence.
    print(f"\n=> DEMO OK : {len(KNOWN_FORMATS)} adaptateurs, completude, dedup, blocage format inconnu.")
    return 0


def _real_jugement(path: str) -> int:
    """Normalise le VRAI cases.jsonl -- affiche UNIQUEMENT les compteurs (aucun contenu)."""
    text = Path(path).read_text(encoding="utf-8")
    r = normalize(text, "jsonl-header-prose")
    print(f"cases.jsonl : n_in={r['n_in']} n_out={r['n_out']} n_dupes={r['n_dupes']}")
    print(f"completude n_out+n_dupes==n_in : {r['n_out'] + r['n_dupes'] == r['n_in']}")
    print("(aucun resume/PII imprime -- confidentialite jugement)")
    return 0 if r["n_out"] + r["n_dupes"] == r["n_in"] else 1


if __name__ == "__main__":
    if "--demo" in sys.argv:
        sys.exit(_demo())
    if "--real-jugement" in sys.argv:
        i = sys.argv.index("--real-jugement")
        sys.exit(_real_jugement(sys.argv[i + 1]))
    print(__doc__)
    sys.exit(0)
