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
  #vez = 0;

  static async criar(elemento, video) {
    const player = new Player();
    player.#YT = await carregarApi();
    await new Promise((resolver, rejeitar) => {
      player.#yt = new player.#YT.Player(elemento, {
        videoId: video,
        // Sem os controles e as teclas do player, que disputariam com os nossos.
        playerVars: { playsinline: 1, rel: 0, controls: 0, disablekb: 1, origin: location.origin },
        events: {
          onReady: resolver,
          onError: ({ data }) => {
            rejeitar(new ErroDoPlayer(data));
            player.#avisar({ erro: new ErroDoPlayer(data) });
          },
          onStateChange: ({ data }) => player.#avisar({ estado: data }),
          // O módulo de legendas só existe depois que o vídeo começa.
          onApiChange: () => player.#esconderLegenda(),
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

  /**
   * Toca uma fala e para no fim dela. Chamar de novo cancela a anterior. Devolve
   * "fim", "pausada" ou "cancelada".
   */
  async tocarFala(inicio, fim, velocidade = 1) {
    const { PAUSED, ENDED } = this.#YT.PlayerState;
    this.#vez += 1;
    const vez = this.#vez;
    this.#esconderLegenda();
    this.#yt.setPlaybackRate(velocidade);
    this.#yt.seekTo(inicio, true);
    this.#yt.playVideo();
    return new Promise((resolver, rejeitar) => {
      // Logo depois do pulo, o player ainda pode informar o tempo antigo. O fim
      // só é conferido depois de o tempo ter entrado na fala.
      let entrou = false;
      const encerrar = (acao, valor) => {
        clearInterval(relogio);
        this.#ouvintes.delete(ouvinte);
        acao(valor);
      };
      const ouvinte = ({ estado, erro }) => {
        if (erro) encerrar(rejeitar, erro);
        else if (entrou && estado === PAUSED) encerrar(resolver, "pausada");
        else if (entrou && estado === ENDED) encerrar(resolver, "fim");
      };
      const relogio = setInterval(() => {
        if (vez !== this.#vez) return encerrar(resolver, "cancelada");
        const agora = this.tempo;
        entrou ||= agora >= inicio - 0.5 && agora < fim;
        if (!entrou || !deveParar(agora, fim)) return undefined;
        this.#yt.pauseVideo();
        return encerrar(resolver, "fim");
      }, 10);
      this.#ouvintes.add(ouvinte);
    });
  }

  /** A legenda do próprio player entregaria a resposta. */
  #esconderLegenda() {
    try {
      this.#yt.setOption("captions", "track", {});
      this.#yt.unloadModule("captions");
    } catch {
      // Não documentado: se sumir, o player segue como a pessoa o configurou.
    }
  }

  get duracao() {
    return this.#yt.getDuration();
  }

  /**
   * Toca de `inicio` até `fim` ou até o vídeo acabar, para gravar o som. Ao
   * contrário de tocarTrecho, uma pausa da pessoa, um anúncio ou uma espera de
   * carregamento não encerram. `sinal` é um AbortSignal para parar antes.
   */
  async tocarParaGravar(inicio, fim, sinal) {
    this.#vez += 1;
    this.#yt.setPlaybackRate(1);
    const { ENDED } = this.#YT.PlayerState;
    this.#yt.seekTo(inicio, true);
    this.#yt.playVideo();
    await new Promise((resolver, rejeitar) => {
      const encerrar = (acao, valor) => {
        clearInterval(relogio);
        this.#ouvintes.delete(ouvinte);
        sinal?.removeEventListener("abort", parar);
        acao(valor);
      };
      const parar = () => encerrar(resolver);
      const ouvinte = ({ estado, erro }) => {
        if (erro) encerrar(rejeitar, erro);
        else if (estado === ENDED) encerrar(resolver);
      };
      const relogio = setInterval(() => deveParar(this.tempo, fim) && encerrar(resolver), 100);
      this.#ouvintes.add(ouvinte);
      sinal?.addEventListener("abort", parar);
      if (sinal?.aborted) parar();
    });
    this.#yt.pauseVideo();
  }

  /** Pausa e espera o som acabar de sair. */
  async pausar() {
    this.#yt.pauseVideo();
    await esperar(600);
  }

  get som() {
    return { volume: this.#yt.getVolume(), mudo: this.#yt.isMuted() };
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
