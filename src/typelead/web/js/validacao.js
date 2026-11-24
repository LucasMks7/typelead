// Página de validação: mede a precisão do player e testa a gravação do som da aba.

import { transcrever } from "./api.js";
import { Gravacao, pedirSomDaAba } from "./gravador.js";
import { julgarSom, resumir, volume } from "./medidas.js";
import { Player, esperar } from "./player.js";

const $ = (id) => document.getElementById(id);
const ms = (segundos) => Math.round(segundos * 1000);

let player;
let videoAtual;

function escrever(id, texto) {
  $(id).textContent = texto;
}

async function prepararPlayer() {
  const video = $("video").value.trim();
  if (!/^[\w-]{11}$/.test(video)) throw new Error("O identificador tem 11 caracteres.");
  if (player && video === videoAtual) return player;
  player?.destruir();
  player = undefined;
  // O player troca este elemento por um iframe, por isso é recriado.
  const alvo = document.createElement("div");
  $("palco").replaceChildren(alvo);
  player = await Player.criar(alvo, video);
  videoAtual = video;
  return player;
}

function lerTrecho() {
  const inicio = Number($("inicio").value);
  const fim = Number($("fim").value);
  if (!(inicio >= 0 && fim > inicio)) throw new Error("O fim precisa vir depois do início.");
  return { inicio, fim, antecipacao: Number($("antecipacao").value) / 1000 };
}

async function comBotoesTravados(id, acao) {
  const botoes = document.querySelectorAll("button");
  botoes.forEach((botao) => (botao.disabled = true));
  try {
    await acao();
  } catch (erro) {
    escrever(id, `Falhou: ${erro.message}`);
  } finally {
    botoes.forEach((botao) => (botao.disabled = false));
  }
}

$("medir").addEventListener("click", () =>
  comBotoesTravados("resultado-trecho", async () => {
    const { inicio, fim, antecipacao } = lerTrecho();
    const vezes = Number($("vezes").value);
    const p = await prepararPlayer();
    p.silenciar($("mudo").checked);
    const comecos = [];
    const paradas = [];
    for (let i = 0; i < vezes; i += 1) {
      escrever("resultado-trecho", `Repetição ${i + 1} de ${vezes}…`);
      const { comecou, parou } = await p.tocarTrecho(inicio, fim, antecipacao);
      comecos.push(ms(comecou - inicio));
      paradas.push(ms(parou - fim));
    }
    // Com a aba escondida, o navegador atrasa os relógios e a medida não vale.
    const resultado = {
      abaVisivel: document.visibilityState === "visible",
      inicio,
      fim,
      antecipacaoMs: ms(antecipacao),
      comecoMs: resumir(comecos),
      paradaMs: resumir(paradas),
      paradas,
    };
    escrever("resultado-trecho", JSON.stringify(resultado, null, 2));
  }),
);

/** Mede o volume até a promessa terminar e devolve o resumo. */
async function ouvirAte(analisador, promessa) {
  const bloco = new Float32Array(analisador.fftSize);
  const volumes = [];
  let terminou = false;
  const fim = promessa.finally(() => (terminou = true));
  while (!terminou) {
    await Promise.race([fim, esperar(50)]);
    analisador.getFloatTimeDomainData(bloco);
    volumes.push(volume(bloco));
  }
  await fim;
  return resumir(volumes);
}

/** Toca um tom baixo da própria página, como controle do teste. */
async function tocarTom(contexto, duracao) {
  const ganho = contexto.createGain();
  ganho.gain.value = 0.03;
  const tom = contexto.createOscillator();
  tom.frequency.value = 440;
  tom.connect(ganho).connect(contexto.destination);
  tom.start();
  await esperar(duracao);
  tom.stop();
  tom.disconnect();
  await esperar(200);
}

$("gravar").addEventListener("click", () =>
  comBotoesTravados("resultado-som", async () => {
    escrever("resultado-som", "Escolha esta aba, deixe o som marcado e não mexa no vídeo.");
    const { faixa, encerrar } = await pedirSomDaAba();
    const contexto = new AudioContext();
    try {
      await contexto.resume();
      const analisador = contexto.createAnalyser();
      contexto.createMediaStreamSource(new MediaStream([faixa])).connect(analisador);

      const { inicio, fim } = lerTrecho();
      const p = await prepararPlayer();
      await p.pausar();
      p.silenciar(false);

      escrever("resultado-som", "1/3 · Medindo o silêncio…");
      const parado = await ouvirAte(analisador, esperar(1500));
      escrever("resultado-som", "2/3 · Tocando o tom de controle…");
      const tom = await ouvirAte(analisador, tocarTom(contexto, 1000));
      escrever("resultado-som", "3/3 · Tocando o trecho do vídeo…");
      const video = await ouvirAte(analisador, p.tocarTrecho(inicio, fim));

      const resultado = {
        somDoPlayerGravado: julgarSom({ parado, tom, video }),
        medidas: { parado, tom, video },
        player: p.som,
        taxa: contexto.sampleRate,
      };
      escrever("resultado-som", JSON.stringify(resultado, null, 2));
    } finally {
      encerrar();
      await contexto.close();
    }
  }),
);

$("transcrever").addEventListener("click", () =>
  comBotoesTravados("resultado-transcricao", async () => {
    escrever("resultado-transcricao", "Escolha esta aba e deixe o som marcado.");
    const { faixa, encerrar } = await pedirSomDaAba();
    let gravado;
    try {
      const { inicio, fim } = lerTrecho();
      const p = await prepararPlayer();
      p.silenciar(false);
      const gravacao = new Gravacao(faixa, () => p.tempo);
      await gravacao.iniciar();
      escrever("resultado-transcricao", "Gravando o trecho…");
      await p.tocarParaGravar(inicio, fim);
      gravado = await gravacao.terminar();
    } finally {
      encerrar();
    }
    const falas = await transcrever(gravado, ({ estado, progresso }) =>
      escrever("resultado-transcricao", `${estado} ${Math.round(progresso * 100)}%`),
    );
    const linhas = falas.map((f) => `${f.inicio.toFixed(2)} → ${f.fim.toFixed(2)}  ${f.texto}`);
    escrever("resultado-transcricao", linhas.join("
"));
  }),
);
