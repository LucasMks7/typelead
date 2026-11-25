import pytest

from typelead.alinhamento import normalizar
from typelead.diagnostico import (
    DIGITACAO,
    ESCUTA,
    HOMOFONO,
    HOMOFONOS,
    INDEFINIDO,
    VIZINHAS,
    VOCABULARIO,
    Desistencia,
    Erro,
    Passo,
    diagnosticar,
    parece_digitacao,
    sao_homofonos,
)


def passo(*erros, certas=(), repeticoes=1, velocidade=1.0, traduziu=False, com_ajuda=False):
    return Passo(repeticoes, velocidade, traduziu, com_ajuda, frozenset(certas), tuple(erros))


def erro(esperada, digitada, posicao=0, numero=1):
    return Erro(numero, posicao, esperada, digitada)


def um(*passos, conhecidas=(), desistencia=None):
    return diagnosticar(passos, set(conhecidas), desistencia)[1]


DESISTIU = Desistencia(1, 1.0, False)


def test_enquanto_a_pessoa_tenta_nao_ha_diagnostico():
    assert um(passo(erro("kettle", "cattle"))) is None


def test_acertou_depois_de_ouvir_de_novo_ou_mais_devagar():
    assert um(passo(erro("kettle", "castle")), passo(certas=[0], repeticoes=2)) == ESCUTA
    assert um(passo(erro("kettle", "castle")), passo(certas=[0], velocidade=0.75)) == ESCUTA
    assert um(passo(erro("kettle", "")), passo(certas=[0], repeticoes=3)) == ESCUTA


def test_consertou_sem_ouvir_de_novo():
    assert um(passo(erro("kettle", "ketle")), passo(certas=[0])) == DIGITACAO
    assert um(passo(erro("kettle", "castle")), passo(certas=[0])) == INDEFINIDO


def test_acertou_so_na_terceira():
    passos = [passo(erro("kettle", "castle")), passo(erro("kettle", "cattle", numero=2)), passo(certas=[0], repeticoes=4)]
    assert diagnosticar(passos, set()) == {1: ESCUTA, 2: ESCUTA}


def test_acertar_outra_palavra_nao_conta():
    assert um(passo(erro("kettle", "castle", posicao=2)), passo(certas=[0, 1], repeticoes=2)) is None


def test_acertar_com_a_resposta_a_mostra_nao_conta():
    passos = [passo(erro("kettle", "castle")), passo(certas=[0], repeticoes=2, com_ajuda=True)]
    assert um(*passos) is None
    assert um(*passos, desistencia=Desistencia(2, 0.5, False)) == VOCABULARIO


def test_desistiu_depois_de_ouvir_devagar_ou_de_traduzir():
    errou = passo(erro("kettle", "castle"))
    assert um(errou, desistencia=Desistencia(4, 0.5, False)) == VOCABULARIO
    assert um(errou, desistencia=Desistencia(1, 1.0, True)) == VOCABULARIO
    assert um(errou, desistencia=DESISTIU) == INDEFINIDO


def test_palavra_conhecida_que_o_ouvido_nao_pegou():
    errou = passo(erro("Kettle,", "castle"))
    assert um(errou, conhecidas=["kettle"], desistencia=Desistencia(4, 0.5, True)) == ESCUTA


def test_erro_de_dedo_em_palavra_conhecida_nao_espera_a_proxima_tentativa():
    assert um(passo(erro("kettle", "ketle")), conhecidas=["kettle"]) == DIGITACAO


def test_letras_invertidas_sao_digitacao_mesmo_em_palavra_nova():
    assert um(passo(erro("divorce", "divroce")), desistencia=Desistencia(4, 0.5, True)) == DIGITACAO
    # Em palavra curta, a inversão pode ser outra palavra: "was" e "saw" não, mas "on" e "no" sim.
    assert um(passo(erro("on", "no")), desistencia=DESISTIU) == INDEFINIDO


def test_homofono_vale_antes_de_tudo():
    assert um(passo(erro("there", "their"))) == HOMOFONO
    assert um(passo(erro("They're", "there")), passo(certas=[0], repeticoes=3)) == HOMOFONO


def test_cada_erro_tem_o_proprio_diagnostico():
    passos = [passo(erro("two", "too", 0, 1), erro("kettle", "castle", 1, 2), erro("cups", "cpus", 2, 3))]
    passos.append(passo(erro("kettle", "cattle", 1, 4), certas=[0, 2]))
    assert diagnosticar(passos, set(), Desistencia(2, 0.75, False)) == {
        1: HOMOFONO,
        2: VOCABULARIO,
        3: DIGITACAO,
        4: VOCABULARIO,
    }


def test_sem_erros():
    assert diagnosticar([passo(certas=[0, 1])], set()) == {}
    assert diagnosticar([], set(), DESISTIU) == {}


@pytest.mark.parametrize(
    ("esperada", "digitada"),
    [("know", "knwo"), ("kettle", "kettl"), ("kettle", "kettlle"), ("kettle", "ketyle"), ("the", "teh"), ("you", "yoi"), ("don't", "dnot")],
)
def test_parece_erro_de_dedo(esperada, digitada):
    assert parece_digitacao(esperada, digitada)


@pytest.mark.parametrize(
    ("esperada", "digitada"),
    [("cat", "can"), ("know", "know"), ("kettle", "castle"), ("the", "they"), ("a", "i"), ("in", "on"), ("kettle", "k"), ("go", "got")],
)
def test_nao_parece_erro_de_dedo(esperada, digitada):
    assert not parece_digitacao(esperada, digitada)


def test_teclas_vizinhas():
    for par in ("qw", "as", "aq", "sw", "za", "nm", "hj", "yu", "gt"):
        assert frozenset(par) in VIZINHAS, par
    for par in ("qp", "am", "ez", "ao"):
        assert frozenset(par) not in VIZINHAS, par


def test_homofonos():
    assert sao_homofonos("two", "too") and sao_homofonos("too", "two")
    assert not sao_homofonos("two", "two")
    assert not sao_homofonos("two", "three")


def test_a_lista_de_homofonos_esta_na_forma_em_que_e_comparada():
    """Um apóstrofo no começo, como em 've, se perderia na comparação."""
    for grupo in HOMOFONOS:
        assert len(grupo) > 1
        for palavra in grupo:
            assert normalizar(palavra) == palavra, palavra
