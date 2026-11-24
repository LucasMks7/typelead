"""Lê legendas (SRT, VTT e o json3 do YouTube) e devolve falas com tempo."""

import html
import re
from dataclasses import dataclass, replace

# Uma legenda de três horas de filme tem menos de 300 KB.
TAMANHO_MAXIMO = 5_000_000


class LegendaInvalida(ValueError):
    """O conteúdo recebido não é uma legenda que dê para praticar."""


@dataclass(frozen=True)
class Palavra:
    texto: str
    inicio: float  # em segundos
    fim: float


@dataclass(frozen=True)
class Fala:
    inicio: float
    fim: float
    texto: str
    # Vazia quando a legenda só diz o tempo da fala inteira.
    palavras: tuple[Palavra, ...] = ()
    # A fala começa com outra pessoa falando ("- Oi", ">> Oi").
    troca: bool = False


TEMPO = r"(?:(\d{1,3}):)?(\d{1,2}):(\d{2})[.,](\d{1,3})"
LINHA_DE_TEMPO = re.compile(rf"^\s*{TEMPO}\s*-->\s*{TEMPO}", re.ASCII)
TEMPO_NO_TEXTO = re.compile(rf"<{TEMPO}>", re.ASCII)
MARCACAO = re.compile(r"</?[a-zA-Z][^<>\n]*>|\{\\[^}\n]*\}")
# Descrições de som: [Music], (Applause). Sem quebra de linha dentro, para um
# colchete esquecido não engolir a legenda.
DESCRICAO = re.compile(r"\[[^\[\]\n]*\]|\([^()\n]{0,60}\)")
NOTA_MUSICAL = re.compile("[♪♫♬]")
# "ROSS: oi". Só em maiúsculas: "Listen: ..." é fala.
NOME_DE_QUEM_FALA = re.compile(r"^[A-Z][A-Z0-9 .'&-]{1,24}:\s+", re.MULTILINE)
TROCA = re.compile(r"(?:^|\s)(?:>>+)\s*|^\s*[-–—]\s*(?=\S)", re.MULTILINE)


def decodificar(conteudo: bytes) -> str:
    """Legendas antigas não usam UTF-8; cp1252 é a alternativa mais comum."""
    if len(conteudo) > TAMANHO_MAXIMO:
        raise LegendaInvalida("O arquivo é grande demais para ser uma legenda.")
    if conteudo.startswith((b"\xff\xfe", b"\xfe\xff")):
        return conteudo.decode("utf-16", errors="replace")
    try:
        return conteudo.decode("utf-8-sig")
    except UnicodeDecodeError:
        return conteudo.decode("cp1252", errors="replace")


def ler_arquivo(conteudo: bytes) -> list[Fala]:
    """Lê um arquivo SRT ou VTT. Os dois têm a mesma forma, com cabeçalhos diferentes."""
    texto = decodificar(conteudo).replace("\r\n", "\n").replace("\r", "\n")

    falas: list[Fala] = []
    # A legenda automática do YouTube em VTT repete a linha anterior em cada
    # bloco, para o texto "rolar" na tela.
    ultima_linha = ""
    for inicio, fim, linhas in _blocos(texto.split("\n")):
        novas = []
        for linha in linhas:
            limpa = _limpar(TEMPO_NO_TEXTO.sub("", linha))
            if limpa and limpa == ultima_linha:
                continue
            novas.append(linha)
            ultima_linha = limpa or ultima_linha
        falas += _falas_do_bloco(inicio, fim, "\n".join(novas))
    return _conferir(falas)


def _blocos(linhas: list[str]):
    """Devolve (início, fim, linhas de texto) de cada bloco com tempo."""
    posicoes = [i for i, linha in enumerate(linhas) if LINHA_DE_TEMPO.match(linha)]
    for i, posicao in enumerate(posicoes):
        limite = posicoes[i + 1] if i + 1 < len(posicoes) else len(linhas)
        texto = []
        for linha in linhas[posicao + 1 : limite]:
            if not linha.strip():
                break
            texto.append(linha)
        else:
            # Sem linha em branco até o próximo bloco: o número dele ficou aqui.
            if limite < len(linhas) and texto and texto[-1].strip().isdecimal():
                texto.pop()
        tempos = LINHA_DE_TEMPO.match(linhas[posicao]).groups()
        yield _segundos(tempos[:4]), _segundos(tempos[4:]), texto


def _segundos(partes) -> float:
    horas, minutos, segundos, fracao = partes
    return (
        int(horas or 0) * 3600 + int(minutos) * 60 + int(segundos) + int(fracao.ljust(3, "0")) / 1000
    )


def _falas_do_bloco(inicio: float, fim: float, texto: str) -> list[Fala]:
    if TEMPO_NO_TEXTO.search(texto):
        return _falas_de_pedacos(_pedacos_com_tempo(inicio, texto), fim)

    fim = max(fim, inicio + 0.1)
    partes = _separar_trocas(texto)
    total = sum(len(parte) for parte, _ in partes)
    falas = []
    agora = inicio
    for parte, troca in partes:
        # Duas pessoas no mesmo bloco dividem o tempo conforme o texto.
        proximo = agora + (fim - inicio) * len(parte) / total
        falas.append(Fala(agora, proximo, parte, troca=troca))
        agora = proximo
    return falas


def _pedacos_com_tempo(inicio: float, texto: str) -> list[tuple[float, str]]:
    pedacos = []
    agora, posicao = inicio, 0
    for marca in TEMPO_NO_TEXTO.finditer(texto):
        pedacos.append((agora, texto[posicao : marca.start()]))
        agora, posicao = _segundos(marca.groups()), marca.end()
    pedacos.append((agora, texto[posicao:]))
    return pedacos


