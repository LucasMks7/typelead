"""Fila de transcrições: uma por vez, em segundo plano."""

import logging
import tempfile
import threading
import uuid
from collections import OrderedDict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from .legendas import Fala
from .transcricao import FalhaNaTranscricao, Marca, Relogio, carregar_modelo, ler_som, transcrever

# Uma hora de gravação ocupa perto de 45 MB.
TAMANHO_MAXIMO = 500_000_000
# As mais antigas são esquecidas, para a memória não crescer sem fim.
MAXIMO_GUARDADO = 20


@dataclass
class Trabalho:
    marcas: list[Marca]
    estado: str = "esperando_som"  # na_fila, carregando, transcrevendo, pronto, falhou
    progresso: float = 0.0
    falas: list[Fala] = field(default_factory=list)
    erro: str | None = None


class Transcricoes:
    """Recebe gravações e transcreve. Os parâmetros existem para os testes usarem dublês."""

    def __init__(
        self,
        carregar: Callable = carregar_modelo,
        ler: Callable = ler_som,
        transcrever: Callable = transcrever,
        pasta: Path | None = None,
    ):
        self._carregar, self._ler, self._transcrever = carregar, ler, transcrever
        self._pasta = pasta
        self._modelo = None
        self._trabalhos: OrderedDict[str, Trabalho] = OrderedDict()
        self._trava = threading.Lock()
        # Uma por vez: duas não cabem juntas na memória da placa.
        self._fila = ThreadPoolExecutor(max_workers=1, thread_name_prefix="transcricao")

    def criar(self, marcas: list[Marca]) -> str:
        """Registra uma gravação que ainda vai chegar. Falha se as marcas não servirem."""
        Relogio(marcas)
        identificador = uuid.uuid4().hex
        with self._trava:
            self._trabalhos[identificador] = Trabalho(marcas)
            acabados = [k for k, t in self._trabalhos.items() if t.estado in {"pronto", "falhou", "esperando_som"}]
            for chave in acabados[: max(0, len(self._trabalhos) - MAXIMO_GUARDADO)]:
                del self._trabalhos[chave]
        return identificador

    def consultar(self, identificador: str) -> Trabalho | None:
        return self._trabalhos.get(identificador)

    def novo_arquivo(self) -> Path:
        """Um arquivo temporário, fora do projeto e do OneDrive."""
        with tempfile.NamedTemporaryFile(prefix="typelead-", suffix=".webm", dir=self._pasta, delete=False) as arquivo:
            return Path(arquivo.name)

    def iniciar(self, identificador: str, som: Path) -> None:
        """Põe na fila. A partir daqui, o arquivo é apagado quando a transcrição acabar."""
        trabalho = self._trabalhos[identificador]
        trabalho.estado = "na_fila"
        self._fila.submit(self._executar, trabalho, som)

    def _executar(self, trabalho: Trabalho, som: Path) -> None:
        try:
            relogio = Relogio(trabalho.marcas)
            trabalho.estado = "carregando"
            amostras = self._ler(som)
            # O som só existe na memória daqui em diante.
            som.unlink(missing_ok=True)
            if self._modelo is None:
                self._modelo, _ = self._carregar()
            trabalho.estado = "transcrevendo"

            def avancar(fracao: float) -> None:
                trabalho.progresso = fracao

            trabalho.falas = self._transcrever(amostras, self._modelo, relogio, avancar)
            trabalho.progresso = 1.0
            trabalho.estado = "pronto"
        except FalhaNaTranscricao as erro:
            trabalho.erro, trabalho.estado = str(erro), "falhou"
        except Exception:
            logging.getLogger(__name__).exception("Falha inesperada na transcrição")
            trabalho.erro, trabalho.estado = "A transcrição falhou de um jeito inesperado.", "falhou"
        finally:
            som.unlink(missing_ok=True)

    def encerrar(self) -> None:
        self._fila.shutdown(wait=False, cancel_futures=True)
