// A tela: abre o vídeo, consegue o texto e conduz a prática.

import { enviarJson, pedir, transcrever } from "./api.js";
import { acaoDaTecla } from "./atalhos.js";
import { separar } from "./correcao.js";
import { QUANDO_CORRIGIR, Resposta } from "./ditado.js";
import { Gravacao, pedirSomDaAba } from "./gravador.js";
import { Lacunas, sortearOcultas } from "./lacunas.js";
import { Player } from "./player.js";
import { Pratica, falaEm, fita, relogio } from "./pratica.js";

const ORIGENS = {
  autor: "",
  automatica: "Legenda automática: pode ter erros",
  som: "Transcrita pelo som: pode ter erros",
  arquivo: "Legenda do seu arquivo",
};

const MODOS = {
  oculto: (fala) => new Lacunas(fala.texto),
  lacunas: (fala) => new Lacunas(fala.texto, sortearOcultas(separar(fala.texto).length)),
  livre: (fala) => new Resposta(fala.texto),
};

const $ = (id) => document.getElementById(id);

let video; // o que o servidor disse do vídeo aberto
let player;
let pratica;
let traducaoAberta = false;
let respostas; // por modo e fala: voltar a uma delas traz o que foi digitado
// Muda a cada vídeo aberto: uma resposta atrasada do anterior é ignorada.
let abertura = 0;

// Avisos

function avisar(texto, erro = false) {
  $("aviso").textContent = texto;
  $("aviso").classList.toggle("erro", erro);
  $("aviso").hidden = !texto;
}

const falhou = (erro) => avisar(erro.message, true);

// Salvar

// Um pedido por vez, na ordem em que aconteceram.
let salvando = Promise.resolve();

function salvar(pedido) {
  salvando = salvando.then(pedido).catch((erro) => avisar(`Isto não foi salvo. ${erro.message}`, true));
  return salvando;
}

// Abrir um vídeo

async function abrir(link, novo = false) {
  abertura += 1;
  const vez = abertura;
  limpar();
  avisar("Procurando o vídeo e a legenda…");
  $("abrir").querySelector("button").disabled = true;
  try {
    const achado = await enviarJson("/api/videos", { link, novo });
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
    const criado = await Player.criar(alvo, achado.id, (erro) => {
      if (vez === abertura && erro.definitivo) falhou(erro);
    });
    if (vez !== abertura) {
      criado.destruir();
      return;
    }
    player = criado;
    avisar("");
    if (achado.falas.length > 0) praticar(achado);
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
    if (vez === abertura) await salvarFalas(falas, "som");
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
    if (vez === abertura) await salvarFalas(falas, "arquivo");
  } catch (erro) {
    falhou(erro);
  }
}

/** Guarda as falas; com isso, cada uma ganha o número que as tentativas usam. */
async function salvarFalas(falas, origem) {
  const vez = abertura;
  const { id, titulo, canal } = video;
  const duracao = video.duracao || player.duracao || null;
  let salvo = { falas, origem, posicao: 0 };
  try {
    salvo = await enviarJson(`/api/videos/${id}/falas`, { titulo, canal, duracao, origem, falas }, "PUT");
  } catch (erro) {
    // A transcrição levou a duração do vídeo: sem salvar, ainda dá para praticar.
    avisar(`As falas não foram salvas. ${erro.message}`, true);
  }
  if (vez === abertura) praticar({ ...salvo, comeco: video.comeco });
}

// A prática

function praticar({ falas, origem, posicao, comeco }) {
  // O tempo pedido no link vale mais que o ponto em que a pessoa parou.
  pratica = new Pratica(falas, comeco ? falaEm(falas, comeco) : posicao);
  respostas = { oculto: [], lacunas: [], livre: [] };
  $("sem-legenda").hidden = true;
  $("pratica").hidden = false;
  $("total").textContent = falas.length;
  $("origem").textContent = ORIGENS[origem];
  $("velocidade").value = String(pratica.velocidade);
  traducaoAberta = false;
  mostrarTraducao();
  montarFita();
  atualizar();
  $("digitado").focus();
}

/** Criada na primeira vez e guardada: as palavras sorteadas não mudam ao voltar. */
function respostaAtual() {
  const doModo = respostas[$("modo").value];
  doModo[pratica.indice] ??= MODOS[$("modo").value](pratica.fala);
  return doModo[pratica.indice];
}
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
    bloco.toggleAttribute("data-acertada", pratica.falas[indice].acertada);
    return bloco;
  });
  $("fita").replaceChildren(...blocos);
  $("fita").hidden = false;
}