def _separar_trocas(texto: str) -> list[tuple[str, bool]]:
    """Separa as falas de pessoas diferentes; o booleano diz se houve troca."""
    texto = _sem_marcas(texto)
    partes, posicao, troca = [], 0, False
    for marca in TROCA.finditer(texto):
        partes.append((texto[posicao : marca.start()], troca))
        posicao, troca = marca.end(), True
    partes.append((texto[posicao:], troca))

    prontas, pendente = [], False
    for parte, troca in partes:
        limpa = _limpar(parte)
        pendente = pendente or troca
        if limpa:
            prontas.append((limpa, pendente))
            pendente = False
    return prontas


def _sem_marcas(texto: str) -> str:
    texto = html.unescape(MARCACAO.sub("", texto)).replace("\xa0", " ").replace("​", "")
    return NOTA_MUSICAL.sub(" ", DESCRICAO.sub(" ", texto))


def _limpar(texto: str) -> str:
    texto = NOME_DE_QUEM_FALA.sub("", _sem_marcas(texto).strip())
    limpo = " ".join(texto.split())
    # Sobrou só pontuação: não há o que digitar.
    return limpo if re.search(r"\w", limpo) else ""


def ler_json3(dados) -> list[Fala]:
    """Lê o formato do YouTube: com tempo por fala (autor) ou por palavra (automática)."""
    try:
        eventos = [evento for evento in dados["events"] if evento.get("segs")]
        automatica = any("tOffsetMs" in seg for evento in eventos for seg in evento["segs"])
        falas = []
        for evento in eventos:
            # Na automática, estes eventos só trazem a quebra de linha.
            if evento.get("aAppend"):
                continue
            inicio = evento["tStartMs"] / 1000
            fim = inicio + evento.get("dDurationMs", 0) / 1000
            if automatica:
                pedacos = [
                    (inicio + seg.get("tOffsetMs", 0) / 1000, seg.get("utf8", ""))
                    for seg in evento["segs"]
                ]
                falas += _falas_de_pedacos(pedacos, fim)
            else:
                falas += _falas_do_bloco(inicio, fim, "".join(s.get("utf8", "") for s in evento["segs"]))
    except (KeyError, TypeError, AttributeError) as erro:
        raise LegendaInvalida("O YouTube mudou o formato da legenda.") from erro
    return _conferir(falas)


def _falas_de_pedacos(pedacos: list[tuple[float, str]], fim: float) -> list[Fala]:
    """Monta falas a partir de textos que trazem o próprio instante."""
    grupos: list[tuple[bool, list[tuple[float, str]]]] = [(False, [])]
    # A descrição de som pode estar partida em dois pedaços, então a limpeza é
    # feita no texto inteiro, sem perder de que pedaço veio cada letra.
    inteiro = "".join(texto for _, texto in pedacos)
    instantes = [instante for instante, texto in pedacos for _ in texto]
    apagar = set()
    for padrao in (MARCACAO, DESCRICAO, NOTA_MUSICAL):
        for achado in padrao.finditer(inteiro):
            apagar.update(range(*achado.span()))
    limpo = "".join(" " if i in apagar else letra for i, letra in enumerate(inteiro))

    for achado in re.finditer(r"\S+", limpo):
        texto = html.unescape(achado.group()).replace("\xa0", " ").strip()
        if re.fullmatch(r">>+", texto):
            grupos.append((True, []))
            continue
        if texto.startswith(">>"):
            grupos.append((True, []))
            texto = texto.lstrip(">")
        if re.search(r"\w", texto):
            grupos[-1][1].append((instantes[achado.start()], texto))

    falas = []
    for troca, itens in grupos:
        if not itens:
            continue
        palavras = []
        for i, (instante, texto) in enumerate(itens):
            # Palavras do mesmo pedaço dividem o tempo até o próximo.
            iguais = [j for j, (outro, _) in enumerate(itens) if outro == instante]
            seguinte = next((outro for outro, _ in itens if outro > instante), None)
            limite = seguinte if seguinte is not None else max(fim, instante)
            duracao = min(limite - instante, sum(duracao_maxima(itens[j][1]) for j in iguais))
            parte = duracao / len(iguais)
            comeco = instante + parte * iguais.index(i)
            palavras.append(Palavra(texto, comeco, comeco + parte))
        falas.append(
            Fala(palavras[0].inicio, palavras[-1].fim, " ".join(p.texto for p in palavras), tuple(palavras), troca)
        )
    return falas


def duracao_maxima(texto: str) -> float:
    """Quanto uma palavra dura no máximo, para o silêncio depois não contar como fala."""
    return 0.35 + 0.06 * len(texto)


def _conferir(falas: list[Fala]) -> list[Fala]:
    """Ordena, junta falas simultâneas e corrige as que invadem a seguinte."""
    falas = sorted(falas, key=lambda fala: fala.inicio)
    if not falas:
        raise LegendaInvalida("Não encontrei nenhuma fala na legenda.")

    prontas: list[Fala] = []
    for fala in falas:
        anterior = prontas[-1] if prontas else None
        if anterior and fala.inicio == anterior.inicio and fala.texto == anterior.texto:
            continue
        if anterior and fala.inicio == anterior.inicio and not fala.palavras:
            prontas[-1] = replace(
                anterior, fim=max(anterior.fim, fala.fim), texto=f"{anterior.texto} {fala.texto}", palavras=()
            )
            continue
        if anterior and not anterior.palavras and anterior.fim > fala.inicio:
            prontas[-1] = replace(anterior, fim=fala.inicio)
        prontas.append(fala)
    return prontas
