// A tela: abre o vídeo, consegue o texto e conduz a prática.

import { enviarJson, pedir, transcrever } from "./api.js";
import { acaoDaTecla } from "./atalhos.js";
import { separar } from "./correcao.js";
import { criar, desenharErro, desenharPalavra, marcar } from "./desenho.js";
import { QUANDO_CORRIGIR, Resposta } from "./ditado.js";
import { Gravacao, pedirSomDaAba } from "./gravador.js";
import { escreverLetreiro, mostrarRecentes, mostrarResumo, mostrarSemana } from "./inicio.js";
import { Lacunas, sortearOcultas } from "./lacunas.js";
import { Player } from "./player.js";
import { Pratica, Sequencia, duracaoDaFita, falaEm, fita, proximaQueFalta, relogio } from "./pratica.js";
import { tocar } from "./sons.js";

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

// As opções em botões: modo, quando corrigir e velocidade.
const escolhas = (nome) => [...document.querySelectorAll(`input[name="${nome}"]`)];
const escolhido = (nome) => escolhas(nome).find((opcao) => opcao.checked).value;

function escolher(nome, valor) {
  const opcao = escolhas(nome).find(({ value }) => value === valor);
  if (opcao) opcao.checked = true;
}

let video; // o que o servidor disse do vídeo aberto
let player;
let pratica;
let traducaoAberta = false;
const sequencia = new Sequencia();
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
    $("ambiente").style.backgroundImage = `url("https://i.ytimg.com/vi/${achado.id}/hqdefault.jpg")`;
    if (!achado.incorporavel) {
      avisar("O dono deste vídeo só permite tocá-lo no site do YouTube. O typelead ainda não consegue praticar com ele.", true);
      return;
    }

    irParaTela("sala");
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
  $("ambiente").style.backgroundImage = "";
  for (const id of ["sem-legenda", "pratica", "fita"]) $(id).hidden = true;
  irParaTela("inicio");
}

/** "inicio" ou "sala". O campo do link vai junto: grande no início, no topo na sala. */
function irParaTela(tela) {
  document.body.dataset.tela = tela;
  $("inicio").hidden = tela !== "inicio";
  $("sala").hidden = tela !== "sala";
  $(tela === "inicio" ? "vaga-inicio" : "vaga-topo").append($("abrir"));
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
  $("legenda").hidePopover();
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
  traducaoAberta = false;
  mostrarTraducao();
  montarFita();
  atualizar();
  $("digitado").focus();
}

/** Criada na primeira vez e guardada: as palavras sorteadas não mudam ao voltar. */
function respostaAtual() {
  const doModo = respostas[escolhido("modo")];
  doModo[pratica.indice] ??= MODOS[escolhido("modo")](pratica.fala);
  return doModo[pratica.indice];
}
const corrigeDigitando = () => escolhido("quando") === "digitando";

function montarFita() {
  const duracao = video.duracao || player.duracao;
  const blocos = fita(pratica.falas, duracao).map(({ esquerda, largura, altura }, indice) => {
    const bloco = document.createElement("button");
    bloco.type = "button";
    // Só a atual entra no Tab: centenas de paradas impediriam de passar dali.
    bloco.tabIndex = -1;
    bloco.style.left = `${esquerda}%`;
    bloco.style.width = `${largura}%`;
    bloco.style.setProperty("--altura", `${altura}%`);
    bloco.dataset.indice = indice;
    const rotulo = `Fala ${indice + 1}, em ${relogio(pratica.falas[indice].inicio)}`;
    bloco.title = rotulo;
    bloco.setAttribute("aria-label", rotulo);
    bloco.toggleAttribute("data-acertada", pratica.falas[indice].acertada);
    return bloco;
  });
  $("fita").replaceChildren(...blocos, criar("span", "", { className: "agulha", ariaHidden: "true" }));
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
  escolher("velocidade", String(pratica.velocidade));

  if ($("digitado").value !== respostaAtual().texto) $("digitado").value = respostaAtual().texto;
  atualizarFala();

  for (const bloco of blocosDaFita()) {
    const atual = Number(bloco.dataset.indice) === pratica.indice;
    bloco.toggleAttribute("aria-current", atual);
    bloco.tabIndex = atual ? 0 : -1;
  }
}

const blocosDaFita = () => [...$("fita").querySelectorAll("button")];

