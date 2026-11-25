// A página inicial: o letreiro que se escreve, a semana e os últimos vídeos.

import { criar } from "./desenho.js";

const $ = (id) => document.getElementById(id);

export const META_DO_DIA = 20;

/** O título começa em pontos e se escreve uma vez. O leitor de tela lê o texto inteiro. */
export function escreverLetreiro() {
  const letreiro = $("letreiro");
  const texto = letreiro.textContent;
  let ordem = 0;
  const palavras = texto.split(" ").flatMap((palavra, i) => {
    const desenhada = criar("span", "", { className: "palavra lacunada", ariaHidden: "true" });
    for (const sinal of palavra) {
      const fixo = !/\p{L}/u.test(sinal);
      const casa = criar("span", sinal, { className: fixo ? "casa" : "casa letra" });
      if (!fixo) {
        casa.style.setProperty("--i", ordem);
        ordem += 1;
      }
      desenhada.append(casa);
    }
    return i ? [" ", desenhada] : [desenhada];
  });
  letreiro.replaceChildren(criar("span", texto, { className: "oculto" }), ...palavras);
}

export function mostrarResumo({ hoje }) {
  $("meta-numero").textContent = hoje;
  $("meta-total").textContent = META_DO_DIA;
  $("meta").style.setProperty("--parte", Math.min(1, hoje / META_DO_DIA));
  $("meta").classList.toggle("cumprida", hoje >= META_DO_DIA);
}

export function mostrarSemana({ semana, dias_seguidos: seguidos }) {
  $("titulo-semana").textContent =
    seguidos === 0 ? "Sua semana" : seguidos === 1 ? "1 dia de prática" : `${seguidos} dias seguidos`;
  $("dias").replaceChildren(
    ...semana.map(({ dia, certas }, i) => {
      // Sem a hora, a data seria lida em UTC e cairia no dia anterior.
      const data = new Date(`${dia}T12:00`);
      const item = criar("li", "", { className: i === semana.length - 1 ? "hoje" : "" });
      item.style.setProperty("--parte", Math.min(1, certas / META_DO_DIA));
      item.append(
        criar("span", "", { className: "coluna", ariaHidden: "true" }),
        criar("span", data.toLocaleDateString("pt-BR", { weekday: "short" }).replace(".", "")),
        criar("span", `${certas} ${certas === 1 ? "fala certa" : "falas certas"}`, { className: "oculto" }),
      );
      item.title = `${data.toLocaleDateString("pt-BR")}: ${certas} ${certas === 1 ? "fala certa" : "falas certas"}`;
      return item;
    }),
  );
}

export function mostrarRecentes(videos) {
  $("continuar").hidden = videos.length === 0;
  $("lista").replaceChildren(
    ...videos.map(({ id, titulo, canal, acertadas, total }) => {
      const item = criar("li");
      const ir = criar("a", "", { href: `?v=${id}`, className: "cartao" });
      const capa = criar("span", "", { className: "capa" });
      capa.append(criar("img", "", { src: `https://i.ytimg.com/vi/${id}/mqdefault.jpg`, alt: "", loading: "lazy", width: 320, height: 180 }));
      const barra = criar("span", "", { className: "parte", ariaHidden: "true" });
      barra.style.setProperty("--parte", total ? acertadas / total : 0);
      capa.append(barra);
      ir.append(
        capa,
        criar("strong", titulo),
        criar("span", canal, { className: "canal" }),
        criar("span", `${acertadas} de ${total} falas certas`, { className: "andamento" }),
      );
      item.append(ir);
      return item;
    }),
  );
}
