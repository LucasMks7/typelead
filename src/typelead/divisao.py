"""Divide o que foi falado em trechos bons de praticar.

A legenda quebra o texto para caber na tela; aqui ele é quebrado para caber na
memória: de 4 a 10 palavras, de preferência terminando onde a frase termina.
"""

import re
from dataclasses import dataclass

from .alinhamento import estimar, normalizar
from .legendas import Fala, Palavra

MINIMO_BOM, MAXIMO_BOM = 4, 10
MAXIMO_DE_PALAVRAS = 18
DURACAO_BOA = 6.0
DURACAO_MAXIMA = 12.0
# Um silêncio destes sempre separa.
SILENCIO_QUE_SEPARA = 2.5

# O trecho começa um pouco antes e termina um pouco depois da fala: os tempos das
# palavras têm erro de décimos, e o gravador atrasa perto de 90 ms.
MARGEM = 0.15
MARGEM_MINIMA = 0.05

FIM_DE_FRASE = (".", "!", "?", "…")
FIM_DE_PARTE = (",", ";", ":", "—", "–")
# Abreviações que terminam com ponto e não encerram a frase.
ABREVIACOES = {"mr.", "mrs.", "ms.", "dr.", "st.", "vs.", "prof.", "jr.", "sr.", "e.g.", "i.e."}
# Antes destas, cortar soa natural; depois das outras, nunca.
COMECAM_PARTE = frozenset(
    "and but or so because if when while that which who where than then although though unless until".split()
)
PEDEM_CONTINUACAO = frozenset(
    "a an the my your his her its our their of to in on at for with from by as is are was were am be "
    "i'm you're he's she's it's we're they're i you he she we they and but or so because if very not".split()
)
# "Ooooh", "mmm", "la la": não há o que escutar nem como escrever.
VOCALIZACAO = re.compile(r"o+h+|a+h+|u+h+|e+h+|o{3,}|a{3,}|m{2,}|h+m+|w+h?o+a+h*|(?:la+|na+|da+|doo+)+")
# Escritas só com vocalizações, mas querem dizer sim, não ou "deu errado".
COM_SENTIDO = {"mmhmm", "mmhm", "mhmm", "mhm", "uhuh", "uhoh"}


@dataclass(frozen=True)
class _Item:
    palavra: Palavra
    # Começa uma fala da legenda original; se vale o tempo dela, é exato.
    comeca_fala: bool
    exato: bool
    troca: bool


def dividir(falas: list[Fala]) -> list[Fala]:
    """Refaz as falas. Cada palavra aparece uma vez, na ordem em que foi dita.

    Só ficam de fora os trechos inteiros de vocalização, a não ser que tudo seja.
    """
    itens = [
        _Item(palavra, k == 0, k == 0 or bool(fala.palavras), k == 0 and fala.troca)
        for fala in falas
        for k, palavra in enumerate(estimar(fala))
    ]
    if not itens:
        return []
    trechos = [_montar(itens[a:b]) for a, b in _melhores_trechos(itens)]
    return _com_margens([trecho for trecho in trechos if not _so_vocalizacao(trecho)] or trechos)


def _so_vocalizacao(fala: Fala) -> bool:
    # Um travessão ou reticências soltas também não são palavra.
    for palavra in fala.texto.split():
        if normalizar(palavra) in COM_SENTIDO:
            return False
        partes = [normalizar(parte) for parte in palavra.split("-")]
        if not all(VOCALIZACAO.fullmatch(parte) for parte in partes if parte):
            return False
    return True


