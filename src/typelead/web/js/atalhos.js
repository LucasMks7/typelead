// Traduz uma tecla na ação da prática. Puro, para ser testado sem navegador.

// Maps, e não objetos, que herdariam nomes como "toString".
const FORA = new Map([
  ["ArrowUp", "voltar"],
  ["ArrowDown", "avancar"],
  ["Enter", "mostrar"],
  [" ", "repetir"],
  ["-", "maisDevagar"],
  ["+", "maisRapido"],
  ["=", "maisRapido"],
]);

// No ditado, espaço e sinais escrevem.
const NO_DITADO = new Map([
  ["ArrowUp", "voltar"],
  ["ArrowDown", "avancar"],
  ["Enter", "enter"],
]);

// Ctrl com - e + é o zoom do navegador; por isso a velocidade fica nas setas.
const COM_CTRL = new Map([
  [" ", "repetir"],
  ["Enter", "mostrar"],
  ["ArrowUp", "maisRapido"],
  ["ArrowDown", "maisDevagar"],
]);

/**
 * Devolve a ação da tecla, ou null.
 * `onde`: "ditado"; "campo", outro campo, dono das próprias teclas; "botao", que
 * já responde a Enter e espaço; ou nada.
 */
export function acaoDaTecla({ key, ctrlKey, altKey, metaKey, shiftKey, isComposing }, onde) {
  if (altKey || metaKey || isComposing || onde === "campo") return null;
  if (onde === "botao" && (key === "Enter" || key === " ")) return null;
  if (ctrlKey) return COM_CTRL.get(key) ?? null;
  if (onde !== "ditado") return FORA.get(key) ?? null;
  // Shift com as setas seleciona o texto digitado.
  if (shiftKey && key.startsWith("Arrow")) return null;
  return NO_DITADO.get(key) ?? null;
}
