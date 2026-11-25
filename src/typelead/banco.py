"""Guarda vídeos, falas e tentativas em um arquivo SQLite, só neste computador."""

import json
import os
import sqlite3
import sys
import threading
from collections.abc import Collection, Iterable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from itertools import groupby
from pathlib import Path

from . import revisao
from .alinhamento import normalizar
from .diagnostico import Desistencia, Erro, Passo, diagnosticar
from .legendas import Fala, Palavra
from .palavras import COMUM_DEMAIS, SABIDA, frequencia, situacao

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
    """
    ALTER TABLE itens ADD COLUMN diagnostico TEXT;
    -- O que a pessoa disse que foi, quando discordou.
    ALTER TABLE itens ADD COLUMN corrigido TEXT;
    -- A pessoa pediu a resposta. Guarda as medidas de quando ela pediu.
    CREATE TABLE desistencias (
        rodada TEXT PRIMARY KEY,
        repeticoes INTEGER NOT NULL,
        velocidade REAL NOT NULL,
        traduziu INTEGER NOT NULL,
        criada_em TEXT NOT NULL
    );
    """,
    """
    -- O resto do banco de palavras é calculado do que já está salvo em itens.
    CREATE TABLE palavras_sabidas (
        forma TEXT PRIMARY KEY,
        marcada_em TEXT NOT NULL
    );
    """,
    """
    -- Nasce na primeira revisão; antes dela, a data sai do último erro.
    CREATE TABLE cartoes (
        forma TEXT PRIMARY KEY,
        -- O estado do FSRS, em JSON, como a biblioteca o escreve.
        estado TEXT NOT NULL,
        vence_em TEXT NOT NULL,
        revisto_em TEXT NOT NULL
    );
    CREATE TABLE revisoes (
        id INTEGER PRIMARY KEY,
        forma TEXT NOT NULL,
        fala_id INTEGER NOT NULL REFERENCES falas (id),
        -- 1: errou; 2: acertou com esforço; 3: acertou bem.
        nota INTEGER NOT NULL,
        digitada TEXT NOT NULL,
        quase INTEGER NOT NULL,
        repeticoes INTEGER NOT NULL,
        velocidade REAL NOT NULL,
        criada_em TEXT NOT NULL
    );
    """,
)

# Como foi cada palavra em cada rodada: uma linha por erro que conta e por acerto
# sem ajuda. Digitação não é falta de palavra. "Não sei dizer" só conta se a pessoa
# desistiu sem ter acertado antes: quem aperta Enter no meio da fala deixa as
# palavras seguintes em branco, e isso não quer dizer que não as conhece. Pela mesma
# razão, a palavra muito comum em branco não conta, a menos que a pessoa diga o motivo.
OCORRENCIAS = f"""
    ultimos_erros AS (
        SELECT itens.id, forma, rodada, posicao, esperada, fala_id, criada_em, tipo, corrigido,
               COALESCE(corrigido, diagnostico) AS motivo,
               -- O mesmo erro que a tela mostra: o último de cada palavra na rodada.
               ROW_NUMBER() OVER (PARTITION BY rodada, posicao ORDER BY itens.id DESC) AS do_fim
        FROM itens JOIN tentativas ON tentativas.id = tentativa_id
        WHERE tipo IN ('trocada', 'faltou') AND forma GLOB '*[a-z]*'
    ),
    erros AS (
        SELECT * FROM ultimos_erros
        WHERE do_fim = 1 AND (
            motivo IN ('escuta', 'vocabulario', 'homofono')
            OR motivo = 'indefinido'
               AND rodada IN (SELECT rodada FROM desistencias)
               AND NOT EXISTS (
                   SELECT 1 FROM itens JOIN tentativas ON tentativas.id = tentativa_id
                   WHERE tentativas.rodada = ultimos_erros.rodada AND itens.posicao = ultimos_erros.posicao
                     AND itens.tipo = 'certa' AND NOT com_ajuda
               )
        ) AND (tipo = 'trocada' OR corrigido IS NOT NULL OR frequencia(esperada) < {COMUM_DEMAIS})
    ),
    ocorrencias AS (
        SELECT forma, rodada, 1 AS errou, criada_em FROM erros
        UNION ALL
        SELECT forma, rodada, 0, criada_em
        FROM itens JOIN tentativas ON tentativas.id = tentativa_id
        WHERE tipo = 'certa' AND NOT com_ajuda AND forma GLOB '*[a-z]*'
          -- No texto livre, um item pode valer por duas palavras: "going to".
          AND NOT (modo = 'livre' AND instr(esperada, ' '))
        UNION ALL
        SELECT forma, 'revisao ' || id, nota = 1, criada_em FROM revisoes
    ),
    por_rodada AS (
        SELECT forma, rodada, MAX(errou) AS errou, MAX(criada_em) AS quando
        FROM ocorrencias GROUP BY forma, rodada
    ),
    com_ultimo_erro AS (
        SELECT *, MAX(CASE WHEN errou THEN quando END) OVER (PARTITION BY forma) AS ultimo_erro
        FROM por_rodada
    ),
    exemplos AS (
        SELECT *, ROW_NUMBER() OVER (PARTITION BY forma ORDER BY id DESC) AS do_fim_da_forma FROM erros
    ),
    historico AS (
        SELECT forma, SUM(errou) AS erros, SUM(NOT errou) AS acertos, ultimo_erro,
               SUM(NOT errou AND (ultimo_erro IS NULL OR quando > ultimo_erro)) AS acertos_seguidos,
               forma IN (SELECT forma FROM palavras_sabidas) AS sabida
        FROM com_ultimo_erro GROUP BY forma
    )
"""


