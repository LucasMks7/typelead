"""Transcreve no próprio PC o som gravado de um vídeo, com o tempo de cada palavra.

As medidas que levaram a estas escolhas estão em docs/transcricao.md.
"""

import ctypes.util
import os
import re
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from .legendas import Fala, Palavra

IDIOMA = "en"
TAXA = 16_000
# Na placa, o large-v3-turbo é bem mais rápido que o tempo real e erra menos. No
# processador, só o small acompanha. int8 é o que cabe e roda bem nos dois.
MODELOS = {"cuda": "large-v3-turbo", "cpu": "small"}

# O modelo recebe o áudio em blocos, para a memória não crescer com o vídeo.
SEGUNDOS_POR_BLOCO = 600
SEGUNDOS_DE_BUSCA_DO_CORTE = 30
JANELA_DO_CORTE = 0.2

# Ajuste das bordas das palavras pela energia do som.
QUADRO = 0.01
FRACAO_DO_PICO = 0.08
PISO = 0.002
FOLGA_NO_COMECO = 0.06
FOLGA_NO_FIM = 0.05
MAXIMO_A_ESTENDER = 0.4

# Regiões sem voz mais longas que isto separam a transcrição em partes: o que o
# modelo inventa em uma abertura com música contaminaria a fala seguinte.
PAUSA_QUE_SEPARA = 8
FOLGA_DA_REGIAO = 1
# Com menos voz que isto, o detector pode estar ignorando um canto: vai tudo.
FRACAO_MINIMA_DE_VOZ = 0.15

# O Whisper escreve frases curtas, como "Thank you.", em música e ruído. Uma fala
# longa e segura fica, mesmo que o detector de voz não a veja: pode ser canto.
PALAVRAS_DE_FRASE_CURTA = 4
CONFIANCA_MINIMA = -0.7

# Acima desta certeza de que a fala é em outro idioma, a transcrição não serve.
CERTEZA_DE_OUTRO_IDIOMA = 0.8


class FalhaNaTranscricao(RuntimeError):
    """O som não pôde ser transcrito."""


@dataclass(frozen=True)
class Marca:
    """Em que ponto do vídeo estava o player em um instante da gravação."""

    gravado: float
    video: float


class Relogio:
    """Converte o tempo da gravação no tempo do vídeo.

    Os dois não andam juntos: o vídeo para quando carrega, quando a pessoa pausa
    ou quando entra um anúncio, e a gravação continua.
    """

    def __init__(self, marcas: Iterable[Marca]):
        self._marcas = sorted(marcas, key=lambda marca: marca.gravado)
        if len(self._marcas) < 2:
            raise FalhaNaTranscricao("A gravação não registrou o andamento do vídeo.")

    def para_o_video(self, gravado: float) -> float | None:
        """O instante do vídeo, ou None se ele não estava andando."""
        marcas = self._marcas
        if gravado <= marcas[0].gravado or gravado >= marcas[-1].gravado:
            ponta, vizinha = (
                (marcas[0], marcas[1]) if gravado <= marcas[0].gravado else (marcas[-1], marcas[-2])
            )
            # Um pouco além das pontas, vale o andamento do trecho vizinho.
            if abs(gravado - ponta.gravado) > 0.5 or not _andando(*sorted((ponta, vizinha), key=lambda m: m.gravado)):
                return None
            return max(0.0, ponta.video + gravado - ponta.gravado)

        for antes, depois in zip(marcas, marcas[1:]):
            if antes.gravado <= gravado <= depois.gravado:
                if not _andando(antes, depois):
                    return None
                parte = (gravado - antes.gravado) / (depois.gravado - antes.gravado or 1)
                return antes.video + parte * (depois.video - antes.video)
        return None


def _andando(antes: Marca, depois: Marca) -> bool:
    """O vídeo avançou junto com a gravação? Pulos e paradas não contam."""
    gravado, video = depois.gravado - antes.gravado, depois.video - antes.video
    return gravado > 0 and abs(video - gravado) <= max(0.25, 0.5 * gravado) and video > 0


