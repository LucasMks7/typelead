"""Reconhece links de vídeos do YouTube, sem acesso à rede."""

import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

YOUTUBE = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
    "www.youtubekids.com",
}
CURTO = {"youtu.be", "www.youtu.be"}

# Páginas que levam o link do vídeo dentro de um parâmetro: domínio, caminho e
# nomes do parâmetro. São as que aparecem ao copiar de uma busca, de um aviso de
# cookies ou de um botão antigo de compartilhar.
EMBRULHOS = [
    (YOUTUBE, "/attribution_link", ("u",)),
    ({"consent.youtube.com"}, "/", ("continue",)),
    ({"google.com", "www.google.com"}, "/url", ("url", "q")),
]

# Caminhos em que o identificador vem logo depois: /shorts/ID, /live/ID...
CAMINHOS_COM_ID = {"watch", "shorts", "live", "embed", "v", "e"}

# Têm 11 caracteres permitidos, como um identificador, mas são páginas do player.
NAO_SAO_ID = {"videoseries", "live_stream"}

IDENTIFICADOR = re.compile(r"[A-Za-z0-9_-]{11}")
ESQUEMA = re.compile(r"[a-z][a-z0-9+.-]*://", re.IGNORECASE)
# 90, 90s, 1m30s ou 1h2m3s. O limite de dígitos evita números absurdos.
TEMPO = re.compile(
    r"(?:(?P<h>[0-9]{1,3})h)?(?:(?P<m>[0-9]{1,4})m)?(?:(?P<s>[0-9]{1,6})(?:\.[0-9]*)?s?)?",
    re.IGNORECASE,
)


class LinkInvalido(ValueError):
    """O texto recebido não leva a um vídeo do YouTube."""


@dataclass(frozen=True)
class Video:
    id: str
    inicio: int = 0  # em segundos

    @property
    def link(self) -> str:
        return f"https://www.youtube.com/watch?v={self.id}"


def reconhecer(texto: str) -> Video:
    """Devolve o vídeo do link ou levanta LinkInvalido com o motivo."""
    # Texto copiado de mensagens traz caracteres invisíveis, que nenhum link usa.
    visivel = "".join(letra for letra in texto if unicodedata.category(letra) != "Cf")
    link = visivel.strip().strip("<>\"'").strip()

    if not link:
        raise LinkInvalido("O link está vazio.")
    # A checagem vem antes do urlsplit, que apaga quebras de linha em silêncio.
    if re.search(r"\s", link):
        raise LinkInvalido("Cole só o link, sem outro texto junto.")

    # Quem copia do código de uma página leva o "&" escrito como "&amp;".
    link = link.replace("&amp;", "&")
    return _do_link(link, desembrulhar=True)


def _do_link(link: str, desembrulhar: bool) -> Video:
    if link.startswith("//"):
        link = "https:" + link
    elif not ESQUEMA.match(link):
        link = "https://" + link

    try:
        partes = urlsplit(link)
        dominio = (partes.hostname or "").removesuffix(".")
    except ValueError as erro:
        raise LinkInvalido("O link está malformado.") from erro

    if partes.scheme not in {"http", "https"}:
        raise LinkInvalido("O link precisa começar com http:// ou https://.")

    parametros = parse_qs(partes.query)

    # Só um nível: um embrulho dentro de outro não é um link que alguém copie.
    if desembrulhar:
        for dominios, caminho, nomes in EMBRULHOS:
            if dominio in dominios and (partes.path.rstrip("/") or "/") == caminho:
                for nome in nomes:
                    if nome in parametros:
                        return _do_link(_completo(parametros[nome][0]), desembrulhar=False)

    if dominio not in YOUTUBE | CURTO:
        raise LinkInvalido("O link não é do YouTube.")

    # Links curtos antigos trazem "&" sem "?": youtu.be/ID&t=30.
    caminho, _, solto = partes.path.partition("&")
    parametros = {**parse_qs(solto), **parametros}
    trechos = [trecho for trecho in caminho.split("/") if trecho]

    candidato = _candidato(trechos, parametros, curto=dominio in CURTO)
    if candidato is None:
        raise LinkInvalido(_por_que_nao(trechos, parametros))
    if not IDENTIFICADOR.fullmatch(candidato):
        raise LinkInvalido("O identificador do vídeo está incompleto ou errado.")

    return Video(candidato, _inicio(parametros, parse_qs(partes.fragment)))


def _completo(interno: str) -> str:
    """O attribution_link guarda só o caminho: /watch?v=ID."""
    if interno.startswith("/") and not interno.startswith("//"):
        return "https://www.youtube.com" + interno
    return interno


def _candidato(trechos: list[str], parametros: dict, curto: bool) -> str | None:
    """O texto que ocupa o lugar do identificador, ainda sem validar."""
    primeiro = trechos[0].lower() if trechos else ""

    if primeiro == "watch" and "v" in parametros:
        return parametros["v"][0]
    if primeiro in CAMINHOS_COM_ID and len(trechos) > 1:
        return None if trechos[1] in NAO_SAO_ID else trechos[1]
    if curto and len(trechos) == 1 and primeiro not in {"watch", "playlist"}:
        return trechos[0]
    return None


def _por_que_nao(trechos: list[str], parametros: dict) -> str:
    primeiro = trechos[0].lower() if trechos else ""

    if primeiro == "clip":
        return "O link é de um clipe, que não diz qual é o vídeo. Abra o clipe e copie o link do vídeo."
    if primeiro == "playlist" or trechos[1:2] == ["videoseries"]:
        return "O link é de uma playlist. Abra um vídeo dela e copie o link."
    if primeiro.startswith("@") or primeiro in {"channel", "c", "user"} or trechos[1:2] == ["live_stream"]:
        return "O link é de um canal. Abra um vídeo dele e copie o link."
    if primeiro == "results":
        return "O link é de uma busca. Abra um vídeo e copie o link."
    if primeiro == "watch" and "list" in parametros:
        return "O link é de uma playlist. Abra um vídeo dela e copie o link."
    return "O link é do YouTube, mas não é de um vídeo."


def _inicio(parametros: dict, fragmento: dict) -> int:
    """O segundo em que o link pede para começar; 0 se não pedir ou for ilegível."""
    for origem, nome in [
        (parametros, "t"),
        (parametros, "start"),
        (parametros, "time_continue"),
        (fragmento, "t"),
    ]:
        if nome in origem:
            tempo = TEMPO.fullmatch(origem[nome][0])
            if tempo:
                horas, minutos, segundos = (int(parte or 0) for parte in tempo.group("h", "m", "s"))
                return horas * 3600 + minutos * 60 + segundos
    return 0
