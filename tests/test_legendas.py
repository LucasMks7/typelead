import pytest

from typelead.legendas import LegendaInvalida, decodificar, ler_arquivo, ler_json3


def textos(falas):
    return [fala.texto for fala in falas]


def tempos(falas):
    return [(round(fala.inicio, 3), round(fala.fim, 3)) for fala in falas]


SRT = """1
00:00:01,000 --> 00:00:02,500
The kettle is on.

2
00:01:03,250 --> 00:01:05,000
Bring two cups
and a spoon.
"""


def test_srt():
    falas = ler_arquivo(SRT.encode())
    assert textos(falas) == ["The kettle is on.", "Bring two cups and a spoon."]
    assert tempos(falas) == [(1, 2.5), (63.25, 65)]
    assert falas[0].palavras == ()


@pytest.mark.parametrize("quebra", ["\r\n", "\r"])
def test_quebras_de_linha_de_outros_sistemas(quebra):
    assert ler_arquivo(SRT.replace("\n", quebra).encode()) == ler_arquivo(SRT.encode())


def test_srt_sem_linha_em_branco_entre_os_blocos():
    texto = SRT.replace("\n\n", "\n")
    assert textos(ler_arquivo(texto.encode())) == ["The kettle is on.", "Bring two cups and a spoon."]


def test_um_numero_falado_nao_e_confundido_com_o_numero_do_bloco():
    texto = "1\n00:00:01,000 --> 00:00:02,000\n42\n\n2\n00:00:03,000 --> 00:00:04,000\nRight.\n"
    assert textos(ler_arquivo(texto.encode())) == ["42", "Right."]


def test_vtt_com_cabecalho_notas_posicao_e_sem_horas():
    vtt = """WEBVTT - Title
Kind: captions

NOTE
this is not speech

STYLE
::cue { color: red }

intro
00:01.500 --> 00:03.000 align:start position:0%
<v Ana>The <i>kettle</i> &amp; the cups.</v>

01:00:00.000 --> 01:00:01.000
Later.
"""
    falas = ler_arquivo(vtt.encode())
    assert textos(falas) == ["The kettle & the cups.", "Later."]
    assert tempos(falas) == [(1.5, 3), (3600, 3601)]


def test_vtt_com_tempo_por_palavra():
    vtt = "WEBVTT\n\n00:01.000 --> 00:03.000\nthe<00:01.400><c> kettle</c><00:02.000><c> is</c>\n"
    (fala,) = ler_arquivo(vtt.encode())
    assert [(p.texto, round(p.inicio, 2)) for p in fala.palavras] == [("the", 1), ("kettle", 1.4), ("is", 2)]


def test_vtt_automatico_que_rola_na_tela_nao_repete_as_linhas():
    vtt = """WEBVTT

00:01.000 --> 00:02.000
the<00:01.400><c> kettle</c>

00:02.000 --> 00:02.010
the kettle

00:02.010 --> 00:03.000
the kettle
is<00:02.400><c> on</c>
"""
    assert textos(ler_arquivo(vtt.encode())) == ["the kettle", "is on"]


@pytest.mark.parametrize(
    ("bruto", "limpo"),
    [
        ("[Music] The kettle", "The kettle"),
        ("The kettle (APPLAUSE) is on", "The kettle is on"),
        ("♪ La la la ♪", "La la la"),
        ("ANA SMITH: The kettle", "The kettle"),
        ("Listen: the kettle", "Listen: the kettle"),
        ("{\\an8}The kettle", "The kettle"),
        ("The&nbsp;kettle", "The kettle"),
        ("2 < 3 and 5 > 4", "2 < 3 and 5 > 4"),
        ("An open [bracket", "An open [bracket"),
    ],
)
def test_tira_o_que_nao_se_fala(bruto, limpo):
    srt = f"1\n00:00:01,000 --> 00:00:02,000\n{bruto}\n"
    assert textos(ler_arquivo(srt.encode())) == [limpo]


@pytest.mark.parametrize("bruto", ["[Music]", "♪♪", "...", "- (laughs)", ">> [Music]"])
def test_bloco_sem_fala_some(bruto):
    srt = f"1\n00:00:01,000 --> 00:00:02,000\n{bruto}\n\n2\n00:00:03,000 --> 00:00:04,000\nHi.\n"
    assert textos(ler_arquivo(srt.encode())) == ["Hi."]


def test_duas_pessoas_no_mesmo_bloco_viram_duas_falas():
    srt = "1\n00:00:10,000 --> 00:00:12,000\n- Tea?\n- Yes!\n"
    falas = ler_arquivo(srt.encode())
    assert textos(falas) == ["Tea?", "Yes!"]
    assert tempos(falas) == [(10, 11), (11, 12)]
    assert [fala.troca for fala in falas] == [True, True]


