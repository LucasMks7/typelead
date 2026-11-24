import http.client
import threading

import pytest

from typelead.servidor import ENDERECO, criar_servidor


@pytest.fixture
def servidor():
    # Porta 0: o sistema escolhe uma livre, e os testes não brigam com o programa.
    with criar_servidor(0) as servidor:
        threading.Thread(target=servidor.serve_forever, daemon=True).start()
        yield servidor
        servidor.shutdown()


def pedir(servidor, caminho, host=None):
    conexao = http.client.HTTPConnection(ENDERECO, servidor.server_port, timeout=5)
    cabecalhos = {"Host": host} if host else {}
    conexao.request("GET", caminho, headers=cabecalhos)
    resposta = conexao.getresponse()
    corpo = resposta.read()
    conexao.close()
    return resposta, corpo


def test_so_escuta_neste_computador(servidor):
    assert servidor.server_address[0] == "127.0.0.1"


def test_entrega_a_pagina_inicial(servidor):
    resposta, corpo = pedir(servidor, "/")
    assert resposta.status == 200
    assert "typelead" in corpo.decode("utf-8")


def test_javascript_sai_com_o_tipo_que_o_navegador_exige_de_um_modulo(servidor):
    resposta, _ = pedir(servidor, "/js/medidas.js")
    assert resposta.status == 200
    assert resposta.getheader("Content-Type").startswith("text/javascript")


def test_manda_o_referer_que_o_player_do_youtube_exige(servidor):
    resposta, _ = pedir(servidor, "/")
    assert resposta.getheader("Referrer-Policy") == "strict-origin-when-cross-origin"


@pytest.mark.parametrize("host", ["localhost", "localhost:8765", "127.0.0.1:8765"])
def test_aceita_os_nomes_deste_computador(servidor, host):
    assert pedir(servidor, "/", host)[0].status == 200


@pytest.mark.parametrize("host", ["exemplo.com", "exemplo.com:8765", "127.0.0.1.exemplo.com"])
def test_recusa_outro_nome_apontado_para_este_computador(servidor, host):
    assert pedir(servidor, "/", host)[0].status == 403


@pytest.mark.parametrize("caminho", ["/js/", "/nao-existe", "/../servidor.py", "/%2e%2e/servidor.py"])
def test_nao_lista_pastas_nem_sai_da_pasta_web(servidor, caminho):
    assert pedir(servidor, caminho)[0].status == 404
