// Grava o som da aba e anota, a cada instante, em que ponto estava o vídeo.

const FORMATO = "audio/webm;codecs=opus";
const INTERVALO_DAS_MARCAS = 200;
const ESPERA_PARA_COMECAR = 5000;

/**
 * Pede o som desta aba. Precisa ser chamado direto de um clique, e o Chrome
 * mostra a própria janela de autorização.
 */
export async function pedirSomDaAba() {
  // O Chrome exige pedir a imagem junto; só a faixa de som é usada. Os filtros
  // de voz ficam desligados: o de eco existe para apagar o som que sai do PC.
  const midia = await navigator.mediaDevices.getDisplayMedia({
    video: true,
    audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
    preferCurrentTab: true,
  });
  const [faixa] = midia.getAudioTracks();
  const encerrar = () => midia.getTracks().forEach((parte) => parte.stop());
  if (!faixa) {
    encerrar();
    throw new Error("A aba foi compartilhada sem o som. Tente de novo com o som marcado.");
  }
  return { faixa, encerrar };
}

export class Gravacao {
  #contexto;
  #gravador;
  #pedacos = [];
  #marcas = [];
  #relogio;
  #comeco;
  #lerTempo;

  /** lerTempo devolve o instante atual do vídeo, em segundos. */
  constructor(faixa, lerTempo) {
    this.#lerTempo = lerTempo;
    this.#contexto = new AudioContext();
    const saida = this.#contexto.createMediaStreamDestination();
    this.#contexto.createMediaStreamSource(new MediaStream([faixa])).connect(saida);
    // Uma aba em silêncio pode não mandar dado nenhum: o gravador nem começaria,
    // e um buraco no meio encurtaria a gravação. Esta fonte, muda, mantém o som
    // contínuo do começo ao fim.
    const muda = this.#contexto.createConstantSource();
    muda.offset.value = 0;
    muda.connect(saida);
    muda.start();

    this.#gravador = new MediaRecorder(saida.stream, {
      mimeType: FORMATO,
      audioBitsPerSecond: 96000,
    });
    this.#gravador.ondataavailable = ({ data }) => data.size && this.#pedacos.push(data);
  }

  async iniciar() {
    await this.#contexto.resume();
    await new Promise((resolver, rejeitar) => {
      const relogio = setTimeout(
        () => rejeitar(new Error("O navegador não começou a gravar.")),
        ESPERA_PARA_COMECAR,
      );
      this.#gravador.onstart = () => {
        clearTimeout(relogio);
        resolver();
      };
      this.#gravador.start(1000);
    });
    // O relógio do contexto é o mesmo do som gravado; o do PC poderia desviar.
    this.#comeco = this.#contexto.currentTime;
    this.#marcar();
    this.#relogio = setInterval(() => this.#marcar(), INTERVALO_DAS_MARCAS);
  }

  #marcar() {
    const gravado = this.#contexto.currentTime - this.#comeco;
    this.#marcas.push({ gravado, video: Math.max(0, this.#lerTempo() || 0) });
  }

  async terminar() {
    clearInterval(this.#relogio);
    this.#marcar();
    if (this.#gravador.state !== "inactive") {
      const parou = new Promise((resolver) => (this.#gravador.onstop = resolver));
      this.#gravador.stop();
      await parou;
    }
    await this.#contexto.close();
    return { som: new Blob(this.#pedacos, { type: FORMATO }), marcas: this.#marcas };
  }
}
