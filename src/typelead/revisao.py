"""Quando cada palavra volta. O algoritmo é o FSRS, da biblioteca fsrs."""

from datetime import datetime

from fsrs import Card, Rating, Scheduler

ERROU = int(Rating.Again)
DIFICIL = int(Rating.Hard)
BOM = int(Rating.Good)

# Ouvir até aqui ainda é acertar sem esforço. A primeira vez é automática.
OUVIR_SEM_ESFORCO = 3

# Os passos de minutos do FSRS servem a quem estuda o dia todo; aqui, o menor
# intervalo é de um dia. Sem o acaso, o mesmo histórico dá sempre a mesma data.
AGENDADOR = Scheduler(learning_steps=(), relearning_steps=(), enable_fuzzing=False)


def dar_nota(acertou: bool, quase: bool, repeticoes: int, velocidade: float) -> int:
    """A nota sai do que a pessoa fez. Perguntar a ela seria mais um passo por palavra.

    `quase`: acertou na segunda chance, depois de errar uma letra.
    """
    if not acertou:
        return ERROU
    com_esforco = quase or repeticoes > OUVIR_SEM_ESFORCO or velocidade < 1
    return DIFICIL if com_esforco else BOM


def agendar(estado: str | None, nota: int, quando: datetime) -> tuple[str, datetime]:
    """O novo estado do cartão e quando ele vence. Sem estado, é a primeira revisão."""
    cartao = Card.from_json(estado) if estado else Card(due=quando)
    # Um relógio atrasado não pode revisar antes da última vez.
    if cartao.last_review is not None:
        quando = max(quando, cartao.last_review)
    cartao, _ = AGENDADOR.review_card(cartao, Rating(nota), quando)
    return cartao.to_json(), cartao.due
