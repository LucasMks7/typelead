# typelead

[![Testes](https://github.com/LucasMks7/typelead/actions/workflows/testes.yml/badge.svg)](https://github.com/LucasMks7/typelead/actions/workflows/testes.yml)

Treino de inglês com vídeos: ouvir uma fala por vez, digitar o que entendeu e rever os erros. Roda no próprio PC, sem conta e sem assinatura.

> **Status:** em desenvolvimento. Já dá para abrir um vídeo, praticar uma fala por vez, em três modos, e continuar de onde parou. O plano completo está em [PLANO.md](PLANO.md).

> **Uso pessoal:** os Termos de Serviço do YouTube restringem downloads e o acesso automatizado. O vídeo toca no player oficial do YouTube e não é baixado. Este projeto não tem ligação com o YouTube.

## Rodar

Precisa de Python 3.11 ou mais novo.

```text
python -m pip install -e ".[dev]"        # no processador
python -m pip install -e ".[dev,gpu]"    # com placa da NVIDIA: mais 2 GB
typelead
```

A primeira transcrição baixa o modelo: 1,5 GB com placa da NVIDIA ou 500 MB sem. A primeira tradução baixa outro, de 236 MB.

O programa abre a página no navegador: http://localhost:8765. Deixe a janela do terminal aberta enquanto pratica. Se ela for fechada, a página avisa e espera; quando o programa volta, ela se reconecta e salva o que faltou, desde que a aba continue aberta. O servidor só atende este computador. Para usar outra porta, `typelead --porta 9000`; para não abrir o navegador, `--sem-navegador`.

## Como usar

1. Cole o link e aperte Enter. Se o vídeo tem legenda em inglês, a prática começa.
2. Sem legenda, escolha **Transcrever pelo som**: o vídeo toca inteiro, e o programa ouve a aba. Na janela do Chrome, escolha a própria aba e deixe o som marcado. Também dá para abrir um arquivo SRT ou VTT.
3. Ouça a fala, digite o que entendeu e aperte Enter. O certo fica verde, e o errado, riscado. Conserte e aperte Enter de novo, ou aperte Enter sem mudar nada para ver a resposta.

| Modo | O que aparece |
| --- | --- |
| Tudo oculto | Uma linha por palavra, com um ponto por letra; cada letra digitada toma o lugar de um ponto |
| Lacunas | Igual, com metade das palavras já à mostra; as que você erra e as da faixa escolhida somem mais |
| Texto livre | Um campo vazio, sem saber o tamanho das palavras |

| Tecla | O que faz |
| --- | --- |
| espaço | próxima palavra, com palavras escondidas |
| Enter | corrigir; depois, ver a resposta ou seguir. Com o campo vazio, ouvir |
| Ctrl+espaço | ouvir a fala de novo |
| ↓ e ↑ | próxima e anterior |
| Ctrl+Enter | mostrar ou esconder o texto |
| Ctrl+I | mostrar ou esconder a tradução |
| Ctrl+↓ e Ctrl+↑ | mais devagar e mais rápido |

Com palavras escondidas, o espaço passa para a próxima e o Backspace, em uma palavra vazia, volta à anterior. Também dá para clicar em uma palavra. A pontuação e o apóstrofo já estão à mostra e não precisam ser digitados; algarismos aparecem como `#`.

Em **Corrigir**, dá para escolher **enquanto digito**. Com palavras escondidas, a correção é letra por letra; no texto livre, cada palavra é corrigida ao apertar espaço, sem revelar a resposta.

### Para manter o ritmo

O topo mostra quantas falas você acertou hoje, sem ver o texto, e a meta de 20. A partir de duas, aparece a sequência de falas certas de primeira. A página inicial mostra a semana, os dias seguidos e os últimos vídeos. Os sons podem ser desligados no topo. Se o sistema pede menos movimento, não há animação.

### Por que errei

Resolvida a fala, cada palavra errada mostra o motivo provável:

| Motivo | Quando |
| --- | --- |
| Digitação | Uma letra trocada, a mais, a menos ou invertida, em palavra que você já acertou antes ou consertou sem ouvir de novo; ou só letras invertidas |
| Escuta | Acertou depois de ouvir de novo ou mais devagar; ou errou uma palavra que já tinha acertado |
| Vocabulário | Viu a resposta depois de ouvir devagar ou de ler a tradução, e nunca tinha acertado a palavra |
| Som igual | Trocou por outra de som igual ou quase, como *their* e *there* |
| Não sei dizer | Os sinais não bastam |

Se não foi isso, escolha outro motivo na lista; a sua escolha fica salva.

### Suas palavras

A página **Suas palavras** lista o que você errou, com a fala de onde veio. Uma palavra fica como *errando* até ser acertada sem ajuda, *aprendendo* no primeiro acerto e *acertando* no segundo seguido. **Já sei** tira a palavra do estudo.

Digitação não entra na lista. O que você deixou em branco e consertou sem ouvir de novo também não, nem uma palavra muito comum deixada em branco. No modo Lacunas, escolha se quer esconder mais palavras comuns, de uso médio ou raras: nada é certo, só mais provável.

### Revisão

A palavra errada volta a partir do dia seguinte, no trecho de vídeo em que você a errou, com o resto da fala à mostra. Palavras do mesmo trecho vêm juntas, para uma não entregar a outra. Uma letra errada ganha uma segunda chance.

| Como foi | Quando volta |
| --- | --- |
| Errou ou clicou em **Não sei** | No dia seguinte |
| Acertou ouvindo mais de 3 vezes, devagar ou na segunda chance | Um intervalo curto |
| Acertou | Um intervalo maior a cada vez |

Os intervalos são do algoritmo [FSRS](https://github.com/open-spaced-repetition/py-fsrs). Cada sessão traz cerca de 20 palavras, começando pelas mais atrasadas. Errar a palavra de novo na prática a traz de volta antes. Trecho acertado na revisão conta na meta do dia.

### O que fica salvo

As falas de cada vídeo, o ponto em que você parou e cada tentativa, com o que foi digitado, quantas vezes ouviu e em que velocidade. Fica tudo em um arquivo SQLite, só neste computador: `%APPDATA%\typelead\typelead.db` no Windows e `~/.local/share/typelead/typelead.db` no Linux. O som e o vídeo não são guardados. Um vídeo salvo abre sem consultar a legenda de novo; o player continua precisando da internet.

### O que conta como certo

Maiúscula, pontuação e acento não contam em nenhum modo. Com palavras escondidas, vale a forma da legenda. No texto livre:

- `don't`, `do not` e `dont` valem o mesmo, assim como `gonna` e `going to`. A exceção é quando o apóstrofo muda a palavra e o som: `were` não vale por `we're`.
- Números de 0 a 100 valem em algarismo ou por extenso. Acima disso, e em anos e ordinais (`1999`, `19th`), só vale a forma da legenda.
- `well-known` vale `well known`, e `sooooo` vale `so`.
- Grafias diferentes, como `colour` e `color`, contam como erro.

Vídeos cujo dono não permite incorporação ainda não funcionam. A página de validação do player e do som fica em `/validacao.html`.

## Links aceitos

| Tipo | Exemplo |
| --- | --- |
| Vídeo, inclusive dentro de playlist ou mix | `youtube.com/watch?v=ID&list=...` |
| Link curto | `youtu.be/ID?si=...` |
| Shorts | `youtube.com/shorts/ID` |
| Live e live gravada | `youtube.com/live/ID` |
| Player incorporado, atual e antigo | `youtube.com/embed/ID`, `youtube.com/v/ID` |
| YouTube Music, Kids e versão de celular | `music.youtube.com/watch?v=ID` |
| Link dentro de outro | resultado do Google, aviso de cookies, `attribution_link` |

O tempo inicial vale como `t=90`, `t=1m30s`, `start=90` ou `#t=90`. Canal, playlist, busca e clipe não levam a um vídeo só, e o programa explica o que fazer. O link reconhecido ainda pode ser de um vídeo que não existe ou não pode ser tocado.

## Testes

```text
python -m pytest
node --test "tests/*.test.mjs"
```

Os testes em JavaScript precisam do Node 22 ou mais novo e não instalam nada.

## Como está organizado

| Parte | O que faz |
| --- | --- |
| `src/typelead/servidor.py` | Servidor local: a interface e a API, só para este computador |
| `src/typelead/banco.py` | Guarda vídeos, falas e tentativas no SQLite |
| `src/typelead/diagnostico.py` | Por que cada palavra foi errada |
| `src/typelead/palavras.py` | Como vai cada palavra e a chance de ela ser escondida |
| `src/typelead/revisao.py` | Quando cada palavra volta |
| `src/typelead/links.py` | Reconhece os links do YouTube e o segundo inicial |
| `src/typelead/youtube.py` | Consulta o vídeo e escolhe a legenda, sem baixar o vídeo |
| `src/typelead/legendas.py` | Lê SRT, VTT e o formato do YouTube |
| `src/typelead/alinhamento.py` | Junta o texto do autor com os tempos da legenda automática |
| `src/typelead/divisao.py` | Divide o que foi falado em trechos bons de praticar |
| `src/typelead/transcricao.py` | Transcreve o som gravado, com o tempo de cada palavra |
| `src/typelead/traducao.py` | Traduz uma fala, neste computador |
| `src/typelead/transcricoes.py` | Fila de transcrições em segundo plano |
| `src/typelead/web/js/api.js`, `fechado.js` | Os pedidos ao servidor e o que fazer quando ele está fechado |
| `src/typelead/web/js/gravador.js` | Grava o som da aba |
| `src/typelead/web/js/player.js` | Conversa com o player do YouTube e toca um trecho exato |
| `src/typelead/web/js/medidas.js` | Contas puras, testadas fora do navegador |
| `src/typelead/web/js/app.js` | A tela de prática |
| `src/typelead/web/js/inicio.js`, `desenho.js`, `sons.js` | A página inicial, as palavras na tela e os sons de acerto e erro |
| `src/typelead/web/js/cartao.js`, `revisao.js` | Um trecho em revisão e a página de revisão |
| `src/typelead/web/js/campo.js` | O campo em que se digita, na prática e na revisão |
| `src/typelead/web/js/palavras.js` | A página das palavras erradas |
| `src/typelead/web/js/correcao.js` | Compara o digitado com a fala, palavra por palavra |
| `src/typelead/web/js/lacunas.js` | As palavras escondidas: a escolha, os pontos e a correção por letra |
| `src/typelead/web/js/ditado.js`, `pratica.js`, `atalhos.js` | O estado do ditado, o da prática e os atalhos, testados fora do navegador |
| `src/typelead/web/js/validacao.js` | Página de validação |
| [docs/player.md](docs/player.md) | O que foi medido no player e as decisões |
| [docs/legendas.md](docs/legendas.md) | O que foi medido na busca de legendas |
| [docs/transcricao.md](docs/transcricao.md) | O que foi medido na transcrição |
| [docs/divisao.md](docs/divisao.md) | O que foi medido na divisão das falas |
| [docs/traducao.md](docs/traducao.md) | O que foi medido na tradução |

## Licença

[MIT](LICENSE). As fontes Red Hat Text e Red Hat Mono, em `src/typelead/web/fontes`, têm licença [SIL OFL 1.1](src/typelead/web/fontes/red-hat-mono-LICENSE.txt). A tradução usa o modelo [opus-mt-tc-big-en-pt](https://huggingface.co/Helsinki-NLP/opus-mt-tc-big-en-pt), da Universidade de Helsinque, sob [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), convertido para o CTranslate2. A frequência das palavras vem da biblioteca [wordfreq](https://github.com/rspeer/wordfreq), de Robyn Speer (Apache 2.0, dados [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)), que reúne, entre outras fontes, as listas SUBTLEX, de Marc Brysbaert e outros, disponíveis gratuitamente, o OpenSubtitles (http://www.opensubtitles.org) e o Google Books Ngrams (http://books.google.com/ngrams). Os dados não são copiados neste repositório.
