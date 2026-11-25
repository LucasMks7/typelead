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

A primeira transcrição baixa o modelo: 1,5 GB com placa da NVIDIA ou 500 MB sem.

Depois, abra http://localhost:8765. O servidor só atende este computador. Para usar outra porta: `typelead --porta 9000`.

## Como usar

1. Cole o link e aperte Enter. Se o vídeo tem legenda em inglês, a prática começa.
2. Sem legenda, escolha **Transcrever pelo som**: o vídeo toca inteiro, e o programa ouve a aba. Na janela do Chrome, escolha a própria aba e deixe o som marcado. Também dá para abrir um arquivo SRT ou VTT.
3. Ouça a fala, digite o que entendeu e aperte Enter. O certo fica verde, e o errado, riscado. Conserte e aperte Enter de novo, ou aperte Enter sem mudar nada para ver a resposta.

| Modo | O que aparece |
| --- | --- |
| Tudo oculto | Uma linha por palavra, com um ponto por letra; cada letra digitada toma o lugar de um ponto |
| Lacunas | Igual, com metade das palavras, sorteadas, já à mostra |
| Texto livre | Um campo vazio, sem saber o tamanho das palavras |

| Tecla | O que faz |
| --- | --- |
| Enter | corrigir; depois, ver a resposta ou seguir. Com o campo vazio, ouvir |
| Ctrl+espaço | ouvir a fala de novo |
| ↓ e ↑ | próxima e anterior |
| Ctrl+Enter | mostrar ou esconder o texto |
| Ctrl+↓ e Ctrl+↑ | mais devagar e mais rápido |

Com palavras escondidas, o espaço passa para a próxima e o Backspace, em uma palavra vazia, volta à anterior. Também dá para clicar em uma palavra. A pontuação e o apóstrofo já estão à mostra e não precisam ser digitados; algarismos aparecem como `#`.

Em **Corrigir**, dá para escolher **enquanto digito**. Com palavras escondidas, a correção é letra por letra; no texto livre, cada palavra é corrigida ao apertar espaço, sem revelar a resposta.

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
| `src/typelead/links.py` | Reconhece os links do YouTube e o segundo inicial |
| `src/typelead/youtube.py` | Consulta o vídeo e escolhe a legenda, sem baixar o vídeo |
| `src/typelead/legendas.py` | Lê SRT, VTT e o formato do YouTube |
| `src/typelead/alinhamento.py` | Junta o texto do autor com os tempos da legenda automática |
| `src/typelead/divisao.py` | Divide o que foi falado em trechos bons de praticar |
| `src/typelead/transcricao.py` | Transcreve o som gravado, com o tempo de cada palavra |
| `src/typelead/transcricoes.py` | Fila de transcrições em segundo plano |
| `src/typelead/web/js/gravador.js` | Grava o som da aba |
| `src/typelead/web/js/player.js` | Conversa com o player do YouTube e toca um trecho exato |
| `src/typelead/web/js/medidas.js` | Contas puras, testadas fora do navegador |
| `src/typelead/web/js/app.js` | A tela de prática |
| `src/typelead/web/js/correcao.js` | Compara o digitado com a fala, palavra por palavra |
| `src/typelead/web/js/lacunas.js` | As palavras escondidas: o sorteio, os pontos e a correção por letra |
| `src/typelead/web/js/ditado.js`, `pratica.js`, `atalhos.js` | O estado do ditado, o da prática e os atalhos, testados fora do navegador |
| `src/typelead/web/js/validacao.js` | Página de validação |
| [docs/player.md](docs/player.md) | O que foi medido no player e as decisões |
| [docs/legendas.md](docs/legendas.md) | O que foi medido na busca de legendas |
| [docs/transcricao.md](docs/transcricao.md) | O que foi medido na transcrição |
| [docs/divisao.md](docs/divisao.md) | O que foi medido na divisão das falas |

## Licença

[MIT](LICENSE)
