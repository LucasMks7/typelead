// A tela: abre o vídeo, consegue o texto e conduz a prática.

import { enviarJson, pedir, transcrever } from "./api.js";
import { acaoDaTecla } from "./atalhos.js";
import { QUANDO_CORRIGIR, Resposta } from "./ditado.js";
import { Gravacao, pedirSomDaAba } from "./gravador.js";
import { Player } from "./player.js";
import { Pratica, fita, relogio } from "./pratica.js";

const ORIGENS = {
  autor: "",
  automatica: "Legenda automática: pode ter erros",
  som: "Transcrita pelo som: pode ter erros",
  arquivo: "Legenda do seu arquivo",
};

const $ = (id) => document.getElementById(id);

let video; // o que o servidor disse do vídeo aberto
let player;
let pratica;
let respostas; // por fala: voltar a uma delas traz o que foi digitado
// Muda a cada vídeo aberto: uma resposta atrasada do anterior é ignorada.
let abertura = 0;

// Avisos

function avisar(texto, erro = false) {
  $("aviso").textContent = texto;
  $("aviso").classList.toggle("erro", erro);
  $("aviso").hidden = !texto;
}

const falhou = (erro) => avisar(erro.message, true);

// Abrir um vídeo

async function abrir(link) {
  abertura += 1;
  const vez = abertura;
  limpar();
  avisar("Procurando o vídeo e a legenda…");
  $("abrir").querySelector("button").disabled = true;
  try {
    const achado = await enviarJson("/api/videos", { link });
    if (vez !== abertura) return;
    video = achado;
    $("titulo").textContent = achado.titulo;
    $("canal").textContent = achado.canal;
    document.title = `${achado.titulo} — typelead`;
    history.replaceState(null, "", `?v=${achado.id}`);
    if (!achado.incorporavel) {
      avisar("O dono deste vídeo só permite tocá-lo no site do YouTube. O typelead ainda não consegue praticar com ele.", true);
      return;
    }

    $("inicio").hidden = true;
    $("sala").hidden = false;
    const alvo = document.createElement("div");
    $("palco").replaceChildren(alvo);
    const novo = await Player.criar(alvo, achado.id, (erro) => {
      if (vez === abertura && erro.definitivo) falhou(erro);
    });
    if (vez !== abertura) {
      novo.destruir();
      return;
    }
    player = novo;
    avisar("");
    if (achado.falas.length > 0) praticar(achado.falas, achado.origem);
    else pedirTexto(achado.motivo);
  } catch (erro) {
    if (vez !== abertura) return;
    limpar();
    falhou(erro);
  } finally {
    if (vez === abertura) $("abrir").querySelector("button").disabled = false;
  }
}

function limpar() {
  gravando?.abort();
  player?.destruir();
  player = undefined;
  pratica = undefined;
  respostas = undefined;
  $("palco").replaceChildren();
  for (const id of ["sala", "sem-legenda", "pratica", "fita"]) $(id).hidden = true;
  $("inicio").hidden = false;
}

// Sem legenda: transcrever ou abrir um arquivo

let gravando;

function pedirTexto(motivo) {
  const duracao = video.duracao || player.duracao;
  $("motivo").textContent = motivo ?? "";
  $("duracao-do-som").textContent = duracao ? ` (${relogio(duracao)})` : "";
  $("sem-legenda").hidden = false;
  $("escolhas").hidden = false;
  $("andamento").hidden = true;
}

function mostrarEtapa(texto, fracao) {
  $("escolhas").hidden = true;
  $("andamento").hidden = false;
  $("etapa").textContent = texto;
  if (fracao === undefined) $("barra").removeAttribute("value");
  else $("barra").value = fracao;
}

