import sqlite3
import threading

import pytest

from typelead import banco as modulo
from typelead.banco import Banco, FalhaNoBanco, Item, Tentativa, caminho_padrao
from typelead.legendas import Fala, Palavra

FALAS = [Fala(0, 2, "The kettle.", (Palavra("The", 0, 1), Palavra("kettle.", 1, 2))), Fala(2, 4, "Two cups.")]


@pytest.fixture
def banco():
    banco = Banco()
    yield banco
    banco.fechar()


def salvar(banco, identificador="abcdefghijk", falas=FALAS, titulo="Chá"):
    banco.salvar_video(identificador, titulo, "Canal", 10.0, True, "autor", falas)


def tentativa(fala_id, *tipos, **mudancas):
    itens = tuple(Item(tipo, i, f"Word{i},", "" if tipo == "faltou" else "x") for i, tipo in enumerate(tipos))
    dados = {
        "fala_id": fala_id,
        "rodada": "r1",
        "modo": "oculto",
        "corrigir": "enter",
        "texto": "x",
        "com_ajuda": False,
        "repeticoes": 2,
        "velocidade": 0.75,
        "duracao": 8.5,
        "itens": itens,
    }
    return Tentativa(**(dados | mudancas))


def ids(banco, identificador="abcdefghijk"):
    return [fala["id"] for fala in banco.abrir_video(identificador)["falas"]]


def test_video_que_nao_existe(banco):
    assert banco.abrir_video("abcdefghijk") is None


def test_guarda_e_abre(banco):
    salvar(banco)
    video = banco.abrir_video("abcdefghijk")
    assert (video["titulo"], video["origem"], video["posicao"], video["incorporavel"]) == ("Chá", "autor", 0, True)
    assert [(f["inicio"], f["fim"], f["texto"], f["acertada"]) for f in video["falas"]] == [
        (0, 2, "The kettle.", False),
        (2, 4, "Two cups.", False),
    ]


def test_o_tempo_das_palavras_fica_guardado(banco):
    salvar(banco)
    guardado = banco._conexao.execute("SELECT palavras FROM falas ORDER BY ordem").fetchall()
    assert [linha[0] for linha in guardado] == ['[["The", 0, 1], ["kettle.", 1, 2]]', "[]"]


def test_continua_de_onde_parou(banco):
    salvar(banco)
    assert banco.marcar_posicao("abcdefghijk", 1)
    assert banco.abrir_video("abcdefghijk")["posicao"] == 1
    assert not banco.marcar_posicao("outro", 1)


def test_fala_acertada_sem_ajuda(banco):
    salvar(banco)
    primeira, segunda = ids(banco)
    banco.salvar_tentativa(tentativa(primeira, "certa", "trocada"))
    banco.salvar_tentativa(tentativa(segunda, "certa", com_ajuda=True))
    assert [f["acertada"] for f in banco.abrir_video("abcdefghijk")["falas"]] == [False, False]
    banco.salvar_tentativa(tentativa(primeira, "certa", "certa"))
    assert [f["acertada"] for f in banco.abrir_video("abcdefghijk")["falas"]] == [True, False]


def test_tentativa_sem_palavra_nao_e_acerto(banco):
    assert not tentativa(1).acertou


def test_tentativa_e_itens_guardados(banco):
    salvar(banco)
    numero = banco.salvar_tentativa(tentativa(ids(banco)[0], "certa", "faltou"))
    linha = dict(banco._conexao.execute("SELECT * FROM tentativas WHERE id = ?", (numero,)).fetchone())
    assert (linha["acertou"], linha["repeticoes"], linha["velocidade"], linha["duracao"]) == (0, 2, 0.75, 8.5)
    itens = banco._conexao.execute("SELECT tipo, posicao, esperada, digitada, forma FROM itens").fetchall()
    assert [tuple(item) for item in itens] == [("certa", 0, "Word0,", "x", "word0"), ("faltou", 1, "Word1,", "", "word1")]


def test_tentativa_em_fala_que_nao_existe(banco):
    assert banco.salvar_tentativa(tentativa(99, "certa")) is None


