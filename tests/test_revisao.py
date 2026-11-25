import itertools
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from typelead.banco import Banco, Item, Tentativa
from typelead.legendas import Fala
from typelead.palavras import APRENDENDO, CONHECIDA, ERRANDO
from typelead.revisao import BOM, DIFICIL, ERROU, agendar, dar_nota

AGORA = datetime(2026, 11, 25, 15, tzinfo=timezone.utc)

# A nota e a data


@pytest.mark.parametrize(
    ("acertou", "quase", "repeticoes", "velocidade", "nota"),
    [
        (True, False, 1, 1, BOM),
        (True, False, 3, 1, BOM),
        (True, False, 4, 1, DIFICIL),
        (True, False, 1, 0.75, DIFICIL),
        (True, True, 1, 1, DIFICIL),
        (False, False, 1, 1, ERROU),
        (False, True, 1, 1, ERROU),
    ],
)
def test_nota(acertou, quase, repeticoes, velocidade, nota):
    assert dar_nota(acertou, quase, repeticoes, velocidade) == nota


def test_quem_acerta_espera_cada_vez_mais():
    estado, vence, intervalos, quando = None, AGORA, [], AGORA
    for _ in range(4):
        estado, vence = agendar(estado, BOM, quando)
        intervalos.append((vence - quando).days)
        quando = vence
    assert intervalos == sorted(intervalos)
    assert intervalos[0] >= 1 and intervalos[-1] > 30


def test_quem_erra_volta_no_dia_seguinte():
    estado, vence = agendar(None, BOM, AGORA)
    _, depois = agendar(estado, ERROU, vence)
    assert (depois - vence).days == 1


def test_dificil_volta_antes_de_bom():
    estado, vence = agendar(None, BOM, AGORA)
    assert agendar(estado, DIFICIL, vence)[1] < agendar(estado, BOM, vence)[1]


def test_o_mesmo_historico_da_a_mesma_data():
    estado, vence = agendar(None, BOM, AGORA)
    assert agendar(estado, BOM, vence)[1] == agendar(estado, BOM, vence)[1]


def test_relogio_atrasado_nao_quebra():
    estado, _ = agendar(None, BOM, AGORA)
    _, vence = agendar(estado, BOM, AGORA - timedelta(days=3))
    assert vence > AGORA


# No banco


class Relogio:
    """Um dia por vez, e um segundo a cada gravação."""

    def __init__(self):
        self.dia = 0
        self.segundos = itertools.count()

    def __call__(self):
        # Meio-dia em UTC: o dia é o mesmo em quase qualquer fuso.
        quando = datetime(2026, 11, 25, 12, tzinfo=timezone.utc) + timedelta(days=self.dia, seconds=next(self.segundos))
        return quando.isoformat(timespec="microseconds")

    @property
    def hoje(self):
        return date(2026, 11, 25) + timedelta(days=self.dia)


@pytest.fixture
def relogio(monkeypatch):
    relogio = Relogio()
    monkeypatch.setattr("typelead.banco._agora", relogio)
    return relogio


@pytest.fixture
def banco(relogio):
    banco = Banco()
    falas = [Fala(0, 2, "The kettle and the teapot."), Fala(2, 4, "A kettle."), Fala(4, 6, "Biscuits.")]
    banco.salvar_video("abcdefghijk", "Chá", "Canal", 10.0, True, "autor", falas)
    banco.salvar_video("outroabcdef", "Café", "Canal", 10.0, True, "autor", [Fala(0, 2, "The grinder.")])
    yield banco
    banco.fechar()


def errar(banco, palavra, posicao=1, fala=1):
    """Troca por outra e acerta depois de ouvir de novo: erro de escuta."""
    rodada = str(uuid.uuid4())
    for repeticoes, (tipo, digitada) in enumerate([("trocada", "zzzzzz"), ("certa", palavra)], 1):
        itens = (Item(tipo, posicao, palavra, digitada),)
        banco.salvar_tentativa(
            Tentativa(fala, rodada, "oculto", "enter", digitada, False, repeticoes, 1, 1, itens)
        )
    banco.diagnosticar(rodada)


def revisar(banco, forma="kettle", acertou=True, fala=1, **mudancas):
    dados = {"quase": False, "digitada": forma, "repeticoes": 1, "velocidade": 1}
    return banco.salvar_revisao(forma, fala, acertou, **(dados | mudancas))


def vencidas(banco, relogio, **opcoes):
    trechos = banco.revisar(relogio.hoje, **opcoes)["trechos"]
    return [[palavra["forma"] for palavra in trecho["palavras"]] for trecho in trechos]


def test_nada_errado_nada_a_revisar(banco, relogio):
    assert banco.revisar(relogio.hoje) == {"trechos": [], "total": 0}


