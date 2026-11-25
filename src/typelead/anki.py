"""Escreve as palavras no formato de texto que o Anki importa.

Sem áudio: o som do vídeo não é guardado nem distribuído. O cartão leva ao trecho.
"""

import re
from collections.abc import Iterable
from html import escape

# O que o Anki lê no começo do arquivo, para a pessoa não configurar nada. Com o
# identificador na primeira coluna, importar de novo atualiza em vez de duplicar.
CABECALHO = (
    "#separator:tab",
    "#html:true",
    "#deck:typelead",
    "#guid column:1",
    "#tags column:4",
)

LETRA = re.compile(r"\w")


def exportar(palavras: Iterable[dict]) -> str:
    """Recebe as palavras como `Banco.palavras` as devolve."""
    linhas = ["\t".join(_campos(palavra)) for palavra in palavras]
    return "\n".join([*CABECALHO, *linhas]) + "\n"


def _campos(palavra: dict) -> tuple[str, str, str, str]:
    texto, traducao = palavra["texto"], palavra["traducao"]
    alvo = _procurar(palavra["esperada"])
    lacuna = _marcar(alvo, texto, lambda achada: LETRA.sub("•", achada))
    resposta = _marcar(alvo, texto, lambda achada: f"<b>{escape(achada)}</b>")
    segundos = int(palavra["inicio"])
    endereco = f"https://youtu.be/{palavra['video_id']}?t={segundos}"

    frente = f'{lacuna}<br><br><a href="{escape(endereco)}">Ouvir o trecho</a>'
    verso = f"<b>{escape(palavra['forma'])}</b><br><br>{resposta}"
    if traducao:
        verso += f"<br><i>{escape(traducao)}</i>"
    verso += f"<br><br><small>{escape(palavra['titulo'])}</small>"
    etiquetas = f"typelead typelead::{palavra['motivo']}"
    return tuple(_uma_linha(c) for c in (f"typelead-{palavra['forma']}", frente, verso, etiquetas))


def _procurar(esperada: str) -> re.Pattern:
    """A palavra sem a pontuação das pontas, em todos os lugares da fala em que aparece."""
    miolo = re.sub(r"^\W+|\W+$", "", esperada)
    return re.compile(rf"(?<![\w'’]){re.escape(miolo)}(?![\w'’])" if miolo else r"(?!)", re.IGNORECASE)


def _marcar(alvo: re.Pattern, texto: str, trocar) -> str:
    """Troca a palavra no texto original e escapa o resto."""
    partes, fim = [], 0
    for achada in alvo.finditer(texto):
        partes += [escape(texto[fim : achada.start()]), trocar(achada[0])]
        fim = achada.end()
    return "".join([*partes, escape(texto[fim:])])


def _uma_linha(campo: str) -> str:
    """Tab e quebra de linha separam campos e notas."""
    return re.sub(r"\s+", " ", campo)
