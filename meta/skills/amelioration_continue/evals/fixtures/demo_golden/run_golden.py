#!/usr/bin/env python3
"""Golden runner de démo (test target_golden) : évalue un SKILL.md -> {pass_rate}.
Règle jouet : le skill 'passe' (1.0) s'il garde sa section '## Regles' ET son frontmatter ;
sinon capacité dégradée (0.5). Sert à prouver le gate de non-régression, pas un vrai golden."""
import json
import sys

md = open(sys.argv[1], encoding="utf-8").read()
rate = 1.0 if ("## Regles" in md and md.lstrip().startswith("---")) else 0.5
print(json.dumps({"pass_rate": rate}))
