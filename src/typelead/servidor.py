"""Servidor local: entrega a interface ao navegador, só neste computador."""

import argparse
import sys
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PASTA_WEB = Path(__file__).parent / "web"
ENDERECO = "127.0.0.1"
PORTA_PADRAO = 8765
NOMES_ACEITOS = {"127.0.0.1", "localhost"}


class Pagina(SimpleHTTPRequestHandler):
    # O Windows pode ter o .js registrado como text/plain, e o navegador se
    # recusa a executar um módulo com esse tipo. Por isso, fica fixado aqui.
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
    }

    def send_head(self):
        # Um site malicioso pode apontar o próprio domínio para 127.0.0.1 e
        # tentar ler esta página (DNS rebinding). O nome pedido o denuncia.
        nome = self.headers.get("Host", "").rsplit(":", 1)[0]
        if nome not in NOMES_ACEITOS:
            self.send_error(HTTPStatus.FORBIDDEN)
            return None
        return super().send_head()

    def end_headers(self):
        # Sem o Referer, o player do YouTube responde com o erro 153.
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def list_directory(self, path):
        self.send_error(HTTPStatus.NOT_FOUND)
        return None

    def log_message(self, formato, *argumentos):
        """Não enche o terminal com uma linha por arquivo."""


class Servidor(ThreadingHTTPServer):
    # No Windows, o padrão deixaria dois servidores na mesma porta, sem erro.
    allow_reuse_address = sys.platform != "win32"
    daemon_threads = True


def criar_servidor(porta: int = PORTA_PADRAO) -> Servidor:
    return Servidor((ENDERECO, porta), partial(Pagina, directory=str(PASTA_WEB)))


def main() -> int:
    parser = argparse.ArgumentParser(prog="typelead", description="Abre o typelead.")
    parser.add_argument("--porta", type=int, default=PORTA_PADRAO)
    porta = parser.parse_args().porta

    try:
        servidor = criar_servidor(porta)
    except (OSError, OverflowError) as erro:
        print(f"Não foi possível usar a porta {porta}: {erro}", file=sys.stderr)
        return 1

    with servidor:
        print(f"typelead em http://{ENDERECO}:{servidor.server_port} (Ctrl+C encerra)", flush=True)
        try:
            servidor.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
