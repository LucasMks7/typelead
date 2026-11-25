"""Servidor local: entrega a interface e a API ao navegador, só neste computador."""

import argparse
import http.client
import json
import mimetypes
import socket
import sqlite3
import sys
import urllib.request
import webbrowser
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi import Path as NoCaminho
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import youtube
from .anki import exportar
from .banco import Banco, FalhaNoBanco, Item, Tentativa, caminho_padrao
from .diagnostico import Desistencia
from .divisao import dividir
from .legendas import TAMANHO_MAXIMO as LEGENDA_MAXIMA
from .legendas import Fala, LegendaInvalida, Palavra, ler_arquivo
from .links import LinkInvalido, reconhecer
from .palavras import APRENDENDO, ERRANDO, NOVA, formas, peso
from .traducao import FalhaNaTraducao, Tradutor
from .transcricao import FalhaNaTranscricao, Marca
from .transcricoes import TAMANHO_MAXIMO, Transcricoes
from .youtube import FalhaNoYouTube

PASTA_WEB = Path(__file__).parent / "web"
ENDERECO = "127.0.0.1"
PORTA_PADRAO = 8765
# O YouTube recusa alguns vídeos em uma página aberta pelo número (docs/player.md).
NOME = "localhost"
NOME_DO_PROGRAMA = "typelead"
NOMES_ACEITOS = {ENDERECO, NOME}

# O YouTube recusa o pedido feito pelo programa, mas o player pode tocar o vídeo
# assim mesmo: a pessoa ainda consegue transcrever.
FALHAS_QUE_AINDA_TOCAM = {"recusado", "desconhecido"}

# O Windows pode ter o .js registrado como text/plain, e o navegador se recusa a
# executar um módulo com esse tipo. Por isso, fica fixado aqui.
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("font/woff2", ".woff2")


IdDoVideo = Annotated[str, NoCaminho(pattern=r"^[A-Za-z0-9_-]{11}$")]


class PedidoDeVideo(BaseModel):
    link: str = Field(max_length=5000)
    # Consulta o YouTube mesmo que o vídeo já esteja salvo.
    novo: bool = False


class PalavraRecebida(BaseModel):
    texto: str = Field(max_length=200)
    inicio: float = Field(ge=0, le=100_000)
    fim: float = Field(ge=0, le=100_000)


class FalaRecebida(BaseModel):
    inicio: float = Field(ge=0, le=100_000)
    fim: float = Field(ge=0, le=100_000)
    texto: str = Field(min_length=1, max_length=2000)
    palavras: list[PalavraRecebida] = Field(default=[], max_length=500)


class VideoRecebido(BaseModel):
    titulo: str = Field(max_length=500)
    canal: str = Field(max_length=500)
    duracao: float | None = Field(default=None, ge=0, le=1_000_000)
    origem: Literal["som", "arquivo"]
    falas: list[FalaRecebida] = Field(min_length=1, max_length=50_000)


class PosicaoRecebida(BaseModel):
    posicao: int = Field(ge=0, le=50_000)


class ItemRecebido(BaseModel):
    tipo: Literal["certa", "trocada", "faltou", "sobrou"]
    posicao: int = Field(ge=0, le=2000)
    esperada: str = Field(max_length=2000)
    digitada: str = Field(max_length=2000)


RODADA = r"^[0-9a-f-]{36}$"


class DesistenciaRecebida(BaseModel):
    repeticoes: int = Field(ge=0, le=100_000)
    velocidade: float = Field(gt=0, le=2)
    traduziu: bool


class DiagnosticoRecebido(BaseModel):
    tipo: Literal["digitacao", "escuta", "vocabulario", "homofono", "indefinido"]


class TentativaRecebida(BaseModel):
    fala_id: int
    rodada: str = Field(pattern=RODADA)
    modo: Literal["oculto", "lacunas", "livre"]
    corrigir: Literal["enter", "digitando"]
    texto: str = Field(max_length=2000)
    com_ajuda: bool
    repeticoes: int = Field(ge=0, le=100_000)
    velocidade: float = Field(gt=0, le=2)
    duracao: float = Field(ge=0, le=10_000_000)
    itens: list[ItemRecebido] = Field(min_length=1, max_length=2000)
    traduziu: bool = False


class PedidoDePesos(BaseModel):
    palavras: list[Annotated[str, Field(max_length=200)]] = Field(max_length=50_000)
    nivel: Literal["iniciante", "intermediario", "avancado"]


class SabidaRecebida(BaseModel):
    forma: str = Field(min_length=1, max_length=200)
    sabida: bool


class RevisaoRecebida(BaseModel):
    forma: str = Field(min_length=1, max_length=200)
    fala_id: int
    acertou: bool
    quase: bool
    digitada: str = Field(max_length=200)
    repeticoes: int = Field(ge=0, le=100_000)
    velocidade: float = Field(gt=0, le=2)


