import assert from "node:assert/strict";
import { test } from "node:test";

import { Lacunas, sortearOcultas } from "../src/typelead/web/js/lacunas.js";

function com(texto, fala = "Bring two cups.", ocultas) {
  const l = new Lacunas(fala, ocultas);
  l.escrever(texto);
  return l;
}

const desenho = (l, aoVivo) => l.vista(aoVivo).map((p) => (p.colada ? "" : " ") + (p.oculta === null ? p.texto : p.sinais.map((s) => s.sinal).join(""))).join("").trim();
const estados = (l, aoVivo) => l.vista(aoVivo).map((p) => p.sinais.map((s) => s.estado[0]).join("")).join(" ");

test("tudo oculto: um ponto por letra, com a pontuação à mostra", () => {
  assert.equal(desenho(com("")), "••••• ••• ••••.");
  assert.equal(desenho(com("", "Don't, it's a “well-known” fact!")), "•••'•, ••'• • “••••-•••••” ••••!");
});

test("números têm outro sinal, para ninguém escrever por extenso", () => {
  assert.equal(desenho(com("", "I have 50% of 1,000.")), "• •••• ##% •• #,###.");
});

test("as letras tomam o lugar dos pontos", () => {
  assert.equal(desenho(com("br")), "br••• ••• ••••.");
  assert.equal(desenho(com("bring t")), "bring t•• ••••.");
});

test("dois espaços pulam uma palavra", () => {
  assert.equal(desenho(com("bring  cu")), "bring ••• cu••.");
  assert.equal(desenho(com("  cups")), "••••• ••• cups.");
});

test("letra a mais, palavra a mais e pontuação não entram", () => {
  assert.equal(com("bringing twooo cups! please").texto, "bring two cups");
  assert.equal(com("don't", "Don't go").texto, "dont");
  assert.equal(com("bring\ntwo").texto, "bring two");
  assert.equal(com("bring two cups ").texto, "bring two cups");
});

test("arrumar o começo do texto dá o começo do texto arrumado: o cursor não pula", () => {
  const digitado = "bringing  cu!ps more";
  const l = com(digitado);
  for (let n = 0; n <= digitado.length; n++) assert.ok(l.texto.startsWith(l.arrumar(digitado.slice(0, n))), digitado.slice(0, n));
});

test("só as escondidas são digitadas", () => {
  const l = com("two", "Bring two cups.", new Set([1]));
  assert.equal(desenho(l), "Bring two cups.");
  assert.equal(desenho(com("", "Bring two cups.", new Set([1]))), "Bring ••• cups.");
  l.conferir();
  assert.deepEqual(l.resumo, { certas: 1, total: 1, sobras: 0, acertou: true });
});

test("acertou, trocou e deixou em branco", () => {
  const l = com("bring tow");
  l.conferir();
  assert.deepEqual(l.itens.map((i) => i.tipo), ["certa", "trocada", "faltou"]);
  assert.deepEqual(l.resumo, { certas: 1, total: 3, sobras: 0, acertou: false });
  assert.equal(estados(l), "ccccc cee fffff");
});

test("maiúscula e acento não contam, e a letra certa toma a forma da fala", () => {
  const l = com("the cafe", "The café");
  l.conferir();
  assert.ok(l.acertou);
  assert.equal(desenho(l), "The café");
});

test("antes de conferir, nada entrega se a letra está certa", () => {
  const l = com("bring");
  assert.equal(desenho(l), "bring ••• ••••.");
  assert.equal(estados(l).split(" ")[0], "ddddd");
});

test("enquanto digita, a correção é letra a letra", () => {
  assert.equal(estados(com("brxng"), true).split(" ")[0], "ccecc");
});

test("a palavra consertada perde a correção antiga; as outras ficam", () => {
  const l = com("bring tow cups");
  l.conferir();
  l.escrever("bring two cups");
  assert.deepEqual(estados(l).split(" "), ["ccccc", "ddd", "ccccf"]);
  assert.ok(!l.conferida);
  l.conferir();
  assert.ok(l.acertou);
});

test("pular a primeira palavra não é o mesmo que digitá-la", () => {
  const l = com("two", "two two");
  l.conferir();
  l.escrever(" two");
  assert.ok(!l.conferida);
});

test("o cursor: palavra e letra", () => {
  const l = com("bring t");
  assert.deepEqual(l.cursor(0), { palavra: 0, letra: 0 });
  assert.deepEqual(l.cursor(5), { palavra: 0, letra: 5 });
  assert.deepEqual(l.cursor(7), { palavra: 1, letra: 1 });
});

test("ir a uma palavra, já digitada ou não", () => {
  assert.deepEqual(com("bring two").irPara(0), { texto: "bring two", posicao: 5 });
  assert.deepEqual(com("bring").irPara(2), { texto: "bring  ", posicao: 7 });
});

test("espaço anda para a próxima palavra, sem empurrar as seguintes", () => {
  const l = com("bring  cups");
  assert.equal(l.passo("insertText", " ", 5), 1);
  assert.equal(l.passo("insertText", " ", 2), 1);
  assert.equal(l.passo("insertText", " ", 11), null);
  assert.equal(l.passo("insertText", "x", 5), undefined);
});

test("apagar na borda de uma palavra anda, e não junta as duas", () => {
  const l = com("bring  cups");
  assert.equal(l.passo("deleteContentBackward", null, 6), 0);
  assert.equal(l.passo("deleteWordBackward", null, 7), 1);
  assert.equal(l.passo("deleteContentBackward", null, 0), null);
  assert.equal(l.passo("deleteContentBackward", null, 3), undefined);
  assert.equal(l.passo("deleteContentForward", null, 5), null);
  assert.equal(l.passo("deleteContentForward", null, 2), undefined);
});

test("o Enter segue os mesmos passos do ditado", () => {
  assert.equal(com("").proximoPasso(false), "repetir");
  assert.equal(com("  ").proximoPasso(false), "repetir");
  assert.equal(com("bring").proximoPasso(false), "conferir");
  assert.equal(com("", "—").proximoPasso(false), "avancar");
  const l = com("bring");
  l.conferir();
  assert.equal(l.proximoPasso(false), "mostrar");
});

test("o sorteio esconde metade, pelo menos uma e nunca todas", () => {
  for (let n = 1; n <= 20; n++) {
    for (let vez = 0; vez < 30; vez++) {
      const ocultas = sortearOcultas(n);
      assert.equal(ocultas.size, Math.ceil(n / 2));
      assert.ok([...ocultas].every((i) => i >= 0 && i < n));
      assert.ok(n === 1 || ocultas.size < n);
    }
  }
  assert.equal(sortearOcultas(0).size, 0);
});

test("o sorteio não tem preferência por posição", () => {
  const vezes = Array(6).fill(0);
  for (let i = 0; i < 6000; i++) for (const k of sortearOcultas(6)) vezes[k] += 1;
  // Esperado: 3000 em cada. O desvio padrão é 39; 250 são mais de seis deles.
  assert.ok(vezes.every((v) => Math.abs(v - 3000) < 250), vezes.join());
});

test("a posição é a da palavra na fala, e não entre as escondidas", () => {
  const l = com("cups", "Bring two cups.", new Set([2]));
  assert.deepEqual(l.corrigirTexto().map((i) => [i.esperada, i.posicao]), [["cups.", 2]]);
});
