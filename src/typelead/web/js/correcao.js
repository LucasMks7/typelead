// Compara o que a pessoa digitou com o que foi dito. Puro, sem navegador.
//
// Cada palavra tem uma ou mais "leituras": "don't" pode ser lida como "dont" ou
// "do not". Duas palavras são a mesma quando têm uma leitura em comum. Maiúscula,
// pontuação e acento somem na leitura e por isso nunca contam como erro.

// Letras e números, com apóstrofo e hífen no meio; "3.5", "1,000" e "U.S." inteiros.
const PALAVRA =
  /'?[\p{L}\p{N}](?:[\p{L}\p{M}\p{N}]|['‐‑-](?=[\p{L}\p{N}])|(?<=\p{N})[.,](?=\p{N})|(?<=(?<![\p{L}\p{N}])\p{L})\.(?=\p{L}(?!\p{L})))*'?|[&%]/gu;

const INFORMAIS = new Map([
  ["won't", ["will not"]],
  ["can't", ["can not"]],
  ["shan't", ["shall not"]],
  ["ain't", []],
  ["cannot", ["can not"]],
  ["let's", ["let us"]],
  ["y'all", ["you all"]],
  ["gonna", ["going to"]],
  ["wanna", ["want to", "want a"]],
  ["gotta", ["got to", "got a"]],
  ["gimme", ["give me"]],
  ["lemme", ["let me"]],
  ["kinda", ["kind of"]],
  ["sorta", ["sort of"]],
  ["outta", ["out of"]],
  ["dunno", ["do not know"]],
  ["'cause", ["because"]],
  ["cuz", ["because"]],
  ["'em", ["them"]],
  ["'til", ["until"]],
  ["'bout", ["about"]],
  ["ok", ["okay"]],
  ["mr", ["mister"]],
  ["&", ["and"]],
  ["%", ["percent"]],
]);

const TERMINACOES = [
  ["n't", ["not"]],
  ["'re", ["are"]],
  ["'ve", ["have"]],
  ["'ll", ["will"]],
  ["'m", ["am"]],
  ["'d", ["would", "had", "did"]],
  ["'s", ["is", "has"]],
];

// Sem o apóstrofo, estas viram outra palavra, com outro som: "we're" não é "were".
const OUTRA_SEM_APOSTROFO = new Set(["were", "well", "ill", "id", "hell", "shell", "wed", "shed", "whore"]);

// Quem digita depressa esquece o apóstrofo: "dont" vale o mesmo que "don't".
const SEM_APOSTROFO = new Map(
  [
    ..."do does did is are was were has have had could would should must need might ca wo ai".split(" ").map((p) => `${p}n't`),
    ..."you we they what who".split(" ").map((p) => `${p}'re`),
    ..."i you we they could would should might must".split(" ").map((p) => `${p}'ve`),
    ..."i you he she it we they that there".split(" ").flatMap((p) => [`${p}'ll`, `${p}'d`]),
    ..."he she it that this there here what who where when how let".split(" ").map((p) => `${p}'s`),
    "i'm",
    "y'all",
  ]
    .map((contracao) => [contracao.replaceAll("'", ""), contracao])
    .filter(([sem]) => !OUTRA_SEM_APOSTROFO.has(sem)),
);

const ATE_VINTE =
  "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split(" ");
const DEZENAS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"];

function porExtenso(numero) {
  if (numero < 20) return [ATE_VINTE[numero]];
  if (numero === 100) return ["one hundred", "a hundred"];
  const unidade = numero % 10;
  return [DEZENAS[Math.floor(numero / 10)] + (unidade ? ` ${ATE_VINTE[unidade]}` : "")];
}

