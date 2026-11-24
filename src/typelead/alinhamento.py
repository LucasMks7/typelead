"""Dá o tempo de cada palavra à legenda que só traz o tempo da fala inteira."""

import re
from dataclasses import replace
from difflib import SequenceMatcher

from .legendas import Fala, Palavra, duracao_maxima

# Abaixo disto, as duas legendas não são do mesmo texto.
FRACAO_MINIMA = 0.6
# Palavras iguais mais distantes que isto são coincidência, não a mesma.
DISTANCIA_MAXIMA = 3.0


def alinhar(do_autor: list[Fala], automatica: list[Fala]) -> list[Fala]:
    """Junta o texto do autor, que é correto, com os tempos da legenda automática.

    Devolve as falas do autor como vieram se as duas não combinarem.
    """
    certas = [(i, palavra) for i, fala in enumerate(do_autor) for palavra in fala.texto.split()]
    ouvidas = [palavra for fala in automatica for palavra in fala.palavras]
    if not certas or not ouvidas:
        return do_autor

    estimadas = [palavra.inicio for fala in do_autor for palavra in estimar(fala)]
    inicios: list[float | None] = [None] * len(certas)
    casador = SequenceMatcher(
        None, [normalizar(p) for _, p in certas], [normalizar(p.texto) for p in ouvidas], autojunk=False
    )
    for a, b, quantidade in casador.get_matching_blocks():
        for k in range(quantidade):
            if abs(ouvidas[b + k].inicio - estimadas[a + k]) <= DISTANCIA_MAXIMA:
                inicios[a + k] = ouvidas[b + k].inicio
    if sum(inicio is not None for inicio in inicios) < FRACAO_MINIMA * len(certas):
        return do_autor

    completos = _completar(inicios, estimadas)
    prontas, posicao = [], 0
    for fala in do_autor:
        textos = fala.texto.split()
        palavras = []
        for k, texto in enumerate(textos):
            inicio = completos[posicao + k]
            seguinte = completos[posicao + k + 1] if posicao + k + 1 < len(completos) else fala.fim
            fim = min(max(seguinte, inicio + 0.02), inicio + duracao_maxima(texto))
            palavras.append(Palavra(texto, inicio, fim))
        posicao += len(textos)
        prontas.append(replace(fala, inicio=palavras[0].inicio, fim=palavras[-1].fim, palavras=tuple(palavras)))
    return prontas


def _completar(inicios: list[float | None], estimadas: list[float]) -> list[float]:
    """Preenche as palavras sem par, entre as vizinhas que têm, sem voltar no tempo."""
    conhecidas = [i for i, inicio in enumerate(inicios) if inicio is not None]
    prontos: list[float] = []
    for i, inicio in enumerate(inicios):
        if inicio is None:
            antes = max((k for k in conhecidas if k < i), default=None)
            depois = min((k for k in conhecidas if k > i), default=None)
            if antes is None:
                inicio = inicios[depois] + estimadas[i] - estimadas[depois]
            elif depois is None:
                inicio = inicios[antes] + estimadas[i] - estimadas[antes]
            else:
                # A mesma proporção que a estimativa dava entre as duas vizinhas.
                total = estimadas[depois] - estimadas[antes]
                parte = (estimadas[i] - estimadas[antes]) / total if total > 0 else 0.5
                inicio = inicios[antes] + parte * (inicios[depois] - inicios[antes])
        inicio = max(inicio, 0.0)
        prontos.append(max(inicio, prontos[-1]) if prontos else inicio)
    return prontos


def estimar(fala: Fala) -> tuple[Palavra, ...]:
    """O tempo das palavras, real ou dividido conforme o tamanho de cada uma."""
    if fala.palavras:
        return fala.palavras
    textos = fala.texto.split()
    total = sum(len(texto) + 1 for texto in textos)
    palavras, agora = [], fala.inicio
    for texto in textos:
        proximo = agora + (fala.fim - fala.inicio) * (len(texto) + 1) / total
        palavras.append(Palavra(texto, agora, proximo))
        agora = proximo
    return tuple(palavras)


def normalizar(texto: str) -> str:
    """A palavra sem pontuação nem maiúsculas, para comparar."""
    return re.sub(r"[^\w']", "", texto.lower().replace("’", "'")).strip("'")
