"""O programa de verdade: a porta, o navegador e o segundo typelead."""

import http.server
import socket
import sys
import threading

import pytest
import uvicorn

from typelead import servidor


@pytest.fixture
def abertas(monkeypatch, tmp_path):
    """As páginas que o programa abriria. Nada toca no banco nem no navegador da pessoa."""
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    paginas = []
    monkeypatch.setattr(servidor.webbrowser, "open", paginas.append)
    return paginas


@pytest.fixture
def porta():
    with socket.socket() as livre:
        livre.bind(("127.0.0.1", 0))
        return livre.getsockname()[1]


def rodar(monkeypatch, *argumentos):
    monkeypatch.setattr(sys, "argv", ["typelead", *map(str, argumentos)])
    return servidor.main()


@pytest.fixture
def aberto(monkeypatch, abertas, porta):
    """Um typelead atendendo em `porta`, sem ter aberto página nenhuma."""
    servidores = []
    original = uvicorn.Server.run

    def run(self, sockets=None):
        servidores.append(self)
        # Os sinais do sistema só podem ser tratados na thread principal.
        original(self, sockets=sockets)

    monkeypatch.setattr(uvicorn.Server, "run", run)
    thread = threading.Thread(target=rodar, args=(monkeypatch, "--porta", porta, "--sem-navegador"))
    thread.start()
    for _ in range(100):
        if servidores and servidores[0].started:
            break
        thread.join(0.1)
    yield servidores[0]
    servidores[0].should_exit = True
    thread.join(10)
    assert not thread.is_alive()


def test_atende_e_se_apresenta(aberto, porta):
    assert servidor.ja_esta_aberto(porta)


def test_aberto_duas_vezes_so_mostra_a_pagina(aberto, abertas, monkeypatch, porta, capsys):
    assert rodar(monkeypatch, "--porta", porta) == 0
    assert abertas == [f"http://localhost:{porta}"]
    assert "já está aberto" in capsys.readouterr().out


def test_abre_a_pagina_depois_de_ocupar_a_porta(abertas, monkeypatch, porta):
    def run(self, sockets):
        # Quem abrir a página agora já encontra a porta atendendo.
        with socket.create_connection(("127.0.0.1", porta), timeout=2):
            pass

    monkeypatch.setattr(uvicorn.Server, "run", run)
    assert rodar(monkeypatch, "--porta", porta) == 0
    assert abertas == [f"http://localhost:{porta}"]


def test_sem_navegador(abertas, monkeypatch, porta):
    monkeypatch.setattr(uvicorn.Server, "run", lambda self, sockets: None)
    assert rodar(monkeypatch, "--porta", porta, "--sem-navegador") == 0
    assert abertas == []


def test_ctrl_c_encerra_sem_erro_e_devolve_a_porta(abertas, monkeypatch, porta):
    def run(self, sockets):
        raise KeyboardInterrupt

    monkeypatch.setattr(uvicorn.Server, "run", run)
    assert rodar(monkeypatch, "--porta", porta) == 0
    with socket.socket() as outra:
        outra.bind(("127.0.0.1", porta))


def test_porta_de_outro_programa_e_recusada_com_explicacao(abertas, monkeypatch, capsys):
    class Outro(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'["outro"]')

        def log_message(self, *_):
            pass

    with http.server.HTTPServer(("127.0.0.1", 0), Outro) as outro:
        threading.Thread(target=outro.serve_forever).start()
        try:
            assert rodar(monkeypatch, "--porta", outro.server_port) == 1
        finally:
            outro.shutdown()
    assert abertas == []
    assert "--porta 9000" in capsys.readouterr().err


def test_porta_que_responde_outra_coisa_nao_e_o_typelead():
    with socket.create_server(("127.0.0.1", 0)) as mudo:
        def responder():
            conexao, _ = mudo.accept()
            conexao.recv(1000)
            conexao.sendall(b"isto nao e HTTP\r\n")
            conexao.close()

        thread = threading.Thread(target=responder)
        thread.start()
        assert not servidor.ja_esta_aberto(mudo.getsockname()[1])
        thread.join()


def test_porta_impossivel(abertas, monkeypatch, capsys):
    assert rodar(monkeypatch, "--porta", 70_000) == 1
    assert "70000" in capsys.readouterr().err