def no_tempo_do_video(palavras: Iterable[Palavra], relogio: Relogio) -> list[Palavra]:
    """Converte as palavras e descarta as ditas com o vídeo parado, como as de um anúncio."""
    prontas = []
    for palavra in palavras:
        inicio, fim = relogio.para_o_video(palavra.inicio), relogio.para_o_video(palavra.fim)
        if inicio is None:
            continue
        if fim is None or fim <= inicio:
            fim = inicio + max(0.05, palavra.fim - palavra.inicio)
        prontas.append(Palavra(palavra.texto, inicio, fim))
    return prontas


def ajustar_bordas(palavras: list[Palavra], amostras: np.ndarray) -> list[Palavra]:
    """Encosta o começo e o fim de cada palavra no som que se ouve.

    O Whisper adianta o começo, incluindo a pausa anterior, e termina antes de o
    som acabar. Sem isso, cortar a fala engoliria a última sílaba. Com música de
    fundo não há silêncio para achar, e as palavras ficam como vieram.
    """
    tamanho = int(QUADRO * TAXA)
    quantidade = len(amostras) // tamanho
    if quantidade == 0 or not palavras:
        return palavras
    quadros = amostras[: quantidade * tamanho].reshape(quantidade, tamanho)
    volume = np.sqrt(np.mean(np.square(quadros, dtype=np.float64), axis=1))

    def indice(segundos: float) -> int:
        return min(max(int(segundos / QUADRO), 0), quantidade - 1)

    limites, comecos = [], []
    for palavra in palavras:
        a, b = indice(palavra.inicio), max(indice(palavra.fim), indice(palavra.inicio) + 1)
        limite = max(float(volume[a:b].max()) * FRACAO_DO_PICO, PISO)
        limites.append(limite)
        com_som = np.flatnonzero(volume[a:b] >= limite)
        comeco = palavra.inicio
        if len(com_som):
            comeco = max(comeco, (a + com_som[0]) * QUADRO - FOLGA_NO_COMECO)
        comecos.append(min(comeco, palavra.fim - 0.02))

    prontas = []
    for i, palavra in enumerate(palavras):
        proximo = comecos[i + 1] if i + 1 < len(palavras) else quantidade * QUADRO
        teto = min(proximo, palavra.fim + MAXIMO_A_ESTENDER)
        quadro = indice(palavra.fim)
        while quadro * QUADRO < teto and quadro < quantidade and volume[quadro] >= limites[i]:
            quadro += 1
        fim = palavra.fim
        # Só vale se o silêncio foi achado: som contínuo até o teto pode ser música.
        if quadro * QUADRO < teto:
            fim = max(fim, min(quadro * QUADRO + FOLGA_NO_FIM, teto))
        elif proximo > palavra.fim:
            fim = min(proximo, palavra.fim + MAXIMO_A_ESTENDER / 2)
        prontas.append(replace(palavra, inicio=comecos[i], fim=max(fim, comecos[i] + 0.02)))
    return prontas


def montar_falas(segmentos: Iterable[list[Palavra]]) -> list[Fala]:
    """Uma fala por segmento do Whisper; a divisão final é feita depois."""
    return [
        Fala(palavras[0].inicio, palavras[-1].fim, " ".join(p.texto for p in palavras), tuple(palavras))
        for palavras in segmentos
        if palavras
    ]