/** O texto da fala: escondido, corrigido ou à mostra. */
function atualizarFala() {
  const resposta = respostaAtual();
  const { mostrada } = pratica;
  $("placar").textContent = placar(resposta, mostrada);
  $("placar").classList.toggle("certo", resposta.acertou);
  mostrarErros(resposta);

  const comLacunas = resposta instanceof Lacunas;
  $("fala").classList.toggle("com-lacunas", comLacunas && !resposta.semPalavras);
  $("digitado").classList.toggle("oculto", comLacunas);
  if (comLacunas && !resposta.semPalavras) return desenharLacunas(resposta, mostrada);

  desenhado = undefined;
  $("fala").classList.remove("acertou", "errou");
  let itens = resposta.itens;
  if (corrigeDigitando() && !resposta.conferida && !mostrada) itens = resposta.parcial();
  if (itens?.length === 0) itens = null;

  const palavras = pratica.quantasPalavras;
  $("fala").classList.toggle("escondida", !itens && !mostrada);
  if (itens) $("fala").replaceChildren(...itens.flatMap((item, i) => [marcar(item, mostrada, 3 * i), " "]));
  else if (mostrada) $("fala").textContent = pratica.fala.texto;
  else $("fala").textContent = `${palavras} ${palavras === 1 ? "palavra" : "palavras"}. Ouça quantas vezes precisar.`;
  // O leitor de tela precisa saber que o texto é em inglês.
  if (itens || mostrada) $("fala").lang = "en";
  else $("fala").removeAttribute("lang");
}

// Desenhar de novo o que não mudou recomeçaria as animações.
let desenhado;
let nova = null; // a letra recém-digitada

/** A fala com pontos no lugar das letras escondidas. */
function desenharLacunas(resposta, mostrada) {
  const cursor = resposta.cursor($("digitado").selectionStart);
  const vista = resposta.vista(corrigeDigitando());
  const estado = JSON.stringify([resposta.rodada, vista, cursor, mostrada]);
  if (estado === desenhado) return;
  desenhado = estado;
  // Com a classe, as letras novas repetiriam a onda da correção.
  $("fala").classList.remove("acertou", "errou");

  let ordem = 0;
  const partes = vista.flatMap((palavra) => {
    const desenhada = desenharPalavra(palavra, { mostrada, cursor, itens: resposta.itens, ordem, nova });
    ordem += palavra.letras ?? 0;
    return palavra.colada ? [desenhada] : [" ", desenhada];
  });
  nova = null;
  $("fala").classList.remove("escondida");
  $("fala").lang = "en";
  $("fala").replaceChildren(...partes);
}

/** A onda que percorre as letras quando a fala é conferida. */
function animarCorrecao(classe) {
  const fala = $("fala");
  fala.classList.remove("acertou", "errou");
  // Ler a posição obriga o navegador a ver a classe sair antes de ela voltar.
  void fala.offsetWidth;
  fala.classList.add(classe);
}

function placar(resposta, mostrada) {
  if (!resposta.conferida) return "";
  const { certas, total, sobras } = resposta.resumo;
  const seguir = pratica.ultima ? "É a última fala do vídeo." : "Enter vai para a próxima.";
  if (resposta.acertou) return `Tudo certo${resposta.comAjuda ? ", com o texto à mostra" : ""}. ${seguir}`;
  const pontos = `${certas} de ${total} certas${sobras ? `, ${sobras} a mais` : ""}.`;
  return mostrada ? `${pontos} ${seguir}` : `${pontos} Corrija e aperte Enter, ou só Enter para ver a resposta.`;
}

let vezDeOuvir = 0;

async function ouvir() {
  const { indice } = pratica;
  const { inicio, fim } = pratica.fala;
  vezDeOuvir += 1;
  const vez = vezDeOuvir;
  avisar("");
  respostaAtual().ouviu(pratica.velocidade);
  document.body.toggleAttribute("data-tocando", true);
  acompanhar(vez);
  try {
    const resultado = await player.tocarFala(inicio, fim, pratica.velocidade);
    if (resultado === "fim") blocosDaFita()[indice]?.setAttribute("data-ouvida", "");
  } catch (erro) {
    falhou(erro);
  } finally {
    if (vez === vezDeOuvir) document.body.removeAttribute("data-tocando");
  }
}

