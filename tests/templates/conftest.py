"""I template condivisi si importano col loro nome, come li importa il motore.

`content/templates` finisce in `sys.path` quando il motore carica un modulo d'autore
(`formats_repo/unstructured/loader.rs`, `TEMPLATES_DIR`): `import inv_managers` funziona lì perché
quella cartella è una radice d'importazione, non un pacchetto. Qui si ricrea la stessa condizione,
così che i test importino esattamente ciò che gira in produzione.
"""

import sys
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parents[2] / "content" / "templates"

if str(TEMPLATES) not in sys.path:
    sys.path.insert(0, str(TEMPLATES))
