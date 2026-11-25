import sqlite3
import threading
from datetime import date, timedelta

import pytest

from typelead import banco as modulo
from typelead.diagnostico import DIGITACAO, ESCUTA, INDEFINIDO, VOCABULARIO, Desistencia
from typelead.banco import Banco, FalhaNoBanco, Item, Tentativa, caminho_padrao, dias_seguidos
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


def test_traducao_guardada(banco):
    salvar(banco)
    primeira = ids(banco)[0]
    assert banco.fala(primeira) == {"id": primeira, "texto": "The kettle.", "traducao": None}
    banco.guardar_traducao(primeira, "A chaleira.")
    assert banco.fala(primeira)["traducao"] == "A chaleira."
    assert banco.abrir_video("abcdefghijk")["falas"][0]["traducao"] == "A chaleira."
    assert banco.fala(99) is None


def test_tentativa_com_traducao(banco):
    salvar(banco)
    banco.salvar_tentativa(tentativa(ids(banco)[0], "certa", traduziu=True))
    assert banco._conexao.execute("SELECT traduziu FROM tentativas").fetchone()[0] == 1


def test_cada_migracao_preserva_os_dados(tmp_path, monkeypatch):
    """Um banco da primeira versão, com dados, chega à atual."""
    caminho = tmp_path / "typelead.db"
    todas = modulo.MIGRACOES
    monkeypatch.setattr(modulo, "MIGRACOES", todas[:1])
    antigo = Banco(caminho)
    antigo._conexao.executescript(
        """
        INSERT INTO videos VALUES ('abcdefghijk', 'Chá', 'Canal', 10, 1, 'autor', 1, 0, '2026-01-01');
        INSERT INTO falas VALUES (1, 'abcdefghijk', 1, 0, 0, 2, 'The kettle.', '[]');
        INSERT INTO tentativas VALUES (1, 1, 'r', 'oculto', 'enter', 'the kettle', 1, 0, 1, 1, 3, '2026-01-01');
        INSERT INTO itens VALUES (1, 1, 'certa', 0, 'The', 'the', 'the');
        """
    )
    antigo.fechar()
    monkeypatch.setattr(modulo, "MIGRACOES", todas)
    novo = Banco(caminho)
    video = novo.abrir_video("abcdefghijk")
    assert (video["titulo"], video["falas"][0]["acertada"], video["falas"][0]["traducao"]) == ("Chá", True, None)
    novo.fechar()


# Diagnóstico


def responder(banco, fala, *itens, rodada="r1", **mudancas):
    banco.salvar_tentativa(tentativa(fala, rodada=rodada, itens=tuple(Item(*item) for item in itens), **mudancas))
    return banco.diagnosticar(rodada)


def test_o_diagnostico_muda_com_o_que_vem_depois(banco):
    salvar(banco)
    fala = ids(banco)[0]
    errado = responder(banco, fala, ("certa", 0, "The", "the"), ("trocada", 1, "kettle.", "castle"), repeticoes=1)
    assert [(e["esperada"], e["digitada"], e["diagnostico"]) for e in errado] == [("kettle.", "castle", None)]
    certo = responder(banco, fala, ("certa", 0, "The", "the"), ("certa", 1, "kettle.", "kettle"), repeticoes=3)
    assert [e["diagnostico"] for e in certo] == [ESCUTA]


def test_palavra_acertada_em_outra_rodada_e_conhecida(banco):
    salvar(banco)
    fala = ids(banco)[0]
    responder(banco, fala, ("certa", 1, "Kettle!", "kettle"), rodada="antes")
    erros = responder(banco, fala, ("trocada", 1, "kettle.", "ketle"), rodada="depois")
    assert [e["diagnostico"] for e in erros] == [DIGITACAO]


def test_palavra_acertada_com_ajuda_nao_e_conhecida(banco):
    salvar(banco)
    fala = ids(banco)[0]
    responder(banco, fala, ("certa", 1, "kettle.", "kettle"), rodada="antes", com_ajuda=True)
    erros = responder(banco, fala, ("trocada", 1, "kettle.", "ketle"), rodada="depois")
    assert [e["diagnostico"] for e in erros] == [None]