function atualizar() {
  respostaAtual().comecou(performance.now());
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
  $("placar").textContent = placar(resposta, mostrada);
  $("placar").classList.toggle("certo", resposta.acertou);

  const comLacunas = resposta instanceof Lacunas;
  $("fala").classList.toggle("com-lacunas", comLacunas && !resposta.semPalavras);
  $("digitado").classList.toggle("oculto", comLacunas);
  if (comLacunas && !resposta.semPalavras) return desenharLacunas(resposta, mostrada);

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
}

/** A fala com pontos no lugar das letras escondidas. */
function desenharLacunas(resposta, mostrada) {
  const campo = $("digitado");
  const cursor = resposta.cursor(campo.selectionStart);
  const partes = resposta.vista(corrigeDigitando()).flatMap((palavra) => {
    const desenhada = desenharPalavra(palavra, mostrada, cursor, resposta.itens);
    return palavra.colada ? [desenhada] : [" ", desenhada];
  });
  $("fala").classList.remove("escondida");
  $("fala").lang = "en";
  $("fala").replaceChildren(...partes);
}

function desenharPalavra({ oculta, texto, sinais, letras, tipo }, mostrada, cursor, itens) {
  const por = (pai, tag, textContent, mais) => {
    const filho = Object.assign(document.createElement(tag), { textContent, ...mais });
    pai.append(filho);
    return filho;
  };
  const marca = document.createElement("span");
  marca.className = "palavra";
  if (oculta === null) {
    marca.textContent = texto;
    return marca;
  }
  // Com a resposta à mostra: a palavra certa, ou a digitada riscada e a certa.
  if (mostrada) {
    const { digitada } = itens?.[oculta] ?? {};
    if (tipo === "certa") return marcar({ tipo, esperada: texto }, true);
    if (tipo) return marcar({ tipo, esperada: texto, digitada }, true);
    por(marca, "strong", texto);
    return marca;
  }
  marca.classList.add("lacunada");
  marca.dataset.oculta = oculta;
  por(marca, "span", `${letras} ${letras === 1 ? "letra" : "letras"}`, { className: "oculto", lang: "pt-BR" });
  const casas = sinais.map(({ sinal, estado }) => por(marca, "span", sinal, { className: `casa ${estado}`, ariaHidden: "true" }));
  if (oculta === cursor.palavra) {
    const daLetra = casas.filter((casa) => !casa.classList.contains("fixo"));
    // Com a palavra completa, o cursor espera depois da última letra.
    if (cursor.letra < letras) daLetra[cursor.letra].classList.add("cursor");
    else daLetra.at(-1).classList.add("cursor-depois");
  }
  return marca;
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
  respostaAtual().ouviu(pratica.velocidade);
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
    salvarTentativa(resposta);
  },
  traduzir: () => {
    traducaoAberta = !traducaoAberta;
    if (traducaoAberta) respostaAtual().traduziu();
    mostrarTraducao();
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

async function mostrarTraducao() {
  $("traduzir").setAttribute("aria-pressed", String(traducaoAberta));
  $("traducao").hidden = !traducaoAberta;
  if (!traducaoAberta) return;
  const { fala } = pratica;
  if (fala.traducao) return escreverTraducao(fala.traducao);
  escreverTraducao("Traduzindo… Na primeira vez, o tradutor é baixado da internet (236 MB).");
  try {
    if (fala.id === undefined) throw new Error("Só uma fala salva pode ser traduzida.");
    fala.traducao = (await pedir(`/api/falas/${fala.id}/traducao`, { method: "POST" })).traducao;
    if (pratica?.fala === fala && traducaoAberta) escreverTraducao(fala.traducao);
  } catch (erro) {
    if (pratica?.fala === fala && traducaoAberta) escreverTraducao(erro.message);
  }
}

function escreverTraducao(texto) {
  $("traducao").textContent = texto;
  $("traducao").title = "Tradução automática: pode errar, principalmente em expressões";
}

function salvarTentativa(resposta) {
  if (pratica.fala.id === undefined) return;
  const tentativa = {
    fala_id: pratica.fala.id,
    rodada: resposta.rodada,
    modo: $("modo").value,
    corrigir: $("quando").value,
    texto: resposta.texto,
    com_ajuda: resposta.comAjuda,
    ...resposta.medidas(performance.now()),
    itens: resposta.itens.map(({ tipo, posicao, esperada, digitada }) => ({ tipo, posicao, esperada, digitada })),
  };
  salvar(() => enviarJson("/api/tentativas", tentativa));
}

/** Muda de fala e já toca a nova. */
function mudar(movimento) {
  if (!movimento()) return;
  const { id } = video;
  const posicao = pratica.indice;
  if (pratica.fala.id !== undefined) salvar(() => enviarJson(`/api/videos/${id}/posicao`, { posicao }, "PUT"));
  traducaoAberta = false;
  mostrarTraducao();
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
for (const id of ["voltar", "repetir", "avancar", "mostrar", "traduzir"]) {
  $(id).addEventListener("click", () => ACOES[id]());
}
$("velocidade").addEventListener("change", ({ target }) => {
  pratica.definirVelocidade(Number(target.value));
  atualizar();
});
$("digitado").addEventListener("input", ({ target, isComposing }) => {
  // No meio de um acento, mexer no campo o desmancharia; "compositionend" vem depois.
  if (!isComposing) escrever(target);
});
$("digitado").addEventListener("compositionend", ({ target }) => escrever(target));

function escrever(campo) {
  const resposta = respostaAtual();
  // O cursor fica onde estava no texto já arrumado.
  const posicao = resposta.arrumar(campo.value.slice(0, campo.selectionStart)).length;
  resposta.escrever(campo.value);
  if (campo.value !== resposta.texto) {
    campo.value = resposta.texto;
    campo.setSelectionRange(posicao, posicao);
  }
  // Nas lacunas, digitar com a resposta à mostra volta aos pontos.
  if (resposta instanceof Lacunas && pratica.mostrada) {
    pratica.mostrar(false);
    atualizar();
  } else atualizarFala();
}

// O cursor das lacunas é desenhado: acompanha o do campo.
document.addEventListener("selectionchange", () => {
  if (pratica && document.activeElement === $("digitado") && respostaAtual() instanceof Lacunas) atualizarFala();
});
$("fala").addEventListener("click", ({ target }) => {
  const palavra = target.closest("[data-oculta]");
  const resposta = pratica && respostaAtual();
  if (!(resposta instanceof Lacunas)) return;
  $("digitado").focus();
  if (!palavra) return;
  irParaPalavra(resposta, Number(palavra.dataset.oculta));
});

function irParaPalavra(resposta, palavra) {
  const { texto, posicao } = resposta.irPara(palavra);
  resposta.escrever(texto);
  $("digitado").value = texto;
  $("digitado").setSelectionRange(posicao, posicao);
  atualizarFala();
}

$("digitado").addEventListener("beforeinput", (evento) => {
  const resposta = respostaAtual();
  const { selectionStart, selectionEnd } = evento.target;
  if (!(resposta instanceof Lacunas) || selectionStart !== selectionEnd) return;
  const palavra = resposta.passo(evento.inputType, evento.data, selectionStart);
  if (palavra === undefined) return;
  evento.preventDefault();
  if (palavra !== null) irParaPalavra(resposta, palavra);
});

function mudarPreferencia({ target }) {
  guardar(target.id, target.value);
  // Anunciar cada palavra digitada atropelaria o leitor de tela.
  $("fala").ariaLive = corrigeDigitando() || $("modo").value !== "livre" ? "off" : "polite";
  if (!pratica) return;
  if (target.id === "modo") pratica.mostrar(false);
  atualizar();
}

// Escolhida uma opção com o mouse, o foco volta ao ditado. Com o teclado, não: cada
// seta muda a opção, e o foco fugiria na primeira.
let comMouse = false;
document.addEventListener("pointerdown", () => (comMouse = true), true);
document.addEventListener("keydown", () => (comMouse = false), true);
for (const id of ["modo", "quando", "velocidade"]) {
  $(id).addEventListener("change", () => comMouse && pratica && $("digitado").focus());
}
for (const id of ["modo", "quando"]) $(id).addEventListener("change", mudarPreferencia);
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

for (const [id, aceitos] of [["modo", Object.keys(MODOS)], ["quando", QUANDO_CORRIGIR]]) {
  if (aceitos.includes(guardado(id))) $(id).value = guardado(id);
  mudarPreferencia({ target: $(id) });
}

// Os últimos vídeos

async function mostrarRecentes() {
  let videos;
  try {
    videos = await pedir("/api/videos");
  } catch (erro) {
    return falhou(erro);
  }
  $("recentes").hidden = videos.length === 0;
  $("lista").replaceChildren(
    ...videos.map(({ id, titulo, canal, acertadas, total }) => {
      const item = document.createElement("li");
      const ir = Object.assign(document.createElement("a"), { href: `?v=${id}` });
      const andamento = Object.assign(document.createElement("progress"), { max: total, value: acertadas, ariaHidden: "true" });
      ir.append(
        Object.assign(document.createElement("strong"), { textContent: titulo }),
        Object.assign(document.createElement("span"), { textContent: canal }),
        andamento,
        Object.assign(document.createElement("span"), { textContent: `${acertadas} de ${total} falas certas` }),
      );
      item.append(ir);
      return item;
    }),
  );
}

const pedido = new URLSearchParams(location.search).get("v");
if (!pedido) mostrarRecentes();
else {
  const link = `https://www.youtube.com/watch?v=${pedido}`;
  $("link").value = link;
  abrir(link);
}
