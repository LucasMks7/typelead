import random

import pytest

from typelead.divisao import dividir
from typelead.legendas import Fala, Palavra


def falada(texto, inicio=0.0, passo=0.3, troca=False):
    """Uma fala com tempo por palavra, sem pausas."""
    palavras = tuple(
        Palavra(p, inicio + i * passo, inicio + (i + 1) * passo) for i, p in enumerate(texto.split())
    )
    return Fala(palavras[0].inicio, palavras[-1].fim, texto, palavras, troca)


def textos(falas):
    return [fala.texto for fala in falas]


def test_falas_curtas_da_mesma_frase_sao_juntadas():
    falas = [falada("The kettle"), falada("is on", 0.6), falada("the stove.", 1.2)]
    assert textos(dividir(falas)) == ["The kettle is on the stove."]


def test_fala_longa_e_dividida_no_fim_das_frases():
    texto = "I put the kettle on the stove. Then I went out to the garden. It was raining all day."
    assert textos(dividir([falada(texto)])) == [
        "I put the kettle on the stove.",
        "Then I went out to the garden.",
        "It was raining all day.",
    ]


def test_frase_longa_e_dividida_na_virgula():
    texto = "When we got back to the old house, my sister was still looking for her keys."
    assert textos(dividir([falada(texto)])) == [
        "When we got back to the old house,",
        "my sister was still looking for her keys.",
    ]


def test_sem_pontuacao_corta_antes_da_conjuncao_e_nao_depois_do_artigo():
    texto = "we walked along the river for two hours because the train was late again that day"
    primeira, segunda = textos(dividir([falada(texto)]))
    assert segunda.startswith("because")


def test_sem_pontuacao_a_pausa_decide_o_corte():
    falas = [falada("we walked along the river all day"), falada("the train was late again today", 7 * 0.3 + 0.8)]
    assert textos(dividir(falas)) == ["we walked along the river all day", "the train was late again today"]


def test_resposta_curta_de_outra_pessoa_e_juntada_a_pergunta():
    falas = [falada("Do you want some tea?"), falada("Yes!", 1.6, troca=True)]
    assert textos(dividir(falas)) == ["Do you want some tea? Yes!"]


def test_falas_boas_de_pessoas_diferentes_ficam_separadas():
    falas = [falada("Do you want some tea?"), falada("Yes, I would love some.", 1.6, troca=True)]
    prontas = dividir(falas)
    assert textos(prontas) == ["Do you want some tea?", "Yes, I would love some."]
    assert [fala.troca for fala in prontas] == [False, True]


def test_silencio_longo_sempre_separa():
    assert textos(dividir([falada("Tea."), falada("Now.", 10)])) == ["Tea.", "Now."]


def test_abreviacao_nao_encerra_a_frase():
    (fala, *resto) = dividir([falada("I saw Mr. Brown at the old station.")])
    assert not resto


def test_sem_tempo_por_palavra_prefere_cortar_onde_a_legenda_corta():
    falas = [Fala(0, 3, "we walked along the river for hours"), Fala(3, 6, "the train was late again that day")]
    assert textos(dividir(falas)) == [fala.texto for fala in falas]


def test_fala_enorme_sem_tempo_por_palavra_ainda_e_dividida():
    texto = " ".join(f"word{i}" for i in range(30))
    assert max(len(t.split()) for t in textos(dividir([Fala(0, 12, texto)]))) <= 18


def test_margem_usa_o_silencio_vizinho_sem_invadir():
    primeira, segunda = dividir([falada("The kettle is on now."), falada("It is still raining out.", 1.7)])
    # As palavras vão de 0 a 1,5 e de 1,7 em diante: 0,2 s de silêncio.
    assert primeira.inicio == 0
    assert primeira.fim == pytest.approx(1.6)
    assert segunda.inicio == pytest.approx(1.6)


def test_a_margem_e_limitada_em_um_silencio_grande():
    primeira, segunda = dividir([falada("The kettle is on now."), falada("It is still raining out.", 10)])
    assert primeira.fim == pytest.approx(1.65)
    assert segunda.inicio == pytest.approx(9.85)


def test_sem_silencio_a_margem_minima_sobrepoe_um_pouco():
    primeira, segunda = dividir([falada("The kettle is on now."), falada("It is still raining out.", 1.5)])
    assert segunda.inicio < primeira.fim <= segunda.inicio + 0.11


def test_nada_para_dividir():
    assert dividir([]) == []


def test_uma_palavra_so():
    assert textos(dividir([falada("Hi.")])) == ["Hi."]


def test_nunca_perde_repete_nem_troca_a_ordem_das_palavras():
    """Falas sorteadas, com e sem tempo por palavra, pausas e pontuação."""
    sorteio = random.Random(45)
    for _ in range(150):
        falas, agora = [], 0.0
        for _ in range(sorteio.randint(1, 25)):
            palavras = [
                sorteio.choice(["the", "kettle", "and", "a", "rain"]) + sorteio.choice(["", "", "", ",", ".", "?"])
                for _ in range(sorteio.randint(1, 25))
            ]
            agora += sorteio.choice([0, 0.1, 0.6, 4])
            fala = falada(" ".join(palavras), agora, sorteio.choice([0.1, 0.3, 0.9]), sorteio.random() < 0.3)
            agora = fala.fim
            falas.append(fala if sorteio.random() < 0.5 else Fala(fala.inicio, fala.fim, fala.texto, (), fala.troca))
        prontas = dividir(falas)
        assert " ".join(textos(prontas)).split() == " ".join(textos(falas)).split()
        assert all(fala.fim > fala.inicio for fala in prontas)
        assert all(a.inicio <= b.inicio for a, b in zip(prontas, prontas[1:]))
        assert all(len(fala.palavras) <= 18 for fala in prontas)
