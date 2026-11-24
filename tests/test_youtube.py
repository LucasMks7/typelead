import io
import json

import pytest

from typelead.links import Video
from typelead.youtube import FalhaNoYouTube, buscar, escolher_legenda, traduzir_erro

VIDEO = Video("aqz-KE-bpKQ")
JSON3 = json.dumps({"events": [{"tStartMs": 1000, "dDurationMs": 900, "segs": [{"utf8": "The kettle is on."}]}]})


def faixa(endereco="https://exemplo/legenda?lang=en", ext="json3"):
    return [{"ext": "vtt", "url": "https://exemplo/vtt"}, {"ext": ext, "url": endereco}]


class Dubl:
    """Ocupa o lugar do yt-dlp."""

    def __init__(self, info=None, erro=None, legenda=JSON3.encode(), erro_da_legenda=None):
        self.info, self.erro = info, erro
        self.legenda, self.erro_da_legenda = legenda, erro_da_legenda
        self.pedidos = []

    def __call__(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def extract_info(self, link, download, process):
        assert download is False and process is False
        if self.erro:
            raise self.erro
        return self.info

    def urlopen(self, endereco):
        self.pedidos.append(endereco)
        if self.erro_da_legenda:
            raise self.erro_da_legenda
        return io.BytesIO(self.legenda)


def info(**outros):
    return {"title": "Tea time", "channel": "Cozinha", "duration": 60, "subtitles": {"en": faixa()}, **outros}


def test_devolve_os_dados_e_as_falas():
    achado = buscar(VIDEO, Dubl(info()))
    assert (achado.titulo, achado.canal, achado.duracao) == ("Tea time", "Cozinha", 60)
    assert achado.origem == "autor"
    assert [fala.texto for fala in achado.falas] == ["The kettle is on."]
    assert achado.motivo is None


@pytest.mark.parametrize(("valor", "esperado"), [(True, True), (False, False), (None, True)])
def test_diz_se_o_dono_permite_incorporar(valor, esperado):
    assert buscar(VIDEO, Dubl(info(playable_in_embed=valor))).incorporavel is esperado


def test_a_legenda_do_autor_vem_antes_da_automatica():
    escolha = escolher_legenda(
        {"subtitles": {"en": faixa("https://exemplo/autor")}, "automatic_captions": {"en-orig": faixa("https://exemplo/auto")}}
    )
    assert escolha == ("autor", "https://exemplo/autor")


def test_automatica_original_vem_antes_da_que_pode_ser_traducao():
    escolha = escolher_legenda(
        {"automatic_captions": {"en": faixa("https://exemplo/en"), "en-orig": faixa("https://exemplo/orig")}}
    )
    assert escolha == ("automatica", "https://exemplo/orig")


def test_automatica_traduzida_de_outro_idioma_nao_serve():
    traduzida = faixa("https://exemplo/legenda?lang=pt&tlang=en")
    assert escolher_legenda({"automatic_captions": {"en": traduzida, "pt-orig": faixa()}}) is None


@pytest.mark.parametrize("nome", ["en", "en-US", "en-GB", "en-AU", "en-eEY6OEpapPo"])
def test_aceita_as_variantes_do_ingles(nome):
    assert escolher_legenda({"subtitles": {nome: faixa()}})[0] == "autor"


@pytest.mark.parametrize("nome", ["pt", "live_chat", "enm", "eng"])
def test_ignora_outros_idiomas_e_o_chat(nome):
    assert escolher_legenda({"subtitles": {nome: faixa()}}) is None


def test_prefere_o_ingles_sem_regiao():
    nomes = {"en-AU": faixa("https://exemplo/au"), "en-GB": faixa("https://exemplo/gb"), "en": faixa("https://exemplo/en")}
    assert escolher_legenda({"subtitles": nomes})[1] == "https://exemplo/en"


def test_sem_o_formato_json3_nao_ha_legenda():
    assert escolher_legenda({"subtitles": {"en": faixa(ext="srv1")}}) is None


@pytest.mark.parametrize(
    ("dubl", "motivo"),
    [
        (Dubl(info(subtitles={})), "não tem legenda"),
        (Dubl(info(subtitles=None, automatic_captions=None)), "não tem legenda"),
        (Dubl(info(subtitles={}, live_status="is_live")), "ao vivo"),
        (Dubl(info(), erro_da_legenda=OSError("HTTP Error 429")), "recusou"),
        (Dubl(info(), legenda=b""), "recusou"),
        (Dubl(info(), legenda=b"<html>"), "formato"),
        (Dubl(info(), legenda=b'{"events": []}'), "nenhuma fala"),
    ],
)
def test_sem_legenda_o_video_ainda_serve_para_transcrever(dubl, motivo):
    achado = buscar(VIDEO, dubl)
    assert achado.origem is None
    assert achado.falas == ()
    assert motivo in achado.motivo


@pytest.mark.parametrize(
    ("texto", "codigo"),
    [
        ("ERROR: [youtube] abc: Sign in to confirm you’re not a bot", "recusado"),
        ("HTTP Error 429: Too Many Requests", "recusado"),
        ("[youtube] abc: Private video. Sign in if you've been granted access", "acesso"),
        ("Sign in to confirm your age. This video may be inappropriate", "acesso"),
        ("Join this channel to get access to members-only content", "acesso"),
        ("The uploader has not made this video available in your country", "regiao"),
        ("This video requires payment to watch", "pago"),
        ("Premieres in 3 hours", "ainda_nao"),
        ("This video is unavailable", "indisponivel"),
        ("Video unavailable. This video has been removed by the uploader", "indisponivel"),
        ("[Errno 11001] getaddrinfo failed", "rede"),
        ("The read operation timed out", "rede"),
        ("algo nunca visto", "desconhecido"),
    ],
)
def test_explica_a_falha(texto, codigo):
    assert traduzir_erro(texto).codigo == codigo


def test_qualquer_erro_do_ytdlp_vira_falha_explicada():
    with pytest.raises(FalhaNoYouTube) as falha:
        buscar(VIDEO, Dubl(erro=RuntimeError("This video is unavailable")))
    assert falha.value.codigo == "indisponivel"
    assert "não existe" in str(falha.value)


AUTOMATICA = {
    "events": [
        {
            "tStartMs": 700,
            "dDurationMs": 2000,
            "segs": [{"utf8": "the"}, {"utf8": " kettle", "tOffsetMs": 300}, {"utf8": " is", "tOffsetMs": 800}, {"utf8": " on", "tOffsetMs": 1000}],
        }
    ]
}


class DublComDuas(Dubl):
    """Tem a legenda do autor e a automática."""

    automatica = json.dumps(AUTOMATICA).encode()

    def urlopen(self, endereco):
        self.pedidos.append(endereco)
        if "auto" in endereco:
            if self.automatica is None:
                raise OSError("HTTP Error 429")
            return io.BytesIO(self.automatica)
        return io.BytesIO(self.legenda)


DUAS = info(automatic_captions={"en-orig": faixa("https://exemplo/auto")})


def test_a_legenda_do_autor_ganha_os_tempos_da_automatica():
    (fala,) = buscar(VIDEO, DublComDuas(DUAS)).falas
    assert fala.texto == "The kettle is on."
    assert [round(p.inicio, 1) for p in fala.palavras] == [0.7, 1.0, 1.5, 1.7]


@pytest.mark.parametrize("resposta", [None, b"", b"<html>", b'{"events": []}'])
def test_sem_a_automatica_a_do_autor_ainda_serve(resposta):
    dubl = DublComDuas(DUAS)
    dubl.automatica = resposta
    achado = buscar(VIDEO, dubl)
    assert achado.origem == "autor"
    assert achado.falas[0].palavras == ()
