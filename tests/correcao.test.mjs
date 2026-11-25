import assert from "node:assert/strict";
import { test } from "node:test";

import { corrigir, corrigirParcial, distancia, resumir, separar } from "../src/typelead/web/js/correcao.js";

const certo = (fala, digitado) => resumir(corrigir(fala, digitado)).acertou;
const tipos = (itens) => itens.map((i) => `${i.tipo}:${i.esperada}/${i.digitada}`);

function aceita(...pares) {
  for (const [fala, digitado] of pares) assert.ok(certo(fala, digitado), `"${digitado}" deveria valer por "${fala}"`);
}

function recusa(...pares) {
  for (const [fala, digitado] of pares) assert.ok(!certo(fala, digitado), `"${digitado}" não deveria valer por "${fala}"`);
}

test("maiúscula, pontuação e acento não são erro", () => {
  aceita(
    ["The kettle is on.", "the kettle is on"],
    ["Wait—what? No… well, OK!", "wait what no well ok"],
    ["“Right,” she said.", "right she said"],
    ["The café's façade", "the cafes facade"],
    ["Yes/no", "yes no"],
    ["In the U.S. today", "in the US today"],
    ["'Hello there,' he said", "hello there he said"],
  );
});

test("contração e forma aberta valem nos dois sentidos", () => {
  const pares = [
    ["I don't know", "I do not know"],
    ["I won't go", "I will not go"],
    ["I can't", "I cannot"],
    ["I can't", "I can not"],
    ["He's late", "he is late"],
    ["He's left", "he has left"],
    ["I'd go", "I would go"],
    ["I'd gone", "I had gone"],
    ["We're here", "we are here"],
    ["They've got it", "they have got it"],
    ["It'll do", "it will do"],
    ["Let's go", "let us go"],
    ["Who'd've thought", "who would have thought"],
    ["I'm gonna go", "I am going to go"],
    ["I dunno", "I don't know"],
    ["I dunno", "I do not know"],
    ["What's she doin'", "what is she doing"],
    ["'cause I like 'em", "because I like them"],
  ];
  aceita(...pares, ...pares.map(([a, b]) => [b, a]));
});

test("apóstrofo curvo, acento agudo ou nenhum", () => {
  aceita(["I don’t", "I don't"], ["I don't", "I don´t"], ["I don't", "I dont"], ["I do not", "i dont"], ["It's fine", "its fine"], ["the dogs' bed", "the dog's bed"]);
});

test("sem apóstrofo, não vale quando é outra palavra com outro som", () => {
  recusa(["We're here", "were here"], ["I'll go", "ill go"], ["He'll go", "hell go"], ["we were", "we we're"], ["I was well", "I was we'll"]);
  aceita(["We're here", "we're here"], ["They were here", "they were here"]);
});

test("palavras parecidas continuam diferentes", () => {
  recusa(["their house", "there house"], ["could have", "could of"], ["he is", "he has"], ["I can", "I can't"], ["I do", "I don't"], ["two", "too"], ["He's", "his"]);
});

test("números de 0 a 100, com algarismo ou por extenso", () => {
  aceita(["I have 2 cups", "I have two cups"], ["25 people", "twenty-five people"], ["twenty five people", "25 people"], ["100%", "a hundred percent"], ["1,000 miles", "1000 miles"]);
  recusa(["3.5 miles", "35 miles"], ["I have 2 cups", "I have three cups"]);
});

test("ninguém conta as letras de uma palavra esticada", () => {
  aceita(["OH COMPANY OOOOOOOOOH", "oh company ooh"], ["Noooo!", "no"], ["sooo good", "soooooo good"], ["sooon", "soon"]);
  recusa(["Noooo!", "not"], ["too", "to"], ["soon", "son"]);
});

test("hífen vale como espaço ou nada", () => {
  aceita(["a well-known fact", "a well known fact"], ["send an e-mail", "send an email"], ["check in", "check-in"], ["twenty-five-year-old", "twentyfiveyearold"]);
});

test("os quatro tipos de item, com a pontuação da fala", () => {
  assert.deepEqual(tipos(corrigir("Bring two cups, please.", "bring cups pleas now")), [
    "certa:Bring/bring",
    "faltou:two/",
    "certa:cups,/cups",
    "trocada:please./pleas",
    "sobrou:/now",
  ]);
});

