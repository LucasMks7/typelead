# typelead

[![Testes](https://github.com/LucasMks7/typelead/actions/workflows/testes.yml/badge.svg)](https://github.com/LucasMks7/typelead/actions/workflows/testes.yml)

Treino de inglês com vídeos: ouvir uma fala por vez, digitar o que entendeu e rever os erros. Roda no próprio PC, sem conta e sem assinatura.

> **Status:** em desenvolvimento. Por enquanto, há uma página de validação do player e o reconhecimento de links, ainda não ligado a ela. O plano completo está em [PLANO.md](PLANO.md).

> **Uso pessoal:** os Termos de Serviço do YouTube restringem downloads e o acesso automatizado. O vídeo toca no player oficial do YouTube e não é baixado. Este projeto não tem ligação com o YouTube.

## Rodar

Precisa de Python 3.10 ou mais novo.

```text
python -m pip install -e ".[dev]"
typelead
```

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
| `src/typelead/servidor.py` | Servidor local, com a biblioteca padrão do Python |
| `src/typelead/links.py` | Reconhece os links do YouTube e o segundo inicial |
| `src/typelead/web/js/player.js` | Conversa com o player do YouTube e toca um trecho exato |
| `src/typelead/web/js/medidas.js` | Contas puras, testadas fora do navegador |
| `src/typelead/web/js/validacao.js` | Página de validação |
| [docs/player.md](docs/player.md) | O que foi medido no player e as decisões |

## Licença

[MIT](LICENSE)
