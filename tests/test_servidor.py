import time

import pytest
from fastapi.testclient import TestClient

from typelead.banco import Banco
from typelead.legendas import Fala
from typelead.servidor import criar_app
from typelead.traducao import Tradutor
from typelead.transcricao import FalhaNaTranscricao
from typelead.transcricoes import Transcricoes
from typelead.youtube import Achado, FalhaNoYouTube

BASE = "http://localhost:8765"
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
    assert cliente.get("/validacao.html").status_code == 200


def test_javascript_sai_com_o_tipo_que_o_navegador_exige_de_um_modulo(cliente):
    assert cliente.get("/js/medidas.js").headers["content-type"].startswith("text/javascript")


def test_manda_o_referer_que_o_player_do_youtube_exige(cliente):
    assert cliente.get("/").headers["referrer-policy"] == "strict-origin-when-cross-origin"


@pytest.mark.parametrize("host", ["localhost", "localhost:8765"])
def test_aceita_o_nome_deste_computador(cliente, host):
    assert cliente.get("/", headers={"host": host}).status_code == 200


@pytest.mark.parametrize("host", ["127.0.0.1", "127.0.0.1:8765", "127.0.0.1:80@exemplo.com"])
def test_a_pagina_aberta_pelo_numero_vai_para_o_nome(cliente, host):
    resposta = cliente.get("/validacao.html?v=abc&t=3", headers={"host": host}, follow_redirects=False)
    assert resposta.status_code == 307
    assert resposta.headers["location"] == "http://localhost:8765/validacao.html?v=abc&t=3"
    assert resposta.headers["referrer-policy"] == "strict-origin-when-cross-origin"


def test_o_desvio_nao_leva_a_outro_site(cliente):
    resposta = cliente.get("//exemplo.com/a", headers={"host": "127.0.0.1:8765"}, follow_redirects=False)
    assert resposta.headers["location"].startswith("http://localhost:8765/")


def test_a_api_pelo_numero_nao_e_desviada(cliente):
    resposta = cliente.get("/api/transcricoes/x", headers={"host": "127.0.0.1:8765"}, follow_redirects=False)
    assert resposta.status_code == 404


def test_outro_site_pelo_numero_continua_recusado(cliente):
    cabecalhos = {"host": "127.0.0.1:8765", "origin": "https://exemplo.com"}
    assert cliente.get("/", headers=cabecalhos, follow_redirects=False).status_code == 403


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


# O vídeo e a legenda


def com_busca(pasta, resposta):
    def buscar(video):
        if isinstance(resposta, Exception):
            raise resposta
        return Achado(video=video, **resposta)

    return TestClient(criar_app(Transcricoes(pasta=pasta), buscar), base_url=BASE)


ACHADO = {
    "titulo": "Tea time",
    "canal": "Cozinha",
    "duracao": 60,
    "incorporavel": True,
    "origem": "autor",
    "falas": (Fala(1, 1.4, "The kettle"), Fala(1.4, 2, "is on.")),
}


def test_abre_o_video_com_as_falas_ja_divididas(pasta):
    resposta = com_busca(pasta, ACHADO).post("/api/videos", json={"link": "youtu.be/aqz-KE-bpKQ?t=9"})
    dados = resposta.json()
    assert resposta.status_code == 200
    assert (dados["id"], dados["comeco"], dados["titulo"], dados["origem"]) == ("aqz-KE-bpKQ", 9, "Tea time", "autor")
    assert [fala["texto"] for fala in dados["falas"]] == ["The kettle is on."]


def test_link_que_nao_serve_explica_o_motivo(pasta):
    resposta = com_busca(pasta, ACHADO).post("/api/videos", json={"link": "https://www.youtube.com/@blender"})
    assert resposta.status_code == 422 and "canal" in resposta.json()["detail"]


def test_video_que_nao_existe(pasta):
    resposta = com_busca(pasta, FalhaNoYouTube("indisponivel", "Não existe.")).post(
        "/api/videos", json={"link": "youtu.be/aqz-KE-bpKQ"}
    )
    assert resposta.status_code == 502 and resposta.json()["detail"] == "Não existe."


def test_recusa_do_youtube_ainda_deixa_transcrever(pasta):
    dados = (
        com_busca(pasta, FalhaNoYouTube("recusado", "Recusou."))
        .post("/api/videos", json={"link": "youtu.be/aqz-KE-bpKQ"})
        .json()
    )
    assert (dados["id"], dados["origem"], dados["falas"], dados["motivo"]) == ("aqz-KE-bpKQ", None, [], "Recusou.")


def test_abre_um_arquivo_de_legenda(cliente):
    srt = "1\n00:00:01,000 --> 00:00:02,000\nThe kettle is on.\n"
    resposta = cliente.post("/api/legendas", content=srt.encode())
    assert [fala["texto"] for fala in resposta.json()["falas"]] == ["The kettle is on."]


def test_arquivo_que_nao_e_legenda(cliente):
    assert cliente.post("/api/legendas", content=b"nada").status_code == 422
    assert cliente.post("/api/legendas", content=b"a" * 5_000_001).status_code == 413


# O que fica salvo

TENTATIVA = {
    "rodada": "0b0e7a52-0000-4000-8000-000000000000",
    "modo": "lacunas",
    "corrigir": "enter",
    "texto": "the kettle",
    "com_ajuda": False,
    "repeticoes": 1,
    "velocidade": 1,
    "duracao": 4.2,
    "itens": [{"tipo": "certa", "posicao": 0, "esperada": "The", "digitada": "the"}],
}
LINK = {"link": "youtu.be/aqz-KE-bpKQ"}


