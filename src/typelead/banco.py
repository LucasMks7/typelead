"""Guarda vídeos, falas e tentativas em um arquivo SQLite, só neste computador."""

import json
import os
import sqlite3
import sys
import threading
from collections.abc import Iterable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .alinhamento import normalizar
from .legendas import Fala, Palavra

# Cada item leva o banco de uma versão à seguinte. Um item publicado nunca muda:
# há bancos por aí que já passaram por ele.
MIGRACOES = (
    """
    CREATE TABLE videos (
        id TEXT PRIMARY KEY,
        titulo TEXT NOT NULL,
        canal TEXT NOT NULL,
        duracao REAL,
        incorporavel INTEGER NOT NULL,
        origem TEXT NOT NULL,
        -- Trocar a legenda cria outra versão das falas. As antigas ficam, porque as
        -- tentativas feitas nelas continuam valendo.
        versao INTEGER NOT NULL,
        posicao INTEGER NOT NULL DEFAULT 0,
        aberto_em TEXT NOT NULL
    );
    CREATE TABLE falas (
        id INTEGER PRIMARY KEY,
        video_id TEXT NOT NULL REFERENCES videos (id),
        versao INTEGER NOT NULL,
        ordem INTEGER NOT NULL,
        inicio REAL NOT NULL,
        fim REAL NOT NULL,
        texto TEXT NOT NULL,
        palavras TEXT NOT NULL,
        UNIQUE (video_id, versao, ordem)
    );
    CREATE TABLE tentativas (
        id INTEGER PRIMARY KEY,
        fala_id INTEGER NOT NULL REFERENCES falas (id),
        -- As tentativas seguidas na mesma fala, até a pessoa sair do vídeo.
        rodada TEXT NOT NULL,
        modo TEXT NOT NULL,
        corrigir TEXT NOT NULL,
        texto TEXT NOT NULL,
        acertou INTEGER NOT NULL,
        com_ajuda INTEGER NOT NULL,
        repeticoes INTEGER NOT NULL,
        velocidade REAL NOT NULL,
        duracao REAL NOT NULL,
        criada_em TEXT NOT NULL
    );
    CREATE INDEX tentativas_da_fala ON tentativas (fala_id);
    CREATE INDEX tentativas_da_rodada ON tentativas (rodada);
    CREATE TABLE itens (
        id INTEGER PRIMARY KEY,
        tentativa_id INTEGER NOT NULL REFERENCES tentativas (id),
        tipo TEXT NOT NULL CHECK (tipo IN ('certa', 'trocada', 'faltou', 'sobrou')),
        -- Qual palavra da fala, contando do zero.
        posicao INTEGER NOT NULL,
        esperada TEXT NOT NULL,
        digitada TEXT NOT NULL,
        -- A palavra esperada sem maiúscula nem pontuação, para achá-la em outras falas.
        forma TEXT NOT NULL
    );
    CREATE INDEX itens_da_tentativa ON itens (tentativa_id);
    CREATE INDEX itens_da_forma ON itens (forma);
    """,
    """
    ALTER TABLE falas ADD COLUMN traducao TEXT;
    -- A pessoa viu a tradução antes de responder.
    ALTER TABLE tentativas ADD COLUMN traduziu INTEGER NOT NULL DEFAULT 0;
    """,
)


class FalhaNoBanco(RuntimeError):
    """O banco não pôde ser aberto."""


@dataclass(frozen=True)
class Item:
    tipo: str
    posicao: int
    esperada: str
    digitada: str


@dataclass(frozen=True)
class Tentativa:
    fala_id: int
    rodada: str
    modo: str
    corrigir: str
    texto: str
    com_ajuda: bool
    repeticoes: int
    velocidade: float
    duracao: float
    itens: tuple[Item, ...]
    traduziu: bool = False

    @property
    def acertou(self) -> bool:
        return bool(self.itens) and all(item.tipo == "certa" for item in self.itens)