/** A agulha da fita segue o vídeo enquanto a fala toca. */
function acompanhar(vez) {
  if (vez !== vezDeOuvir || !player || !pratica || !document.body.hasAttribute("data-tocando")) return;
  const total = duracaoDaFita(pratica.falas, video.duracao || player.duracao);
  $("fita").style.setProperty("--agulha", `${Math.min(100, (100 * player.tempo) / total)}%`);
  requestAnimationFrame(() => acompanhar(vez));
}

const ACOES = {
  voltar: () => mudar(() => pratica.voltar()),
  avancar: () => mudar(() => pratica.avancar()),
  repetir: ouvir,
  mostrar: () => {
    pratica.mostrar(!pratica.mostrada);
    const resposta = respostaAtual();
    if (pratica.mostrada) {
      resposta.mostrou();
      if (resposta.itens && !resposta.acertou) salvarDesistencia(resposta);
    }
    atualizar();
  },
  conferir: () => {
    const resposta = respostaAtual();
    resposta.conferir();
    const { acertou } = resposta;
    if (acertou && !resposta.comAjuda) {
      pratica.fala.acertada = true;
      blocosDaFita()[pratica.indice].setAttribute("data-acertada", "");
    }
    const cresceu = sequencia.registrar(resposta);
    mostrarSequencia(cresceu);
    atualizar();
    animarCorrecao(acertou ? "acertou" : "errou");
    if (sonsLigados()) tocar(acertou ? "acerto" : "erro");
    salvarTentativa(resposta);
  },
  traduzir: () => {
    traducaoAberta = !traducaoAberta;
    if (traducaoAberta) respostaAtual().traduziu();
    mostrarTraducao();
  },
  enter: () => {
    const passo = respostaAtual().proximoPasso(pratica.mostrada);
    if (passo === "avancar" && pratica.ultima) chegarAoFim();
    else ACOES[passo]();
  },
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
    modo: escolhido("modo"),
    corrigir: escolhido("quando"),
    texto: resposta.texto,
    com_ajuda: resposta.comAjuda,
    ...resposta.medidas(performance.now()),
    itens: resposta.itens.map(({ tipo, posicao, esperada, digitada }) => ({ tipo, posicao, esperada, digitada })),
  };
  receberErros(resposta, () => enviarJson("/api/tentativas", tentativa));
}

function salvarDesistencia(resposta) {
  if (pratica.fala.id === undefined) return;
  const { repeticoes, velocidade, traduziu } = resposta.medidas(performance.now());
  receberErros(resposta, () =>
    enviarJson(`/api/rodadas/${resposta.rodada}/desistencia`, { repeticoes, velocidade, traduziu }, "PUT"),
  );
}

async function receberErros(resposta, pedido) {
  const salvo = await salvar(pedido);
  if (!salvo) return;
  resposta.erros = salvo.erros;
  if (salvo.resumo) mostrarResumo(salvo.resumo);
  if (pratica && respostaAtual() === resposta) mostrarErros(resposta);
}

/** Por que errou cada palavra; só com a fala resolvida, para não entregar a resposta. */
function mostrarErros(resposta) {
  const resolvida = resposta.acertou || (pratica.mostrada && resposta.conferida);
  const erros = resolvida ? resposta.erros.filter((erro) => erro.diagnostico) : [];
  // Os que dizem algo vêm primeiro.
  erros.sort((a, b) => (a.diagnostico === "indefinido") - (b.diagnostico === "indefinido"));
  $("motivos").hidden = erros.length === 0;
  $("erros").replaceChildren(...erros.map((erro) => desenharErro(erro, (tipo) => trocarDiagnostico(erro, tipo))));
}

function trocarDiagnostico(erro, tipo) {
  erro.corrigido = tipo;
  salvar(() => enviarJson(`/api/erros/${erro.id}/diagnostico`, { tipo }, "PUT"));
  if (comMouse) $("digitado").focus();
}

// Sequência e fim do vídeo

function mostrarSequencia(cresceu) {
  $("sequencia").hidden = sequencia.atual < 2;
  $("sequencia-numero").textContent = sequencia.atual;
  if (!cresceu) return;
  $("sequencia").classList.remove("pulsou");
  void $("sequencia").offsetWidth;
  $("sequencia").classList.add("pulsou");
}