async function transcreverPeloSom() {
  // Sem isto, a pessoa autorizaria o som de um vídeo que não vai tocar.
  if (player.impedimento) return falhou(player.impedimento);
  const vez = abertura;
  avisar("");
  let som;
  try {
    som = await pedirSomDaAba();
  } catch (erro) {
    // A pessoa fechou a janela do Chrome: não é um erro.
    if (erro.name !== "NotAllowedError") falhou(erro);
    return;
  }
  gravando = new AbortController();
  const { signal } = gravando;
  // Parar de compartilhar pela barra do Chrome vale como "parar aqui".
  som.faixa.addEventListener("ended", () => gravando?.abort());
  const duracao = player.duracao || video.duracao || Infinity;
  const atualizar = setInterval(() => {
    if (player) mostrarEtapa(`Ouvindo o vídeo: ${relogio(player.tempo)} de ${relogio(duracao)}`, player.tempo / duracao);
  }, 500);
  try {
    $("parar-aqui").hidden = false;
    mostrarEtapa("Ouvindo o vídeo…", 0);
    player.silenciar(false);
    const gravacao = new Gravacao(som.faixa, () => player?.tempo);
    await gravacao.iniciar();
    let gravado;
    try {
      await player.tocarParaGravar(0, duracao, signal);
    } finally {
      clearInterval(atualizar);
      $("parar-aqui").hidden = true;
      gravado = await gravacao.terminar();
      som.encerrar();
    }
    if (vez !== abertura) return;
    mostrarEtapa("Enviando para a transcrição, neste computador…");
    const falas = await transcrever(gravado, ({ estado, progresso }) => {
      if (vez !== abertura) return;
      if (estado === "transcrevendo") mostrarEtapa(`Transcrevendo: ${Math.round(progresso * 100)}%`, progresso);
      else mostrarEtapa("Preparando o modelo. Na primeira vez, ele é baixado da internet…");
    });
    if (vez === abertura) praticar(falas, "som");
  } catch (erro) {
    if (vez !== abertura) return;
    falhou(erro);
    pedirTexto(video.motivo);
  } finally {
    clearInterval(atualizar);
    som.encerrar();
    if (gravando?.signal === signal) gravando = undefined;
  }
}

async function abrirArquivo(arquivo) {
  const vez = abertura;
  avisar("");
  try {
    const { falas } = await pedir("/api/legendas", { method: "POST", body: arquivo });
    if (vez === abertura) praticar(falas, "arquivo");
  } catch (erro) {
    falhou(erro);
  }
}

// A prática

function praticar(falas, origem) {
  pratica = new Pratica(falas, video.comeco);
  respostas = falas.map((fala) => new Resposta(fala.texto));
  $("sem-legenda").hidden = true;
  $("pratica").hidden = false;
  $("total").textContent = falas.length;
  $("origem").textContent = ORIGENS[origem];
  $("velocidade").value = String(pratica.velocidade);
  montarFita();
  atualizar();
  $("digitado").focus();
}

const respostaAtual = () => respostas[pratica.indice];
const corrigeDigitando = () => $("quando").value === "digitando";

function montarFita() {
  const duracao = video.duracao || player.duracao;
  const blocos = fita(pratica.falas, duracao).map(({ esquerda, largura }, indice) => {
    const bloco = document.createElement("button");
    bloco.type = "button";
    // Só a atual entra no Tab: centenas de paradas impediriam de passar dali.
    bloco.tabIndex = -1;
    bloco.style.left = `${esquerda}%`;
    bloco.style.width = `${largura}%`;
    bloco.dataset.indice = indice;
    const rotulo = `Fala ${indice + 1}, em ${relogio(pratica.falas[indice].inicio)}`;
    bloco.title = rotulo;
    bloco.setAttribute("aria-label", rotulo);
    return bloco;
  });
  $("fita").replaceChildren(...blocos);
  $("fita").hidden = false;
}

