import assert from "node:assert/strict";
import { test } from "node:test";

import { deveParar, resumir, volume } from "../src/typelead/web/js/medidas.js";

test("resume uma quantidade ímpar de valores, sem depender da ordem", () => {
  assert.deepEqual(resumir([30, 10, 20]), { n: 3, minimo: 10, mediana: 20, maximo: 30 });
});

test("a mediana de uma quantidade par é a média dos dois do meio", () => {
  assert.equal(resumir([40, 10, 20, 30]).mediana, 25);
});

test("ordena como número, não como texto", () => {
  assert.deepEqual(resumir([9, 100, -5]), { n: 3, minimo: -5, mediana: 9, maximo: 100 });
});

test("não altera a lista recebida", () => {
  const valores = [3, 1, 2];
  resumir(valores);
  assert.deepEqual(valores, [3, 1, 2]);
});

test("lista vazia não tem resumo", () => {
  assert.equal(resumir([]), null);
});

test("o silêncio tem volume zero", () => {
  assert.equal(volume(new Float32Array(128)), 0);
  assert.equal(volume([]), 0);
});

test("o volume não depende do sinal da onda", () => {
  assert.equal(volume([0.5, -0.5, 0.5, -0.5]), 0.5);
});

test("para no fim do trecho, ou antes dele com a antecipação", () => {
  assert.equal(deveParar(9.9, 10), false);
  assert.equal(deveParar(10, 10), true);
  assert.equal(deveParar(9.9, 10, 0.1), true);
  assert.equal(deveParar(9.8, 10, 0.1), false);
});
