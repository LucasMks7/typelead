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
