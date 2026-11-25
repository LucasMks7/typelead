// Uma fala em revisão, com as palavras vencidas escondidas. Puro, sem navegador.

import { distancia, separar } from "./correcao.js";
import { Lacunas } from "./lacunas.js";

/** A palavra como o banco a guarda; a mesma regra de `normalizar`, no Python. */
export function formaDe(texto) {
  return texto
    .toLowerCase()
    .replace(/’/g, "'")
    .replace(/[^\p{L}\p{N}_']/gu, "")
    .replace(/^'+|'+$/g, "");
}

// Em palavra curta, uma letra muda quase tudo: "cat" e "can".
const MINIMO_PARA_QUASE = 4;

function quase({ esperada, digitada }) {
  const certa = formaDe(esperada).replaceAll("'", "");
  return certa.length >= MINIMO_PARA_QUASE && distancia(certa, formaDe(digitada)) === 1;
}

export class Cartao {
  #formaDaPosicao = new Map();
  #quase = new Set();
  #tentou = false;
  #repeticoes = 0;
  #velocidade = 1;

  /** As lacunas para digitar. */
  resposta;
  /** null, "acertou" ou "errou". */
  resultado = null;

  /** `palavras`: as vencidas, cada uma com a `forma` e a `posicao` na fala. */
  constructor(texto, palavras) {
    const formas = new Set(palavras.map(({ forma }) => forma));
    separar(texto).forEach((palavra, i) => {
      // A palavra repetida na fala entregaria a resposta.
      const forma = formaDe(palavra.texto);
      if (formas.has(forma)) this.#formaDaPosicao.set(i, forma);
    });
    for (const { forma, posicao } of palavras) this.#formaDaPosicao.set(posicao, forma);
    this.resposta = new Lacunas(texto, new Set(this.#formaDaPosicao.keys()));
  }

  ouviu(velocidade) {
    if (this.resultado) return;
    this.#repeticoes += 1;
    this.#velocidade = Math.min(this.#velocidade, velocidade);
  }

  /** A primeira palavra ainda em branco, pela ordem entre as escondidas, ou -1. */
  get emBranco() {
    return this.resposta.partes.findIndex((parte) => parte === "");
  }

  /** Devolve "acertou", "errou" ou, na primeira vez em que só falta uma letra, "quase". */
  conferir() {
    this.resposta.conferir();
    const erradas = this.resposta.itens.filter(({ tipo }) => tipo !== "certa");
    if (!this.#tentou && erradas.length > 0 && erradas.every(quase)) {
      this.#tentou = true;
      for (const { posicao } of erradas) this.#quase.add(this.#formaDaPosicao.get(posicao));
      return "quase";
    }
    this.resultado = erradas.length === 0 ? "acertou" : "errou";
    return this.resultado;
  }

  desistir() {
    this.resposta.conferir();
    this.resultado = "errou";
  }

  /** O que salvar: uma linha por palavra vencida. */
  resultados() {
    const porForma = new Map();
    for (const { tipo, posicao, digitada } of this.resposta.itens) {
      const forma = this.#formaDaPosicao.get(posicao);
      const anterior = porForma.get(forma);
      porForma.set(forma, {
        forma,
        acertou: tipo === "certa" && (anterior?.acertou ?? true),
        digitada: anterior && !anterior.acertou ? anterior.digitada : digitada,
        quase: this.#quase.has(forma),
        repeticoes: this.#repeticoes,
        velocidade: this.#velocidade,
      });
    }
    return [...porForma.values()];
  }
}
