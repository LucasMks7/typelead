"""Busca os dados e a legenda de um vídeo do YouTube, sem baixar o vídeo."""

import json
import re
from dataclasses import dataclass

from .legendas import Fala, LegendaInvalida, ler_json3
from .links import Video

SEGUNDOS_DE_ESPERA = 20

# A ordem importa: vale o primeiro padrão. O pedido de login "para confirmar que
# você não é um robô" é uma recusa passageira; os outros dependem da conta.
ERROS = (
    (
        r"not a bot|HTTP Error 429|HTTP Error 403",
        "recusado",
        "O YouTube recusou o pedido. Tente mais tarde.",
    ),
    (
        r"will begin in|Premieres in|is upcoming",
        "ainda_nao",
        "Este vídeo ainda não começou.",
    ),
    (
        r"\bDRM\b|requires payment|purchase|rent\b",
        "pago",
        "Este vídeo é pago ou protegido, e o programa não contorna isso.",
    ),
    (
        r"your country|not available in your|blocked it in",
        "regiao",
        "Este vídeo não está disponível no seu país.",
    ),
    (
        r"Private video|confirm your age|age.restricted|members|Sign in|\blog ?in\b",
        "acesso",
        "Este vídeo é privado, só para membros ou tem restrição de idade.",
    ),
    (
        r"unavailable|not available|has been removed|HTTP Error 404|does not exist|terminated",
        "indisponivel",
        "Este vídeo não existe mais ou o link está errado.",
    ),
    (
        r"getaddrinfo|Failed to resolve|timed out|Connection|Network is unreachable|URLError",
        "rede",
        "Não foi possível falar com o YouTube. Verifique a internet.",
    ),
)


class FalhaNoYouTube(Exception):
    """O vídeo não pôde ser consultado. O código diz o tipo do problema."""

    def __init__(self, codigo: str, mensagem: str):
        super().__init__(mensagem)
        self.codigo = codigo


@dataclass(frozen=True)
class Achado:
    video: Video
    titulo: str
    canal: str
    duracao: float | None
    # False quando o dono só permite tocar no site do YouTube.
    incorporavel: bool
    # "autor", "automatica" ou None, quando não há legenda utilizável.
    origem: str | None
    falas: tuple[Fala, ...]
    # Por que não há legenda, quando origem é None.
    motivo: str | None = None


def traduzir_erro(texto: str) -> FalhaNoYouTube:
    for padrao, codigo, mensagem in ERROS:
        if re.search(padrao, texto, re.IGNORECASE):
            return FalhaNoYouTube(codigo, mensagem)
    return FalhaNoYouTube("desconhecido", f"O YouTube respondeu algo inesperado: {texto[:200]}")


def escolher_legenda(info: dict) -> tuple[str, str] | None:
    """Devolve (origem, endereço) da melhor legenda em inglês, ou None."""
    do_autor = info.get("subtitles") or {}
    automaticas = info.get("automatic_captions") or {}

    candidatas = [("autor", nome) for nome in sorted(do_autor, key=_preferencia) if _ingles(nome)]
    # "en" pode ser uma tradução automática; "en-orig" é o que foi falado.
    candidatas += [
        ("automatica", nome)
        for nome in sorted(automaticas, key=lambda nome: (not nome.endswith("-orig"), _preferencia(nome)))
        if _ingles(nome)
    ]
    for origem, nome in candidatas:
        formatos = (do_autor if origem == "autor" else automaticas)[nome]
        for formato in formatos:
            endereco = formato.get("url", "")
            # "tlang" no endereço indica tradução: não é o que se ouve no vídeo.
            if formato.get("ext") == "json3" and endereco and not re.search(r"[?&]tlang=", endereco):
                return origem, endereco
    return None


def _ingles(nome: str) -> bool:
    return nome == "en" or nome.startswith("en-")


def _preferencia(nome: str) -> tuple:
    ordem = ["en", "en-US", "en-GB"]
    return (ordem.index(nome) if nome in ordem else len(ordem), nome)


def buscar(video: Video, abrir=None) -> Achado:
    """Consulta o vídeo e devolve a legenda em inglês, se houver.

    Levanta FalhaNoYouTube se o vídeo não puder ser consultado. Uma legenda que
    falte ou seja recusada não é falha: o vídeo ainda pode ser transcrito.
    abrir existe para os testes trocarem o yt-dlp por um dublê.
    """
    with (abrir or _abrir_ytdlp)() as ytdlp:
        try:
            # process=False pula a escolha de formato de vídeo, que não é usada.
            info = ytdlp.extract_info(video.link, download=False, process=False)
        # O yt-dlp deixa escapar erros de tipos variados quando o site muda.
        except Exception as erro:
            raise traduzir_erro(str(erro)) from erro

        origem, falas, motivo = _legenda(ytdlp, info)
        return Achado(
            video=video,
            titulo=info.get("title") or "Vídeo sem título",
            canal=info.get("channel") or info.get("uploader") or "",
            duracao=info.get("duration"),
            incorporavel=info.get("playable_in_embed") is not False,
            origem=origem,
            falas=tuple(falas),
            motivo=motivo,
        )


def _legenda(ytdlp, info: dict) -> tuple[str | None, list[Fala], str | None]:
    escolhida = escolher_legenda(info)
    if escolhida is None:
        if info.get("live_status") == "is_live":
            return None, [], "A transmissão está ao vivo e ainda não tem legenda."
        return None, [], "Este vídeo não tem legenda em inglês."
    origem, endereco = escolhida
    try:
        conteudo = ytdlp.urlopen(endereco).read()
    except Exception:
        return None, [], "O YouTube recusou o pedido da legenda."
    # Quando desconfia do pedido, o YouTube responde com sucesso e nada dentro.
    if not conteudo.strip():
        return None, [], "O YouTube recusou o pedido da legenda."
    try:
        return origem, ler_json3(json.loads(conteudo)), None
    except LegendaInvalida as erro:
        return None, [], str(erro)
    except ValueError:
        return None, [], "O YouTube mudou o formato da legenda."


class _Mudo:
    """O yt-dlp avisa sobre formatos de vídeo, que não são usados aqui."""

    def debug(self, mensagem):
        pass

    info = warning = error = debug


def _abrir_ytdlp():
    # Importado aqui porque demora: os testes não precisam esperar por ele.
    import yt_dlp

    return yt_dlp.YoutubeDL(
        {
            "quiet": True,
            "logger": _Mudo(),
            "socket_timeout": SEGUNDOS_DE_ESPERA,
            # Nada é guardado em disco e nenhuma configuração do PC é lida.
            "cachedir": False,
            "noplaylist": True,
        }
    )
