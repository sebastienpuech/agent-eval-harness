# adapters.md — contrat d'entrée par format + contrat de délégation

> Étape 0bis. Deux contrats distincts : (A) **normalisation** des retours bruts vers
> `FeedbackItem[]` ; (B) **délégation** du patch factuel à `skill-auto-improver`.
> `scripts/normalize_feedback.py` implémente (A). (B) est une **HYPOTHÈSE** tant que la cible
> n'a pas de `SKILL.md` vérifiable (cf. §B).

---

## A. Contrat de normalisation (retours bruts → FeedbackItem[])

Chaque **format de retour** a un adaptateur explicite. Un format sans adaptateur →
`BlockedInputError` (**Scénario 3 : bloqué input externe**), jamais un parser inventé.

`FeedbackItem` au stade normalisation = `{id, source_ref, resume, format_origine}`.
`type` / `regle_cible` / `disposition` sont ajoutés par le **classificateur** (Session 3).

**Garanties** (`normalize_feedback.py`) : complétude `n_out + n_dupes == n_in` (assertion
dure, rien perdu silencieusement) ; dédup par `(source_ref, resume)` ; IDs uniques en sortie.

### `tracker-HTML` (tableur)
| Élément | Contrat |
|---|---|
| Entrée | export HTML du tracker ; commentaires **ancrés** |
| Sélecteur | élément `class~="comment"` portant `data-anchor="<case>#<section>"` (ou `data-ancre`) |
| `id` | `cas-{NNNN}` séquentiel |
| `source_ref` | la valeur `data-anchor` (ex. `C21#S4`) — **référence, pas verbatim** |
| `resume` | texte de l'élément commentaire (issue) |
| Exemple résolu | `<div class="comment" data-anchor="C21#S4">…</div>` → `{id:cas-0001, source_ref:C21#S4, resume:…}` |

> ⚠ Le sélecteur (`class="comment"` + `data-anchor`) est le **point d'ajustement unique** si
> l'export réel du tracker tableur diffère. Ne pas deviner : vérifier la structure réelle et
> adapter `_CommentParser`, sinon bloquer (S3).

### `jsonl-header-prose` (corpus jugement)
| Élément | Contrat |
|---|---|
| Entrée | 1 objet JSON / ligne. Clés observées : `id, header, contexte, fil, raw` |
| Issue | champ **`header`** (prose) — l'intitulé du raté, écrit à la main |
| `id` / `source_ref` | champ `id` du cas |
| `resume` | `header` seulement |
| **PII** | `contexte` (la situation de l'échange) / `fil` (les messages eux-mêmes, noms d'auteurs compris) / `raw` → **jamais lus ni copiés**. Ce sont des fils de revue non anonymes : `header` est la seule clé assez neutre pour sortir du corpus. |
| Vérifié sur | le vrai `cases.jsonl` (49 lignes) : `n_out == n_in`, aucun contenu imprimé |

### `tags-binaires`
| Élément | Contrat |
|---|---|
| Entrée | enregistrements `{run_id, verdict[, note]}` — `verdict` = le message proposé a-t-il été retenu tel quel (`retenu`) ou réécrit à la main (`reecrit`) ? |
| `id` | `tag-{run_id}` |
| `source_ref` | `run_id` |
| `resume` | `tag=<verdict>[ : <note>]` |

### `chat-transcript` (Cowork / Claude Code) — auto-collecte
| Élément | Contrat |
|---|---|
| Entrée | un bundle de session (tours user/assistant) produit par `collect_sessions.py` |
| Découverte | `collect_sessions.py --skill <cible> --since-days N` : scanne `local-agent-mode-sessions` (Cowork) + `.claude/projects` (CC), **long-path safe** (>260 car), filtre date + nom de skill |
| Candidat retour | un tour **user qui suit un tour assistant** (= réaction à une sortie du skill) → `adapt_chat.py` |
| `id` / `source_ref` | `chat-<session>-<turn>` / `<session>#turn<i>` |
| `resume` | excerpt provisoire (1 ligne) — **neutralisé sans-PII par le classificateur** avant persistance |
| **PII** | bundles en `.iter/collected/` (**gitignore**, local) ; `collect_sessions.py` n'imprime que des métadonnées ; rien de brut ne persiste hors `.iter/` |

