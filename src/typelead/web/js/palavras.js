// A página das palavras já erradas.

import { enviarJson, insistir, pedir } from "./api.js";
import { DIAGNOSTICOS, criar, destacar } from "./desenho.js";
import "./fechado.js";
import { relogio } from "./pratica.js";

const $ = (id) => document.getElementById(id);

const SITUACOES = {
  errando: "errando",
  aprendendo: "aprendendo",
  conhecida: "acertando",
  sabida: "já sei",
};

const ESTUDAR = new Set(["errando", "aprendendo"]);
const FILTROS = {
  estudar: ({ situacao }) => ESTUDAR.has(situacao),
  prontas: ({ situacao }) => !ESTUDAR.has(situacao),
  todas: () => true,
};

let palavras = [];

const vezes = (quantas, uma, varias) => `${quantas} ${quantas === 1 ? uma : varias}`;

function falhou(erro) {
  $("aviso").textContent = erro.message;
  $("aviso").classList.add("erro");
  $("aviso").hidden = false;
}

function desenhar(palavra) {
  const { forma, situacao, erros, acertos, motivo, texto, posicao, esperada, traducao, video_id: video, titulo, inicio } = palavra;
  const item = criar("li", "", { className: "verbete" });
  item.dataset.situacao = situacao;

  const cabeca = criar("div", "", { className: "cabeca" });
  cabeca.append(criar("strong", forma, { lang: "en" }), criar("span", SITUACOES[situacao], { className: "etiqueta" }));

  const fala = criar("p", "", { className: "exemplo", lang: "en" });
  fala.append(...destacar(texto, posicao, esperada));

  const pe = criar("p", "", { className: "pe" });
  const onde = criar("a", `${titulo}, ${relogio(inicio)}`, { href: `/?v=${video}&t=${Math.floor(inicio)}` });
  const conta = `${vezes(erros, "erro", "erros")}, ${vezes(acertos, "acerto", "acertos")}. Motivo do último erro: ${DIAGNOSTICOS[motivo]}. `;
  pe.append(conta, onde);

  const sabida = situacao === "sabida";
  const botao = criar("button", sabida ? "Voltar a estudar" : "Já sei", { type: "button", className: "discreto" });
  botao.addEventListener("click", () => marcar(palavra, !sabida));

  item.append(cabeca, fala);
  if (traducao) item.append(criar("p", traducao, { className: "traducao", title: "Tradução automática" }));
  item.append(pe, botao);
  return item;
}

async function marcar({ forma }, sabida) {
  try {
    await insistir(() => enviarJson("/api/palavras", { forma, sabida }, "PUT"));
    await carregar();
  } catch (erro) {
    falhou(erro);
  }
}

function mostrar() {
  const filtro = FILTROS[document.querySelector('input[name="filtro"]:checked').value];
  const mostradas = palavras.filter(filtro);
  $("lista").replaceChildren(...mostradas.map(desenhar));
  $("vazio").hidden = mostradas.length > 0;
}

async function carregar() {
  palavras = await insistir(() => pedir("/api/palavras"));
  const estudar = palavras.filter(FILTROS.estudar).length;
  $("com-palavras").hidden = palavras.length === 0;
  $("resumo").textContent =
    palavras.length === 0
      ? "As palavras que você errar na prática aparecem aqui, com a fala de onde vieram."
      : `${vezes(estudar, "palavra", "palavras")} para estudar e ${vezes(palavras.length - estudar, "já sabida", "já sabidas")}.`;
  mostrar();
}

for (const opcao of document.querySelectorAll('input[name="filtro"]')) opcao.addEventListener("change", mostrar);
carregar().catch(falhou);
