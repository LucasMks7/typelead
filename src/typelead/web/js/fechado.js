// O aviso de que o programa foi fechado. Some sozinho quando ele volta.

import { conexao, pedir } from "./api.js";
import { criar } from "./desenho.js";

const aviso = criar("div", "", { className: "aviso erro fechado", hidden: true });
aviso.setAttribute("role", "alert");
const explicacao = criar("p");
explicacao.append(
  criar("b", "O typelead está fechado."),
  " Abra-o de novo no PowerShell e deixe a janela aberta. Esta página se reconecta sozinha.",
);
const comando = criar("code", "typelead");
const copiar = criar("button", "Copiar", { type: "button" });
const linha = criar("p", "", { className: "comando" });
linha.append(comando, copiar);
aviso.append(explicacao, linha);
document.querySelector("main").prepend(aviso);

copiar.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(comando.textContent);
    copiar.textContent = "Copiado";
  } catch {
    copiar.textContent = "Copie pelo texto";
  }
  setTimeout(() => (copiar.textContent = "Copiar"), 1500);
});

conexao.addEventListener("caiu", () => (aviso.hidden = false));
conexao.addEventListener("voltou", () => (aviso.hidden = true));

// Pedido agora, enquanto há quem responda.
pedir("/api/programa")
  .then((programa) => {
    // As aspas protegem um caminho com espaço; o & é do PowerShell.
    comando.textContent = `& "${programa.comando}"`;
  })
  .catch(() => {});
