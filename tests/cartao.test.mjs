import assert from "node:assert/strict";
import { test } from "node:test";

import { Cartao, formaDe } from "../src/typelead/web/js/cartao.js";

const FALA = "The kettle and the teapot.";
const KETTLE = { forma: "kettle", posicao: 1 };
const TEAPOT = { forma: "teapot", posicao: 4 };

function com(digitado, palavras = [KETTLE], fala = FALA) {
  const cartao = new Cartao(fala, palavras);
  cartao.resposta.escrever(digitado);
  return cartao;
}

const desenho = (cartao) =>
  cartao.resposta
    .vista()
    .map((p) => (p.oculta === null ? p.texto : p.sinais.map((s) => s.sinal).join("")))
    .join(" ");

test("a forma é a que o banco guarda", () => {
  assert.equal(formaDe("“Kettle,”"), "kettle");
  assert.equal(formaDe("Don’t!"), "don't");
  assert.equal(formaDe("'cause"), "cause");
  assert.equal(formaDe("well-known"), "wellknown");
});

test("só a palavra vencida fica escondida", () => {
  assert.equal(desenho(com("")), "The •••••• and the teapot.");
  assert.equal(desenho(com("", [KETTLE, TEAPOT])), "The •••••• and the ••••••.");
});

test("a palavra repetida na fala também some, para não entregar a resposta", () => {
  const cartao = com("", [{ forma: "the", posicao: 0 }]);
  assert.equal(desenho(cartao), "••• kettle and ••• teapot.");
});

test("acertou", () => {
  const cartao = com("Kettle");
  assert.equal(cartao.conferir(), "acertou");
  assert.deepEqual(cartao.resultados(), [
    { forma: "kettle", acertou: true, digitada: "Kettle", quase: false, repeticoes: 0, velocidade: 1 },
  ]);
});

test("uma letra errada ganha uma segunda chance, e só uma", () => {
  const cartao = com("kettla");
  assert.equal(cartao.conferir(), "quase");
  assert.equal(cartao.resultado, null);
  cartao.resposta.escrever("kettle");
  assert.equal(cartao.conferir(), "acertou");
  assert.equal(cartao.resultados()[0].quase, true);

  const outro = com("kettla");
  outro.conferir();
  assert.equal(outro.conferir(), "errou");
  assert.equal(outro.resultados()[0].acertou, false);
});

test("palavra curta ou muito diferente não ganha segunda chance", () => {
  assert.equal(com("castle").conferir(), "errou");
  assert.equal(com("an", [{ forma: "and", posicao: 2 }]).conferir(), "errou");
});

test("com duas palavras, a segunda chance só vem se as duas quase deram certo", () => {
  assert.equal(com("kettla zzzzzz", [KETTLE, TEAPOT]).conferir(), "errou");
  const cartao = com("kettle teapat", [KETTLE, TEAPOT]);
  assert.equal(cartao.conferir(), "quase");
  cartao.resposta.escrever("kettle teapot");
  cartao.conferir();
  assert.deepEqual(cartao.resultados().map(({ forma, acertou, quase }) => [forma, acertou, quase]), [
    ["kettle", true, false],
    ["teapot", true, true],
  ]);
});

test("cada palavra tem o próprio resultado", () => {
  const cartao = com("kettle zzzzzz", [KETTLE, TEAPOT]);
  assert.equal(cartao.conferir(), "errou");
  assert.deepEqual(cartao.resultados().map(({ forma, acertou }) => [forma, acertou]), [["kettle", true], ["teapot", false]]);
});

test("a palavra repetida só conta como certa se todas estiverem", () => {
  const cartao = com("the thx", [{ forma: "the", posicao: 0 }]);
  cartao.conferir();
  const resultados = cartao.resultados();
  assert.equal(resultados.length, 1);
  assert.deepEqual([resultados[0].acertou, resultados[0].digitada], [false, "thx"]);
});

test("desistir guarda o que já tinha sido digitado", () => {
  const cartao = com("kettle", [KETTLE, TEAPOT]);
  cartao.desistir();
  assert.equal(cartao.resultado, "errou");
  assert.deepEqual(cartao.resultados().map(({ acertou, digitada }) => [acertou, digitada]), [[true, "kettle"], [false, ""]]);
});

test("a primeira em branco, para o Enter ir até ela", () => {
  assert.equal(com("", [KETTLE, TEAPOT]).emBranco, 0);
  assert.equal(com("kettle", [KETTLE, TEAPOT]).emBranco, 1);
  assert.equal(com("kettle teapot", [KETTLE, TEAPOT]).emBranco, -1);
});

test("conta o que ouviu até responder, na menor velocidade", () => {
  const cartao = com("kettle");
  cartao.ouviu(1);
  cartao.ouviu(0.75);
  cartao.ouviu(1);
  cartao.conferir();
  cartao.ouviu(0.5);
  const [{ repeticoes, velocidade }] = cartao.resultados();
  assert.deepEqual([repeticoes, velocidade], [3, 0.75]);
});

test("se a legenda mudou e a palavra não está mais ali, a posição ainda vale", () => {
  assert.equal(desenho(com("", [{ forma: "spoon", posicao: 1 }])), "The •••••• and the teapot.");
});
