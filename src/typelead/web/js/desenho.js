// Transforma o que os módulos puros calculam em elementos da tela. Nenhum texto
// vira HTML: legenda e digitação entram só por textContent.

import { separar } from "./correcao.js";

export function criar(tag, textContent = "", mais = {}) {
  return Object.assign(document.createElement(tag), { textContent, ...mais });
}

/** Uma palavra do texto livre, corrigida. A resposta só aparece se a fala estiver à mostra. */
export function marcar({ tipo, esperada, digitada }, mostrada, ordem = 0) {
  const marca = criar("span", "", { className: `palavra ${tipo}` });
  marca.style.setProperty("--i", ordem);
  // A cor não chega a todos: o tipo do erro também vai em texto para o leitor de tela.
  const explicar = (texto) => marca.append(criar("span", texto, { className: "oculto", lang: "pt-BR" }));

  if (tipo === "certa" || tipo === "pendente") {
    marca.append(criar("span", esperada || digitada));
    return marca;
  }
  if (digitada) {
    explicar(tipo === "sobrou" ? " a mais: " : " errada: ");
    marca.append(criar("s", digitada));
  }
  if (esperada && mostrada) {
    explicar(" o certo: ");
    marca.append(criar("strong", esperada));
  } else if (tipo === "faltou") {
    explicar(" falta uma palavra ");
    marca.append(criar("span", "", { className: "lacuna" }));
  }
  return marca;
}

/**
 * Uma palavra das lacunas. `ordem`: quantas letras vieram antes, para a onda da
 * correção; `nova`: a letra recém-digitada, que salta.
 */
export function desenharPalavra(palavra, { mostrada, cursor, itens, ordem, nova }) {
  const { oculta, texto, sinais, letras, tipo } = palavra;
  if (oculta === null) return criar("span", texto, { className: "palavra a-mostra" });
  if (mostrada) {
    // A palavra certa, ou a digitada riscada e a certa.
    if (tipo) return marcar({ tipo, esperada: texto, digitada: itens?.[oculta]?.digitada ?? "" }, true, ordem);
    const marca = criar("span", "", { className: "palavra" });
    marca.append(criar("strong", texto));
    return marca;
  }

  const marca = criar("span", "", { className: "palavra lacunada" });
  marca.dataset.oculta = oculta;
  marca.append(criar("span", `${letras} ${letras === 1 ? "letra" : "letras"}`, { className: "oculto", lang: "pt-BR" }));
  const daLetra = [];
  for (const { sinal, estado } of sinais) {
    const casa = criar("span", sinal, { className: `casa ${estado}`, ariaHidden: "true" });
    casa.style.setProperty("--i", ordem + daLetra.length);
    marca.append(casa);
    if (estado !== "fixo") daLetra.push(casa);
  }
  if (oculta === nova?.palavra) daLetra[nova.letra]?.classList.add("nova");
  if (oculta === cursor.palavra) {
    // Com a palavra completa, o cursor espera depois da última letra.
    if (cursor.letra < letras) daLetra[cursor.letra].classList.add("cursor");
    else daLetra.at(-1).classList.add("cursor-depois");
  }
  return marca;
}

export const DIAGNOSTICOS = {
  digitacao: "digitação",
  escuta: "escuta",
  vocabulario: "vocabulário",
  homofono: "som igual",
  indefinido: "não sei dizer",
};

/** A fala com uma palavra em destaque. Se a legenda mudou e ela não está lá, só o texto. */
export function destacar(texto, posicao, esperada) {
  const palavras = separar(texto);
  return palavras.flatMap((palavra, i) => {
    const alvo = i === posicao && palavra.texto === esperada;
    return [i && !palavra.colada ? " " : "", alvo ? criar("b", palavra.texto) : palavra.texto];
  });
}

/** Um erro com o motivo provável, que a pessoa pode trocar. */
export function desenharErro(erro, aoTrocar) {
  const item = criar("li");
  const palavras = criar("span", "", { lang: "en" });
  if (erro.digitada) palavras.append(criar("s", erro.digitada), " ");
  palavras.append(criar("b", erro.esperada));
  const escolha = criar("select", "", { title: "Se não foi isso, escolha o motivo" });
  escolha.setAttribute("aria-label", `Por que errei ${erro.esperada}`);
  for (const [tipo, nome] of Object.entries(DIAGNOSTICOS)) escolha.append(new Option(nome, tipo));
  escolha.value = erro.corrigido ?? erro.diagnostico;
  item.dataset.tipo = escolha.value;
  escolha.addEventListener("change", () => {
    item.dataset.tipo = escolha.value;
    aoTrocar(escolha.value);
  });
  item.append(palavras, escolha);
  return item;
}
