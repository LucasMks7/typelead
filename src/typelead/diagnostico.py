"""Descobre por que uma palavra foi errada, por regras simples.

A mesma palavra pode mudar de diagnóstico: só depois se sabe se a pessoa acertou
ouvindo de novo, ou se desistiu. Por isso a rodada inteira é reavaliada sempre.
"""

import re
from collections.abc import Collection, Sequence
from dataclasses import dataclass

from .alinhamento import normalizar

DIGITACAO = "digitacao"
ESCUTA = "escuta"
VOCABULARIO = "vocabulario"
HOMOFONO = "homofono"
# Os sinais não bastam: melhor dizer isso que chutar.
INDEFINIDO = "indefinido"
TIPOS = (DIGITACAO, ESCUTA, VOCABULARIO, HOMOFONO, INDEFINIDO)

# Palavras de som igual, ou quase, na fala corrente. Lista escrita para o projeto.
HOMOFONOS = tuple(
    frozenset(grupo.split())
    for grupo in """
    their there they're
    your you're
    its it's
    to too two
    were we're where
    whose who's
    then than
    of have
    hear here
    know no
    knew new
    right write rite
    night knight
    by buy bye
    for four fore
    ate eight
    one won
    son sun
    sea see
    be bee
    been bin
    meet meat
    peace piece
    plain plane
    pair pear pare
    bear bare
    fair fare
    hair hare
    stair stare
    wait weight
    way weigh
    week weak
    whole hole
    which witch
    whether weather
    wood would
    break brake
    steal steel
    real reel
    heal heel he'll
    mail male
    tail tale
    sail sale
    made maid
    main mane
    pain pane
    rain reign rein
    road rode
    role roll
    root route
    sole soul
    some sum
    threw through
    blue blew
    flew flu
    flour flower
    our hour are
    aloud allowed
    ant aunt
    base bass
    board bored
    cell sell
    cent scent sent
    cite sight site
    course coarse
    dear deer
    die dye
    fir fur
    great grate
    hi high
    him hymn
    i eye
    i'll aisle isle
    knot not
    lead led
    loan lone
    mind mined
    morning mourning
    muscle mussel
    oh owe
    past passed
    pray prey
    principal principle
    red read
    ring wring
    sew so sow
    shore sure
    stationary stationery
    tea tee
    tied tide
    toe tow
    vain vein
    waist waste
    warn worn
    ware wear
    we'll wheel
    we've weave
    you'll yule
    """.strip().splitlines()
)

# Quem está ao lado de quem no teclado, nas fileiras do QWERTY.
FILEIRAS = ("qwertyuiop", "asdfghjkl", "zxcvbnm")


def _vizinhas() -> set[frozenset[str]]:
    pares = set()
    for numero, fileira in enumerate(FILEIRAS):
        pares |= {frozenset(par) for par in zip(fileira, fileira[1:])}
        # Cada fileira começa um pouco à direita da de cima.
        if numero + 1 < len(FILEIRAS):
            for coluna, letra in enumerate(FILEIRAS[numero + 1]):
                pares |= {frozenset((letra, acima)) for acima in fileira[coluna : coluna + 2]}
    return pares


VIZINHAS = _vizinhas()


@dataclass(frozen=True)
class Erro:
    id: int
    posicao: int
    esperada: str
    digitada: str


@dataclass(frozen=True)
class Passo:
    """Uma tentativa da rodada. As medidas são as acumuladas até ela."""

    repeticoes: int
    velocidade: float
    traduziu: bool
    com_ajuda: bool
    # As posições acertadas e os erros.
    certas: frozenset[int]
    erros: tuple[Erro, ...]


@dataclass(frozen=True)
class Desistencia:
    """A pessoa pediu a resposta. As medidas são as de quando ela pediu."""

    repeticoes: int
    velocidade: float
    traduziu: bool


def diagnosticar(
    passos: Sequence[Passo], conhecidas: Collection[str], desistencia: Desistencia | None = None
) -> dict[int, str | None]:
    """O diagnóstico de cada erro da rodada; None enquanto a pessoa ainda tenta.

    `conhecidas`: as palavras já acertadas antes, sem ajuda, em outras rodadas.
    """
    return {
        erro.id: _de_um(erro, passo, passos[i + 1 :], conhecidas, desistencia)
        for i, passo in enumerate(passos)
        for erro in passo.erros
    }


def _de_um(
    erro: Erro,
    passo: Passo,
    seguintes: Sequence[Passo],
    conhecidas: Collection[str],
    desistencia: Desistencia | None,
) -> str | None:
    esperada, digitada = normalizar(erro.esperada), normalizar(erro.digitada)
    conhecida = esperada in conhecidas
    if digitada and sao_homofonos(esperada, digitada):
        return HOMOFONO
    parecida = bool(digitada) and parece_digitacao(esperada, digitada)
    # Com todas as letras e só duas fora de ordem, a palavra era conhecida.
    if parecida and (conhecida or (len(esperada) > 3 and inverteu(esperada, digitada))):
        return DIGITACAO

    # Com a resposta à mostra, acertar não diz nada.
    acerto = next((s for s in seguintes if erro.posicao in s.certas and not s.com_ajuda), None)
    if acerto is not None:
        ouviu_de_novo = acerto.repeticoes > passo.repeticoes or acerto.velocidade < passo.velocidade
        if ouviu_de_novo:
            return ESCUTA
        # Consertou sem ouvir de novo: já sabia qual era a palavra.
        return DIGITACAO if parecida else INDEFINIDO

    if desistencia is None:
        return None
    if conhecida:
        return ESCUTA
    if desistencia.traduziu or desistencia.velocidade < 1:
        return VOCABULARIO
    return INDEFINIDO


def sao_homofonos(uma: str, outra: str) -> bool:
    return uma != outra and any(uma in grupo and outra in grupo for grupo in HOMOFONOS)


def parece_digitacao(esperada: str, digitada: str) -> bool:
    """Uma letra trocada, a mais ou a menos, ou duas vizinhas invertidas.

    Em palavra curta, uma letra muda quase tudo ("cat" e "can"): em três letras, só
    valem a tecla vizinha e a inversão; em duas, só a inversão ("in" e "on").
    """
    a, b = _so_letras(esperada), _so_letras(digitada)
    if a == b:
        return False
    if len(a) == len(b):
        trocas = [i for i in range(len(a)) if a[i] != b[i]]
        if len(trocas) == 1:
            vizinhas = frozenset((a[trocas[0]], b[trocas[0]])) in VIZINHAS
            return len(a) > 3 or (len(a) == 3 and vizinhas)
        return inverteu(a, b)
    curta, longa = sorted((a, b), key=len)
    if len(longa) - len(curta) != 1 or len(a) <= 3:
        return False
    return any(longa[:i] + longa[i + 1 :] == curta for i in range(len(longa)))


def inverteu(esperada: str, digitada: str) -> bool:
    """Duas letras vizinhas fora de ordem, e nada mais."""
    a, b = _so_letras(esperada), _so_letras(digitada)
    if len(a) != len(b):
        return False
    trocas = [i for i in range(len(a)) if a[i] != b[i]]
    return (
        len(trocas) == 2
        and trocas[1] == trocas[0] + 1
        and a[trocas[0]] == b[trocas[1]]
        and a[trocas[1]] == b[trocas[0]]
    )


def _so_letras(palavra: str) -> str:
    return re.sub(r"[^\w]", "", palavra)
