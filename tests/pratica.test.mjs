import assert from "node:assert/strict";
import { test } from "node:test";

import { acaoDaTecla } from "../src/typelead/web/js/atalhos.js";
import { Pratica, Sequencia, falaEm, fita, proximaQueFalta, relogio } from "../src/typelead/web/js/pratica.js";

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

test("continua da fala pedida, sem passar das pontas", () => {
  assert.equal(new Pratica(falas, 1).indice, 1);
  assert.equal(new Pratica(falas, 99).indice, 2);
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
  assert.deepEqual(fita(falas, 20)[2], { esquerda: 45, largura: 5, altura: 47.5 });
  assert.equal(fita(falas, 20)[0].altura, 100);
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

test("no ditado, espaço e sinais escrevem, e Enter é do ditado", () => {
  const acao = (key, mais) => acaoDaTecla({ key, ...mais }, "ditado");
  assert.equal(acao(" "), null);
  assert.equal(acao("-"), null);
  assert.equal(acao("Enter"), "enter");
  assert.equal(acao("ArrowDown"), "avancar");
  assert.equal(acao("ArrowUp", { shiftKey: true }), null);
});

test("com Ctrl, os atalhos que o ditado ocupou", () => {
  const acao = (key) => acaoDaTecla({ key, ctrlKey: true }, "ditado");
  assert.equal(acao(" "), "repetir");
  assert.equal(acao("Enter"), "mostrar");
  assert.equal(acao("ArrowUp"), "maisRapido");
  assert.equal(acao("ArrowDown"), "maisDevagar");
  assert.equal(acao("c"), null);
  assert.equal(acao("i"), "traduzir");
  assert.equal(acao("I"), "traduzir");
});

test("outro campo, como o do link, é dono de todas as teclas", () => {
  for (const key of ["Enter", "ArrowDown", " ", "+"]) assert.equal(acaoDaTecla({ key }, "campo"), null);
});

test("em um botão, Enter e espaço são do botão", () => {
  assert.equal(acaoDaTecla({ key: "Enter" }, "botao"), null);
  assert.equal(acaoDaTecla({ key: " " }, "botao"), null);
  assert.equal(acaoDaTecla({ key: "ArrowDown" }, "botao"), "avancar");
});

test("não rouba o zoom, o Alt nem a digitação com acento", () => {
  assert.equal(acaoDaTecla({ key: "-", ctrlKey: true }), null);
  assert.equal(acaoDaTecla({ key: "ArrowUp", altKey: true }), null);
  assert.equal(acaoDaTecla({ key: "Enter", isComposing: true }, "ditado"), null);
});

test("a sequência conta acertos de primeira e sem ajuda, e zera no erro", () => {
  const s = new Sequencia();
  const registrar = (rodada, acertou, comAjuda = false) => s.registrar({ rodada, acertou, comAjuda });
  assert.equal(registrar("a", true), true);
  assert.equal(registrar("b", true), true);
  assert.equal(s.atual, 2);
  // Conferir de novo a mesma fala não conta outra vez.
  assert.equal(registrar("b", true), false);
  // Com ajuda não conta, mas também não zera.
  assert.equal(registrar("c", true, true), false);
  assert.equal(s.atual, 2);
  registrar("d", false);
  assert.equal(s.atual, 0);
  // Consertar depois não vale como de primeira.
  assert.equal(registrar("d", true), false);
  assert.equal(s.atual, 0);
});

test("a próxima fala que falta dá a volta", () => {
  const marcadas = [false, true, false].map((acertada) => ({ acertada }));
  assert.equal(proximaQueFalta(marcadas), 0);
  assert.equal(proximaQueFalta(marcadas, 0), 2);
  assert.equal(proximaQueFalta(marcadas, 2), 0);
  assert.equal(proximaQueFalta([{ acertada: true }]), -1);
});
