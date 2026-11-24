import pytest

from typelead.links import LinkInvalido, Video, reconhecer

ID = "aqz-KE-bpKQ"


@pytest.mark.parametrize(
    "link",
    [
        # Vídeo comum
        f"https://www.youtube.com/watch?v={ID}",
        f"http://youtube.com/watch?v={ID}",
        f"https://m.youtube.com/watch?v={ID}",
        f"https://www.youtube.com/watch?app=desktop&v={ID}",
        f"https://www.youtube.com/watch/?v={ID}",
        f"https://www.youtube.com/watch/{ID}",
        # Dentro de uma playlist ou de um mix
        f"https://www.youtube.com/watch?v={ID}&list=PL1234567890&index=3",
        f"https://www.youtube.com/watch?list=RD{ID}&v={ID}&start_radio=1",
        # Link curto
        f"https://youtu.be/{ID}",
        f"https://youtu.be/{ID}?si=AbCdEfGhIjKlMnOp",
        f"https://youtu.be/{ID}/",
        f"https://youtu.be/{ID}&feature=share",
        f"https://youtu.be/watch?v={ID}",
        # Shorts, lives e player incorporado
        f"https://www.youtube.com/shorts/{ID}",
        f"https://youtube.com/shorts/{ID}?feature=share",
        f"https://www.youtube.com/live/{ID}?si=AbCdEfGhIjKlMnOp",
        f"https://www.youtube.com/embed/{ID}?rel=0",
        f"https://www.youtube-nocookie.com/embed/{ID}",
        f"https://www.youtube.com/v/{ID}?version=3",
        f"https://www.youtube.com/e/{ID}",
        # YouTube Music
        f"https://music.youtube.com/watch?v={ID}&si=AbCdEfGhIjKlMnOp",
        # YouTube Kids
        f"https://www.youtubekids.com/watch?v={ID}",
        # Link dentro de outro
        f"https://www.youtube.com/attribution_link?a=x&u=%2Fwatch%3Fv%3D{ID}%26feature%3Dshare",
        f"https://consent.youtube.com/?continue=https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3D{ID}&gl=BR",
        f"https://www.google.com/url?sa=t&url=https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3D{ID}",
        f"https://www.google.com/url?q=https://youtu.be/{ID}",
        # Jeitos de colar
        f"youtube.com/watch?v={ID}",
        f"youtu.be/{ID}",
        f"//www.youtube.com/watch?v={ID}",
        f"  https://youtu.be/{ID}\n",
        f"<https://youtu.be/{ID}>",
        f'"https://youtu.be/{ID}"',
        f"\u200bhttps://youtu.be/{ID}\u200e",
        f"\ufeffhttps://youtu.be/{ID}",
        f"HTTPS://WWW.YouTube.COM/watch?v={ID}",
        f"https://www.youtube.com./watch?v={ID}",
        f"https://www.youtube.com:443/watch?v={ID}",
        f"https://www.youtube.com/watch?list=PL123&amp;v={ID}",
    ],
)
def test_todos_os_formatos_levam_ao_mesmo_video(link):
    assert reconhecer(link).id == ID


def test_o_link_devolvido_e_sempre_o_mesmo():
    assert reconhecer(f"youtu.be/{ID}?t=9").link == f"https://www.youtube.com/watch?v={ID}"


def test_maiusculas_do_identificador_sao_mantidas():
    assert reconhecer("https://youtu.be/AbCdEfGhIjK").id == "AbCdEfGhIjK"


@pytest.mark.parametrize(
    ("final", "segundos"),
    [
        ("?t=90", 90),
        ("?t=90s", 90),
        ("?t=1m30s", 90),
        ("?t=1h2m3s", 3723),
        ("?t=2h", 7200),
        ("?t=1M30S", 90),
        ("?t=90.7", 90),
        ("?start=45", 45),
        ("?time_continue=12", 12),
        ("#t=1m", 60),
        ("&t=30", 30),
        # Sem tempo, ou com um que não dá para entender
        ("", 0),
        ("?t=", 0),
        ("?t=abc", 0),
        ("?t=-5", 0),
        ("?t=" + "9" * 5000, 0),
        ("?t=٣", 0),
        ("?si=abc#comentarios", 0),
    ],
)
def test_tempo_inicial(final, segundos):
    assert reconhecer(f"https://youtu.be/{ID}{final}") == Video(ID, segundos)