def test_desistiu(banco):
    salvar(banco)
    fala = ids(banco)[0]
    responder(banco, fala, ("faltou", 1, "kettle.", ""))
    banco.desistir("r1", Desistencia(4, 0.5, False))
    # Vale a primeira vez.
    banco.desistir("r1", Desistencia(1, 1.0, False))
    assert [e["diagnostico"] for e in banco.diagnosticar("r1")] == [VOCABULARIO]


def test_desistir_sem_ter_tentado_nao_registra_nada(banco):
    banco.desistir("r1", Desistencia(1, 1.0, False))
    assert banco.diagnosticar("r1") == []
    assert banco._conexao.execute("SELECT COUNT(*) FROM desistencias").fetchone()[0] == 0


def test_contracao_vale_pelas_palavras_que_abre(banco):
    salvar(banco)
    fala = ids(banco)[0]
    responder(banco, fala, ("faltou", 2, "not", ""), repeticoes=1)
    erros = responder(banco, fala, ("certa", 1, "do not", "don't"), repeticoes=2)
    assert [e["diagnostico"] for e in erros] == [ESCUTA]


def test_um_erro_por_palavra_o_ultimo_na_ordem_da_fala(banco):
    salvar(banco)
    fala = ids(banco)[0]
    responder(banco, fala, ("trocada", 0, "The", "a"), ("trocada", 1, "kettle.", "castle"))
    erros = responder(banco, fala, ("trocada", 1, "kettle.", "cattle"), ("sobrou", 2, "", "x"), ("certa", 0, "The", "the"))
    assert [(e["posicao"], e["digitada"], e["diagnostico"]) for e in erros] == [(0, "a", INDEFINIDO), (1, "cattle", None)]


def test_a_pessoa_discorda(banco):
    salvar(banco)
    erro = responder(banco, ids(banco)[0], ("certa", 0, "The", "the"), ("faltou", 1, "kettle.", ""))[0]
    assert banco.corrigir_diagnostico(erro["id"], VOCABULARIO)
    assert banco.diagnosticar("r1")[0]["corrigido"] == VOCABULARIO
    assert not banco.corrigir_diagnostico(erro["id"] - 1, VOCABULARIO)
    assert not banco.corrigir_diagnostico(999, VOCABULARIO)


# O resumo

HOJE = date(2026, 3, 10)


def antes(*quantos):
    return {HOJE - timedelta(days=n) for n in quantos}


@pytest.mark.parametrize(
    ("dias", "esperado"),
    [(antes(), 0), (antes(0), 1), (antes(0, 1, 2), 3), (antes(1, 2), 2), (antes(0, 2, 3), 1), (antes(2, 3), 0)],
)
def test_dias_seguidos(dias, esperado):
    assert dias_seguidos(dias, HOJE) == esperado


def test_resumo_do_dia(banco):
    salvar(banco)
    primeira, segunda = ids(banco)
    for fala, opcoes in [(primeira, {}), (primeira, {}), (segunda, {"com_ajuda": True})]:
        banco.salvar_tentativa(tentativa(fala, "certa", **opcoes))
    resumo = banco.resumo()
    assert (resumo["hoje"], resumo["dias_seguidos"]) == (1, 1)
    assert [dia["certas"] for dia in resumo["semana"]] == [0, 0, 0, 0, 0, 0, 1]
    # Dez dias depois, aquilo já saiu da semana e da sequência.
    assert banco.resumo(date.today() + timedelta(days=10))["semana"][0]["certas"] == 0


def test_resumo_vazio(banco):
    resumo = banco.resumo(HOJE)
    assert (resumo["hoje"], resumo["dias_seguidos"], len(resumo["semana"])) == (0, 0, 7)
    assert resumo["semana"][-1]["dia"] == "2026-03-10"
