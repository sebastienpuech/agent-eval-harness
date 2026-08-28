# Telegram — format, commandes, corrélation, gotchas

Bot **dédié** (`bot/ameliore_bot.py`), modèle = un bot Telegram minimal (python-telegram-bot).
**Token dédié** (`AMELIORE_BOT_TOKEN`, `.env` non commité), **instance unique par token** (2 process
sur le même token → `409 Conflict`). `chat_id` whitelisté en dur (`AMELIORE_CHAT_ID`). Tâche planifiée
au logon (pas NSSM). Canal privé mono-utilisateur.

## Message de proposition (4 blocs, run_id, 0 verbatim)
```
🔧 <skill> — proposition <run_id>
QUOI : <quoi ≤ 400 c>
POURQUOI : <pourquoi ≤ 400 c>
DELTA : <delta ≤ 400 c>
VALIDER : « oui <run_id> » (ou réponds à ce message) / « non <raison> ».
```
`notify.push` LINT (fail-closed) avant tout envoi : email/URL/téléphone + denylist verbatim → refus, 0 envoi.

## Commandes
| Commande | Effet | Écriture |
|---|---|---|
| `ameliore <skill>` | lance `run_chain` en **subprocess détaché** (après check LOCK) ; refuse si skill absent du registre | aucune (le run écrit ses artefacts) |
| `status` / `pending` | **lecture seule** des `proposition.json` `etat==en_attente` (dérivé de `decision.jsonl`) | aucune |
| `oui [run_id]` / reply-to | corrèle → LOCK apply → `apply_proposal` (muscle) → commit → `decision.jsonl` | **SEULE écriture live** |
| `non <raison>` | archive + `proposed_fixes.md` + `decision.jsonl` | live inchangé |

## Corrélation du « oui » (SIM-005)
1. `oui <run_id>` explicite → ce run_id.
2. reply-to → match `telegram_message_id` de la proposition.
3. `oui` **nu** : si **1 seule** proposition en attente → elle ; si **0 ou ≥ 2** → **rien appliqué**, la liste des run_id est renvoyée.

## Invariants
- `decision.jsonl` = **source de vérité** de la décision (écrite par le SEUL bot, append-only). `etat`
  est dérivé (en_attente si run_id absent de `decision.jsonl`). Pas de `_A_VALIDER.md`.
- **Passe en cours** (LOCK `pass` tenu) → « oui » répond « passe en cours », **0 écriture**, proposition reste `en_attente` (S12).
- Le bot **lit** l'état de la chaîne, ne l'écrit jamais (sauf `decision.jsonl`).

## Gotchas (mémoire projet)
- `409 Conflict` si 2 process pollent le même token → instance unique, token dédié.
- Background tué en veille Windows → état fichier-résident, reprise à zéro d'une passe interrompue.
- Éviter argv > 32k (Agent SDK) — non concerné ici (le bot ne passe pas de gros payloads).
