import pytest

from typelead.traducao import FalhaNaTraducao, Tradutor, preparar


def test_maiusculas_viram_texto_comum():
    assert preparar("KEEP EACH OTHER COMPANY") == "Keep each other company"
    assert preparar("I'm in the USA.") == "I'm in the USA."
    assert preparar("") == ""


def test_o_modelo_carrega_uma_vez_e_so_quando_pedem():
    vezes = []

    def carregar():
        vezes.append(1)
        return lambda texto: f" {texto} em português "

    tradutor = Tradutor(carregar)
    assert vezes == []
    assert tradutor.traduzir("Tea") == "Tea em português"
    tradutor.traduzir("Cup")
    assert vezes == [1]


def test_falha_ao_carregar_permite_tentar_de_novo():
    respostas = iter([OSError("sem internet"), lambda texto: "ok"])

    def carregar():
        resposta = next(respostas)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta

    tradutor = Tradutor(carregar)
    with pytest.raises(FalhaNaTraducao, match="sem internet"):
        tradutor.traduzir("Tea")
    assert tradutor.traduzir("Tea") == "ok"


def test_falha_do_modelo_e_resposta_vazia():
    def quebrar(_):
        raise RuntimeError("memória")

    with pytest.raises(FalhaNaTraducao, match="memória"):
        Tradutor(lambda: quebrar).traduzir("Tea")
    with pytest.raises(FalhaNaTraducao, match="não devolveu"):
        Tradutor(lambda: lambda _: "  ").traduzir("Tea")
