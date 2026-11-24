from types import SimpleNamespace

import numpy as np
import pytest

from typelead.legendas import Palavra
from typelead.transcricao import (
    TAXA,
    FalhaNaTranscricao,
    Marca,
    Relogio,
    ajustar_bordas,
    carregar_modelo,
    dividir_em_blocos,
    no_tempo_do_video,
    regioes_com_voz,
    transcrever,
)


def marcas(*pares):
    return [Marca(gravado, video) for gravado, video in pares]


def andando(inicio, fim, video, passo=0.2):
    """Marcas de um vídeo que anda junto com a gravação."""
    quantidade = round((fim - inicio) / passo)
    return [Marca(inicio + i * passo, video + i * passo) for i in range(quantidade + 1)]


# O relógio


def test_o_video_que_anda_junto_so_tem_um_deslocamento():
    relogio = Relogio(andando(0.5, 10, video=60))
    assert relogio.para_o_video(3) == pytest.approx(62.5)


def test_depois_de_uma_pausa_o_tempo_do_video_continua_certo():
    relogio = Relogio(andando(0, 4, video=0) + andando(9, 14, video=4))
    assert relogio.para_o_video(2) == pytest.approx(2)
    assert relogio.para_o_video(6) is None
    assert relogio.para_o_video(10) == pytest.approx(5)


def test_o_que_se_ouve_com_o_video_parado_e_descartado():
    """Um anúncio toca som, mas o vídeo não anda."""
    parado = [Marca(4 + i * 0.2, 4) for i in range(1, 50)]
    relogio = Relogio(andando(0, 4, video=0) + parado + andando(14, 18, video=4))
    palavras = [Palavra("fala", 1, 1.4), Palavra("anúncio", 8, 8.5), Palavra("volta", 15, 15.5)]
    assert [(p.texto, round(p.inicio, 1)) for p in no_tempo_do_video(palavras, relogio)] == [("fala", 1), ("volta", 5)]


def test_pulo_para_a_frente_nao_inventa_tempo():
    relogio = Relogio(andando(0, 4, video=0) + andando(4.2, 8, video=100))
    assert relogio.para_o_video(4.1) is None
    assert relogio.para_o_video(6) == pytest.approx(101.8)


def test_um_pouco_alem_das_pontas_vale_o_trecho_vizinho():
    relogio = Relogio(andando(1, 5, video=10))
    assert relogio.para_o_video(0.8) == pytest.approx(9.8)
    assert relogio.para_o_video(5.3) == pytest.approx(14.3)
    assert relogio.para_o_video(0.2) is None
    assert relogio.para_o_video(9) is None


def test_o_tempo_do_video_nunca_e_negativo():
    assert Relogio(andando(0.4, 5, video=0)).para_o_video(0) == 0


def test_a_ordem_das_marcas_nao_importa():
    assert Relogio(reversed(andando(0, 4, video=7))).para_o_video(1) == pytest.approx(8)


@pytest.mark.parametrize("poucas", [[], marcas((0, 0))])
def test_sem_marcas_nao_ha_relogio(poucas):
    with pytest.raises(FalhaNaTranscricao, match="andamento"):
        Relogio(poucas)


# As bordas das palavras


def som(*trechos):
    """Monta um som a partir de (segundos, volume)."""
    partes = []
    for segundos, volume in trechos:
        t = np.arange(round(segundos * TAXA)) / TAXA
        partes.append(volume * np.sin(2 * np.pi * 200 * t))
    return np.concatenate(partes).astype(np.float32)


def test_o_comeco_adiantado_encosta_no_som():
    (palavra,) = ajustar_bordas([Palavra("kettle", 0.2, 1.4)], som((1, 0), (0.5, 0.3), (1, 0)))
    assert palavra.inicio == pytest.approx(0.94, abs=0.02)


def test_o_fim_adiantado_vai_ate_o_som_acabar():
    (palavra,) = ajustar_bordas([Palavra("kettle", 1, 1.3)], som((1, 0), (0.5, 0.3), (1, 0)))
    assert palavra.fim == pytest.approx(1.55, abs=0.02)


