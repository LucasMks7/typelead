// Traduz uma tecla na ação da prática. Puro, para ser testado sem navegador.

// Um Map, e não um objeto, que herdaria nomes como "toString".
const ACOES = new Map([
  ["ArrowUp", "voltar"],
  ["ArrowDown", "avancar"],
  ["Enter", "mostrar"],
  [" ", "repetir"],
  ["-", "maisDevagar"],
  ["+", "maisRapido"],
  ["=", "maisRapido"],
]);

// Dentro de um campo, estas escrevem texto; com Ctrl, continuam sendo atalho.
const ESCREVEM = new Set([" ", "-", "+", "="]);

/**
 * Devolve a ação da tecla, ou null.
 * `emCampo`: o foco está em um campo de texto. `emBotao`: em algo que já
 * responde a Enter e espaço.
 */
export function acaoDaTecla({ key, ctrlKey, altKey, metaKey, isComposing }, { emCampo, emBotao } = {}) {
  if (altKey || metaKey || isComposing) return null;
  const acao = ACOES.get(key);
  if (!acao) return null;
  if (ctrlKey) return key === " " ? acao : null; // Ctrl com - e + é o zoom.
  if (emCampo && ESCREVEM.has(key)) return null;
  if (emBotao && (key === "Enter" || key === " ")) return null;
  return acao;
}
