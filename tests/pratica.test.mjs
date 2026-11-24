import assert from "node:assert/strict";
import { test } from "node:test";

import { acaoDaTecla } from "../src/typelead/web/js/atalhos.js";
import { Pratica, falaEm, fita, relogio } from "../src/typelead/web/js/pratica.js";

const falas = [
  { inicio: 1, fim: 3, texto: "The kettle is on." },
  { inicio: 3, fim: 5, texto: "Bring two cups." },
  { inicio: 9, fim: 10, texto: "Right." },
];

test("começa na primeira fala, com o texto escondido e em velocidade normal", () => {
  const p = new Pratica(falas);
  assert.equal(p.indice, 0);
  assert.equal(p.mostrada, false);
  assert.equal(p.velocidade, 1);
  assert.equal(p.quantasPalavras, 4);
});

test("começa na fala do tempo pedido no link", () => {
  assert.equal(new Pratica(falas, 4).indice, 1);
});

test("avançar e voltar param nas pontas", () => {
  const p = new Pratica(falas);
  assert.equal(p.voltar(), false);
  assert.ok(p.primeira);
  assert.equal(p.avancar(), true);
  p.avancar();
  assert.ok(p.ultima);
  assert.equal(p.avancar(), false);
  assert.equal(p.indice, 2);
});

test("mudar de fala esconde o texto, e tentar passar da ponta não", () => {
  const p = new Pratica(falas);
  p.mostrar();
  p.voltar();
  assert.equal(p.mostrada, true);
  p.avancar();
  assert.equal(p.mostrada, false);
});

test("a velocidade anda um passo por vez, muda só entre as aceitas e fica ao trocar de fala", () => {
  const p = new Pratica(falas);
  p.mudarVelocidade(1);
  assert.equal(p.velocidade, 1);
  p.mudarVelocidade(-1);
  assert.equal(p.velocidade, 0.75);
  p.mudarVelocidade(-1);
  p.mudarVelocidade(-1);
  assert.equal(p.velocidade, 0.5);
  p.definirVelocidade(3);
  p.avancar();
  assert.equal(p.velocidade, 0.5);
});

test("sem falas não há prática", () => {
  assert.throws(() => new Pratica([]));
});

test("a fala de um instante: dentro, entre duas, antes da primeira e depois da última", () => {
  assert.equal(falaEm(falas, 3.5), 1);
  assert.equal(falaEm(falas, 7), 2);
  assert.equal(falaEm(falas, 0), 0);
  assert.equal(falaEm(falas, 99), 2);
});

test("a fita fica na escala do vídeo", () => {
  assert.deepEqual(fita(falas, 20)[2], { esquerda: 45, largura: 5 });
});

test("sem a duração, ou com uma menor que as falas, a fita vai até a última", () => {
  assert.equal(fita(falas, null)[2].esquerda + fita(falas, null)[2].largura, 100);
  assert.equal(fita(falas, 5)[2].esquerda, 90);
});

test("relógio", () => {
  assert.deepEqual([0, 65, 3725, -1, null].map(relogio), ["0:00", "1:05", "1:02:05", "0:00", "0:00"]);
});

test("atalhos fora de um campo", () => {
  const acao = (key) => acaoDaTecla({ key });
  assert.equal(acao(" "), "repetir");
  assert.equal(acao("ArrowDown"), "avancar");
  assert.equal(acao("ArrowUp"), "voltar");
  assert.equal(acao("Enter"), "mostrar");
  assert.equal(acao("-"), "maisDevagar");
  assert.equal(acao("a"), null);
  assert.equal(acao("toString"), null);
});

test("dentro de um campo, espaço e sinais escrevem; Ctrl+espaço repete", () => {
  const campo = { emCampo: true };
  assert.equal(acaoDaTecla({ key: " " }, campo), null);
  assert.equal(acaoDaTecla({ key: "-" }, campo), null);
  assert.equal(acaoDaTecla({ key: " ", ctrlKey: true }, campo), "repetir");
  assert.equal(acaoDaTecla({ key: "ArrowDown" }, campo), "avancar");
});

test("em um botão, Enter e espaço são do botão", () => {
  assert.equal(acaoDaTecla({ key: "Enter" }, { emBotao: true }), null);
  assert.equal(acaoDaTecla({ key: " " }, { emBotao: true }), null);
  assert.equal(acaoDaTecla({ key: "ArrowDown" }, { emBotao: true }), "avancar");
});

test("não rouba o zoom, o Alt nem a digitação com acento", () => {
  assert.equal(acaoDaTecla({ key: "-", ctrlKey: true }), null);
  assert.equal(acaoDaTecla({ key: "ArrowUp", altKey: true }), null);
  assert.equal(acaoDaTecla({ key: "Enter", isComposing: true }), null);
});
