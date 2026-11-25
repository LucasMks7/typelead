// A página de revisão: os trechos vencidos, um por vez.

import { enviarJson, insistir, pedir } from "./api.js";
import { acaoDaTecla } from "./atalhos.js";
import { ligarCampo } from "./campo.js";
import { Cartao } from "./cartao.js";
import { desenharPalavra } from "./desenho.js";
import "./fechado.js";
import { Player } from "./player.js";
import { VELOCIDADES } from "./pratica.js";
import { tocar } from "./sons.js";

const $ = (id) => document.getElementById(id);

let trechos = []; // os que faltam hoje
let total = 0;
let indice = -1;
let cartao;
let player;
let videoDoPlayer;
let nova;
const placar = { certas: 0, erradas: 0 };

const trecho = () => trechos[indice];
const vezes = (quantas, uma, varias) => `${quantas} ${quantas === 1 ? uma : varias}`;

function avisar(texto, erro = false) {
  $("aviso").textContent = texto;
  $("aviso").classList.toggle("erro", erro);
  $("aviso").hidden = !texto;
}

const falhou = (erro) => avisar(erro.message, true);

// A velocidade

const opcoes = () => [...document.querySelectorAll('input[name="velocidade"]')];
const velocidade = () => Number(opcoes().find(({ checked }) => checked).value);

function mudarVelocidade(passo) {
  const atual = VELOCIDADES.indexOf(velocidade());
  const nova = VELOCIDADES[Math.min(Math.max(atual + passo, 0), VELOCIDADES.length - 1)];
  opcoes().find(({ value }) => Number(value) === nova).checked = true;
}

// O vídeo

async function prepararPlayer(video) {
  if (videoDoPlayer === video) return;
  player?.destruir();
  player = undefined;
  videoDoPlayer = undefined;
  const alvo = document.createElement("div");
  $("palco").replaceChildren(alvo);
  player = await Player.criar(alvo, video);
  videoDoPlayer = video;
}

let vezDeOuvir = 0;

async function ouvir() {
  if (!player) return;
  const { inicio, fim } = trecho();
  vezDeOuvir += 1;
  const vez = vezDeOuvir;
  cartao.ouviu(velocidade());
  document.body.toggleAttribute("data-tocando", true);
  try {
    await player.tocarFala(inicio, fim, velocidade());
  } catch (erro) {
    falhou(erro);
  } finally {
    if (vez === vezDeOuvir) document.body.removeAttribute("data-tocando");
  }
}

// Um trecho

async function abrir(proximo) {
  indice = proximo;
  if (!trecho()) return terminar();
  const deste = indice;
  const { texto, palavras, titulo, video_id: video } = trecho();
  cartao = new Cartao(texto, palavras);
  nova = null;
  avisar("");
  $("numero").textContent = indice + 1;
  $("titulo").textContent = titulo;
  $("ambiente").style.backgroundImage = `url("https://i.ytimg.com/vi/${video}/hqdefault.jpg")`;
  $("digitado").value = "";
  $("fala").classList.remove("acertou", "errou");
  desenhar();
  mostrarEstado("");
  $("digitado").focus();
  try {
    await prepararPlayer(video);
    if (deste === indice) await ouvir();
  } catch (erro) {
    if (deste === indice) falhou(new Error(`${erro.message} Dá para responder mesmo assim ou pular.`));
  }
}

function desenhar() {
  const { resposta, resultado } = cartao;
  const cursor = resposta.cursor($("digitado").selectionStart);
  let ordem = 0;
  const partes = resposta.vista().flatMap((palavra) => {
    const desenhada = desenharPalavra(palavra, { mostrada: Boolean(resultado), cursor, itens: resposta.itens, ordem, nova });
    ordem += palavra.letras ?? 0;
    return palavra.colada ? [desenhada] : [" ", desenhada];
  });
  nova = null;
  $("fala").replaceChildren(...partes);
}

function mostrarEstado(texto) {
  const { resultado } = cartao;
  $("placar").textContent = texto;
  $("placar").classList.toggle("certo", resultado === "acertou");
  $("seguir").textContent = resultado ? "Continuar" : "Conferir";
  $("nao-sei").hidden = Boolean(resultado);
  $("pular").hidden = Boolean(resultado);
  const { traducao } = trecho();
  $("traducao").textContent = traducao ?? "";
  // Antes da resposta, a tradução entregaria a palavra.
  $("traducao").hidden = !resultado || !traducao;
}

function animar(classe) {
  $("fala").classList.remove("acertou", "errou");
  void $("fala").offsetWidth;
  $("fala").classList.add(classe);
}

function conferir() {
  const resultado = cartao.conferir();
  if (resultado === "quase") {
    desenhar();
    animar("errou");
    return mostrarEstado("Quase: falta acertar uma letra. Tente mais uma vez.");
  }
  resolver();
}

function naoSei() {
  if (cartao.resultado) return;
  cartao.desistir();
  resolver();
}