function chegarAoFim() {
  const total = pratica.falas.length;
  const certas = pratica.falas.filter((fala) => fala.acertada).length;
  const falta = proximaQueFalta(pratica.falas, pratica.indice);
  $("fim-titulo").textContent = certas === total ? "Vídeo completo" : "Você chegou ao fim";
  $("fim-texto").textContent =
    certas === total
      ? `Você acertou as ${total} falas sem ver o texto.`
      : `Você acertou ${certas} de ${total} falas sem ver o texto.`;
  $("fim-falta").hidden = falta === -1;
  $("fim").showModal();
  if (sonsLigados()) tocar("fim");
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
for (const opcao of escolhas("velocidade")) {
  opcao.addEventListener("change", () => {
    pratica.definirVelocidade(Number(opcao.value));
    atualizar();
  });
}
$("fim-falta").addEventListener("click", () => {
  $("fim").close();
  mudar(() => pratica.irPara(proximaQueFalta(pratica.falas, pratica.indice)));
});
$("fim-fechar").addEventListener("click", () => $("fim").close());
$("buscar-de-novo").addEventListener("click", () => {
  $("legenda").hidePopover();
  abrir(`https://www.youtube.com/watch?v=${video.id}`, true);
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
  const antes = resposta.texto.length;
  resposta.escrever(campo.value);
  if (resposta instanceof Lacunas && resposta.texto.length === antes + 1) {
    const { palavra, letra } = resposta.cursor(posicao);
    nova = { palavra, letra: letra - 1 };
  }
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
  guardar(target.name, target.value);
  anunciarSePuder();
  if (!pratica) return;
  if (target.name === "modo") pratica.mostrar(false);
  atualizar();
}

/** Anunciar cada palavra digitada atropelaria o leitor de tela. */
function anunciarSePuder() {
  $("fala").ariaLive = corrigeDigitando() || escolhido("modo") !== "livre" ? "off" : "polite";
}

// Escolhida uma opção com o mouse, o foco volta ao ditado. Com o teclado, não: cada
// seta muda a opção, e o foco fugiria na primeira.
let comMouse = false;
document.addEventListener("pointerdown", () => (comMouse = true), true);
document.addEventListener("keydown", () => (comMouse = false), true);
for (const opcao of [...escolhas("modo"), ...escolhas("quando")]) opcao.addEventListener("change", mudarPreferencia);
for (const nome of ["modo", "quando", "velocidade"]) {
  for (const opcao of escolhas(nome)) {
    // O clique no rótulo só passa o foco à opção depois do "change".
    opcao.addEventListener("click", () => comMouse && pratica && $("digitado").focus());
  }
}

const sonsLigados = () => $("sons").getAttribute("aria-pressed") === "true";

$("sons").addEventListener("click", () => {
  $("sons").setAttribute("aria-pressed", String(!sonsLigados()));
  guardar("sons", String(sonsLigados()));
  if (sonsLigados()) tocar("acerto");
});

$("fita").addEventListener("click", ({ target }) => {
  if (target.dataset.indice) mudar(() => pratica.irPara(Number(target.dataset.indice)));
});

// Clicado com o mouse, o botão devolve o foco ao ditado. Pelo teclado, o foco
// continua onde está.
document.addEventListener("click", (evento) => {
  if (pratica && evento.detail > 0 && evento.target.closest("#pratica button, #fita button, #sons")) $("digitado").focus();
});

function onde(alvo) {
  if (alvo.id === "digitado") return "ditado";
  if (alvo.matches("input, textarea, select")) return "campo";
  return alvo.matches("button, a") ? "botao" : undefined;
}

document.addEventListener("keydown", (evento) => {
  if (!pratica || evento.defaultPrevented || $("fim").open) return;
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

for (const [nome, aceitos] of [["modo", Object.keys(MODOS)], ["quando", QUANDO_CORRIGIR]]) {
  if (aceitos.includes(guardado(nome))) escolher(nome, guardado(nome));
}
if (guardado("sons") === "false") $("sons").setAttribute("aria-pressed", "false");
anunciarSePuder();

// Ao abrir a página

async function comecar() {
  const pedido = new URLSearchParams(location.search).get("v");
  if (pedido) {
    const link = `https://www.youtube.com/watch?v=${pedido}`;
    $("link").value = link;
    abrir(link);
  } else escreverLetreiro();
  try {
    const [resumo, videos] = await Promise.all([pedir("/api/resumo"), pedir("/api/videos")]);
    mostrarResumo(resumo);
    mostrarSemana(resumo);
    mostrarRecentes(videos);
  } catch (erro) {
    falhou(erro);
  }
}

comecar();
