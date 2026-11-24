import pytest

from typelead.alinhamento import alinhar, estimar, normalizar
from typelead.legendas import Fala, Palavra


def autor(*partes):
    return [Fala(inicio, fim, texto) for inicio, fim, texto in partes]


def automatica(*palavras):
    """Uma fala automática a partir de (instante, palavra)."""
    prontas = tuple(Palavra(texto, inicio, inicio + 0.2) for inicio, texto in palavras)
    return [Fala(prontas[0].inicio, prontas[-1].fim, "", prontas)]


def instantes(falas):
    return [round(palavra.inicio, 2) for fala in falas for palavra in fala.palavras]


def test_texto_do_autor_com_o_tempo_da_automatica():
    (fala,) = alinhar(
        autor((1, 3, "The kettle is on.")),
        automatica((0.8, "the"), (1.0, "kettle"), (1.9, "is"), (2.1, "on")),
    )
    assert fala.texto == "The kettle is on."
    assert [p.texto for p in fala.palavras] == ["The", "kettle", "is", "on."]
    assert instantes([fala]) == [0.8, 1.0, 1.9, 2.1]
    assert fala.inicio == 0.8


def test_palavra_que_a_automatica_errou_fica_entre_as_vizinhas():
    falas = alinhar(
        autor((1, 3, "The kettle is on now.")),
        automatica((1, "the"), (1.2, "cattle"), (2, "is"), (2.2, "on"), (2.4, "now")),
    )
    the, kettle, is_, *_ = instantes(falas)
    assert the < kettle < is_


@pytest.mark.parametrize("faltando", [0, 4])
def test_ponta_sem_par_usa_o_passo_estimado(faltando):
    palavras = [(1, "the"), (1.4, "kettle"), (1.8, "is"), (2.2, "on"), (2.6, "now")]
    del palavras[faltando]
    tempos = instantes(alinhar(autor((1, 3, "The kettle is on now.")), automatica(*palavras)))
    assert tempos == sorted(tempos) and len(tempos) == 5


def test_repeticao_distante_nao_e_a_mesma_palavra():
    """"yes" aparece de novo um minuto depois; o instante não pode ser o de lá."""
    falas = alinhar(
        autor((1, 2, "The kettle is on now."), (2, 3, "Yes")),
        automatica((1, "the"), (1.2, "kettle"), (1.4, "is"), (1.6, "on"), (1.8, "now"), (60, "yes")),
    )
    assert falas[1].inicio < 4


def test_textos_diferentes_ficam_como_vieram():
    falas = autor((1, 3, "The kettle is on."))
    assert alinhar(falas, automatica((1, "completely"), (2, "different"))) == falas


@pytest.mark.parametrize("vazia", [[], [Fala(1, 2, "sem tempo por palavra")]])
def test_sem_tempos_para_usar_ficam_como_vieram(vazia):
    falas = autor((1, 3, "The kettle is on."))
    assert alinhar(falas, vazia) == falas


def test_palavra_antes_do_silencio_nao_se_estende_por_ele():
    falas = alinhar(
        autor((1, 2, "The kettle."), (30, 31, "Right now.")),
        automatica((1, "the"), (1.3, "kettle"), (30, "right"), (30.3, "now")),
    )
    assert falas[0].fim < 3


def test_o_tempo_nunca_volta():
    falas = alinhar(
        autor((1, 3, "one two three four")), automatica((1, "one"), (2, "two"), (1.5, "three"), (3, "four"))
    )
    tempos = instantes(falas)
    assert tempos == sorted(tempos)


def test_estimativa_divide_pelo_tamanho_e_cobre_a_fala():
    palavras = estimar(Fala(10, 12, "I understand"))
    assert palavras[0].inicio == 10 and palavras[-1].fim == pytest.approx(12)
    assert palavras[1].fim - palavras[1].inicio > palavras[0].fim - palavras[0].inicio


@pytest.mark.parametrize(
    ("texto", "limpo"), [("Kettle,", "kettle"), ("don’t", "don't"), ("'cause", "cause"), ("well-known", "wellknown"), ("...", "")]
)
def test_normalizar(texto, limpo):
    assert normalizar(texto) == limpo
