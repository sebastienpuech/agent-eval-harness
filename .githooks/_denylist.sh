#!/bin/sh
# Chargement de la denylist locale -- SOURCE par `pre-commit` ET par `commit-msg`.
#
# Pourquoi un fichier commun plutot que dix lignes recopiees dans chaque hook : la regle
# fail-closed (denylist absente ou vide -> refus) doit rester IDENTIQUE dans les deux. Deux
# copies derivent, l'une des deux devient decorative, et c'est precisement le hook qu'on
# croyait actif qui laisse passer.
#
# Le prefixe `_` garantit que git ne prend jamais ce fichier pour un hook a executer.
#
# Contrat : l'appelant pose HOOK_DIR, puis `load_denylist <fichier_de_sortie>`.
#   retour 0 -> <fichier_de_sortie> contient les motifs (une ERE par ligne), non vide
#   retour 1 -> message sur stderr, l'appelant DOIT sortir en 1

load_denylist() {
  _out=$1
  _dl="$HOOK_DIR/denylist.local.txt"
  if [ ! -f "$_dl" ]; then
    echo "hook: $_dl introuvable. Copie .githooks/denylist.example.txt vers" >&2
    echo "  .githooks/denylist.local.txt et mets-y TES motifs. Refus par securite." >&2
    return 1
  fi
  grep -vE '^[[:space:]]*(#|$)' "$_dl" > "$_out"
  if [ ! -s "$_out" ]; then
    echo "hook: denylist vide -> refus." >&2
    return 1
  fi
  return 0
}