def _melhores_trechos(itens: list[_Item]) -> list[tuple[int, int]]:
    """Escolhe os cortes de menor custo total, por programação dinâmica.

    menor[fim] é o menor custo para dividir as palavras até fim. Cada uma é
    alcançada a partir das até MAXIMO_DE_PALAVRAS anteriores, então o tempo
    cresce em linha reta com o tamanho do vídeo.
    """
    quantidade = len(itens)
    menor = [0.0] + [float("inf")] * quantidade
    veio_de = [0] * (quantidade + 1)
    for fim in range(1, quantidade + 1):
        custo_do_corte = _custo_do_corte(itens, fim) if fim < quantidade else 0.0
        dentro = 0.0
        for comeco in range(fim - 1, max(-1, fim - 1 - MAXIMO_DE_PALAVRAS), -1):
            if comeco < fim - 1:
                emenda = _custo_da_emenda(itens, comeco + 1)
                if emenda is None:
                    break
                dentro += emenda
            duracao = itens[fim - 1].palavra.fim - itens[comeco].palavra.inicio
            if duracao > DURACAO_MAXIMA and comeco < fim - 1:
                break
            custo = menor[comeco] + custo_do_corte + dentro + _custo_do_tamanho(fim - comeco, duracao)
            if custo < menor[fim]:
                menor[fim], veio_de[fim] = custo, comeco

    trechos, fim = [], quantidade
    while fim > 0:
        trechos.append((veio_de[fim], fim))
        fim = veio_de[fim]
    return trechos[::-1]


def _custo_do_tamanho(palavras: int, duracao: float) -> float:
    custo = 0.0
    if palavras < MINIMO_BOM:
        custo += (MINIMO_BOM - palavras) ** 2
    if palavras > MAXIMO_BOM:
        custo += 0.6 * (palavras - MAXIMO_BOM) ** 2
    return custo + 1.5 * max(0.0, duracao - DURACAO_BOA)


def _custo_do_corte(itens: list[_Item], posicao: int) -> float:
    """Quanto custa cortar antes desta palavra."""
    antes, depois = itens[posicao - 1].palavra, itens[posicao]
    pausa = depois.palavra.inicio - antes.fim
    if depois.troca or _termina_frase(antes.texto):
        custo = 0.0
    elif pausa >= 0.5:
        custo = 0.5
    elif antes.texto.endswith(FIM_DE_PARTE):
        custo = 1.5
    elif normalizar(depois.palavra.texto) in COMECAM_PARTE:
        custo = 2.5
    else:
        custo = 4.0
    if not antes.texto.endswith(FIM_DE_FRASE + FIM_DE_PARTE) and normalizar(antes.texto) in PEDEM_CONTINUACAO:
        custo += 3.0
    # Dentro de uma fala sem tempo por palavra, o corte cairia em um ponto estimado.
    return custo if depois.exato else custo + 3.0


def _custo_da_emenda(itens: list[_Item], posicao: int) -> float | None:
    """Quanto custa não cortar antes desta palavra; None se o corte é obrigatório."""
    antes, depois = itens[posicao - 1].palavra, itens[posicao]
    pausa = max(0.0, depois.palavra.inicio - antes.fim)
    if pausa >= SILENCIO_QUE_SEPARA:
        return None
    custo = 1.5 * pausa
    if depois.troca:
        custo += 3.0
    elif _termina_frase(antes.texto):
        custo += 1.5
    return custo


def _termina_frase(texto: str) -> bool:
    limpo = texto.rstrip("\"'”’)")
    return limpo.endswith(FIM_DE_FRASE) and limpo.lower() not in ABREVIACOES


def _montar(itens: list[_Item]) -> Fala:
    palavras = tuple(item.palavra for item in itens)
    return Fala(
        palavras[0].inicio,
        palavras[-1].fim,
        " ".join(palavra.texto for palavra in palavras),
        palavras,
        itens[0].troca,
    )


def _com_margens(falas: list[Fala]) -> list[Fala]:
    """Estica cada trecho até a metade do silêncio vizinho, sem passar da margem."""
    prontas = []
    for i, fala in enumerate(falas):
        antes = fala.inicio - falas[i - 1].fim if i else fala.inicio
        depois = falas[i + 1].inicio - fala.fim if i + 1 < len(falas) else MARGEM * 2
        prontas.append(
            Fala(
                max(0.0, fala.inicio - _margem(antes)),
                fala.fim + _margem(depois),
                fala.texto,
                fala.palavras,
                fala.troca,
            )
        )
    return prontas


def _margem(silencio: float) -> float:
    return min(MARGEM, max(MARGEM_MINIMA, silencio / 2))