CAMPOS_DO_TRECHO = ("fala_id", "inicio", "fim", "texto", "traducao", "video_id", "titulo")


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
            self._conexao.create_function("frequencia", 1, frequencia, deterministic=True)
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

    def resumo(self, hoje: date | None = None) -> dict:
        """Quantas falas certas hoje, há quantos dias seguidos e os últimos sete dias."""
        hoje = hoje or date.today()
        with self._usar() as conexao:
            linhas = conexao.execute(
                """
                SELECT date(criada_em, 'localtime') AS dia, COUNT(DISTINCT fala_id) AS certas
                FROM (
                    SELECT criada_em, fala_id FROM tentativas WHERE acertou AND NOT com_ajuda
                    UNION ALL
                    SELECT criada_em, fala_id FROM revisoes WHERE nota > 1
                )
                GROUP BY dia
                """
            ).fetchall()
        por_dia = {date.fromisoformat(linha["dia"]): linha["certas"] for linha in linhas}
        semana = [hoje - timedelta(days=atras) for atras in range(6, -1, -1)]
        return {
            "hoje": por_dia.get(hoje, 0),
            "dias_seguidos": dias_seguidos(por_dia, hoje),
            "semana": [{"dia": dia.isoformat(), "certas": por_dia.get(dia, 0)} for dia in semana],
        }

    # Palavras

    def situacoes(self) -> dict[str, str]:
        """Como a pessoa vai com cada palavra que já apareceu."""
        with self._usar() as conexao:
            linhas = conexao.execute(f"WITH {OCORRENCIAS} SELECT * FROM historico").fetchall()
            sabidas = conexao.execute("SELECT forma FROM palavras_sabidas").fetchall()
        # A sabida pode nunca ter aparecido em um erro que conta.
        return {linha["forma"]: SABIDA for linha in sabidas} | {linha["forma"]: _situacao(linha) for linha in linhas}

    def palavras(self) -> list[dict]:
        """As palavras já erradas, da mais recente à mais antiga, com a última fala em que aconteceu."""
        with self._usar() as conexao:
            linhas = conexao.execute(
                f"""
                WITH {OCORRENCIAS}
                SELECT historico.*, exemplos.posicao, esperada, motivo, fala_id, inicio, fim, falas.texto, traducao,
                       video_id, titulo
                FROM historico
                JOIN exemplos ON exemplos.forma = historico.forma AND do_fim_da_forma = 1
                JOIN falas ON falas.id = fala_id
                JOIN videos ON videos.id = video_id
                ORDER BY ultimo_erro DESC, historico.forma
                """
            ).fetchall()
        prontas = []
        for linha in linhas:
            dados = dict(linha) | {"situacao": _situacao(linha)}
            del dados["acertos_seguidos"], dados["sabida"]
            prontas.append(dados)
        return prontas

    def marcar_sabida(self, forma: str, sabida: bool) -> None:
        with self._usar() as conexao:
            if sabida:
                conexao.execute(
                    "INSERT OR IGNORE INTO palavras_sabidas (forma, marcada_em) VALUES (?, ?)", (forma, _agora())
                )
            else:
                conexao.execute("DELETE FROM palavras_sabidas WHERE forma = ?", (forma,))

    # Revisão

    def revisar(self, hoje: date | None = None, limite: int = 20) -> dict:
        """Os trechos vencidos, cada um com as palavras a completar, e quantas palavras venceram.

        As palavras da mesma fala vêm juntas: em separado, uma entregaria a outra. O
        limite é de palavras, e o último trecho pode passar dele.
        """
        with self._usar() as conexao:
            linhas = conexao.execute(
                f"""
                WITH {OCORRENCIAS},
                prazos AS (
                    SELECT historico.forma, sabida,
                           CASE
                               -- Errada de novo na prática depois da última revisão: volta antes.
                               WHEN vence_em IS NULL THEN date(ultimo_erro, 'localtime', '+1 day')
                               WHEN ultimo_erro > revisto_em
                                   THEN MIN(date(vence_em, 'localtime'), date(ultimo_erro, 'localtime', '+1 day'))
                               ELSE date(vence_em, 'localtime')
                           END AS prazo
                    FROM historico LEFT JOIN cartoes ON cartoes.forma = historico.forma
                )
                SELECT prazos.forma, prazo, exemplos.posicao, esperada, fala_id, inicio, fim, falas.texto, traducao,
                       video_id, titulo
                FROM prazos
                JOIN exemplos ON exemplos.forma = prazos.forma AND do_fim_da_forma = 1
                JOIN falas ON falas.id = fala_id
                JOIN videos ON videos.id = video_id
                WHERE NOT sabida AND prazo <= ?
                ORDER BY prazo, video_id, ordem, exemplos.posicao
                """,
                ((hoje or date.today()).isoformat(),),
            ).fetchall()
        trechos: dict[int, dict] = {}
        for linha in linhas:
            trecho = {campo: linha[campo] for campo in CAMPOS_DO_TRECHO} | {"palavras": []}
            palavra = {"forma": linha["forma"], "posicao": linha["posicao"], "esperada": linha["esperada"]}
            trechos.setdefault(linha["fala_id"], trecho)["palavras"].append(palavra)
        escolhidos, quantas = [], 0
        for trecho in trechos.values():
            if quantas >= limite:
                break
            escolhidos.append(trecho)
            quantas += len(trecho["palavras"])
        # Trocar de vídeo custa uma espera: os do mesmo vídeo vêm seguidos.
        ordem = {trecho["video_id"]: i for i, trecho in reversed(list(enumerate(escolhidos)))}
        escolhidos.sort(key=lambda trecho: ordem[trecho["video_id"]])
        return {"trechos": escolhidos, "total": len(linhas)}

    def salvar_revisao(
        self, forma: str, fala_id: int, acertou: bool, quase: bool, digitada: str, repeticoes: int, velocidade: float
    ) -> str | None:
        """Agenda a próxima vez e devolve quando é, ou None se a fala não existe."""
        agora = _agora()
        nota = revisao.dar_nota(acertou, quase, repeticoes, velocidade)
        with self._usar() as conexao:
            if conexao.execute("SELECT 1 FROM falas WHERE id = ?", (fala_id,)).fetchone() is None:
                return None
            cartao = conexao.execute("SELECT estado FROM cartoes WHERE forma = ?", (forma,)).fetchone()
            estado, vence = revisao.agendar(cartao and cartao["estado"], nota, datetime.fromisoformat(agora))
            vence_em = vence.astimezone(timezone.utc).isoformat(timespec="microseconds")
            conexao.execute(
                """
                INSERT INTO revisoes (forma, fala_id, nota, digitada, quase, repeticoes, velocidade, criada_em)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (forma, fala_id, nota, digitada, quase, repeticoes, velocidade, agora),
            )
            conexao.execute(
                """
                INSERT INTO cartoes (forma, estado, vence_em, revisto_em) VALUES (?, ?, ?, ?)
                ON CONFLICT (forma) DO UPDATE SET
                    estado = excluded.estado, vence_em = excluded.vence_em, revisto_em = excluded.revisto_em
                """,
                (forma, estado, vence_em, agora),
            )
        return vence_em

    # Diagnóstico

    def desistir(self, rodada: str, desistencia: Desistencia) -> None:
        """Registra que a pessoa viu a resposta. Vale a primeira vez em cada rodada."""
        with self._usar() as conexao:
            conexao.execute(
                """
                INSERT OR IGNORE INTO desistencias (rodada, repeticoes, velocidade, traduziu, criada_em)
                SELECT ?, ?, ?, ?, ? WHERE EXISTS (SELECT 1 FROM tentativas WHERE rodada = ?)
                """,
                (rodada, desistencia.repeticoes, desistencia.velocidade, desistencia.traduziu, _agora(), rodada),
            )

    def diagnosticar(self, rodada: str) -> list[dict]:
        """Reavalia a rodada. Devolve o último erro de cada palavra, na ordem da fala."""
        with self._usar() as conexao:
            passos = self._passos(conexao, rodada)
            linha = conexao.execute(
                "SELECT repeticoes, velocidade, traduziu FROM desistencias WHERE rodada = ?", (rodada,)
            ).fetchone()
            desistencia = Desistencia(linha["repeticoes"], linha["velocidade"], bool(linha["traduziu"])) if linha else None
            diagnosticos = diagnosticar(passos, self._conhecidas(conexao, rodada), desistencia)
            conexao.executemany(
                "UPDATE itens SET diagnostico = ? WHERE id = ?",
                [(tipo, numero) for numero, tipo in diagnosticos.items()],
            )
            erros = conexao.execute(
                """
                SELECT itens.id, posicao, esperada, digitada, diagnostico, corrigido
                FROM itens JOIN tentativas ON tentativas.id = tentativa_id
                WHERE rodada = ? AND tipo IN ('trocada', 'faltou')
                ORDER BY itens.id
                """,
                (rodada,),
            ).fetchall()
        ultimos = {erro["posicao"]: dict(erro) for erro in erros}
        return [ultimos[posicao] for posicao in sorted(ultimos)]

    def corrigir_diagnostico(self, numero: int, tipo: str) -> bool:
        """A pessoa discorda. Devolve se o erro existe."""
        with self._usar() as conexao:
            return (
                conexao.execute(
                    "UPDATE itens SET corrigido = ? WHERE id = ? AND tipo IN ('trocada', 'faltou')", (tipo, numero)
                ).rowcount
                > 0
            )

    @staticmethod
    def _passos(conexao: sqlite3.Connection, rodada: str) -> list[Passo]:
        linhas = conexao.execute(
            """
            SELECT tentativa_id, repeticoes, velocidade, traduziu, com_ajuda,
                   itens.id, tipo, posicao, esperada, digitada
            FROM tentativas JOIN itens ON tentativa_id = tentativas.id
            WHERE rodada = ?
            ORDER BY tentativa_id, itens.id
            """,
            (rodada,),
        ).fetchall()
        passos = []
        for _, grupo in groupby(linhas, key=lambda linha: linha["tentativa_id"]):
            itens = list(grupo)
            certas = {
                # Uma contração pode valer por duas ou três palavras da fala.
                item["posicao"] + k
                for item in itens
                if item["tipo"] == "certa"
                for k in range(len(item["esperada"].split()))
            }
            erros = tuple(
                Erro(item["id"], item["posicao"], item["esperada"], item["digitada"])
                for item in itens
                if item["tipo"] in {"trocada", "faltou"}
            )
            primeiro = itens[0]
            passos.append(
                Passo(
                    primeiro["repeticoes"],
                    primeiro["velocidade"],
                    bool(primeiro["traduziu"]),
                    bool(primeiro["com_ajuda"]),
                    frozenset(certas),
                    erros,
                )
            )
        return passos

    @staticmethod
    def _conhecidas(conexao: sqlite3.Connection, rodada: str) -> set[str]:
        """Das palavras erradas na rodada, as que já foram acertadas em outra, sem ajuda."""
        linhas = conexao.execute(
            """
            SELECT DISTINCT acertos.forma
            FROM itens AS acertos JOIN tentativas ON tentativas.id = acertos.tentativa_id
            WHERE acertos.tipo = 'certa' AND NOT com_ajuda AND rodada <> :rodada
              AND acertos.forma IN (
                  SELECT itens.forma FROM itens JOIN tentativas ON tentativas.id = tentativa_id
                  WHERE rodada = :rodada AND tipo IN ('trocada', 'faltou')
              )
            """,
            {"rodada": rodada},
        ).fetchall()
        return {linha["forma"] for linha in linhas}


def _situacao(linha: sqlite3.Row) -> str:
    return situacao(linha["erros"], linha["acertos_seguidos"], bool(linha["sabida"]))


def dias_seguidos(dias: Collection[date], hoje: date) -> int:
    """Sem prática hoje, a sequência de ontem ainda vale: o dia não acabou."""
    dia = hoje if hoje in dias else hoje - timedelta(days=1)
    quantos = 0
    while dia in dias:
        quantos += 1
        dia -= timedelta(days=1)
    return quantos


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _para_json(palavras: Iterable[Palavra]) -> str:
    return json.dumps([[p.texto, p.inicio, p.fim] for p in palavras], ensure_ascii=False)