def test_o_fim_nao_invade_a_palavra_seguinte():
    palavras = ajustar_bordas([Palavra("a", 1, 1.2), Palavra("b", 1.3, 1.5)], som((1, 0), (0.6, 0.3), (1, 0)))
    assert palavras[0].fim <= palavras[1].inicio


def test_com_musica_continua_as_palavras_ficam_perto_de_onde_vieram():
    (palavra,) = ajustar_bordas([Palavra("kettle", 1, 1.5)], som((4, 0.3)))
    assert palavra.inicio == 1
    assert 1.5 <= palavra.fim <= 1.75


def test_bordas_de_um_som_vazio_nao_mudam():
    palavras = [Palavra("a", 0, 1)]
    assert ajustar_bordas(palavras, np.zeros(0, dtype=np.float32)) == palavras


def test_palavra_alem_do_fim_do_som_nao_quebra():
    (palavra,) = ajustar_bordas([Palavra("a", 5, 6)], som((1, 0.3)))
    assert palavra.fim > palavra.inicio


# As regiões e os blocos


def test_pausa_longa_separa_regioes_e_curta_nao():
    assert regioes_com_voz([(20, 30), (33, 50), (70, 80)], 90) == [(19, 51), (69, 81)]


def test_a_folga_nao_passa_das_pontas():
    assert regioes_com_voz([(0.2, 9.8)], 10) == [(0, 10)]


def test_com_pouca_voz_detectada_vai_tudo_porque_pode_ser_canto():
    assert regioes_com_voz([(10, 11)], 100) == [(0, 100)]
    assert regioes_com_voz([], 100) == [(0, 100)]


def test_o_bloco_e_cortado_no_silencio():
    amostras = som((2.5, 0.3), (0.5, 0), (2, 0.3))
    (primeiro, segundo) = dividir_em_blocos(amostras, segundos=4)
    assert primeiro[0] == 0 and segundo == (primeiro[1], len(amostras))
    assert 2.5 * TAXA <= primeiro[1] <= 3 * TAXA


def test_audio_curto_fica_em_um_bloco_so():
    assert dividir_em_blocos(som((1, 0.3)), segundos=4) == [(0, TAXA)]


# A transcrição


class Modelo:
    """Ocupa o lugar do Whisper."""

    def __init__(self, *segmentos, idioma=("en", 0.99), erro=None):
        self.segmentos, self.idioma, self.erro = segmentos, idioma, erro
        self.opcoes = []

    def detect_language(self, amostras, **_):
        return (*self.idioma, [])

    def transcribe(self, amostras, **opcoes):
        self.opcoes.append(opcoes)
        if self.erro:
            raise self.erro
        return iter(self.segmentos), None


def segmento(*palavras, confianca=-0.2):
    ws = [SimpleNamespace(word=f" {texto}", start=a, end=b) for texto, a, b in palavras]
    return SimpleNamespace(words=ws, end=palavras[-1][2] if palavras else 0, avg_logprob=confianca)


TUDO = [(0.0, 10.0)]


def executar(modelo, vozes=TUDO, amostras=None, relogio=None, **outros):
    amostras = som((10, 0.3)) if amostras is None else amostras
    relogio = relogio or Relogio(andando(0, 10, video=100))
    return transcrever(amostras, modelo, relogio, achar_vozes=lambda _: vozes, **outros)


def test_devolve_as_falas_no_tempo_do_video():
    falas = executar(Modelo(segmento(("The", 1, 1.2), ("kettle.", 1.2, 1.8)), segmento(("Right.", 3, 3.5))))
    assert [fala.texto for fala in falas] == ["The kettle.", "Right."]
    assert falas[0].inicio == pytest.approx(101)
    assert [p.texto for p in falas[0].palavras] == ["The", "kettle."]


def test_pede_o_tempo_por_palavra_em_ingles_com_o_texto_anterior():
    modelo = Modelo(segmento(("Right.", 3, 3.5)))
    executar(modelo)
    opcoes = modelo.opcoes[0]
    assert opcoes["language"] == "en" and opcoes["word_timestamps"] and opcoes["condition_on_previous_text"]


