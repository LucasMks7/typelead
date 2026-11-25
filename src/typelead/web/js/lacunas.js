// A fala com palavras escondidas, um ponto por letra. Puro, sem navegador.
//
// O que a pessoa digita é um texto comum: o espaço passa para a próxima palavra
// escondida, e dois espaços pulam uma. Cada pedaço entre espaços preenche uma palavra.

import { separar } from "./correcao.js";
import { Resposta } from "./ditado.js";

const LETRA = /[\p{L}\p{N}]/u;
const NUMERO = /\p{N}/u;

const letrasDe = (texto) => [...texto].filter((sinal) => LETRA.test(sinal));

const simples = (letra) => letra.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();

/** Sorteia quais palavras esconder: metade, nunca nenhuma nem, se puder, todas. */
export function sortearOcultas(quantas, sorteio = Math.random) {
  const ordem = Array.from({ length: quantas }, (_, i) => i);
  // Embaralhamento de Fisher-Yates: toda ordem tem a mesma chance.
  for (let i = quantas - 1; i > 0; i--) {
    const j = Math.floor(sorteio() * (i + 1));
    [ordem[i], ordem[j]] = [ordem[j], ordem[i]];
  }
  return new Set(ordem.slice(0, Math.ceil(quantas / 2)));
}

export class Lacunas extends Resposta {
  #palavras;
  #ocultas;

  /** `ocultas`: quais palavras esconder, pela ordem na fala. Sem ele, todas. */
  constructor(fala, ocultas) {
    super(fala);
    this.#palavras = separar(fala.normalize("NFC")).map(({ texto, colada }, i) => ({
      texto,
      colada,
      letras: letrasDe(texto),
      oculta: !ocultas || ocultas.has(i),
    }));
    // "&" e "%" não têm letra para digitar.
    for (const palavra of this.#palavras) palavra.oculta &&= palavra.letras.length > 0;
    this.#ocultas = this.#palavras.filter((palavra) => palavra.oculta);
  }

  get semPalavras() {
    return this.#ocultas.length === 0;
  }

  /** O que foi digitado em cada palavra escondida. */
  get partes() {
    const partes = this.texto.split(" ");
    return this.#ocultas.map((_, i) => partes[i] ?? "");
  }

  /** Tira o que não cabe: letras a mais, palavras a mais e a pontuação, já à mostra. */
  arrumar(texto) {
    return texto
      .normalize("NFC")
      .replace(/\s/gu, " ")
      .split(" ")
      .slice(0, this.#ocultas.length)
      .map((parte, i) => letrasDe(parte).slice(0, this.#ocultas[i].letras.length).join(""))
      .join(" ");
  }

  corrigirTexto() {
    return this.#ocultas.map(({ texto, letras }, i) => {
      const digitada = this.partes[i];
      const digitadas = [...digitada];
      const certa = digitadas.length === letras.length && letras.every((l, k) => simples(l) === simples(digitadas[k]));
      return { tipo: certa ? "certa" : digitada ? "trocada" : "faltou", esperada: texto, digitada, palavras: 1 };
    });
  }

  /** Em que palavra escondida e em que letra dela está esta posição do texto. */
  cursor(posicao) {
    const antes = this.texto.slice(0, posicao).split(" ");
    return { palavra: antes.length - 1, letra: [...antes.at(-1)].length };
  }

  /** O texto e a posição para continuar a digitar em uma palavra escondida. */
  irPara(palavra) {
    const partes = this.texto.split(" ");
    while (partes.length <= palavra) partes.push("");
    return { texto: partes.join(" "), posicao: partes.slice(0, palavra + 1).join(" ").length };
  }

  /**
   * Espaço e apagar nas bordas de uma palavra andam entre elas. Como texto comum,
   * criariam ou tirariam uma separação, e as palavras seguintes mudariam de lugar.
   * Devolve a palavra para onde ir; null, se não há o que fazer; undefined, se é
   * uma digitação comum.
   */
  passo(tipo, dado, posicao) {
    const { palavra, letra } = this.cursor(posicao);
    if (tipo === "insertText" && dado === " ") return palavra + 1 < this.#ocultas.length ? palavra + 1 : null;
    if (tipo.startsWith("delete") && tipo.endsWith("Backward") && letra === 0) return palavra > 0 ? palavra - 1 : null;
    const fim = [...(this.partes[palavra] ?? "")].length;
    if (tipo.startsWith("delete") && tipo.endsWith("Forward") && letra >= fim) return null;
    return undefined;
  }

  /**
   * O que desenhar: por palavra, seus sinais. A pontuação aparece sempre. Com
   * `aoVivo`, cada letra é corrigida na hora; sem ele, só depois de conferir, e a
   * palavra mexida desde então volta a ficar sem correção.
   */
  vista(aoVivo = false) {
    const { partes, itens } = this;
    let oculta = -1;
    return this.#palavras.map((palavra) => {
      if (!palavra.oculta) return { oculta: null, texto: palavra.texto, colada: palavra.colada, sinais: [] };
      oculta += 1;
      const digitadas = [...partes[oculta]];
      const conferida = itens?.[oculta].digitada === partes[oculta];
      let k = -1;
      const sinais = [...palavra.texto].map((sinal) => {
        if (!LETRA.test(sinal)) return { sinal, estado: "fixo" };
        k += 1;
        const digitada = digitadas[k];
        if (digitada === undefined) return { sinal: NUMERO.test(sinal) ? "#" : "•", estado: conferida ? "faltou" : "vazia" };
        if (!aoVivo && !conferida) return { sinal: digitada, estado: "digitada" };
        // A letra certa toma a forma da fala: a maiúscula e o acento.
        return simples(digitada) === simples(sinal) ? { sinal, estado: "certa" } : { sinal: digitada, estado: "errada" };
      });
      return { oculta, texto: palavra.texto, colada: palavra.colada, sinais, letras: palavra.letras.length, tipo: conferida ? itens[oculta].tipo : null };
    });
  }
}