def test_video_salvo_abre_sem_consultar_o_youtube(pasta):
    vezes = []

    def buscar(video):
        vezes.append(video.id)
        return Achado(video=video, **ACHADO)

    cliente = TestClient(criar_app(Transcricoes(pasta=pasta), buscar), base_url=BASE)
    primeira = cliente.post("/api/videos", json=LINK).json()
    segunda = cliente.post("/api/videos", json=LINK).json()
    assert primeira == segunda and len(vezes) == 1
    cliente.post("/api/videos", json=LINK | {"novo": True})
    assert len(vezes) == 2


def test_continua_de_onde_parou(pasta):
    cliente = com_busca(pasta, ACHADO)
    cliente.post("/api/videos", json=LINK)
    assert cliente.put("/api/videos/aqz-KE-bpKQ/posicao", json={"posicao": 3}).status_code == 204
    assert cliente.post("/api/videos", json=LINK).json()["posicao"] == 3
    assert cliente.put("/api/videos/aaaaaaaaaaa/posicao", json={"posicao": 3}).status_code == 404
    assert cliente.put("/api/videos/aqz-KE-bpKQ/posicao", json={"posicao": -1}).status_code == 422
    assert cliente.put("/api/videos/curto/posicao", json={"posicao": 1}).status_code == 422


def test_tentativa_certa_marca_a_fala_e_aparece_nos_recentes(pasta):
    cliente = com_busca(pasta, ACHADO)
    fala = cliente.post("/api/videos", json=LINK).json()["falas"][0]
    assert cliente.post("/api/tentativas", json=TENTATIVA | {"fala_id": fala["id"]}).status_code == 201
    assert cliente.post("/api/videos", json=LINK).json()["falas"][0]["acertada"]
    recentes = cliente.get("/api/videos").json()
    assert [(v["id"], v["acertadas"], v["total"]) for v in recentes] == [("aqz-KE-bpKQ", 1, 1)]


@pytest.mark.parametrize(
    "mudanca",
    [{"modo": "outro"}, {"rodada": "x"}, {"itens": []}, {"velocidade": 0}, {"itens": [{"tipo": "x"}]}],
)
def test_tentativa_malformada(pasta, mudanca):
    cliente = com_busca(pasta, ACHADO)
    fala = cliente.post("/api/videos", json=LINK).json()["falas"][0]
    assert cliente.post("/api/tentativas", json=TENTATIVA | {"fala_id": fala["id"]} | mudanca).status_code == 422


def test_tentativa_em_fala_que_nao_existe(cliente):
    assert cliente.post("/api/tentativas", json=TENTATIVA | {"fala_id": 99}).status_code == 404


def test_transcricao_salva_nao_se_perde(pasta):
    cliente = com_busca(pasta, FalhaNoYouTube("recusado", "Recusou."))
    cliente.post("/api/videos", json=LINK)
    assert cliente.get("/api/videos").json() == []
    falas = [{"inicio": 1, "fim": 2, "texto": "The kettle.", "palavras": [{"texto": "The", "inicio": 1, "fim": 1.2}]}]
    corpo = {"titulo": "Chá", "canal": "", "duracao": None, "origem": "som", "falas": falas}
    salvo = cliente.put("/api/videos/aqz-KE-bpKQ/falas", json=corpo).json()
    assert salvo["falas"][0]["id"]
    aberto = cliente.post("/api/videos", json=LINK).json()
    assert (aberto["origem"], aberto["titulo"], aberto["falas"][0]["texto"]) == ("som", "Chá", "The kettle.")


def test_falha_do_banco_vira_uma_mensagem(pasta):
    cliente = com_busca(pasta, ACHADO)
    banco = Banco()
    banco.fechar()
    quebrado = TestClient(criar_app(Transcricoes(pasta=pasta), banco=banco), base_url=BASE, raise_server_exceptions=False)
    resposta = quebrado.get("/api/videos")
    assert resposta.status_code == 500 and "salvar" in resposta.json()["detail"]
    assert cliente.get("/api/videos").status_code == 200


def test_traduz_uma_vez_e_guarda(pasta):
    pedidos = []

    def traduzir(texto):
        pedidos.append(texto)
        return "A chaleira está no fogo."

    cliente = TestClient(
        criar_app(Transcricoes(pasta=pasta), lambda v: Achado(video=v, **ACHADO), tradutor=Tradutor(lambda: traduzir)),
        base_url=BASE,
    )
    fala = cliente.post("/api/videos", json=LINK).json()["falas"][0]
    for _ in range(2):
        resposta = cliente.post(f"/api/falas/{fala['id']}/traducao")
        assert resposta.json() == {"traducao": "A chaleira está no fogo."}
    assert pedidos == ["The kettle is on."]
    assert cliente.post("/api/falas/99/traducao").status_code == 404


def test_tradutor_que_nao_carrega_explica_o_motivo(pasta):
    def carregar():
        raise OSError("sem internet")

    cliente = TestClient(
        criar_app(Transcricoes(pasta=pasta), lambda v: Achado(video=v, **ACHADO), tradutor=Tradutor(carregar)),
        base_url=BASE,
    )
    fala = cliente.post("/api/videos", json=LINK).json()["falas"][0]
    resposta = cliente.post(f"/api/falas/{fala['id']}/traducao")
    assert resposta.status_code == 503 and "sem internet" in resposta.json()["detail"]