def test_avisa_o_andamento():
    avisos = []
    executar(Modelo(segmento(("a", 1, 2)), segmento(("b", 3, 5))), ao_avancar=avisos.append)
    assert avisos == [pytest.approx(0.2), pytest.approx(0.5)]


def test_frase_curta_onde_nao_ha_voz_e_descartada():
    modelo = Modelo(segmento(("Thank", 7, 7.2), ("you.", 7.2, 7.5)), segmento(("Right.", 1, 1.5)))
    assert [fala.texto for fala in executar(modelo, vozes=[(0, 5)])] == ["Right."]


def test_frase_longa_e_segura_fica_mesmo_sem_voz_detectada():
    canto = segmento(*[(palavra, 6 + i * 0.3, 6.3 + i * 0.3) for i, palavra in enumerate("la la over the hills".split())])
    assert len(executar(Modelo(canto), vozes=[(0, 5)])) == 1


def test_frase_longa_e_insegura_onde_nao_ha_voz_e_descartada():
    ruim = segmento(*[(palavra, 6 + i * 0.3, 6.3 + i * 0.3) for i, palavra in enumerate("a b c d e".split())], confianca=-1.2)
    with pytest.raises(FalhaNaTranscricao, match="Não encontrei fala"):
        executar(Modelo(ruim), vozes=[(0, 5)])


def test_cada_regiao_e_transcrita_com_o_proprio_deslocamento():
    falas = executar(
        Modelo(segmento(("Right.", 1.5, 2))),
        vozes=[(1, 5), (20, 28)],
        amostras=som((30, 0.3)),
        relogio=Relogio(andando(0, 30, video=0)),
    )
    assert [round(fala.inicio, 1) for fala in falas] == [1.5, 20.5]


@pytest.mark.parametrize("amostras", [np.zeros(TAXA * 5, dtype=np.float32), np.zeros(0, dtype=np.float32)])
def test_gravacao_muda(amostras):
    with pytest.raises(FalhaNaTranscricao, match="muda"):
        executar(Modelo(), amostras=amostras)


def test_fala_em_outro_idioma_e_avisada():
    with pytest.raises(FalhaNaTranscricao, match="pt"):
        executar(Modelo(segmento(("Oi", 1, 2)), idioma=("pt", 0.95)))


def test_duvida_sobre_o_idioma_nao_impede():
    assert executar(Modelo(segmento(("Hi", 1, 2)), idioma=("cy", 0.5)))


def test_sem_nenhuma_palavra():
    with pytest.raises(FalhaNaTranscricao, match="Não encontrei fala"):
        executar(Modelo(segmento(), segmento(("...", 1, 2))))


def test_memoria_cheia_vira_mensagem():
    with pytest.raises(FalhaNaTranscricao, match="parou"):
        executar(Modelo(erro=RuntimeError("CUDA out of memory")))


# A escolha do dispositivo


def test_usa_a_placa_quando_ela_funciona():
    criados = []
    modelo, dispositivo = carregar_modelo(lambda nome, disp: criados.append((nome, disp)) or Modelo(), lambda: True)
    assert dispositivo == "cuda" and criados == [("large-v3-turbo", "cuda")]


def test_sem_placa_usa_o_processador():
    assert carregar_modelo(lambda nome, disp: Modelo(), lambda: False)[1] == "cpu"


def test_placa_que_falha_no_calculo_cai_para_o_processador():
    def criar(nome, dispositivo):
        return Modelo(erro=RuntimeError("cublas64_12.dll") if dispositivo == "cuda" else None)

    assert carregar_modelo(criar, lambda: True)[1] == "cpu"


def test_sem_internet_na_primeira_vez_explica_o_download():
    def criar(nome, dispositivo):
        raise OSError("sem rede")

    with pytest.raises(FalhaNaTranscricao, match="baixado"):
        carregar_modelo(criar, lambda: False)
