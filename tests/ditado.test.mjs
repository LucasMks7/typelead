import assert from "node:assert/strict";
import { test } from "node:test";

import { Resposta } from "../src/typelead/web/js/ditado.js";

const FALA = "Bring two cups.";

function digitando(texto, fala = FALA) {
  const r = new Resposta(fala);
  r.escrever(texto);
  return r;
}

test("com o campo vazio, o Enter ouve de novo", () => {
  assert.equal(digitando("").proximoPasso(false), "repetir");
  assert.equal(digitando("  ").proximoPasso(false), "repetir");
  assert.equal(digitando(" ...").proximoPasso(false), "repetir");
});

test("acertou: conferir e avançar", () => {
  const r = digitando("bring two cups");
  assert.equal(r.proximoPasso(false), "conferir");
  r.conferir();
  assert.ok(r.acertou);
  assert.ok(!r.comAjuda);
  assert.equal(r.proximoPasso(false), "avancar");
});

test("errou: o mesmo Enter outra vez mostra a resposta, e o seguinte avança", () => {
  const r = digitando("bring cups");
  r.conferir();
  assert.ok(!r.acertou);
  assert.equal(r.proximoPasso(false), "mostrar");
  r.mostrou();
  assert.equal(r.proximoPasso(true), "avancar");
  assert.ok(r.comAjuda);
});

test("errou e consertou: confere de novo, com a correção anterior à vista até lá", () => {
  const r = digitando("bring cups");
  r.conferir();
  const antes = r.itens;
  r.escrever("bring two cups");
  assert.equal(r.itens, antes);
  assert.ok(!r.conferida);
  assert.ok(!r.acertou);
  assert.equal(r.proximoPasso(false), "conferir");
  r.conferir();
  assert.ok(r.acertou);
  assert.ok(!r.comAjuda);
});

test("um espaço a mais no fim não é outra resposta", () => {
  const r = digitando("bring cups");
  r.conferir();
  r.escrever("bring cups ");
  assert.ok(r.conferida);
});

test("ver o texto antes do acerto é ajuda; depois, não", () => {
  const antes = digitando("bring two cups");
  antes.mostrou();
  antes.conferir();
  assert.ok(antes.acertou && antes.comAjuda);
  const depois = digitando("bring two cups");
  depois.conferir();
  depois.mostrou();
  assert.ok(!depois.comAjuda);
});

test("com o texto à mostra e nada digitado, o Enter avança", () => {
  assert.equal(digitando("").proximoPasso(true), "avancar");
});

test("fala sem palavra não prende ninguém", () => {
  assert.equal(digitando("", "—").proximoPasso(false), "avancar");
});
