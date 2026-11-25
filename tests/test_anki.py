from typelead.anki import CABECALHO, exportar

PALAVRA = {
    "forma": "kettle",
    "esperada": "kettle,",
    "motivo": "escuta",
    "texto": "The kettle, please.",
    "traducao": "A chaleira, por favor.",
    "video_id": "abcdefghijk",
    "titulo": "Chá",
    "inicio": 12.9,
}


def campos(**mudancas):
    linhas = exportar([PALAVRA | mudancas]).splitlines()
    assert linhas[: len(CABECALHO)] == list(CABECALHO)
    (linha,) = linhas[len(CABECALHO) :]
    partes = linha.split("\t")
    assert len(partes) == 4
    return partes


def test_sem_palavras_so_o_cabecalho():
    assert exportar([]).splitlines() == list(CABECALHO)


def test_a_frente_tem_a_lacuna_e_o_link_e_nao_entrega_a_palavra():
    _, frente, _, _ = campos()
    assert frente.startswith("The ••••••, please.")
    assert 'href="https://youtu.be/abcdefghijk?t=12"' in frente
    assert "kettle" not in frente
    # A tradução também entregaria.
    assert "chaleira" not in frente


def test_o_verso_tem_a_palavra_a_fala_a_traducao_e_o_video():
    _, _, verso, _ = campos()
    assert verso.startswith("<b>kettle</b>")
    assert "The <b>kettle</b>, please." in verso
    assert "A chaleira, por favor." in verso and "Chá" in verso


def test_sem_traducao():
    assert "<i>" not in campos(traducao=None)[2]


def test_identificador_fixo_e_etiquetas():
    guid, _, _, etiquetas = campos()
    assert guid == "typelead-kettle" == campos(texto="A kettle.", esperada="kettle.")[0]
    assert etiquetas == "typelead typelead::escuta"


def test_a_palavra_repetida_some_em_todos_os_lugares():
    assert campos(texto="Kettle or kettle, kettles.")[1].startswith("•••••• or ••••••, kettles.")


def test_apostrofo_e_hifen():
    assert campos(forma="don't", esperada="don’t", texto="I don’t know.")[1].startswith("I •••’• know.")
    assert campos(forma="wellknown", esperada="well-known", texto="A well-known fact.")[1].startswith("A ••••-••••• fact.")
    # A palavra dentro de uma contração é outra palavra.
    assert campos(forma="i", esperada="I", texto="I'm what I am.")[1].startswith("I&#x27;m what • am.")


def test_texto_de_fora_nao_vira_html_nem_quebra_o_arquivo():
    _, frente, verso, _ = campos(texto='<b>"Kettle"</b>\t& tea\nnow', titulo="<script>", esperada='"Kettle"')
    assert frente.startswith("&lt;b&gt;&quot;••••••&quot;&lt;/b&gt; &amp; tea now")
    assert "<script>" not in verso and "&lt;script&gt;" in verso


def test_palavra_que_nao_esta_na_fala():
    assert campos(esperada="—")[1].startswith("The kettle, please.")