function atualizar() {
  $("numero").textContent = pratica.indice + 1;
  $("instante").textContent = relogio(pratica.fala.inicio);
  $("voltar").disabled = pratica.primeira;
  $("avancar").disabled = pratica.ultima;
  $("mostrar").textContent = pratica.mostrada ? "Esconder texto" : "Mostrar texto";
  $("mostrar").setAttribute("aria-pressed", String(pratica.mostrada));
  $("velocidade").value = String(pratica.velocidade);

  if ($("digitado").value !== respostaAtual().texto) $("digitado").value = respostaAtual().texto;
  atualizarFala();

  for (const bloco of $("fita").children) {
    const atual = Number(bloco.dataset.indice) === pratica.indice;
    bloco.toggleAttribute("aria-current", atual);
    bloco.tabIndex = atual ? 0 : -1;
  }
}

/** O texto da fala: escondido, corrigido ou à mostra. */
function atualizarFala() {
  const resposta = respostaAtual();
  const { mostrada } = pratica;
  let itens = resposta.itens;
  if (corrigeDigitando() && !resposta.conferida && !mostrada) itens = resposta.parcial();
  if (itens?.length === 0) itens = null;

  const palavras = pratica.quantasPalavras;
  $("fala").classList.toggle("escondida", !itens && !mostrada);
  if (itens) $("fala").replaceChildren(...itens.flatMap((item) => [marcar(item, mostrada), " "]));
  else if (mostrada) $("fala").textContent = pratica.fala.texto;
  else $("fala").textContent = `${palavras} ${palavras === 1 ? "palavra" : "palavras"}. Ouça quantas vezes precisar.`;
  // O leitor de tela precisa saber que o texto é em inglês.
  if (itens || mostrada) $("fala").lang = "en";
  else $("fala").removeAttribute("lang");

  $("placar").textContent = placar(resposta, mostrada);
  $("placar").classList.toggle("certo", resposta.acertou);
}

/** Uma palavra corrigida. A resposta só aparece se a fala estiver à mostra. */
function marcar({ tipo, esperada, digitada }, mostrada) {
  const marca = document.createElement("span");
  marca.className = `palavra ${tipo}`;
  const por = (tag, textContent, mais) => marca.append(Object.assign(document.createElement(tag), { textContent, ...mais }));
  // A cor não chega a todos: o tipo do erro também vai em texto para o leitor de tela.
  const explicar = (texto) => por("span", texto, { className: "oculto", lang: "pt-BR" });

  if (tipo === "certa" || tipo === "pendente") {
    por("span", esperada || digitada);
    return marca;
  }
  if (digitada) {
    explicar(tipo === "sobrou" ? " a mais: " : " errada: ");
    por("s", digitada);
  }
  if (esperada && mostrada) {
    explicar(" o certo: ");
    por("strong", esperada);
  } else if (tipo === "faltou") {
    explicar(" falta uma palavra ");
    por("span", "", { className: "lacuna" });
  }
  return marca;
}

function placar(resposta, mostrada) {
  if (!resposta.conferida) return "";
  const { certas, total, sobras } = resposta.resumo;
  const seguir = pratica.ultima ? "É a última fala do vídeo." : "Enter vai para a próxima.";
  if (resposta.acertou) return `Tudo certo${resposta.comAjuda ? ", com o texto à mostra" : ""}. ${seguir}`;
  const pontos = `${certas} de ${total} certas${sobras ? `, ${sobras} a mais` : ""}.`;
  return mostrada ? `${pontos} ${seguir}` : `${pontos} Corrija e aperte Enter, ou só Enter para ver a resposta.`;
}

async function ouvir() {
  const { indice } = pratica;
  const { inicio, fim } = pratica.fala;
  avisar("");
  try {
    const resultado = await player.tocarFala(inicio, fim, pratica.velocidade);
    if (resultado === "fim") $("fita").children[indice]?.setAttribute("data-ouvida", "");
  } catch (erro) {
    falhou(erro);
  }
}

