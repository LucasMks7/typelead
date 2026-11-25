// Conversa com o servidor local.

export class ErroDaApi extends Error {}

/** Ninguém atendeu: o programa foi fechado, quase sempre. */
export class SemServidor extends ErroDaApi {
  constructor() {
    super("O typelead está fechado.");
  }
}

/** Avisa "caiu" e "voltou". */
export const conexao = new EventTarget();

const esperar = (ms) => new Promise((resolver) => setTimeout(resolver, ms));

async function responde() {
  try {
    return (await fetch("/api/programa")).ok;
  } catch {
    return false;
  }
}

let volta;

/** Espera o programa atender de novo. Todos os que esperam dividem as mesmas tentativas. */
export function ateVoltar(intervalo = 1500) {
  volta ??= (async () => {
    // Um pedido pode falhar com o programa aberto; só o segundo silêncio conta.
    if (!(await responde())) {
      conexao.dispatchEvent(new Event("caiu"));
      do await esperar(intervalo);
      while (!(await responde()));
      conexao.dispatchEvent(new Event("voltou"));
    }
    volta = undefined;
  })();
  return volta;
}

/** Faz o pedido e devolve o JSON; transforma a recusa em uma mensagem clara. */
export async function pedir(caminho, opcoes = {}) {
  let resposta;
  try {
    resposta = await fetch(caminho, opcoes);
  } catch {
    ateVoltar();
    throw new SemServidor();
  }
  const dados = await resposta.json().catch(() => null);
  if (resposta.ok) return dados;
  const detalhe = typeof dados?.detail === "string" ? dados.detail : null;
  throw new ErroDaApi(detalhe ?? `O typelead recusou o pedido (código ${resposta.status}).`);
}

export const enviarJson = (caminho, dados, method = "POST") =>
  pedir(caminho, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(dados),
  });

/** Repete o pedido, quando o programa voltar, até alguém atender. */
export async function insistir(pedido) {
  for (;;) {
    try {
      return await pedido();
    } catch (erro) {
      if (!(erro instanceof SemServidor)) throw erro;
      await ateVoltar();
    }
  }
}

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
