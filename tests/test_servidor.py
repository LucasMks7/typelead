import time

import pytest
from fastapi.testclient import TestClient

from typelead.legendas import Fala
from typelead.servidor import criar_app
from typelead.transcricao import FalhaNaTranscricao
from typelead.transcricoes import Transcricoes

BASE = "http://127.0.0.1:8765"
MARCAS = {"marcas": [{"gravado": 0, "video": 0}, {"gravado": 1, "video": 1}]}


@pytest.fixture
def pasta(tmp_path):
    return tmp_path


def montar(pasta, transcrever=lambda *_: [Fala(1, 2, "The kettle.")], **outros):
    opcoes = {"carregar": lambda: (object(), "cpu"), "ler": lambda som: som.read_bytes(), **outros}
    return TestClient(criar_app(Transcricoes(transcrever=transcrever, pasta=pasta, **opcoes)), base_url=BASE)


@pytest.fixture
def cliente(pasta):
    return montar(pasta)


# A página e as proteções


def test_entrega_a_pagina_inicial(cliente):
    resposta = cliente.get("/")
    assert resposta.status_code == 200
    assert "typelead" in resposta.text


def test_javascript_sai_com_o_tipo_que_o_navegador_exige_de_um_modulo(cliente):
    assert cliente.get("/js/medidas.js").headers["content-type"].startswith("text/javascript")


def test_manda_o_referer_que_o_player_do_youtube_exige(cliente):
    assert cliente.get("/").headers["referrer-policy"] == "strict-origin-when-cross-origin"


@pytest.mark.parametrize("host", ["localhost", "localhost:8765", "127.0.0.1:8765"])
def test_aceita_os_nomes_deste_computador(cliente, host):
    assert cliente.get("/", headers={"host": host}).status_code == 200


@pytest.mark.parametrize("host", ["exemplo.com", "exemplo.com:8765", "127.0.0.1.exemplo.com", ""])
def test_recusa_outro_nome_apontado_para_este_computador(cliente, host):
    assert cliente.get("/", headers={"host": host}).status_code == 403


@pytest.mark.parametrize("origem", ["https://exemplo.com", "http://127.0.0.1:9999", "https://127.0.0.1:8765", "null"])
def test_recusa_pedido_vindo_de_outro_site(cliente, origem):
    assert cliente.post("/api/transcricoes", json=MARCAS, headers={"origin": origem}).status_code == 403


def test_aceita_pedido_da_propria_pagina(cliente):
    assert cliente.post("/api/transcricoes", json=MARCAS, headers={"origin": BASE}).status_code == 201


def test_recusa_formulario_de_outro_site_mesmo_sem_origem(cliente):
    resposta = cliente.post("/api/transcricoes", json=MARCAS, headers={"sec-fetch-site": "cross-site"})
    assert resposta.status_code == 403


@pytest.mark.parametrize("caminho", ["/js/", "/nao-existe", "/%2e%2e/servidor.py", "/docs", "/openapi.json"])
def test_nao_lista_pastas_nem_sai_da_pasta_web(cliente, caminho):
    assert cliente.get(caminho).status_code == 404


# A transcrição


def criar(cliente):
    return cliente.post("/api/transcricoes", json=MARCAS).json()["id"]


def esperar(cliente, identificador):
    for _ in range(200):
        trabalho = cliente.get(f"/api/transcricoes/{identificador}").json()
        if trabalho["estado"] in {"pronto", "falhou"}:
            return trabalho
        time.sleep(0.01)
    raise AssertionError("não terminou")


def test_transcreve_e_apaga_o_som(cliente, pasta):
    identificador = criar(cliente)
    assert cliente.get(f"/api/transcricoes/{identificador}").json()["estado"] == "esperando_som"
    assert cliente.put(f"/api/transcricoes/{identificador}/som", content=b"som").status_code == 202
    trabalho = esperar(cliente, identificador)
    assert trabalho["estado"] == "pronto"
    assert [fala["texto"] for fala in trabalho["falas"]] == ["The kettle."]
    assert list(pasta.iterdir()) == []


@pytest.mark.parametrize(
    ("erro", "mensagem"),
    [(FalhaNaTranscricao("A gravação está muda."), "muda"), (ValueError("interno"), "inesperado")],
)
def test_falha_chega_explicada_e_o_som_e_apagado(pasta, erro, mensagem):
    def falhar(*_):
        raise erro

    cliente = montar(pasta, transcrever=falhar)
    identificador = criar(cliente)
    cliente.put(f"/api/transcricoes/{identificador}/som", content=b"som")
    trabalho = esperar(cliente, identificador)
    assert trabalho["estado"] == "falhou" and mensagem in trabalho["erro"]
    assert list(pasta.iterdir()) == []


def test_o_modelo_e_carregado_uma_vez_so(pasta):
    cargas = []
    cliente = montar(pasta, carregar=lambda: (cargas.append(1) or object(), "cpu"))
    for _ in range(2):
        identificador = criar(cliente)
        cliente.put(f"/api/transcricoes/{identificador}/som", content=b"som")
        esperar(cliente, identificador)
    assert len(cargas) == 1


def test_depois_de_uma_falha_a_fila_continua(pasta):
    respostas = [FalhaNaTranscricao("muda"), None]

    def transcrever(*_):
        erro = respostas.pop(0)
        if erro:
            raise erro
        return [Fala(1, 2, "Ok.")]

    cliente = montar(pasta, transcrever=transcrever)
    estados = []
    for _ in range(2):
        identificador = criar(cliente)
        cliente.put(f"/api/transcricoes/{identificador}/som", content=b"som")
        estados.append(esperar(cliente, identificador)["estado"])
    assert estados == ["falhou", "pronto"]


def test_gravacao_vazia_e_recusada_sem_deixar_arquivo(cliente, pasta):
    assert cliente.put(f"/api/transcricoes/{criar(cliente)}/som", content=b"").status_code == 422
    assert list(pasta.iterdir()) == []


def test_gravacao_grande_demais(pasta, monkeypatch):
    monkeypatch.setattr("typelead.servidor.TAMANHO_MAXIMO", 2)
    cliente = montar(pasta)
    assert cliente.put(f"/api/transcricoes/{criar(cliente)}/som", content=b"som").status_code == 413
    assert list(pasta.iterdir()) == []


def test_o_som_so_e_aceito_uma_vez(cliente):
    identificador = criar(cliente)
    cliente.put(f"/api/transcricoes/{identificador}/som", content=b"som")
    assert cliente.put(f"/api/transcricoes/{identificador}/som", content=b"som").status_code == 409


def test_transcricao_desconhecida(cliente):
    assert cliente.get("/api/transcricoes/nada").status_code == 404
    assert cliente.put("/api/transcricoes/nada/som", content=b"som").status_code == 404


@pytest.mark.parametrize(
    "marcas", [[], [{"gravado": 0, "video": 0}], [{"gravado": -1, "video": 0}] * 2, [{"gravado": "x", "video": 0}] * 2]
)
def test_marcas_que_nao_servem(cliente, marcas):
    assert cliente.post("/api/transcricoes", json={"marcas": marcas}).status_code == 422


def test_as_antigas_sao_esquecidas(cliente):
    primeira = criar(cliente)
    for _ in range(20):
        criar(cliente)
    assert cliente.get(f"/api/transcricoes/{primeira}").status_code == 404
