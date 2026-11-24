// O estado da prática, sem navegador: qual fala, em que velocidade, à mostra ou não.

import { separar } from "./correcao.js";

export const VELOCIDADES = [0.5, 0.75, 1];

export class Pratica {
  #falas;
  #indice = 0;
  #mostrada = false;
  #velocidade = 1;

  constructor(falas, comeco = 0) {
    if (falas.length === 0) throw new Error("Não há falas para praticar.");
    this.#falas = falas;
    this.#indice = falaEm(falas, comeco);
  }

  get falas() {
    return this.#falas;
  }

  get indice() {
    return this.#indice;
  }

  get fala() {
    return this.#falas[this.#indice];
  }

  get mostrada() {
    return this.#mostrada;
  }

  get velocidade() {
    return this.#velocidade;
  }

  get primeira() {
    return this.#indice === 0;
  }

  get ultima() {
    return this.#indice === this.#falas.length - 1;
  }

  get quantasPalavras() {
    return separar(this.fala.texto).length;
  }

  /** Vai para uma fala, escondendo o texto. Devolve se mudou de lugar. */
  irPara(indice) {
    const destino = Math.min(Math.max(indice, 0), this.#falas.length - 1);
    if (destino === this.#indice) return false;
    this.#indice = destino;
    this.#mostrada = false;
    return true;
  }

  avancar() {
    return this.irPara(this.#indice + 1);
  }

  voltar() {
    return this.irPara(this.#indice - 1);
  }

  mostrar(sim = true) {
    this.#mostrada = sim;
  }

  /** Muda um passo: -1 mais devagar, 1 mais rápido. */
  mudarVelocidade(passo) {
    const atual = VELOCIDADES.indexOf(this.#velocidade);
    const novo = Math.min(Math.max(atual + passo, 0), VELOCIDADES.length - 1);
    this.#velocidade = VELOCIDADES[novo];
  }

  definirVelocidade(velocidade) {
    if (VELOCIDADES.includes(velocidade)) this.#velocidade = velocidade;
  }
}

/** A fala que está no ar neste instante ou, entre duas, a próxima. */
export function falaEm(falas, instante) {
  const achada = falas.findIndex((fala) => fala.fim > instante);
  return achada === -1 ? falas.length - 1 : achada;
}

/** Posição e largura de cada fala na fita, em porcentagem do vídeo. */
export function fita(falas, duracao) {
  const total = Math.max(duracao || 0, falas.at(-1)?.fim ?? 0) || 1;
  return falas.map(({ inicio, fim }) => ({
    esquerda: (100 * inicio) / total,
    largura: (100 * (fim - inicio)) / total,
  }));
}

/** 65 vira "1:05" e 3725 vira "1:02:05". */
export function relogio(segundos) {
  const total = Math.max(0, Math.floor(segundos || 0));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = String(total % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${s}` : `${m}:${s}`;
}
