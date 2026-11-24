// Conversa com o servidor local.

export class ErroDaApi extends Error {}

/** Faz o pedido e devolve o JSON; transforma a recusa em uma mensagem clara. */
export async function pedir(caminho, opcoes = {}) {
  let resposta;
  try {
    resposta = await fetch(caminho, opcoes);
  } catch {
    throw new ErroDaApi("O typelead não respondeu. Confira se ele ainda está aberto no terminal.");
  }
  const dados = await resposta.json().catch(() => null);
  if (resposta.ok) return dados;
  const detalhe = typeof dados?.detail === "string" ? dados.detail : null;
  throw new ErroDaApi(detalhe ?? `O typelead recusou o pedido (código ${resposta.status}).`);
}

export const enviarJson = (caminho, dados) =>
  pedir(caminho, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(dados),
  });

const esperar = (ms) => new Promise((resolver) => setTimeout(resolver, ms));

/** Envia a gravação e acompanha a transcrição até o fim. Devolve as falas. */
export async function transcrever({ som, marcas }, aoAvancar = () => {}) {
  const { id } = await enviarJson("/api/transcricoes", { marcas });
  await pedir(`/api/transcricoes/${id}/som`, { method: "PUT", body: som });
  for (;;) {
    const trabalho = await pedir(`/api/transcricoes/${id}`);
    if (trabalho.estado === "pronto") return trabalho.falas;
    if (trabalho.estado === "falhou") throw new ErroDaApi(trabalho.erro);
    aoAvancar(trabalho);
    await esperar(700);
  }
}
