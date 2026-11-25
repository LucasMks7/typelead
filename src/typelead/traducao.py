"""Traduz uma fala do inglês para o português do Brasil, neste computador.

O modelo é o opus-mt-tc-big-en-pt, do grupo OPUS-MT da Universidade de Helsinque
(CC BY 4.0), convertido para o CTranslate2. As medidas estão em docs/traducao.md.
"""

import threading
from collections.abc import Callable

REPOSITORIO = "gow-solucoes/opus-mt-en-pt-ct2"
# Fixa: o conteúdo conferido é este, e não o que o repositório vier a ter.
REVISAO = "884d2305736eb9c15e297bd2cb7fc95727283b32"
ARQUIVOS = ["config.json", "model.bin", "shared_vocabulary.json", "source.spm", "target.spm"]
# O modelo traduz para o português do Brasil (pob) e o europeu (por).
PARA_O_BRASIL = ">>pob<<"
FIM = "</s>"


class FalhaNaTraducao(RuntimeError):
    """A fala não pôde ser traduzida."""


def preparar(texto: str) -> str:
    """Legenda toda em maiúsculas sai mal traduzida: passa para o tamanho comum."""
    if not texto.isupper():
        return texto
    baixo = texto.lower()
    return baixo[:1].upper() + baixo[1:]


def carregar_modelo() -> Callable[[str], str]:
    """Na primeira vez, baixa o modelo: 236 MB."""
    # Importados aqui porque demoram, e só quem pede uma tradução precisa deles.
    import ctranslate2
    import sentencepiece
    from huggingface_hub import snapshot_download

    opcoes = {"repo_id": REPOSITORIO, "revision": REVISAO, "allow_patterns": ARQUIVOS}
    try:
        # Já baixado, nem pergunta à internet.
        pasta = snapshot_download(**opcoes, local_files_only=True)
    except Exception:
        pasta = snapshot_download(**opcoes)

    tradutor = ctranslate2.Translator(pasta, device="cpu", compute_type="int8")
    entrada = sentencepiece.SentencePieceProcessor(model_file=f"{pasta}/source.spm")
    saida = sentencepiece.SentencePieceProcessor(model_file=f"{pasta}/target.spm")

    def traduzir(texto: str) -> str:
        pedacos = [PARA_O_BRASIL, *entrada.encode(texto, out_type=str), FIM]
        resultado = tradutor.translate_batch([pedacos], beam_size=4, max_decoding_length=256)
        return saida.decode(resultado[0].hypotheses[0])

    return traduzir


class Tradutor:
    """Carrega o modelo no primeiro pedido e atende um por vez."""

    def __init__(self, carregar: Callable[[], Callable[[str], str]] = carregar_modelo):
        self._carregar = carregar
        self._modelo: Callable[[str], str] | None = None
        self._trava = threading.Lock()

    def traduzir(self, texto: str) -> str:
        with self._trava:
            if self._modelo is None:
                try:
                    self._modelo = self._carregar()
                except Exception as erro:
                    # Fica sem modelo: o próximo pedido tenta de novo.
                    raise FalhaNaTraducao(
                        "Não foi possível carregar o tradutor. Na primeira vez, ele é baixado da "
                        f"internet (236 MB). Detalhe: {erro}"
                    ) from erro
            try:
                traduzida = self._modelo(preparar(texto)).strip()
            except Exception as erro:
                raise FalhaNaTraducao(f"O tradutor falhou nesta fala. Detalhe: {erro}") from erro
        if not traduzida:
            raise FalhaNaTraducao("O tradutor não devolveu nada para esta fala.")
        return traduzida