/** As palavras do texto, cada uma como aparece (com a pontuação) e suas leituras. */
export function separar(texto) {
  const reto = texto.replace(/[’‘´`ʼ]/g, "'");
  const achadas = [...reto.matchAll(PALAVRA)];
  return achadas.map((achada, i) => {
    const comeco = i === 0 ? 0 : achada.index;
    return {
      texto: texto.slice(comeco, achadas[i + 1]?.index).trim(),
      leituras: leituras(limpar(achada[0])),
    };
  });
}

function limpar(palavra) {
  return palavra
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .replace(/[‐‑]/g, "-")
    .replace(/(?<=\d),(?=\d)/g, "")
    .replace(/(?<=\p{L})\.(?=\p{L})/gu, "");
}

function leituras(palavra) {
  const partes = palavra.split("-");
  if (partes.length === 1) return [...new Set(leiturasSimples(palavra))];
  // "well-known" vale "well known" e "wellknown". Com muitas partes, as combinações
  // cresceriam demais, e as contrações de dentro deixam de ser abertas.
  const abertas = partes.length <= 3 ? combinar(partes.map(leiturasSimples)) : [partes.join(" ")];
  return [...new Set([partes.join(""), ...abertas])];
}

// Nenhuma palavra inglesa tem três letras iguais seguidas: "soooo" é "so" esticado, e
// ninguém deve contar quantas letras a legenda usou.
const ESTICADA = /(\p{L})\1{2,}/gu;

function leiturasSimples(palavra) {
  const curta = palavra.replace(ESTICADA, "$1");
  if (curta !== palavra) return [...leiturasSimples(curta), ...leiturasSimples(palavra.replace(ESTICADA, "$1$1"))];
  if (INFORMAIS.has(palavra)) return [semApostrofo(palavra), ...INFORMAIS.get(palavra)];
  if (palavra.length > 4 && palavra.endsWith("in'")) return [palavra.slice(0, -1), `${palavra.slice(0, -1)}g`];
  // O que sobra nas pontas são aspas simples ou o plural em "dogs'".
  const dentro = palavra.replace(/^'|'$/g, "");
  if (dentro !== palavra) return leiturasSimples(dentro);
  if (SEM_APOSTROFO.has(palavra)) return [palavra, ...leiturasSimples(SEM_APOSTROFO.get(palavra))];
  if (/^\d{1,2}$|^100$/.test(palavra)) return [String(Number(palavra)), ...porExtenso(Number(palavra))];
  for (const [fim, abertas] of TERMINACOES) {
    if (palavra.length > fim.length && palavra.endsWith(fim)) {
      const bases = leiturasSimples(palavra.slice(0, -fim.length));
      return [semApostrofo(palavra), ...combinar([bases, abertas])];
    }
  }
  return [semApostrofo(palavra)];
}

function semApostrofo(palavra) {
  const sem = palavra.replaceAll("'", "");
  return OUTRA_SEM_APOSTROFO.has(sem) ? palavra : sem;
}

/** [["a", "b"], ["c"]] vira ["a c", "b c"]. */
function combinar(listas) {
  return listas.reduce((prontas, lista) => prontas.flatMap((p) => lista.map((l) => (p ? `${p} ${l}` : l))), [""]);
}

const leiturasDe = (palavras) => combinar(palavras.map((p) => p.leituras));

// O alinhamento

// Trocar custa entre 0,7 (palavras quase iguais) e 1,3: assim "kettel" se junta a
// "kettle", e não à palavra vizinha. Sobrar custa um pouco mais que faltar porque,
// em um ditado, pular uma palavra é mais comum que inventar uma.
const CUSTO_DE_FALTAR = 1;
const CUSTO_DE_SOBRAR = 1.05;

function custoDeTroca(esperada, digitada) {
  const a = esperada.leituras[0];
  const b = digitada.leituras[0];
  return 0.7 + (0.6 * distancia(a, b)) / Math.max(a.length, b.length);
}

/** Quantas letras mudar, tirar ou pôr para uma virar a outra. */
export function distancia(a, b) {
  let anterior = Array.from({ length: b.length + 1 }, (_, j) => j);
  for (let i = 1; i <= a.length; i++) {
    const linha = [i];
    for (let j = 1; j <= b.length; j++) {
      linha[j] = Math.min(anterior[j] + 1, linha[j - 1] + 1, anterior[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    }
    anterior = linha;
  }
  return anterior[b.length];
}

// Uma palavra pode equivaler a até três: "dunno" e "do not know".
const TAMANHOS = [[1, 1], [1, 2], [1, 3], [2, 1], [3, 1]];

function iguais(esperadas, digitadas) {
  const possiveis = new Set(leiturasDe(esperadas));
  return leiturasDe(digitadas).some((l) => possiveis.has(l));
}

/** Tabela de menor custo, como em um `diff`, com o passo que levou a cada casa. */
function alinhar(esperadas, digitadas) {
  const tabela = Array.from({ length: esperadas.length + 1 }, () => Array(digitadas.length + 1).fill(undefined));
  tabela[0][0] = { custo: 0 };
  for (let i = 0; i <= esperadas.length; i++) {
    for (let j = 0; j <= digitadas.length; j++) {
      const tentar = (a, b, tipo, custo) => {
        const total = tabela[i][j].custo + custo;
        const destino = tabela[i + a][j + b];
        if (!destino || total < destino.custo) tabela[i + a][j + b] = { custo: total, tipo, a, b };
      };
      for (const [a, b] of TAMANHOS) {
        if (i + a > esperadas.length || j + b > digitadas.length) continue;
        if (iguais(esperadas.slice(i, i + a), digitadas.slice(j, j + b))) tentar(a, b, "certa", 0);
      }
      if (i < esperadas.length && j < digitadas.length) tentar(1, 1, "trocada", custoDeTroca(esperadas[i], digitadas[j]));
      if (i < esperadas.length) tentar(1, 0, "faltou", CUSTO_DE_FALTAR);
      if (j < digitadas.length) tentar(0, 1, "sobrou", CUSTO_DE_SOBRAR);
    }
  }
  return tabela;
}

function caminho(tabela, esperadas, digitadas, i, j) {
  const juntar = (palavras) => palavras.map((p) => p.texto).join(" ");
  const itens = [];
  while (i > 0 || j > 0) {
    const { tipo, a, b } = tabela[i][j];
    i -= a;
    j -= b;
    itens.unshift({
      tipo,
      esperada: juntar(esperadas.slice(i, i + a)),
      digitada: juntar(digitadas.slice(j, j + b)),
      palavras: a,
    });
  }
  return itens;
}

/**
 * Compara a fala inteira. Devolve itens na ordem da fala, cada um com o `tipo`:
 * "certa", "trocada", "faltou" (não foi digitada) ou "sobrou" (não foi dita).
 */
export function corrigir(fala, digitado) {
  const esperadas = separar(fala);
  const digitadas = separar(digitado);
  return caminho(alinhar(esperadas, digitadas), esperadas, digitadas, esperadas.length, digitadas.length);
}

/**
 * Corrige só as palavras já terminadas com espaço, sem cobrar o resto da fala.
 * "pendente" é a que pode ser o começo de uma contração: "do", quando foi dito "don't".
 */
export function corrigirParcial(fala, digitado) {
  const terminado = digitado.match(/^[\s\S]*\s/)?.[0] ?? "";
  const esperadas = separar(fala);
  const digitadas = separar(terminado);
  const tabela = alinhar(esperadas, digitadas);
  const fim = digitadas.length;

  // No empate, vence o ponto mais cedo da fala: a pessoa ainda está digitando.
  let melhor = { custo: Infinity };
  for (let i = 0; i <= esperadas.length; i++) {
    for (let j = fim; j >= Math.max(0, fim - 2); j--) {
      if (j < fim && !(i < esperadas.length && comecam(esperadas[i], digitadas.slice(j)))) continue;
      if (tabela[i][j].custo < melhor.custo) melhor = { custo: tabela[i][j].custo, i, j };
    }
  }
  const pendentes = digitadas.slice(melhor.j).map((p) => ({ tipo: "pendente", esperada: "", digitada: p.texto, palavras: 0 }));
  return [...caminho(tabela, esperadas, digitadas, melhor.i, melhor.j), ...pendentes];
}

function comecam(esperada, digitadas) {
  return leiturasDe(digitadas).some((comeco) => esperada.leituras.some((l) => l.startsWith(`${comeco} `)));
}

/** Quantas palavras da fala foram acertadas e quantas sobraram. */
export function resumir(itens) {
  const somar = (tipos) => itens.filter((i) => tipos.includes(i.tipo)).reduce((s, i) => s + i.palavras, 0);
  return {
    certas: somar(["certa"]),
    total: somar(["certa", "trocada", "faltou"]),
    sobras: itens.filter((i) => i.tipo === "sobrou").length,
    acertou: itens.every((i) => i.tipo === "certa"),
  };
}
