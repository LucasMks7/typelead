// Página de validação: mede a precisão do player e testa a gravação do som da aba.

import { resumir, volume } from "./medidas.js";
import { Player, esperar } from "./player.js";

// Volume abaixo disto é tratado como silêncio.
const SILENCIO = 0.001;

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

$("gravar").addEventListener("click", () =>
  comBotoesTravados("resultado-som", async () => {
    escrever("resultado-som", "Escolha esta aba e deixe marcado o compartilhamento do som.");
    // O Chrome exige pedir a imagem junto; só a faixa de som é usada.
    const midia = await navigator.mediaDevices.getDisplayMedia({
      video: true,
      audio: true,
      preferCurrentTab: true,
    });
    const contexto = new AudioContext();
    try {
      const [faixa] = midia.getAudioTracks();
      if (!faixa) throw new Error("a aba foi compartilhada sem o som.");
      await contexto.resume();
      const analisador = contexto.createAnalyser();
      contexto.createMediaStreamSource(new MediaStream([faixa])).connect(analisador);
      const bloco = new Float32Array(analisador.fftSize);
      const ouvir = async (duracao) => {
        const volumes = [];
        for (let t = 0; t < duracao; t += 50) {
          analisador.getFloatTimeDomainData(bloco);
          volumes.push(volume(bloco));
          await esperar(50);
        }
        return resumir(volumes);
      };

      const p = await prepararPlayer();
      p.silenciar(false);
      const { inicio, fim } = lerTrecho();
      // O silêncio antes de tocar é a referência: sem ele, um som qualquer do
      // PC poderia passar por som do vídeo.
      escrever("resultado-som", "Medindo o silêncio antes de tocar…");
      const antes = await ouvir(1500);
      escrever("resultado-som", "Tocando o trecho e medindo o som…");
      const [durante] = await Promise.all([
        ouvir((fim - inicio) * 1000),
        p.tocarTrecho(inicio, fim),
      ]);
      const ouviu = antes.maximo < SILENCIO && durante.maximo > SILENCIO;
      escrever(
        "resultado-som",
        JSON.stringify({ somDoPlayerGravado: ouviu, taxa: contexto.sampleRate, antes, durante }, null, 2),
      );
    } finally {
      midia.getTracks().forEach((faixa) => faixa.stop());
      await contexto.close();
    }
  }),
);