def caminho_padrao() -> Path:
    """Fora do projeto e do OneDrive, que brigaria com o arquivo aberto."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "typelead" / "typelead.db"


class Banco:
    """Uma conexão só, usada por uma thread de cada vez."""

    def __init__(self, caminho: Path | str = ":memory:"):
        if caminho != ":memory:":
            Path(caminho).parent.mkdir(parents=True, exist_ok=True)
        self._trava = threading.RLock()
        try:
            self._conexao = sqlite3.connect(caminho, check_same_thread=False)
            self._conexao.row_factory = sqlite3.Row
            self._conexao.execute("PRAGMA foreign_keys = ON")
            self._migrar()
        except sqlite3.Error as erro:
            raise FalhaNoBanco(f"Não foi possível abrir o banco em {caminho}: {erro}") from erro

    def _migrar(self) -> None:
        versao = self._conexao.execute("PRAGMA user_version").fetchone()[0]
        if versao > len(MIGRACOES):
            raise FalhaNoBanco("O banco foi criado por uma versão mais nova do typelead.")
        for numero, sql in enumerate(MIGRACOES[versao:], versao + 1):
            try:
                # A versão muda junto com as tabelas: ou tudo, ou nada.
                self._conexao.executescript(f"BEGIN; {sql}; PRAGMA user_version = {numero}; COMMIT;")
            except sqlite3.Error:
                if self._conexao.in_transaction:
                    self._conexao.rollback()
                raise

    @contextmanager
    def _usar(self):
        with self._trava, self._conexao:
            yield self._conexao

    def fechar(self) -> None:
        with self._trava:
            self._conexao.close()

    # Vídeos

    def salvar_video(
        self,
        identificador: str,
        titulo: str,
        canal: str,
        duracao: float | None,
        incorporavel: bool,
        origem: str,
        falas: Iterable[Fala],
    ) -> None:
        """Guarda o vídeo e as falas, como uma versão nova se ele já existia."""
        with self._usar() as conexao:
            versao = conexao.execute(
                """
                INSERT INTO videos (id, titulo, canal, duracao, incorporavel, origem, versao, aberto_em)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                ON CONFLICT (id) DO UPDATE SET
                    titulo = excluded.titulo, canal = excluded.canal, duracao = excluded.duracao,
                    incorporavel = excluded.incorporavel, origem = excluded.origem,
                    versao = versao + 1, posicao = 0, aberto_em = excluded.aberto_em
                RETURNING versao
                """,
                (identificador, titulo, canal, duracao, incorporavel, origem, _agora()),
            ).fetchone()["versao"]
            conexao.executemany(
                """
                INSERT INTO falas (video_id, versao, ordem, inicio, fim, texto, palavras)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (identificador, versao, ordem, fala.inicio, fala.fim, fala.texto, _para_json(fala.palavras))
                    for ordem, fala in enumerate(falas)
                ],
            )

    def abrir_video(self, identificador: str) -> dict | None:
        """O vídeo salvo, com as falas atuais e o que já foi feito, ou None."""
        with self._usar() as conexao:
            video = conexao.execute("SELECT * FROM videos WHERE id = ?", (identificador,)).fetchone()
            if video is None:
                return None
            conexao.execute("UPDATE videos SET aberto_em = ? WHERE id = ?", (_agora(), identificador))
            falas = conexao.execute(
                """
                SELECT falas.id, inicio, fim, falas.texto, traducao,
                       EXISTS (
                           SELECT 1 FROM tentativas
                           WHERE fala_id = falas.id AND acertou AND NOT com_ajuda
                       ) AS acertada
                FROM falas
                WHERE video_id = ? AND versao = ?
                ORDER BY ordem
                """,
                (identificador, video["versao"]),
            ).fetchall()
        return {
            "id": video["id"],
            "titulo": video["titulo"],
            "canal": video["canal"],
            "duracao": video["duracao"],
            "incorporavel": bool(video["incorporavel"]),
            "origem": video["origem"],
            "posicao": video["posicao"],
            "falas": [dict(fala) | {"acertada": bool(fala["acertada"])} for fala in falas],
        }

    def recentes(self, limite: int = 12) -> list[dict]:
        """Os últimos vídeos abertos, com o andamento de cada um."""
        with self._usar() as conexao:
            linhas = conexao.execute(
                """
                SELECT videos.id, titulo, canal, videos.duracao, posicao, aberto_em,
                       COUNT(DISTINCT falas.id) AS total,
                       COUNT(DISTINCT tentativas.fala_id) AS acertadas
                FROM videos
                JOIN falas ON falas.video_id = videos.id AND falas.versao = videos.versao
                LEFT JOIN tentativas
                    ON tentativas.fala_id = falas.id AND tentativas.acertou AND NOT tentativas.com_ajuda
                GROUP BY videos.id
                ORDER BY aberto_em DESC
                LIMIT ?
                """,
                (limite,),
            ).fetchall()
        return [dict(linha) for linha in linhas]

    def marcar_posicao(self, identificador: str, posicao: int) -> bool:
        """Devolve se o vídeo existe."""
        with self._usar() as conexao:
            return (
                conexao.execute("UPDATE videos SET posicao = ? WHERE id = ?", (posicao, identificador)).rowcount > 0
            )

    # Falas

    def fala(self, numero: int) -> dict | None:
        with self._usar() as conexao:
            linha = conexao.execute("SELECT id, texto, traducao FROM falas WHERE id = ?", (numero,)).fetchone()
        return dict(linha) if linha else None

    def guardar_traducao(self, numero: int, traducao: str) -> None:
        with self._usar() as conexao:
            conexao.execute("UPDATE falas SET traducao = ? WHERE id = ?", (traducao, numero))

    # Tentativas

    def salvar_tentativa(self, tentativa: Tentativa) -> int | None:
        """Devolve o número da tentativa, ou None se a fala não existe."""
        with self._usar() as conexao:
            if conexao.execute("SELECT 1 FROM falas WHERE id = ?", (tentativa.fala_id,)).fetchone() is None:
                return None
            numero = conexao.execute(
                """
                INSERT INTO tentativas (fala_id, rodada, modo, corrigir, texto, acertou, com_ajuda,
                                        repeticoes, velocidade, duracao, traduziu, criada_em)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tentativa.fala_id,
                    tentativa.rodada,
                    tentativa.modo,
                    tentativa.corrigir,
                    tentativa.texto,
                    tentativa.acertou,
                    tentativa.com_ajuda,
                    tentativa.repeticoes,
                    tentativa.velocidade,
                    tentativa.duracao,
                    tentativa.traduziu,
                    _agora(),
                ),
            ).lastrowid
            conexao.executemany(
                """
                INSERT INTO itens (tentativa_id, tipo, posicao, esperada, digitada, forma)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (numero, item.tipo, item.posicao, item.esperada, item.digitada, normalizar(item.esperada))
                    for item in tentativa.itens
                ],
            )
        return numero


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _para_json(palavras: Iterable[Palavra]) -> str:
    return json.dumps([[p.texto, p.inicio, p.fim] for p in palavras], ensure_ascii=False)
