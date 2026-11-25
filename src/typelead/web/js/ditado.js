// O estado do ditado, sem navegador: o que foi digitado em uma fala e o que o Enter faz.

import { corrigir, corrigirParcial, resumir, separar } from "./correcao.js";

export const QUANDO_CORRIGIR = ["enter", "digitando"];

export class Resposta {
  #fala;
  #texto = "";
  #conferido = null;
  #itens = null;
  #comAjuda = false;
  #repeticoes = 0;
  #velocidade = null;
  #desde = null;
  #traduziu = false;

  /** Une as tentativas seguidas na mesma fala. */
  rodada = crypto.randomUUID();

  constructor(fala) {
    this.#fala = fala;
  }

  get texto() {
    return this.#texto;
  }

  /** A última correção, que fica à vista enquanto a pessoa conserta os erros. */
  get itens() {
    return this.#itens;
  }

  get resumo() {
    return this.#itens && resumir(this.#itens);
  }

  /** O texto atual é o que foi conferido. */
  get conferida() {
    return this.#conferido !== null && this.#conferido === this.#texto.trimEnd();
  }

  get acertou() {
    return this.conferida && this.resumo.acertou;
  }

  /** O texto da fala já apareceu antes do acerto. */
  get comAjuda() {
    return this.#comAjuda;
  }

  get vazia() {
    return separar(this.#texto).length === 0;
  }

  /** Não há o que digitar nesta fala. */
  get semPalavras() {
    return separar(this.#fala).length === 0;
  }

  escrever(texto) {
    this.#texto = this.arrumar(texto);
  }

  /** O que fica de um texto digitado. Aqui, tudo. */
  arrumar(texto) {
    return texto;
  }

  corrigirTexto() {
    return corrigir(this.#fala, this.#texto);
  }

  parcial() {
    return corrigirParcial(this.#fala, this.#texto);
  }

  conferir() {
    this.#itens = this.corrigirTexto();
    this.#conferido = this.#texto.trimEnd();
  }

  /** A fala apareceu na tela. Vale a primeira vez. */
  comecou(agora) {
    this.#desde ??= agora;
  }

  ouviu(velocidade) {
    this.#repeticoes += 1;
    this.#velocidade = Math.min(this.#velocidade ?? velocidade, velocidade);
  }

  /** A tradução apareceu. Depois do acerto, já não é pista. */
  traduziu() {
    if (!this.acertou) this.#traduziu = true;
  }

  /** Como a pessoa chegou até aqui: quanto ouviu, a menor velocidade, se traduziu e os segundos. */
  medidas(agora) {
    return {
      repeticoes: this.#repeticoes,
      velocidade: this.#velocidade ?? 1,
      traduziu: this.#traduziu,
      duracao: Math.max(0, (agora - (this.#desde ?? agora)) / 1000),
    };
  }

  /** A fala foi mostrada. Depois do acerto, já não é ajuda. */
  mostrou() {
    if (!this.acertou) this.#comAjuda = true;
  }

  /** O que o Enter faz agora. Um Enter por passo, sem tirar a mão do teclado. */
  proximoPasso(mostrada) {
    if (this.semPalavras) return "avancar";
    if (this.conferida) return this.acertou || mostrada ? "avancar" : "mostrar";
    if (this.vazia) return mostrada ? "avancar" : "repetir";
    return "conferir";
  }
}
