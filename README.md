# typelead

[![Testes](https://github.com/LucasMks7/typelead/actions/workflows/testes.yml/badge.svg)](https://github.com/LucasMks7/typelead/actions/workflows/testes.yml)

Treino de inglês com vídeos: ouvir uma fala por vez, digitar o que entendeu e rever os erros. Roda no próprio PC, sem conta e sem assinatura.

> **Status:** em desenvolvimento. Por enquanto, há uma página de validação do player e da transcrição, e o reconhecimento de links e a busca de legendas, ainda não ligados a ela. O plano completo está em [PLANO.md](PLANO.md).

> **Uso pessoal:** os Termos de Serviço do YouTube restringem downloads e o acesso automatizado. O vídeo toca no player oficial do YouTube e não é baixado. Este projeto não tem ligação com o YouTube.

## Rodar

Precisa de Python 3.11 ou mais novo.

```text
python -m pip install -e ".[dev]"        # no processador
python -m pip install -e ".[dev,gpu]"    # com placa da NVIDIA: mais 2 GB
typelead
```

A primeira transcrição baixa o modelo: 1,5 GB com placa da NVIDIA ou 500 MB sem.

Depois, abra http://127.0.0.1:8765. O servidor só atende este computador. Para usar outra porta: `typelead --porta 9000`.

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
| `src/typelead/web/js/validacao.js` | Página de validação |
| [docs/player.md](docs/player.md) | O que foi medido no player e as decisões |
| [docs/legendas.md](docs/legendas.md) | O que foi medido na busca de legendas |
| [docs/transcricao.md](docs/transcricao.md) | O que foi medido na transcrição |
| [docs/divisao.md](docs/divisao.md) | O que foi medido na divisão das falas |

## Licença

[MIT](LICENSE)