class MarcaRecebida(BaseModel):
    gravado: float = Field(ge=0, le=100_000)
    video: float = Field(ge=0, le=100_000)


class PedidoDeTranscricao(BaseModel):
    # Uma marca a cada 200 ms em seis horas de vídeo.
    marcas: list[MarcaRecebida] = Field(max_length=110_000)


def criar_app(
    transcricoes: Transcricoes | None = None,
    buscar: Callable = youtube.buscar,
    banco: Banco | None = None,
    tradutor: Tradutor | None = None,
) -> FastAPI:
    """Os parâmetros existem para os testes usarem dublês. Sem banco, nada vai para o disco."""
    transcricoes = transcricoes or Transcricoes()
    banco = banco or Banco()
    tradutor = tradutor or Tradutor()
    # A documentação automática carregaria scripts de outro site.
    app = FastAPI(title="typelead", docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def proteger(request: Request, seguir):
        # Um site malicioso pode apontar o próprio domínio para 127.0.0.1 e
        # tentar ler esta página (DNS rebinding). O nome pedido o denuncia.
        # Ele também pode mandar um pedido direto para cá; a origem o denuncia.
        if not _nome_aceito(request.headers.get("host", "")) or not _origem_aceita(request):
            return JSONResponse({"detail": "Pedido recusado."}, status_code=403)
        resposta = _para_o_nome(request) or await seguir(request)
        # Sem o Referer, o player do YouTube responde com o erro 153.
        resposta.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        resposta.headers["X-Content-Type-Options"] = "nosniff"
        resposta.headers["Cache-Control"] = "no-store"
        return resposta

    @app.exception_handler(sqlite3.Error)
    async def banco_falhou(_: Request, erro: sqlite3.Error):
        return JSONResponse({"detail": f"Não foi possível salvar: {erro}"}, status_code=500)

    @app.get("/api/programa")
    def apresentar():
        """Diz quem atende aqui e como abrir de novo, para a página saber o que mostrar."""
        return {"programa": NOME_DO_PROGRAMA, "comando": sys.argv[0]}

    @app.get("/api/videos")
    def listar_videos():
        return banco.recentes()

    @app.get("/api/resumo")
    def resumir():
        return banco.resumo()

    @app.post("/api/videos")
    def abrir_video(pedido: PedidoDeVideo):
        try:
            video = reconhecer(pedido.link)
        except LinkInvalido as erro:
            raise HTTPException(422, str(erro)) from erro
        dados = {"id": video.id, "comeco": video.inicio}
        # O que já foi salvo não é pedido de novo ao YouTube.
        if not pedido.novo and (salvo := banco.abrir_video(video.id)):
            return dados | salvo | {"motivo": None}
        try:
            achado = buscar(video)
        except FalhaNoYouTube as erro:
            if erro.codigo not in FALHAS_QUE_AINDA_TOCAM:
                raise HTTPException(502, str(erro)) from erro
            return dados | {
                "titulo": "Vídeo do YouTube",
                "canal": "",
                "duracao": None,
                "incorporavel": True,
                "origem": None,
                "motivo": str(erro),
                "falas": [],
            }
        if falas := dividir(list(achado.falas)):
            banco.salvar_video(
                video.id, achado.titulo, achado.canal, achado.duracao, achado.incorporavel, achado.origem, falas
            )
            return dados | banco.abrir_video(video.id) | {"motivo": None}
        return dados | {
            "titulo": achado.titulo,
            "canal": achado.canal,
            "duracao": achado.duracao,
            "incorporavel": achado.incorporavel,
            "origem": None,
            "motivo": achado.motivo or "A legenda deste vídeo está vazia.",
            "falas": [],
        }

    @app.put("/api/videos/{identificador}/falas")
    def salvar_falas(identificador: IdDoVideo, recebido: VideoRecebido):
        """Guarda o que foi transcrito ou lido de um arquivo."""
        falas = [
            Fala(f.inicio, f.fim, f.texto, tuple(Palavra(p.texto, p.inicio, p.fim) for p in f.palavras))
            for f in recebido.falas
        ]
        banco.salvar_video(
            identificador, recebido.titulo, recebido.canal, recebido.duracao, True, recebido.origem, falas
        )
        return banco.abrir_video(identificador)

    @app.put("/api/videos/{identificador}/posicao", status_code=204)
    def marcar_posicao(identificador: IdDoVideo, recebida: PosicaoRecebida):
        if not banco.marcar_posicao(identificador, recebida.posicao):
            raise HTTPException(404, "Este vídeo não está salvo.")

    @app.post("/api/falas/{numero}/traducao")
    def traduzir_fala(numero: int):
        fala = banco.fala(numero)
        if fala is None:
            raise HTTPException(404, "Esta fala não está salva.")
        if fala["traducao"] is None:
            try:
                fala["traducao"] = tradutor.traduzir(fala["texto"])
            except FalhaNaTraducao as erro:
                raise HTTPException(503, str(erro)) from erro
            banco.guardar_traducao(numero, fala["traducao"])
        return {"traducao": fala["traducao"]}

    @app.post("/api/tentativas", status_code=201)
    def salvar_tentativa(recebida: TentativaRecebida):
        dados = recebida.model_dump()
        dados["itens"] = tuple(Item(**item) for item in dados["itens"])
        numero = banco.salvar_tentativa(Tentativa(**dados))
        if numero is None:
            raise HTTPException(404, "Esta fala não está salva.")
        return {"id": numero, "erros": banco.diagnosticar(recebida.rodada), "resumo": banco.resumo()}

    @app.put("/api/rodadas/{rodada}/desistencia")
    def desistir(rodada: Annotated[str, NoCaminho(pattern=RODADA)], recebida: DesistenciaRecebida):
        banco.desistir(rodada, Desistencia(**recebida.model_dump()))
        return {"erros": banco.diagnosticar(rodada)}

    @app.put("/api/erros/{numero}/diagnostico", status_code=204)
    def corrigir_diagnostico(numero: int, recebido: DiagnosticoRecebido):
        if not banco.corrigir_diagnostico(numero, recebido.tipo):
            raise HTTPException(404, "Este erro não está salvo.")

    @app.get("/api/palavras")
    def listar_palavras():
        return banco.palavras()

    @app.put("/api/palavras", status_code=204)
    def marcar_palavra(recebida: SabidaRecebida):
        banco.marcar_sabida(recebida.forma, recebida.sabida)

    @app.get("/api/anki")
    def exportar_para_o_anki():
        """Só as palavras que ainda estão sendo estudadas."""
        estudando = [palavra for palavra in banco.palavras() if palavra["situacao"] in {ERRANDO, APRENDENDO}]
        return PlainTextResponse(
            exportar(estudando), headers={"Content-Disposition": 'attachment; filename="typelead-anki.txt"'}
        )

    @app.post("/api/pesos")
    def pesar(pedido: PedidoDePesos):
        """A chance de cada palavra ser escondida nas lacunas, na ordem em que veio."""
        situacoes = banco.situacoes()
        return {
            "pesos": [
                peso(palavra, pedido.nivel, situacoes.get(forma, NOVA))
                for palavra, forma in zip(pedido.palavras, formas(pedido.palavras))
            ]
        }

    @app.get("/api/revisao")
    def listar_revisao():
        return banco.revisar()

    @app.post("/api/revisao", status_code=201)
    def salvar_revisao(recebida: RevisaoRecebida):
        vence_em = banco.salvar_revisao(**recebida.model_dump())
        if vence_em is None:
            raise HTTPException(404, "Esta fala não está salva.")
        return {"vence_em": vence_em}

    @app.post("/api/legendas")
    async def abrir_legenda(request: Request):
        conteudo = b""
        async for pedaco in request.stream():
            conteudo += pedaco
            if len(conteudo) > LEGENDA_MAXIMA:
                raise HTTPException(413, "O arquivo é grande demais para ser uma legenda.")
        try:
            return {"falas": _para_a_tela(ler_arquivo(conteudo))}
        except LegendaInvalida as erro:
            raise HTTPException(422, str(erro)) from erro

    @app.post("/api/transcricoes", status_code=201)
    def criar_transcricao(pedido: PedidoDeTranscricao):
        try:
            return {"id": transcricoes.criar([Marca(m.gravado, m.video) for m in pedido.marcas])}
        except FalhaNaTranscricao as erro:
            raise HTTPException(422, str(erro)) from erro

    @app.put("/api/transcricoes/{identificador}/som", status_code=202)
    async def receber_som(identificador: str, request: Request):
        trabalho = transcricoes.consultar(identificador)
        if trabalho is None:
            raise HTTPException(404, "Essa transcrição não existe mais.")
        if trabalho.estado != "esperando_som":
            raise HTTPException(409, "O som dessa transcrição já foi recebido.")
        arquivo = transcricoes.novo_arquivo()
        try:
            recebido = 0
            with arquivo.open("wb") as destino:
                async for pedaco in request.stream():
                    recebido += len(pedaco)
                    if recebido > TAMANHO_MAXIMO:
                        raise HTTPException(413, "A gravação é grande demais.")
                    destino.write(pedaco)
            if recebido == 0:
                raise HTTPException(422, "A gravação chegou vazia.")
        except BaseException:
            # Inclui a conexão cortada no meio: o som nunca fica esquecido no disco.
            arquivo.unlink(missing_ok=True)
            raise
        transcricoes.iniciar(identificador, arquivo)
        return {"estado": "na_fila"}

    @app.get("/api/transcricoes/{identificador}")
    def consultar_transcricao(identificador: str):
        trabalho = transcricoes.consultar(identificador)
        if trabalho is None:
            raise HTTPException(404, "Essa transcrição não existe mais.")
        return {
            "estado": trabalho.estado,
            "progresso": trabalho.progresso,
            "erro": trabalho.erro,
            "falas": _para_a_tela(trabalho.falas),
        }

    app.mount("/", StaticFiles(directory=PASTA_WEB, html=True))
    return app


def _para_a_tela(falas: list[Fala] | tuple[Fala, ...]) -> list[dict]:
    return [asdict(fala) for fala in dividir(list(falas))]


def _nome_aceito(host: str) -> bool:
    return host.rsplit(":", 1)[0] in NOMES_ACEITOS


def _para_o_nome(request: Request) -> RedirectResponse | None:
    """Leva a página aberta pelo número ao mesmo lugar, pelo nome."""
    pelo_numero = request.headers.get("host", "").startswith(ENDERECO)
    if not pelo_numero or request.method not in {"GET", "HEAD"} or request.url.path.startswith("/api/"):
        return None
    # A porta é a do servidor, e não a do cabeçalho, que poderia levar a outro site.
    porta = request.scope["server"][1]
    return RedirectResponse(str(request.url.replace(scheme="http", netloc=f"{NOME}:{porta}")), status_code=307)


def _origem_aceita(request: Request) -> bool:
    """Só a própria página muda alguma coisa aqui; ler também, por garantia."""
    origem = request.headers.get("origin")
    if origem is None:
        # Navegação comum e programas não mandam origem; formulários de outros
        # sites mandam, e o navegador ainda diz de onde veio o pedido.
        return request.method in {"GET", "HEAD"} or request.headers.get("sec-fetch-site") in {
            None,
            "same-origin",
        }
    partes = urlsplit(origem)
    return partes.scheme == "http" and partes.netloc == request.headers.get("host")


def ja_esta_aberto(porta: int) -> bool:
    """Quem ocupa a porta é outro typelead?"""
    # Um proxy configurado no sistema não conhece este computador.
    abridor = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with abridor.open(f"http://{ENDERECO}:{porta}/api/programa", timeout=3) as resposta:
            dados = json.loads(resposta.read(10_000))
    except (OSError, ValueError, http.client.HTTPException):
        return False
    return isinstance(dados, dict) and dados.get("programa") == NOME_DO_PROGRAMA


def main() -> int:
    parser = argparse.ArgumentParser(prog="typelead", description="Abre o typelead.")
    parser.add_argument("--porta", type=int, default=PORTA_PADRAO)
    parser.add_argument("--sem-navegador", action="store_true", help="não abre a página ao iniciar")
    argumentos = parser.parse_args()
    porta, abrir_pagina = argumentos.porta, not argumentos.sem_navegador
    endereco = f"http://{NOME}:{porta}"

    # A porta é ocupada antes de tudo: quem chega segundo não mexe no banco, e a
    # página aberta abaixo já encontra quem a atenda.
    tomada = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if sys.platform != "win32":
            # No Windows, esta opção deixaria dois programas na mesma porta.
            tomada.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        tomada.bind((ENDERECO, porta))
        tomada.listen()
    except (OSError, OverflowError) as erro:
        tomada.close()
        if ja_esta_aberto(porta):
            print(f"O typelead já está aberto em {endereco}", flush=True)
            if abrir_pagina:
                webbrowser.open(endereco)
            return 0
        print(
            f"Não foi possível usar a porta {porta}: {erro}\nTente outra, por exemplo: typelead --porta 9000",
            file=sys.stderr,
        )
        return 1

    # Importado aqui porque só o programa de verdade precisa dele.
    import uvicorn

    try:
        banco = Banco(caminho_padrao())
    except (FalhaNoBanco, OSError) as erro:
        tomada.close()
        print(erro, file=sys.stderr)
        return 1
    transcricoes = Transcricoes()
    print(f"typelead em {endereco}. Deixe esta janela aberta; Ctrl+C encerra.", flush=True)
    if abrir_pagina:
        webbrowser.open(endereco)
    servidor = uvicorn.Server(uvicorn.Config(criar_app(transcricoes, banco=banco), log_level="warning"))
    try:
        servidor.run(sockets=[tomada])
    except KeyboardInterrupt:
        pass
    finally:
        tomada.close()
        transcricoes.encerrar()
        banco.fechar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
