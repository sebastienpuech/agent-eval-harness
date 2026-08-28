#!/usr/bin/env python3
"""Golden de démo qui PÉNALISE l'ajout du principe jugement 'Profondeur alignee' (rate 1.0 -> 0.5).
Sert à prouver que run_chain REFUSE une proposition qui régresse le golden du skill cible."""
import json
import sys

md = open(sys.argv[1], encoding="utf-8").read()
print(json.dumps({"pass_rate": 0.5 if "Profondeur alignee" in md else 1.0}))