def test_tentativa_com_item_invalido_nao_fica_pela_metade(banco):
    salvar(banco)
    with pytest.raises(sqlite3.IntegrityError):
        banco.salvar_tentativa(tentativa(ids(banco)[0], "certa", "inventado"))
    assert banco._conexao.execute("SELECT COUNT(*) FROM tentativas").fetchone()[0] == 0


def test_trocar_a_legenda_cria_outra_versao_e_preserva_as_tentativas(banco):
    salvar(banco)
    banco.salvar_tentativa(tentativa(ids(banco)[0], "certa"))
    banco.marcar_posicao("abcdefghijk", 1)
    salvar(banco, falas=[Fala(0, 4, "The kettle and two cups.")])
    video = banco.abrir_video("abcdefghijk")
    assert [f["texto"] for f in video["falas"]] == ["The kettle and two cups."]
    assert (video["posicao"], video["falas"][0]["acertada"]) == (0, False)
    assert banco._conexao.execute("SELECT COUNT(*) FROM tentativas").fetchone()[0] == 1


def test_recentes_do_mais_novo_ao_mais_antigo_com_o_andamento(banco):
    salvar(banco, "aaaaaaaaaaa", titulo="A")
    salvar(banco, "bbbbbbbbbbb", titulo="B")
    primeira = ids(banco, "aaaaaaaaaaa")[0]
    # Acertar a mesma fala duas vezes conta uma.
    banco.salvar_tentativa(tentativa(primeira, "certa"))
    banco.salvar_tentativa(tentativa(primeira, "certa"))
    recentes = banco.recentes()
    assert [(v["titulo"], v["acertadas"], v["total"]) for v in recentes] == [("A", 1, 2), ("B", 0, 2)]
    assert len(banco.recentes(1)) == 1


def test_o_arquivo_sobrevive_ao_fechamento(tmp_path):
    caminho = tmp_path / "pasta nova" / "typelead.db"
    primeiro = Banco(caminho)
    salvar(primeiro)
    primeiro.fechar()
    segundo = Banco(caminho)
    assert segundo.abrir_video("abcdefghijk")["titulo"] == "Chá"
    segundo.fechar()


def test_arquivo_que_nao_e_um_banco(tmp_path):
    caminho = tmp_path / "typelead.db"
    caminho.write_bytes(b"isto nao e um banco " * 100)
    with pytest.raises(FalhaNoBanco, match="Não foi possível abrir"):
        Banco(caminho)


def test_banco_de_uma_versao_mais_nova(tmp_path):
    caminho = tmp_path / "typelead.db"
    conexao = sqlite3.connect(caminho)
    conexao.execute("PRAGMA user_version = 999")
    conexao.close()
    with pytest.raises(FalhaNoBanco, match="mais nova"):
        Banco(caminho)


def test_migracao_que_falha_nao_deixa_nada_pela_metade(tmp_path, monkeypatch):
    caminho = tmp_path / "typelead.db"
    Banco(caminho).fechar()
    antes = len(modulo.MIGRACOES)
    monkeypatch.setattr(modulo, "MIGRACOES", (*modulo.MIGRACOES, "CREATE TABLE nova (a); CREATE TABLE videos (b)"))
    with pytest.raises(FalhaNoBanco):
        Banco(caminho)
    conexao = sqlite3.connect(caminho)
    assert conexao.execute("PRAGMA user_version").fetchone()[0] == antes
    assert conexao.execute("SELECT 1 FROM sqlite_master WHERE name = 'nova'").fetchone() is None
    conexao.close()


def test_varias_threads_ao_mesmo_tempo(banco):
    salvar(banco)
    fala = ids(banco)[0]
    threads = [threading.Thread(target=lambda: banco.salvar_tentativa(tentativa(fala, "certa"))) for _ in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert banco._conexao.execute("SELECT COUNT(*) FROM tentativas").fetchone()[0] == 20


def test_o_caminho_padrao_fica_nos_dados_da_pessoa(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert caminho_padrao() == tmp_path / "typelead" / "typelead.db"
