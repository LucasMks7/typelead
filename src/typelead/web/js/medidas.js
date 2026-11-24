// Contas puras, sem navegador, para poderem ser testadas com `node --test`.

/** Resume uma lista de números. Devolve null se ela estiver vazia. */
export function resumir(valores) {
  if (valores.length === 0) return null;
  const ordenados = [...valores].sort((a, b) => a - b);
  const meio = Math.floor(ordenados.length / 2);
  const mediana =
    ordenados.length % 2 === 1 ? ordenados[meio] : (ordenados[meio - 1] + ordenados[meio]) / 2;
  return {
    n: ordenados.length,
    minimo: ordenados[0],
    mediana,
    maximo: ordenados[ordenados.length - 1],
  };
}

/** Volume médio (RMS) de um bloco de som, de 0 (silêncio) a 1. */
export function volume(amostras) {
  if (amostras.length === 0) return 0;
  let soma = 0;
  for (const amostra of amostras) soma += amostra * amostra;
  return Math.sqrt(soma / amostras.length);
}

/** O trecho já deve parar? A antecipação compensa a demora da pausa. */
export function deveParar(agora, fim, antecipacao = 0) {
  return agora >= fim - antecipacao;
}

// Volume abaixo disto é tratado como silêncio.
export const SILENCIO = 0.001;

/**
 * Interpreta o teste do som da aba a partir de três resumos de volume: com tudo
 * parado, com um tom da própria página e com o vídeo tocando.
 *
 * "Não gravou" só é afirmado quando o teste era capaz de ouvir: um silêncio
 * prévio de verdade e um tom de controle que chegou. Fora disso, é inconclusivo.
 */
export function julgarSom({ parado, tom, video }) {
  if (!parado || !tom || !video) {
    return { resposta: "inconclusivo", motivo: "Faltou uma das medidas." };
  }
  if (parado.mediana >= SILENCIO) {
    return { resposta: "inconclusivo", motivo: "Já havia som na aba antes de tocar o vídeo." };
  }
  if (video.mediana >= SILENCIO) {
    return { resposta: "sim", motivo: "O som apareceu na gravação quando o vídeo tocou." };
  }
  if (tom.mediana < SILENCIO) {
    return {
      resposta: "inconclusivo",
      motivo: "Nem o tom da própria página chegou: outra aba escolhida ou som não compartilhado.",
    };
  }
  return { resposta: "não", motivo: "O tom da página chegou, mas o som do vídeo não." };
}