### Faisabilité corpus (gate amont) — `scripts/feasibility.py`
Checklist spec §0bis, **bloque proprement** (ne reconstruit pas de corpus) :
1. corpus localisé ET lisible ; 2. ≥3 held-out candidats non-cités ; 3. format parsable ;
4. lot de retours normalisable (adaptateur présent).
Échec → `bloque_input_externe` (Scénario 3), exit 2. Cas hors-repo (datasets tableur) → message
actionnable listant les chemins candidats + **run partiel dégradé** possible (archi §3.1).

---

## B. Contrat de délégation — **HYPOTHÈSE (non vérifié)**

> **STATUT : HYPOTHÈSE — mais le blocage a sauté (mise à jour 2026-07-14).** La cible retenue est
> **`skill_auto_improver_v2`**. Ce paragraphe disait « v2 n'a pas encore de `SKILL.md`, le gate §0bis
> ne peut pas être franchi » : **c'est périmé**. v2 a désormais un `SKILL.md` exécutable, et le v1
> `skill-auto-improver` sur lequel on refusait de s'ancrer a été **supprimé du parc le 2026-07-14**
> (il n'y a plus d'alternative à v2).
>
> Le gate §0bis est donc **franchissable, et non franchi** : personne n'a encore lu le `SKILL.md` réel
> de v2 pour y ancrer le contrat ci-dessous. Tant que ce n'est pas fait, `scripts/delegation.py`
> continue — à raison — d'estampiller `HYPOTHESE_V2`. **Action ouverte**, pas une fatalité.

**Contrat pressenti, lu dans `skill_auto_improver_v2/data_model.md` (intention de design)** :

| {clé} | Valeur pressentie (v2) | Source |
|---|---|---|
| Fichier d'entrée (machinerie) | `evals/evals.json` format `critical_checks` (vérifiable sans LLM) | v2 §2 |
| Fichier d'entrée (skill cible) | `evals/cible/<skill>/sealed.json` — **golden cible scellé** que le juge gelé note ; cases `{id, input(fixture synthétique/anonymisée), assertions[{check,op,value}], source_session_id}` | v2 patch ARCH-001 |
| Deux runners | `meta_runner.py` (machinerie) + `target_runner.py` (skill cible) ; `golden_runner.py` → `{capability_pass_rate, regression_pass_rate}` | v2 §2 / patch |
| Invocation | branche git dédiée, boucle propose→juge→keep/revert | v2 archi |
| Verdict retourné | `{variante_id, capability_pass_rate, regression_pass_rate, decision: keep\|revert, vs_precedent, commentaire}` ; **`keep` exige `regression_pass_rate == 1.0` ET capability↑** | v2 §3 message `verdict` |
| Handoff humain | message `proposition` (`diff_path`, `quoi`, `pourquoi`, `delta_golden`, `valider`) + `proposed_fixes.md` (décision humaine append-only) | v2 §3/§4 |

**Mapping avec notre sortie** (`auto_improver_call.json`, data_model §3) :
- notre `evals_file` → `evals/evals.json` (`critical_checks`) **+** (v2) un `sealed.json` cible ;
- notre `holdout_case_ids` (à EXCLURE des `test_cases`) → s'aligne sur le **holdout G12** de v2
  (`source_session_id` disjoint du POOL-DIAGNOSTIC). **Invariant conservé** : le held-out
  sanctuarisé est retiré des evals passées au moteur ;
- notre `regles_a_detecteur` → assertions `critical_checks` (ex. `count_min`, `regex`, `contains`).

**Divergence v1 vs v2 à retenir** : v1 ne connaît qu'`evals/evals.json` (machinerie) ; v2 ajoute
le **golden cible scellé** + deux runners + une fitness `capability sous contrainte
regression==1.0`. Notre contrat de sortie devra produire **les deux** fichiers quand v2 sera
exécutable. Jusque-là : `HYPOTHESE_V2`, à re-vérifier contre le `SKILL.md` réel de v2 (re-ouvrir
ce gate en Session 4 avant d'écrire `auto_improver_call.json`).