const ACOES = {
  voltar: () => mudar(() => pratica.voltar()),
  avancar: () => mudar(() => pratica.avancar()),
  repetir: ouvir,
  mostrar: () => {
    pratica.mostrar(!pratica.mostrada);
    if (pratica.mostrada) respostaAtual().mostrou();
    atualizar();
  },
  conferir: () => {
    const resposta = respostaAtual();
    resposta.conferir();
    if (resposta.acertou && !resposta.comAjuda) $("fita").children[pratica.indice].setAttribute("data-acertada", "");
    atualizar();
  },
  enter: () => ACOES[respostaAtual().proximoPasso(pratica.mostrada)](),
  maisDevagar: () => {
    pratica.mudarVelocidade(-1);
    atualizar();
  },
  maisRapido: () => {
    pratica.mudarVelocidade(1);
    atualizar();
  },
};

/** Muda de fala e já toca a nova. */
function mudar(movimento) {
  if (!movimento()) return;
  atualizar();
  $("digitado").focus();
  ouvir();
}

// Ligações

$("abrir").addEventListener("submit", (evento) => {
  evento.preventDefault();
  $("link").blur();
  abrir($("link").value);
});
$("transcrever").addEventListener("click", transcreverPeloSom);
$("parar-aqui").addEventListener("click", () => gravando?.abort());
$("arquivo").addEventListener("change", ({ target }) => {
  if (target.files[0]) abrirArquivo(target.files[0]);
  target.value = "";
});
for (const id of ["voltar", "repetir", "avancar", "mostrar"]) {
  $(id).addEventListener("click", () => ACOES[id]());
}
$("velocidade").addEventListener("change", ({ target }) => {
  pratica.definirVelocidade(Number(target.value));
  atualizar();
});
$("digitado").addEventListener("input", ({ target }) => {
  respostaAtual().escrever(target.value);
  atualizarFala();
});
$("quando").addEventListener("change", ({ target }) => {
  guardar("quando", target.value);
  // Anunciar cada palavra digitada atropelaria o leitor de tela.
  $("fala").ariaLive = corrigeDigitando() ? "off" : "polite";
  if (pratica) atualizarFala();
});
$("fita").addEventListener("click", ({ target }) => {
  if (target.dataset.indice) mudar(() => pratica.irPara(Number(target.dataset.indice)));
});

// Clicado com o mouse, o botão devolve o foco ao ditado. Pelo teclado, o foco
// continua onde está.
document.addEventListener("click", (evento) => {
  if (evento.detail > 0 && evento.target.closest("#pratica button, #fita button")) $("digitado").focus();
});

function onde(alvo) {
  if (alvo.id === "digitado") return "ditado";
  if (alvo.matches("input, textarea, select")) return "campo";
  return alvo.matches("button, a") ? "botao" : undefined;
}

document.addEventListener("keydown", (evento) => {
  if (!pratica || evento.defaultPrevented) return;
  const acao = acaoDaTecla(evento, onde(evento.target));
  if (!acao) return;
  evento.preventDefault();
  // Segurar o Enter não pode conferir, mostrar e avançar de uma vez.
  if (evento.repeat && evento.key === "Enter") return;
  ACOES[acao]();
});

// Depois de um clique no vídeo, o teclado ficaria preso dentro do player.
window.addEventListener("blur", () => {
  setTimeout(() => {
    if (pratica && document.activeElement?.tagName === "IFRAME") {
      document.activeElement.blur();
      window.focus();
      $("digitado").focus();
    }
  }, 0);
});

// A preferência fica neste navegador. Com o armazenamento bloqueado, vale só até
// recarregar.

function guardar(nome, valor) {
  try {
    localStorage.setItem(nome, valor);
  } catch {
    // Sem armazenamento: nada a fazer.
  }
}

function guardado(nome) {
  try {
    return localStorage.getItem(nome);
  } catch {
    return null;
  }
}

if (QUANDO_CORRIGIR.includes(guardado("quando"))) {
  $("quando").value = guardado("quando");
  $("quando").dispatchEvent(new Event("change"));
}

const pedido = new URLSearchParams(location.search).get("v");
if (pedido) {
  const link = `https://www.youtube.com/watch?v=${pedido}`;
  $("link").value = link;
  abrir(link);
}
