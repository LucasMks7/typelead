import assert from "node:assert/strict";
import { afterEach, test } from "node:test";

import { ErroDaApi, SemServidor, ateVoltar, conexao, insistir, pedir } from "../src/typelead/web/js/api.js";

const original = globalThis.fetch;
afterEach(() => (globalThis.fetch = original));

const json = (dados, status = 200) => new Response(JSON.stringify(dados), { status });

/** Um servidor que pode ser fechado e aberto. */
function simular(atender = () => json({})) {
  const estado = { aberto: true, pedidos: [] };
  globalThis.fetch = async (caminho) => {
    estado.pedidos.push(caminho);
    if (!estado.aberto) throw new TypeError("Failed to fetch");
    return atender(caminho);
  };
  return estado;
}

function ouvir() {
  const eventos = [];
  const anotar = ({ type }) => eventos.push(type);
  for (const tipo of ["caiu", "voltou"]) conexao.addEventListener(tipo, anotar);
  return { eventos, parar: () => ["caiu", "voltou"].forEach((tipo) => conexao.removeEventListener(tipo, anotar)) };
}

test("devolve o JSON e transforma a recusa em mensagem", async () => {
  simular((caminho) => (caminho === "/certo" ? json({ a: 1 }) : json({ detail: "Link inválido." }, 422)));
  assert.deepEqual(await pedir("/certo"), { a: 1 });
  await assert.rejects(pedir("/errado"), (erro) => erro instanceof ErroDaApi && !(erro instanceof SemServidor) && erro.message === "Link inválido.");
});

test("programa fechado: avisa uma vez que caiu e uma que voltou", async () => {
  const servidor = simular();
  const { eventos, parar } = ouvir();
  servidor.aberto = false;
  const espera = ateVoltar(5);
  await assert.rejects(pedir("/a"), SemServidor);
  await assert.rejects(pedir("/b"), SemServidor);
  assert.deepEqual(eventos, ["caiu"]);
  servidor.aberto = true;
  await espera;
  assert.deepEqual(eventos, ["caiu", "voltou"]);
  parar();
});

test("pedido que falha com o programa aberto não é dado como fechado", async () => {
  simular();
  const { eventos, parar } = ouvir();
  await ateVoltar(5);
  assert.deepEqual(eventos, []);
  parar();
});

test("insistir espera o programa voltar e repete o pedido", async () => {
  const servidor = simular((caminho) => json({ caminho }));
  servidor.aberto = false;
  const espera = ateVoltar(5);
  const pedido = insistir(() => pedir("/salvar"));
  setTimeout(() => (servidor.aberto = true), 30);
  assert.deepEqual(await pedido, { caminho: "/salvar" });
  await espera;
  assert.equal(servidor.pedidos.filter((caminho) => caminho === "/salvar").length, 2);
});

test("insistir não repete o que o programa recusou", async () => {
  const servidor = simular(() => json({ detail: "Não." }, 422));
  await assert.rejects(insistir(() => pedir("/salvar")), /Não\./);
  assert.equal(servidor.pedidos.length, 1);
});