def test_o_erro_de_hoje_volta_amanha_com_o_trecho_original(banco, relogio):
    errar(banco, "kettle")
    assert vencidas(banco, relogio) == []
    relogio.dia = 1
    (trecho,) = banco.revisar(relogio.hoje)["trechos"]
    assert trecho["palavras"] == [{"forma": "kettle", "posicao": 1, "esperada": "kettle"}]
    assert (trecho["video_id"], trecho["inicio"], trecho["fim"]) == ("abcdefghijk", 0, 2)
    assert trecho["texto"] == "The kettle and the teapot."


def test_palavras_da_mesma_fala_vem_juntas(banco, relogio):
    errar(banco, "teapot.", posicao=4)
    errar(banco, "kettle")
    relogio.dia = 1
    assert vencidas(banco, relogio) == [["kettle", "teapot"]]
    assert banco.revisar(relogio.hoje)["total"] == 2


def test_acertada_some_ate_o_prazo_e_volta(banco, relogio):
    errar(banco, "kettle")
    relogio.dia = 1
    prazo = datetime.fromisoformat(revisar(banco)).date()
    assert vencidas(banco, relogio) == []
    relogio.dia = (prazo - date(2026, 11, 25)).days - 1
    assert vencidas(banco, relogio) == []
    relogio.dia += 1
    assert vencidas(banco, relogio) == [["kettle"]]


def test_errada_na_revisao_volta_no_dia_seguinte(banco, relogio):
    errar(banco, "kettle")
    relogio.dia = 1
    revisar(banco, acertou=False)
    assert vencidas(banco, relogio) == []
    relogio.dia = 2
    assert vencidas(banco, relogio) == [["kettle"]]


def test_errada_de_novo_na_pratica_volta_antes_do_prazo_na_fala_nova(banco, relogio):
    errar(banco, "kettle")
    for relogio.dia in (1, 3):
        revisar(banco)
    relogio.dia = 4
    errar(banco, "kettle", fala=2)
    assert vencidas(banco, relogio) == []
    relogio.dia = 5
    (trecho,) = banco.revisar(relogio.hoje)["trechos"]
    assert trecho["texto"] == "A kettle."


def test_a_que_a_pessoa_diz_saber_nao_volta(banco, relogio):
    errar(banco, "kettle")
    relogio.dia = 1
    banco.marcar_sabida("kettle", True)
    assert vencidas(banco, relogio) == []
    banco.marcar_sabida("kettle", False)
    assert vencidas(banco, relogio) == [["kettle"]]


def test_a_revisao_conta_na_situacao(banco, relogio):
    errar(banco, "kettle")
    situacoes = []
    for relogio.dia, acertou in ((1, True), (3, True), (14, False)):
        revisar(banco, acertou=acertou)
        situacoes.append(banco.palavras()[0]["situacao"])
    assert situacoes == [APRENDENDO, CONHECIDA, ERRANDO]


def test_o_limite_nao_quebra_um_trecho_e_o_total_conta_tudo(banco, relogio):
    errar(banco, "kettle")
    errar(banco, "teapot.", posicao=4)
    errar(banco, "Biscuits.", posicao=0, fala=3)
    relogio.dia = 1
    assert vencidas(banco, relogio, limite=1) == [["kettle", "teapot"]]
    assert banco.revisar(relogio.hoje, limite=1)["total"] == 3


def test_o_mais_atrasado_vem_primeiro_e_o_mesmo_video_vem_seguido(banco, relogio):
    errar(banco, "Biscuits.", posicao=0, fala=3)
    relogio.dia = 1
    errar(banco, "grinder.", fala=4)
    relogio.dia = 2
    errar(banco, "kettle")
    relogio.dia = 5
    assert vencidas(banco, relogio) == [["biscuits"], ["kettle"], ["grinder"]]


def test_fala_que_nao_existe(banco):
    assert revisar(banco, fala=99) is None


def test_a_revisao_certa_conta_no_dia(banco, relogio):
    errar(banco, "kettle")
    relogio.dia = 1
    revisar(banco, acertou=False)
    assert banco.resumo(relogio.hoje)["hoje"] == 0
    revisar(banco)
    assert banco.resumo(relogio.hoje)["hoje"] == 1
    assert banco.resumo(relogio.hoje)["dias_seguidos"] == 2


def test_o_cartao_sobrevive_ao_programa_fechado(tmp_path, relogio):
    caminho = tmp_path / "typelead.db"
    banco = Banco(caminho)
    banco.salvar_video("abcdefghijk", "Chá", "Canal", 10.0, True, "autor", [Fala(0, 2, "The kettle.")])
    errar(banco, "kettle.")
    relogio.dia = 1
    primeiro = revisar(banco)
    banco.fechar()
    banco = Banco(caminho)
    relogio.dia = 3
    assert revisar(banco) > primeiro
    banco.fechar()
