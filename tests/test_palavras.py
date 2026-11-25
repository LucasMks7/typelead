import itertools
import uuid

import pytest

from typelead.banco import Banco, Item, Tentativa
from typelead.diagnostico import Desistencia
from typelead.legendas import Fala
from typelead.palavras import (
    ALVOS,
    APRENDENDO,
    CONHECIDA,
    ERRANDO,
    NOVA,
    SABIDA,
    formas,
    frequencia,
    peso,
    situacao,
)

# A regra


@pytest.mark.parametrize(
    ("erros", "seguidos", "esperada"),
    [(0, 0, NOVA), (0, 1, CONHECIDA), (1, 0, ERRANDO), (3, 1, APRENDENDO), (3, 2, CONHECIDA)],
)
def test_situacao(erros, seguidos, esperada):
    assert situacao(erros, seguidos) == esperada
    assert situacao(erros, seguidos, sabida=True) == SABIDA


def test_frequencia_distingue_o_comum_do_raro():
    assert frequencia("the") > frequencia("resolution") > frequencia("ubiquitous") > 0
    assert frequencia("xqzvbn") == 0


def test_frequencia_usa_a_grafia_com_hifen_e_apostrofo():
    assert frequencia("well-known") > frequencia("wellknown")
    assert frequencia("don’t") == frequencia("don't")


@pytest.mark.parametrize(
    ("nivel", "palavra"), [("iniciante", "house"), ("intermediario", "resolution"), ("avancado", "ubiquitous")]
)
def test_cada_nivel_prefere_a_propria_faixa(nivel, palavra):
    palavras = ["house", "resolution", "ubiquitous"]
    assert max(palavras, key=lambda p: peso(p, nivel, NOVA)) == palavra


def test_errada_pesa_mais_que_nova_e_sabida_quase_nada():
    pesos = [peso("kettle", "intermediario", s) for s in (ERRANDO, APRENDENDO, NOVA, CONHECIDA, SABIDA)]
    assert pesos == sorted(pesos, reverse=True)
    assert len(set(pesos)) == len(pesos)


@pytest.mark.parametrize("nivel", ALVOS)
@pytest.mark.parametrize("palavra", ["the", "xqzvbn", "&", "1999", ""])
def test_peso_nunca_e_zero(nivel, palavra):
    assert peso(palavra, nivel, SABIDA) > 0


def test_formas():
    assert formas(["Kettle,", "don’t", "well-known", "&"]) == ["kettle", "don't", "wellknown", ""]


# O histórico, no banco


@pytest.fixture
def banco(monkeypatch):
    # Um instante por gravação: no mesmo microssegundo, não haveria antes e depois.
    instantes = (f"2026-11-25T10:{n // 60:02}:{n % 60:02}.000000+00:00" for n in itertools.count())
    monkeypatch.setattr("typelead.banco._agora", lambda: next(instantes))
    banco = Banco()
    banco.salvar_video(
        "abcdefghijk", "Chá", "Canal", 10.0, True, "autor", [Fala(0, 2, "The kettle."), Fala(2, 4, "A kettle.")]
    )
    yield banco
    banco.fechar()


def praticar(banco, *tentativas, fala=1, desistiu=False, rodada=None, **mudancas):
    """Uma rodada. Cada tentativa é o que foi digitado no lugar de "kettle"."""
    rodada = rodada or str(uuid.uuid4())
    for repeticoes, digitada in enumerate(tentativas, 1):
        tipo = "faltou" if not digitada else "certa" if digitada == "kettle" else "trocada"
        dados = {
            "fala_id": fala,
            "rodada": rodada,
            "modo": "oculto",
            "corrigir": "enter",
            "texto": digitada,
            "com_ajuda": False,
            "repeticoes": repeticoes,
            "velocidade": 1,
            "duracao": 1,
            "itens": (Item(tipo, 1, "kettle.", digitada),),
        }
        banco.salvar_tentativa(Tentativa(**(dados | mudancas)))
    if desistiu:
        banco.desistir(rodada, Desistencia(1, 1, False))
    banco.diagnosticar(rodada)
    return rodada


def test_sem_historico(banco):
    assert banco.palavras() == []
    assert banco.situacoes() == {}


def test_acerto_de_primeira_nao_entra_na_lista_mas_conta(banco):
    praticar(banco, "kettle")
    assert banco.palavras() == []
    assert banco.situacoes() == {"kettle": CONHECIDA}


def test_acerto_com_ajuda_nao_conta(banco):
    praticar(banco, "kettle", com_ajuda=True)
    assert banco.situacoes() == {}


def test_erro_de_escuta_entra_com_a_fala_de_onde_veio(banco):
    praticar(banco, "castle", "kettle")  # acertou depois de ouvir de novo
    (palavra,) = banco.palavras()
    assert (palavra["forma"], palavra["situacao"], palavra["motivo"]) == ("kettle", ERRANDO, "escuta")
    # A rodada foi um erro, mesmo terminando certa.
    assert (palavra["erros"], palavra["acertos"]) == (1, 0)
    assert (palavra["texto"], palavra["posicao"], palavra["esperada"]) == ("The kettle.", 1, "kettle.")
    assert (palavra["video_id"], palavra["titulo"], palavra["inicio"]) == ("abcdefghijk", "Chá", 0)