def test_hifen_dentro_da_fala_nao_e_troca_de_pessoa():
    srt = "1\n00:00:10,000 --> 00:00:12,000\nA well-known cup - mine.\n"
    (fala,) = ler_arquivo(srt.encode())
    assert fala.texto == "A well-known cup - mine."
    assert not fala.troca


def test_fala_que_invade_a_seguinte_e_encurtada_e_a_ordem_e_corrigida():
    srt = "00:00:03,000 --> 00:00:05,000\nSecond.\n\n00:00:01,000 --> 00:00:04,000\nFirst.\n"
    falas = ler_arquivo(srt.encode())
    assert textos(falas) == ["First.", "Second."]
    assert tempos(falas) == [(1, 3), (3, 5)]


def test_falas_simultaneas_sao_juntadas():
    bloco = "00:00:01,000 --> 00:00:02,000\n{}\n\n"
    falas = ler_arquivo((bloco.format("Up here.") + bloco.format("Down there.")).encode())
    assert textos(falas) == ["Up here. Down there."]


@pytest.mark.parametrize(
    ("conteudo", "texto"),
    [
        ("café".encode("utf-8"), "café"),
        ("café".encode("utf-8-sig"), "café"),
        ("café".encode("cp1252"), "café"),
        ("café".encode("utf-16"), "café"),
    ],
)
def test_codificacoes(conteudo, texto):
    assert decodificar(conteudo) == texto


@pytest.mark.parametrize("conteudo", [b"", b"just text", b"WEBVTT\n\n", b"\x00\x01\x02\xff"])
def test_o_que_nao_e_legenda_e_recusado(conteudo):
    with pytest.raises(LegendaInvalida, match="nenhuma fala"):
        ler_arquivo(conteudo)


def test_arquivo_enorme_e_recusado():
    with pytest.raises(LegendaInvalida, match="grande demais"):
        ler_arquivo(b"a" * 5_000_001)


def test_json3_do_autor():
    dados = {
        "events": [
            {"tStartMs": 0, "dDurationMs": 100},
            {"tStartMs": 1000, "dDurationMs": 1500, "segs": [{"utf8": "The kettle\nis on."}]},
            {"tStartMs": 3000, "dDurationMs": 1000, "segs": [{"utf8": "[Music]"}]},
        ]
    }
    falas = ler_json3(dados)
    assert textos(falas) == ["The kettle is on."]
    assert tempos(falas) == [(1, 2.5)]


def automatica(*segs, inicio=1000, duracao=4000):
    return {"tStartMs": inicio, "dDurationMs": duracao, "segs": list(segs)}


def test_json3_automatico_traz_o_tempo_de_cada_palavra():
    dados = {
        "events": [
            automatica({"utf8": "the"}, {"utf8": " kettle", "tOffsetMs": 300}, {"utf8": " is", "tOffsetMs": 900}),
            {"tStartMs": 2500, "aAppend": 1, "segs": [{"utf8": "\n"}]},
            automatica({"utf8": "on"}, {"utf8": " now", "tOffsetMs": 200}, inicio=3000),
        ]
    }
    falas = ler_json3(dados)
    assert textos(falas) == ["the kettle is", "on now"]
    assert [(p.texto, round(p.inicio, 2), round(p.fim, 2)) for p in falas[0].palavras] == [
        ("the", 1, 1.3),
        ("kettle", 1.3, 1.9),
        # A última não se estende pelo silêncio até o fim do evento, em 5 s.
        ("is", 1.9, 2.37),
    ]


def test_json3_automatico_com_varias_palavras_no_mesmo_pedaco():
    dados = {"events": [automatica({"utf8": "the kettle"}, {"utf8": " is", "tOffsetMs": 600})]}
    (fala,) = ler_json3(dados)
    assert [(p.texto, round(p.inicio, 2)) for p in fala.palavras] == [("the", 1), ("kettle", 1.3), ("is", 1.6)]


def test_json3_automatico_tira_sons_ate_os_partidos_e_marca_a_troca_de_pessoa():
    dados = {
        "events": [
            automatica(
                {"utf8": "[ __"},
                {"utf8": " ]", "tOffsetMs": 100},
                {"utf8": " tea", "tOffsetMs": 300},
                {"utf8": " >>", "tOffsetMs": 600},
                {"utf8": " yes", "tOffsetMs": 900},
            )
        ]
    }
    falas = ler_json3(dados)
    assert [(fala.texto, fala.troca) for fala in falas] == [("tea", False), ("yes", True)]
    assert falas[1].inicio == pytest.approx(1.9)


@pytest.mark.parametrize(
    "dados", [{}, [], None, {"events": None}, {"events": [None]}, {"events": [{"segs": [{"utf8": "a"}]}]}]
)
def test_json3_com_outro_formato_avisa(dados):
    with pytest.raises(LegendaInvalida, match="formato"):
        ler_json3(dados)


def test_json3_sem_falas():
    with pytest.raises(LegendaInvalida, match="nenhuma fala"):
        ler_json3({"events": []})