def test_tempo_ilegivel_nao_esconde_outro_legivel():
    assert reconhecer(f"https://www.youtube.com/watch?v={ID}&t=abc&start=20").inicio == 20


def test_o_tempo_de_um_link_embrulhado_e_mantido():
    link = f"https://www.google.com/url?q=https%3A%2F%2Fyoutu.be%2F{ID}%3Ft%3D15"
    assert reconhecer(link).inicio == 15


@pytest.mark.parametrize(
    ("link", "motivo"),
    [
        ("", "vazio"),
        ("\u200b", "vazio"),
        ("   ", "vazio"),
        ('""', "vazio"),
        (f"veja isto https://youtu.be/{ID}", "sem outro texto"),
        (f"https://youtu.be/{ID}\nhttps://youtu.be/{ID}", "sem outro texto"),
        ("https://[youtube.com/watch", "malformado"),
        # O link de dentro também pode estar quebrado
        ("https://www.youtube.com/attribution_link?u=//[", "malformado"),
        ("https://www.google.com/url?q=http://[x", "malformado"),
        (f"ftp://youtube.com/watch?v={ID}", "http://"),
        (f"file:///watch?v={ID}", "http://"),
        # Páginas do YouTube que não são vídeos
        ("https://www.youtube.com/", "não é de um vídeo"),
        ("https://www.youtube.com/watch", "não é de um vídeo"),
        ("https://www.youtube.com/shorts/", "não é de um vídeo"),
        ("https://www.youtube.com/feed/trending", "não é de um vídeo"),
        ("https://youtu.be/", "não é de um vídeo"),
        ("https://www.youtube.com/playlist?list=PL123", "playlist"),
        ("https://www.youtube.com/watch?list=PL123", "playlist"),
        ("https://youtu.be/playlist?list=PL123", "playlist"),
        ("https://youtu.be/watch", "não é de um vídeo"),
        ("https://www.youtube.com/@blender", "canal"),
        ("https://www.youtube.com/@blender/videos", "canal"),
        ("https://www.youtube.com/channel/UC1234567890", "canal"),
        ("https://www.youtube.com/c/blender", "canal"),
        ("https://www.youtube.com/results?search_query=bunny", "busca"),
        ("https://www.youtube.com/clip/UgkxAbCdEf", "clipe"),
        # Têm 11 caracteres, como um identificador, mas não são
        ("https://www.youtube.com/embed/videoseries?list=PL123", "playlist"),
        ("https://www.youtube.com/embed/live_stream?channel=UC123", "canal"),
        # Identificador errado
        ("https://www.youtube.com/watch?v=curto", "identificador"),
        (f"https://www.youtube.com/watch?v={ID}x", "identificador"),
        ("https://youtu.be/aqz-KE-bp*Q", "identificador"),
        ("https://youtu.be/ação-KE-bpK", "identificador"),
        # Outros sites, inclusive os que se disfarçam
        (f"https://vimeo.com/{ID}", "não é do YouTube"),
        (f"https://youtube.com.exemplo.com/watch?v={ID}", "não é do YouTube"),
        (f"https://exemplo-youtube.com/watch?v={ID}", "não é do YouTube"),
        (f"https://youtube.com@exemplo.com/watch?v={ID}", "não é do YouTube"),
        (f"https://exemplo.com/?u=https://youtu.be/{ID}", "não é do YouTube"),
        (f"https://www.google.com/url?q=https://exemplo.com/watch?v={ID}", "não é do YouTube"),
        ("https://www.google.com/search?q=youtube", "não é do YouTube"),
        ("javascript:alert(1)", "não é do YouTube"),
        # Uma palavra de 11 letras não vira vídeo por acaso
        ("programming", "não é do YouTube"),
    ],
)
def test_explica_por_que_o_link_nao_serve(link, motivo):
    with pytest.raises(LinkInvalido, match=motivo):
        reconhecer(link)


def test_embrulho_dentro_de_embrulho_nao_entra_em_laco():
    link = f"https://youtu.be/{ID}"
    for _ in range(3):
        link = f"https://www.google.com/url?q={link.replace('&', '%26')}"
    with pytest.raises(LinkInvalido):
        reconhecer(link)
