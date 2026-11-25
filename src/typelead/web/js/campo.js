// O campo em que se digita a fala. Nas lacunas, ele fica invisível e o cursor é
// desenhado nas palavras.

import { Lacunas } from "./lacunas.js";

/**
 * `resposta`: devolve a resposta atual, se houver. `aoMudar({ digitando, nova })`:
 * redesenhar; `nova` é a letra recém-digitada, se foi só uma.
 */
export function ligarCampo({ campo, fala, resposta, aoMudar }) {
  function escrever() {
    const atual = resposta();
    if (!atual) return;
    // O cursor fica onde estava no texto já arrumado.
    const posicao = atual.arrumar(campo.value.slice(0, campo.selectionStart)).length;
    const antes = atual.texto.length;
    atual.escrever(campo.value);
    let nova;
    if (atual instanceof Lacunas && atual.texto.length === antes + 1) {
      const { palavra, letra } = atual.cursor(posicao);
      nova = { palavra, letra: letra - 1 };
    }
    if (campo.value !== atual.texto) {
      campo.value = atual.texto;
      campo.setSelectionRange(posicao, posicao);
    }
    aoMudar({ digitando: true, nova });
  }

  function irPara(palavra) {
    const atual = resposta();
    const { texto, posicao } = atual.irPara(palavra);
    atual.escrever(texto);
    campo.value = texto;
    campo.setSelectionRange(posicao, posicao);
    aoMudar({ digitando: false });
  }

  campo.addEventListener("input", ({ isComposing }) => {
    // No meio de um acento, mexer no campo o desmancharia; "compositionend" vem depois.
    if (!isComposing) escrever();
  });
  campo.addEventListener("compositionend", escrever);

  campo.addEventListener("beforeinput", (evento) => {
    const atual = resposta();
    if (!(atual instanceof Lacunas) || campo.selectionStart !== campo.selectionEnd) return;
    const palavra = atual.passo(evento.inputType, evento.data, campo.selectionStart);
    if (palavra === undefined) return;
    evento.preventDefault();
    if (palavra !== null) irPara(palavra);
  });

  // O cursor das lacunas é desenhado: acompanha o do campo.
  document.addEventListener("selectionchange", () => {
    if (document.activeElement === campo && resposta() instanceof Lacunas) aoMudar({ digitando: false });
  });

  fala.addEventListener("click", ({ target }) => {
    if (!(resposta() instanceof Lacunas)) return;
    const palavra = target.closest("[data-oculta]");
    campo.focus();
    if (palavra) irPara(Number(palavra.dataset.oculta));
  });

  return { irPara };
}