def test_a_mesma_palavra_errada_tres_vezes_na_rodada_e_um_erro(banco):
    praticar(banco, "castle", "cattle", "cable", "kettle")
    assert banco.palavras()[0]["erros"] == 1


def test_digitacao_nao_e_palavra_para_estudar(banco):
    praticar(banco, "kettel", "kettle")  # duas letras invertidas
    assert banco.palavras() == []


def test_em_branco_e_consertada_sem_ouvir_de_novo_nao_conta(banco):
    # Enter no meio da fala: as palavras seguintes ainda não tinham sido digitadas.
    rodada = praticar(banco, "", repeticoes=1)
    praticar(banco, "kettle", repeticoes=1, rodada=rodada, desistiu=True)
    assert banco.palavras() == []


def test_desistir_conta_mesmo_sem_saber_o_motivo(banco):
    praticar(banco, "", desistiu=True)
    (palavra,) = banco.palavras()
    assert (palavra["motivo"], palavra["situacao"]) == ("indefinido", ERRANDO)


@pytest.mark.parametrize(("palavra", "entra"), [("and", False), ("limb", True)])
def test_palavra_muito_comum_deixada_em_branco_nao_conta(banco, palavra, entra):
    praticar(banco, "", desistiu=True, itens=(Item("faltou", 0, palavra, ""),))
    assert bool(banco.palavras()) is entra


def test_palavra_muito_comum_trocada_por_outra_conta(banco):
    praticar(banco, "x", desistiu=True, itens=(Item("trocada", 0, "and", "under"),))
    assert banco.palavras()[0]["forma"] == "and"


def test_palavra_muito_comum_em_branco_conta_se_a_pessoa_disser_o_motivo(banco):
    rodada = praticar(banco, "", desistiu=True, itens=(Item("faltou", 0, "and", ""),))
    (erro,) = banco.diagnosticar(rodada)
    banco.corrigir_diagnostico(erro["id"], "escuta")
    assert banco.palavras()[0]["motivo"] == "escuta"


def test_ainda_tentando_nao_conta(banco):
    praticar(banco, "castle")
    assert banco.palavras() == []


def test_o_motivo_corrigido_vale_mais(banco):
    rodada = praticar(banco, "castle", "cattle", "kettle")
    (erro,) = banco.diagnosticar(rodada)
    banco.corrigir_diagnostico(erro["id"], "digitacao")
    # Some de vez: o erro anterior da mesma palavra, na mesma rodada, não o substitui.
    assert banco.palavras() == []


def test_de_errando_a_conhecida_e_de_volta(banco):
    situacoes = []
    praticar(banco, "castle", "kettle")
    for tentativas in (["kettle"], ["kettle"], ["castle", "kettle"]):
        praticar(banco, *tentativas, fala=2)
        situacoes.append(banco.palavras()[0]["situacao"])
    assert situacoes == [APRENDENDO, CONHECIDA, ERRANDO]
    assert banco.palavras()[0]["texto"] == "A kettle."
    assert (banco.palavras()[0]["erros"], banco.palavras()[0]["acertos"]) == (2, 2)


def test_ja_sei_vale_mais_que_o_historico_e_pode_ser_desfeito(banco):
    praticar(banco, "castle", "kettle")
    banco.marcar_sabida("kettle", True)
    banco.marcar_sabida("kettle", True)
    assert banco.palavras()[0]["situacao"] == SABIDA
    assert banco.situacoes() == {"kettle": SABIDA}
    banco.marcar_sabida("kettle", False)
    assert banco.palavras()[0]["situacao"] == ERRANDO


def test_sabida_que_nunca_apareceu(banco):
    banco.marcar_sabida("teapot", True)
    assert banco.situacoes() == {"teapot": SABIDA}
    assert banco.palavras() == []


def test_numero_e_contracao_que_vale_por_duas_palavras_ficam_de_fora(banco):
    praticar(banco, "x", itens=(Item("certa", 0, "1999", "1999"),))
    praticar(banco, "x", modo="livre", itens=(Item("certa", 0, "going to", "gonna"),))
    assert banco.situacoes() == {}


def test_sobrou_nao_e_palavra(banco):
    praticar(banco, "x", itens=(Item("sobrou", 1, "", "teapot"),), desistiu=True)
    assert banco.palavras() == []


def test_trocar_a_legenda_mantem_as_palavras(banco):
    praticar(banco, "castle", "kettle")
    banco.salvar_video("abcdefghijk", "Chá", "Canal", 10.0, True, "arquivo", [Fala(0, 2, "Other.")])
    assert banco.palavras()[0]["texto"] == "The kettle."