def dividir_em_blocos(amostras: np.ndarray, segundos: float = SEGUNDOS_POR_BLOCO) -> list[tuple[int, int]]:
    """Divide em blocos, cortando no ponto mais silencioso do final de cada um."""
    tamanho = int(segundos * TAXA)
    busca = min(SEGUNDOS_DE_BUSCA_DO_CORTE * TAXA, tamanho // 2)
    janela = int(JANELA_DO_CORTE * TAXA)
    blocos, inicio = [], 0
    while len(amostras) - inicio > tamanho:
        limite = inicio + tamanho
        trecho = amostras[limite - busca : limite]
        quantidade = len(trecho) // janela
        fim = limite
        if quantidade:
            janelas = trecho[: quantidade * janela].reshape(quantidade, janela)
            volumes = np.mean(np.square(janelas, dtype=np.float64), axis=1)
            fim = limite - busca + int(np.argmin(volumes)) * janela + janela // 2
        blocos.append((inicio, fim))
        inicio = fim
    if inicio < len(amostras):
        blocos.append((inicio, len(amostras)))
    return blocos


def regioes_com_voz(vozes: list[tuple[float, float]], duracao: float) -> list[tuple[float, float]]:
    """Junta os trechos com voz próximos; as pausas longas ficam de fora."""
    if sum(fim - inicio for inicio, fim in vozes) < FRACAO_MINIMA_DE_VOZ * duracao:
        return [(0, duracao)]
    regioes: list[tuple[float, float]] = []
    for inicio, fim in vozes:
        if regioes and inicio - regioes[-1][1] < PAUSA_QUE_SEPARA:
            regioes[-1] = (regioes[-1][0], fim)
        else:
            regioes.append((inicio, fim))
    return [(max(0, a - FOLGA_DA_REGIAO), min(duracao, b + FOLGA_DA_REGIAO)) for a, b in regioes]


def _blocos_com_voz(amostras, vozes, segundos_por_bloco) -> list[tuple[int, int]]:
    blocos = []
    for a, b in regioes_com_voz(vozes, len(amostras) / TAXA):
        comeco, final = int(a * TAXA), int(b * TAXA)
        blocos += [
            (comeco + inicio, comeco + fim)
            for inicio, fim in dividir_em_blocos(amostras[comeco:final], segundos_por_bloco)
        ]
    return blocos


def transcrever(
    amostras: np.ndarray,
    modelo,
    relogio: Relogio,
    ao_avancar: Callable[[float], None] = lambda fracao: None,
    segundos_por_bloco: float = SEGUNDOS_POR_BLOCO,
    achar_vozes: Callable[[np.ndarray], list[tuple[float, float]]] | None = None,
) -> list[Fala]:
    """Transcreve o som gravado e devolve as falas no tempo do vídeo.

    achar_vozes existe para os testes não carregarem o detector de voz.
    """
    achar_vozes = achar_vozes or detectar_vozes
    if len(amostras) < TAXA // 2 or float(np.abs(amostras).max()) < PISO:
        raise FalhaNaTranscricao("A gravação está muda. Confira se o som da aba foi compartilhado.")
    _conferir_idioma(amostras, modelo)

    segmentos_prontos: list[list[Palavra]] = []
    try:
        vozes = achar_vozes(amostras)
        for inicio, fim in _blocos_com_voz(amostras, vozes, segundos_por_bloco):
            deslocamento = inicio / TAXA
            segmentos, _ = modelo.transcribe(
                amostras[inicio:fim],
                language=IDIOMA,
                word_timestamps=True,
                # O filtro de voz adiantou os começos e piorou a pontuação nas
                # medidas. Ele é usado depois, para julgar o que foi escrito.
                vad_filter=False,
                # Sem o texto anterior, o large-v3-turbo perde a pontuação e
                # repete palavras na emenda das janelas.
                condition_on_previous_text=True,
            )
            for segmento in segmentos:
                palavras = [
                    Palavra(p.word.strip(), p.start + deslocamento, p.end + deslocamento)
                    for p in segmento.words or []
                    if re.search(r"\w", p.word)
                ]
                if not _inventado(segmento.avg_logprob, palavras, vozes):
                    segmentos_prontos.append(palavras)
                ao_avancar(min((segmento.end + deslocamento) * TAXA / len(amostras), 1.0))
    # O CTranslate2 avisa os problemas dele, como falta de memória, com RuntimeError.
    except (RuntimeError, MemoryError) as erro:
        raise FalhaNaTranscricao(f"A transcrição parou: {erro}") from erro

    ajustadas = iter(ajustar_bordas([p for s in segmentos_prontos for p in s], amostras))
    falas = montar_falas(
        no_tempo_do_video([next(ajustadas) for _ in segmento], relogio) for segmento in segmentos_prontos
    )
    if not falas:
        raise FalhaNaTranscricao("Não encontrei fala em inglês neste vídeo.")
    return sorted(falas, key=lambda fala: fala.inicio)


def _inventado(confianca: float, palavras: list[Palavra], vozes: list[tuple[float, float]]) -> bool:
    """O texto foi escrito onde não há voz?"""
    if not palavras:
        return True
    inicio, fim = palavras[0].inicio, palavras[-1].fim
    if any(a < fim and b > inicio for a, b in vozes):
        return False
    return len(palavras) <= PALAVRAS_DE_FRASE_CURTA or confianca < CONFIANCA_MINIMA


def detectar_vozes(amostras: np.ndarray) -> list[tuple[float, float]]:
    """Os trechos com voz, em segundos, pelo Silero VAD que vem no faster-whisper."""
    from faster_whisper.vad import get_speech_timestamps

    return [(voz["start"] / TAXA, voz["end"] / TAXA) for voz in get_speech_timestamps(amostras)]


def _conferir_idioma(amostras: np.ndarray, modelo) -> None:
    idioma, certeza, _ = modelo.detect_language(amostras[: 120 * TAXA], language_detection_segments=4)
    if idioma != IDIOMA and certeza >= CERTEZA_DE_OUTRO_IDIOMA:
        raise FalhaNaTranscricao(f"A fala deste vídeo não parece ser em inglês (idioma detectado: {idioma}).")


def ler_som(arquivo: Path) -> np.ndarray:
    """Decodifica o arquivo gravado para 16 kHz, em um canal."""
    import av
    from faster_whisper.audio import decode_audio

    try:
        return decode_audio(str(arquivo), sampling_rate=TAXA)
    except (av.error.FFmpegError, OSError, IndexError) as erro:
        raise FalhaNaTranscricao("O som gravado está vazio ou danificado.") from erro


def preparar_bibliotecas_cuda() -> bool:
    """Põe no PATH o cuBLAS e o cuDNN instalados pelo pip, e diz se foram achados.

    O Windows não os procura no site-packages, e o os.add_dll_directory não
    funciona com o CTranslate2 (medido no transcritor de aulas).
    """
    if sys.platform != "win32":
        return True
    try:
        import nvidia
    except ImportError:
        return False
    for raiz in nvidia.__path__:
        for biblioteca in ("cublas", "cudnn"):
            pasta = str(Path(raiz) / biblioteca / "bin")
            if Path(pasta).is_dir() and pasta not in os.environ["PATH"].split(os.pathsep):
                os.environ["PATH"] = pasta + os.pathsep + os.environ["PATH"]
    return ctypes.util.find_library("cublas64_12.dll") is not None


def _criar_whisper(nome: str, dispositivo: str):
    # Importado aqui porque é pesado: os testes não precisam esperar por ele.
    from faster_whisper import WhisperModel

    return WhisperModel(nome, device=dispositivo, compute_type="int8")


def _ha_placa() -> bool:
    if not preparar_bibliotecas_cuda():
        return False
    import ctranslate2

    return ctranslate2.get_cuda_device_count() > 0


def carregar_modelo(criar=_criar_whisper, ha_placa=_ha_placa):
    """Usa a placa de vídeo, se ela funcionar; senão, o processador.

    Devolve (modelo, dispositivo).
    """
    try:
        if ha_placa():
            modelo = criar(MODELOS["cuda"], "cuda")
            # A falta de uma biblioteca da NVIDIA só aparece no primeiro cálculo.
            list(modelo.transcribe(np.zeros(TAXA, dtype=np.float32), language=IDIOMA)[0])
            return modelo, "cuda"
    except RuntimeError:
        pass  # Driver antigo, DLL ausente ou memória cheia: o processador resolve.
    except Exception as erro:
        raise _falha_ao_carregar(MODELOS["cuda"], erro) from erro
    try:
        return criar(MODELOS["cpu"], "cpu"), "cpu"
    except Exception as erro:
        raise _falha_ao_carregar(MODELOS["cpu"], erro) from erro


def _falha_ao_carregar(nome: str, erro: Exception) -> FalhaNaTranscricao:
    return FalhaNaTranscricao(
        f"Não foi possível carregar o modelo {nome}. Na primeira vez, ele é baixado da "
        f"internet e precisa de espaço em disco. Detalhe: {erro}"
    )
