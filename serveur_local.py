"""Serveur local de prévisualisation, lancé par voir_site.bat.

Il sert le dossier docs/ comme le ferait « python -m http.server », mais
interdit au navigateur de garder les pages en cache : après chaque
construction, un simple rechargement affiche la dernière version.

Usage : python serveur_local.py [port]
"""

import functools
import http.server
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parent / "docs"


class SansCache(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".woff2": "font/woff2",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
        ".js": "text/javascript",
    }

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, format, *args):
        pass  # console silencieuse


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8030
    gestionnaire = functools.partial(SansCache, directory=str(DOCS))
    try:
        serveur = http.server.ThreadingHTTPServer(("127.0.0.1", port), gestionnaire)
    except OSError:
        print(f"Le port {port} est déjà utilisé : une autre fenêtre voir_site.bat est sans doute ouverte.")
        return 1
    with serveur:
        serveur.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
