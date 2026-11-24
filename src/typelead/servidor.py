"""Servidor local: entrega a interface e a API ao navegador, só neste computador."""

import argparse
import mimetypes
import sys
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .transcricao import FalhaNaTranscricao, Marca
from .transcricoes import TAMANHO_MAXIMO, Transcricoes

PASTA_WEB = Path(__file__).parent / "web"
ENDERECO = "127.0.0.1"
PORTA_PADRAO = 8765
NOMES_ACEITOS = {"127.0.0.1", "localhost"}

# O Windows pode ter o .js registrado como text/plain, e o navegador se recusa a
# executar um módulo com esse tipo. Por isso, fica fixado aqui.
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")


class MarcaRecebida(BaseModel):
    gravado: float = Field(ge=0, le=100_000)
    video: float = Field(ge=0, le=100_000)


class PedidoDeTranscricao(BaseModel):
    # Uma marca a cada 200 ms em seis horas de vídeo.
    marcas: list[MarcaRecebida] = Field(max_length=110_000)


def criar_app(transcricoes: Transcricoes | None = None) -> FastAPI:
    transcricoes = transcricoes or Transcricoes()
    # A documentação automática carregaria scripts de outro site.
    app = FastAPI(title="typelead", docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def proteger(request: Request, seguir):
        # Um site malicioso pode apontar o próprio domínio para 127.0.0.1 e
        # tentar ler esta página (DNS rebinding). O nome pedido o denuncia.
        # Ele também pode mandar um pedido direto para cá; a origem o denuncia.
        if not _nome_aceito(request.headers.get("host", "")) or not _origem_aceita(request):
            return JSONResponse({"detail": "Pedido recusado."}, status_code=403)
        resposta = await seguir(request)
        # Sem o Referer, o player do YouTube responde com o erro 153.
        resposta.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        resposta.headers["X-Content-Type-Options"] = "nosniff"
        resposta.headers["Cache-Control"] = "no-store"
        return resposta

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
            "falas": [asdict(fala) for fala in trabalho.falas],
        }

    app.mount("/", StaticFiles(directory=PASTA_WEB, html=True))
    return app


def _nome_aceito(host: str) -> bool:
    return host.rsplit(":", 1)[0] in NOMES_ACEITOS


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


def main() -> int:
    parser = argparse.ArgumentParser(prog="typelead", description="Abre o typelead.")
    parser.add_argument("--porta", type=int, default=PORTA_PADRAO)
    porta = parser.parse_args().porta

    # Importado aqui porque só o programa de verdade precisa dele.
    import uvicorn

    transcricoes = Transcricoes()
    print(f"typelead em http://{ENDERECO}:{porta} (Ctrl+C encerra)", flush=True)
    try:
        uvicorn.run(criar_app(transcricoes), host=ENDERECO, port=porta, log_level="warning")
    finally:
        transcricoes.encerrar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
