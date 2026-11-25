"""Como a pessoa vai com cada palavra e quanto vale a pena escondê-la."""

from .alinhamento import normalizar

NOVA = "nova"
ERRANDO = "errando"
APRENDENDO = "aprendendo"
CONHECIDA = "conhecida"
# A pessoa disse que já sabe. Vale mais que o histórico.
SABIDA = "sabida"

# Quantos acertos seguidos, depois do último erro, para dar a palavra por conhecida.
ACERTOS_PARA_CONHECER = 2

# A frequência que cada nível treina, na escala Zipf: 3 é uma vez por milhão de
# palavras, e cada ponto a mais é dez vezes mais comum. "the" tem 7,7 e
# "ubiquitous", 3,4. São palpites, à espera de uso real.
ALVOS = {"iniciante": 5.3, "intermediario": 4.5, "avancado": 3.6}
NIVEIS = tuple(ALVOS)
# A esta distância do alvo, a frequência já não pesa a favor.
ALCANCE = 1.5

# Daqui para cima ("go", "and", "want"), deixar em branco diz mais da fala inteira que
# da palavra: quem desiste de uma fala não precisa estudar "and".
COMUM_DEMAIS = 5.5

PESO_DA_SITUACAO = {ERRANDO: 5.0, APRENDENDO: 2.5, NOVA: 1.0, CONHECIDA: 0.4, SABIDA: 0.05}
# O que a lista não conhece costuma ser nome próprio ou erro da legenda.
PESO_FORA_DA_LISTA = 0.5


def situacao(erros: int, acertos_seguidos: int, sabida: bool = False) -> str:
    """`acertos_seguidos`: os que vieram depois do último erro."""
    if sabida:
        return SABIDA
    if erros == 0:
        return CONHECIDA if acertos_seguidos else NOVA
    if acertos_seguidos == 0:
        return ERRANDO
    return CONHECIDA if acertos_seguidos >= ACERTOS_PARA_CONHECER else APRENDENDO


def frequencia(palavra: str) -> float:
    """Na escala Zipf; zero se a lista não conhece a palavra."""
    # Importado aqui porque carregar a lista leva quase um segundo.
    from wordfreq import zipf_frequency

    # A grafia, e não a forma: "well-known" sem o hífen seria uma palavra rara.
    return zipf_frequency(palavra.replace("’", "'"), "en")


def peso(palavra: str, nivel: str, como_vai: str) -> float:
    """A chance relativa de ser escondida nas lacunas. Nunca zero."""
    zipf = frequencia(palavra)
    if zipf == 0:
        da_frequencia = PESO_FORA_DA_LISTA
    else:
        # De 1, longe do alvo, a 4, em cima dele.
        da_frequencia = 1 + 3 * max(0.0, 1 - abs(zipf - ALVOS[nivel]) / ALCANCE)
    return da_frequencia * PESO_DA_SITUACAO[como_vai]


def formas(palavras: list[str]) -> list[str]:
    """A forma com que o banco guarda cada palavra."""
    return [normalizar(palavra) for palavra in palavras]