test("a palavra trocada se junta à mais parecida", () => {
  assert.deepEqual(tipos(corrigir("put the big kettle on", "put the kettel on")), [
    "certa:put/put",
    "certa:the/the",
    "faltou:big/",
    "trocada:kettle/kettel",
    "certa:on/on",
  ]);
});

test("o resumo conta as palavras da fala, e não os itens", () => {
  assert.deepEqual(resumir(corrigir("I do not know", "I don't no way")), { certas: 3, total: 4, sobras: 1, acertou: false });
});

test("campo vazio: faltou tudo; fala sem palavra: nada a corrigir", () => {
  assert.deepEqual(resumir(corrigir("Right.", "")), { certas: 0, total: 1, sobras: 0, acertou: false });
  assert.deepEqual(corrigir("—", ""), []);
});

test("nada do texto da fala se perde ao separar", () => {
  const fala = "“Well… I'm 5'9\", she said—in the U.S., at 3.5%.”";
  const juntas = separar(fala).map((p) => p.texto).join("");
  assert.equal(juntas.replace(/\s/g, ""), fala.replace(/\s/g, ""));
});

test("as aspas de abertura são da palavra seguinte", () => {
  const separadas = separar("She paid “about $5” (50% off)—right?");
  assert.deepEqual(separadas.map((p) => p.texto), ["She", "paid", "“about", "$5”", "(50", "%", "off)—", "right?"]);
  assert.deepEqual(separadas.filter((p) => p.colada).map((p) => p.texto), ["%", "right?"]);
});

test("no meio da digitação, só as palavras terminadas são corrigidas", () => {
  assert.deepEqual(corrigirParcial("Bring two cups", ""), []);
  assert.deepEqual(corrigirParcial("Bring two cups", "brin"), []);
  assert.deepEqual(tipos(corrigirParcial("Bring two cups", "bring tw")), ["certa:Bring/bring"]);
  assert.deepEqual(tipos(corrigirParcial("Bring two cups", "bring too ")), ["certa:Bring/bring", "trocada:two/too"]);
});

test("no meio da digitação, uma palavra pulada aparece quando a seguinte chega", () => {
  assert.deepEqual(tipos(corrigirParcial("Bring two cups", "bring cups ")), ["certa:Bring/bring", "faltou:two/", "certa:cups/cups"]);
});

test("palavra repetida na fala: vale a primeira", () => {
  assert.deepEqual(tipos(corrigirParcial("the cat and the dog", "the ")), ["certa:the/the"]);
});

test("começo de uma contração fica pendente até se decidir", () => {
  assert.deepEqual(tipos(corrigirParcial("I don't know", "I do ")), ["certa:I/I", "pendente:/do"]);
  assert.deepEqual(tipos(corrigirParcial("I don't know", "I do not ")), ["certa:I/I", "certa:don't/do not"]);
  assert.deepEqual(tipos(corrigirParcial("I don't know", "I do know ")).at(-1), "certa:know/know");
  assert.deepEqual(tipos(corrigirParcial("I dunno", "I do not ")), ["certa:I/I", "pendente:/do", "pendente:/not"]);
});

test("digitar a fala inteira, palavra por palavra, nunca acusa erro no caminho", () => {
  const casos = [
    ["I don't think he's gonna make it.", "I do not think he is going to make it "],
    ["I do not think he is going to make it.", "I don't think he's gonna make it "],
    ["25 well-known people", "twenty five well known people "],
  ];
  for (const [fala, digitado] of casos) {
    for (let n = 1; n <= digitado.length; n++) {
      const ruins = corrigirParcial(fala, digitado.slice(0, n)).filter((i) => ["trocada", "sobrou"].includes(i.tipo));
      assert.deepEqual(ruins, [], digitado.slice(0, n));
    }
  }
});

test("distância", () => {
  assert.equal(distancia("kettle", "kettel"), 2);
  assert.equal(distancia("", "abc"), 3);
  assert.equal(distancia("same", "same"), 0);
});

test("um texto colado enorme não trava", () => {
  const comeco = performance.now();
  corrigir("I don't think he's gonna make it to the well-known place, is he?", "don't he's gonna ".repeat(100));
  assert.ok(performance.now() - comeco < 2000);
});

test("cada item diz qual palavra da fala ele é", () => {
  const posicoes = corrigir("I do not know why", "I don't why now").map((i) => [i.tipo, i.posicao]);
  assert.deepEqual(posicoes, [["certa", 0], ["certa", 1], ["faltou", 3], ["certa", 4], ["sobrou", 5]]);
});
