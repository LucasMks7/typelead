// Conversa com o player oficial do YouTube (IFrame Player API).

import { deveParar } from "./medidas.js";

// O YouTube também devolve 150 para um vídeo que não existe (docs/player.md).
const NAO_TOCA_AQUI =
  "Este vídeo não toca fora do YouTube: o dono não permite, ou o vídeo não existe mais.";

const ERROS = {
  2: "O identificador do vídeo não é válido.",
  5: "O YouTube não conseguiu tocar este vídeo no player.",
  100: "O vídeo não existe mais ou é privado.",
  101: NAO_TOCA_AQUI,
  150: NAO_TOCA_AQUI,
  153: "O YouTube não recebeu o endereço desta página (Referer).",
};

export class ErroDoPlayer extends Error {
  constructor(codigo) {
    super(ERROS[codigo] ?? `O player do YouTube falhou (código ${codigo}).`);
    this.codigo = codigo;
  }
}

let apiCarregada;

function carregarApi() {
  apiCarregada ??= new Promise((resolver, rejeitar) => {
    window.onYouTubeIframeAPIReady = () => resolver(window.YT);
    const script = document.createElement("script");
    script.src = "https://www.youtube.com/iframe_api";
    script.onerror = () => rejeitar(new Error("Não foi possível carregar o player do YouTube."));
    document.head.append(script);
  });
  return apiCarregada;
}

export const esperar = (ms) => new Promise((resolver) => setTimeout(resolver, ms));

export class Player {
  #yt;
  #YT;
  #ouvintes = new Set();

  static async criar(elemento, video) {
    const player = new Player();
    player.#YT = await carregarApi();
    await new Promise((resolver, rejeitar) => {
      player.#yt = new player.#YT.Player(elemento, {
        videoId: video,
        playerVars: { playsinline: 1, rel: 0, origin: location.origin },
        events: {
          onReady: resolver,
          onError: ({ data }) => {
            rejeitar(new ErroDoPlayer(data));
            player.#avisar({ erro: new ErroDoPlayer(data) });
          },
          onStateChange: ({ data }) => player.#avisar({ estado: data }),
        },
      });
    });
    return player;
  }

  get tempo() {
    return this.#yt.getCurrentTime();
  }

  silenciar(sim) {
    if (sim) this.#yt.mute();
    else this.#yt.unMute();
  }

  destruir() {
    this.#yt.destroy();
  }

  #avisar(evento) {
    for (const ouvinte of [...this.#ouvintes]) ouvinte(evento);
  }

  /** Espera um dos estados; falha se o player der erro ou demorar demais. */
  #ateEstado(estados, limite = 15000) {
    return new Promise((resolver, rejeitar) => {
      const encerrar = (acao, valor) => {
        clearTimeout(relogio);
        this.#ouvintes.delete(ouvinte);
        acao(valor);
      };
      const ouvinte = ({ estado, erro }) => {
        if (erro) encerrar(rejeitar, erro);
        else if (estados.includes(estado)) encerrar(resolver, estado);
      };
      const relogio = setTimeout(
        () => encerrar(rejeitar, new Error("O player não respondeu a tempo.")),
        limite,
      );
      this.#ouvintes.add(ouvinte);
    });
  }

  /**
   * Toca de `inicio` a `fim`, em segundos, e devolve onde o player começou e
   * onde de fato parou.
   */
  async tocarTrecho(inicio, fim, antecipacao = 0) {
    const { PLAYING, PAUSED, ENDED } = this.#YT.PlayerState;
    const tocando = this.#ateEstado([PLAYING]);
    this.#yt.seekTo(inicio, true);
    this.#yt.playVideo();
    await tocando;
    const comecou = this.tempo;

    const parado = this.#ateEstado([PAUSED, ENDED], (fim - inicio) * 1000 + 15000);
    const relogio = setInterval(() => {
      if (!deveParar(this.tempo, fim, antecipacao)) return;
      clearInterval(relogio);
      this.#yt.pauseVideo();
    }, 10);
    try {
      await parado;
    } finally {
      clearInterval(relogio);
    }
    // O tempo informado só assenta um pouco depois da pausa.
    await esperar(600);
    return { comecou, parou: this.tempo };
  }
}
