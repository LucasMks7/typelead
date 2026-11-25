// Sons curtos de acerto e erro, gerados na hora: nenhum arquivo de áudio.

// Cada nota: frequência em Hz, quando começa e quanto dura, em segundos.
const SONS = {
  acerto: { onda: "sine", notas: [[659, 0, 0.12], [988, 0.09, 0.22]] },
  erro: { onda: "triangle", notas: [[185, 0, 0.14]] },
  fim: { onda: "sine", notas: [[523, 0, 0.16], [659, 0.12, 0.16], [784, 0.24, 0.34]] },
};
const VOLUME = 0.07;

let contexto;

export function tocar(nome) {
  const { onda, notas } = SONS[nome];
  try {
    contexto ??= new AudioContext();
    contexto.resume();
    const agora = contexto.currentTime;
    for (const [frequencia, quando, duracao] of notas) {
      const oscilador = new OscillatorNode(contexto, { type: onda, frequency: frequencia });
      const ganho = new GainNode(contexto, { gain: 0 });
      // Subir e descer aos poucos evita o estalo.
      ganho.gain.setValueAtTime(0, agora + quando);
      ganho.gain.linearRampToValueAtTime(VOLUME, agora + quando + 0.01);
      ganho.gain.exponentialRampToValueAtTime(0.0001, agora + quando + duracao);
      oscilador.connect(ganho).connect(contexto.destination);
      oscilador.start(agora + quando);
      oscilador.stop(agora + quando + duracao);
    }
  } catch {
    // Sem saída de som, a prática segue.
  }
}