function resolver() {
  desenhar();
  animar(cartao.resultado);
  if (localStorage.getItem("sons") !== "false") tocar(cartao.resultado === "acertou" ? "acerto" : "erro");
  mostrarEstado(
    cartao.resultado === "acertou" ? "Certo. Enter continua." : "Volta amanhã. Ouça de novo, se quiser; Enter continua.",
  );
  for (const resultado of cartao.resultados()) {
    placar[resultado.acertou ? "certas" : "erradas"] += 1;
    salvar({ ...resultado, fala_id: trecho().fala_id });
  }
}

// Um pedido por vez; com o programa fechado, a fila espera.
let salvando = Promise.resolve();

function salvar(resultado) {
  salvando = salvando
    .then(() => insistir(() => enviarJson("/api/revisao", resultado)))
    .catch((erro) => avisar(`Isto não foi salvo. ${erro.message}`, true));
}

function enter() {
  if (cartao.resultado) return abrir(indice + 1);
  if (cartao.emBranco === -1) return conferir();
  if (cartao.resposta.vazia) return ouvir();
  // Um Enter cedo demais seria um erro que a pessoa não cometeu.
  campo.irPara(cartao.emBranco);
}

// Começo e fim

async function carregar() {
  ({ trechos, total } = await insistir(() => pedir("/api/revisao")));
  const palavras = trechos.reduce((soma, { palavras: p }) => soma + p.length, 0);
  $("total").textContent = trechos.length;
  $("comecar").hidden = trechos.length === 0;
  $("quantas").textContent =
    trechos.length === 0
      ? "Nada para revisar hoje. As palavras erradas na prática voltam a partir do dia seguinte."
      : `${vezes(palavras, "palavra", "palavras")} em ${vezes(trechos.length, "trecho", "trechos")}${total > palavras ? `, de ${total} que venceram` : ""}. Ouça e complete o que falta.`;
}

async function terminar() {
  player?.destruir();
  player = undefined;
  videoDoPlayer = undefined;
  cartao = undefined;
  $("palco").replaceChildren();
  $("ambiente").style.backgroundImage = "";
  $("sala").hidden = true;
  $("capa").hidden = false;
  document.body.dataset.tela = "palavras";
  document.body.removeAttribute("data-tocando");
  // O que falta só é conhecido depois de tudo salvo.
  await salvando;
  try {
    await carregar();
  } catch (erro) {
    return falhou(erro);
  }
  const { certas, erradas } = placar;
  const fim = `Fim da revisão: ${vezes(certas, "palavra certa", "palavras certas")} e ${vezes(erradas, "que volta amanhã", "que voltam amanhã")}.`;
  $("quantas").textContent = trechos.length ? `${fim} Ainda há ${vezes(trechos.length, "trecho", "trechos")} para hoje.` : fim;
  $("comecar").textContent = "Continuar";
  if (localStorage.getItem("sons") !== "false") tocar("fim");
  Object.assign(placar, { certas: 0, erradas: 0 });
}

// Ligações

const campo = ligarCampo({
  campo: $("digitado"),
  fala: $("fala"),
  resposta: () => (cartao && !cartao.resultado ? cartao.resposta : undefined),
  aoMudar: (mudanca) => {
    nova = mudanca.nova ?? nova;
    desenhar();
  },
});

// O clique em "Começar" também é o que autoriza o navegador a tocar sozinho.
$("comecar").addEventListener("click", () => {
  $("capa").hidden = true;
  $("sala").hidden = false;
  document.body.dataset.tela = "sala";
  abrir(0);
});
$("repetir").addEventListener("click", ouvir);
$("seguir").addEventListener("click", enter);
$("nao-sei").addEventListener("click", naoSei);
$("pular").addEventListener("click", () => abrir(indice + 1));

document.addEventListener("click", (evento) => {
  if (cartao && evento.detail > 0 && evento.target.closest("#pratica button, #pratica label")) $("digitado").focus();
});

const ACOES = {
  enter,
  repetir: ouvir,
  mostrar: naoSei,
  maisDevagar: () => mudarVelocidade(-1),
  maisRapido: () => mudarVelocidade(1),
};

document.addEventListener("keydown", (evento) => {
  if (!cartao || evento.defaultPrevented) return;
  const noDitado = evento.target.id === "digitado";
  const onde = noDitado ? "ditado" : evento.target.matches("input") ? "campo" : evento.target.matches("button, a") ? "botao" : undefined;
  const acao = ACOES[acaoDaTecla(evento, onde)];
  if (!acao) return;
  evento.preventDefault();
  // Segurar o Enter não pode conferir e continuar de uma vez.
  if (!evento.repeat) acao();
});

// Depois de um clique no vídeo, o teclado ficaria preso dentro do player.
window.addEventListener("blur", () => {
  setTimeout(() => {
    if (cartao && document.activeElement?.tagName === "IFRAME") {
      document.activeElement.blur();
      window.focus();
      $("digitado").focus();
    }
  }, 0);
});

carregar().catch(falhou);
