# typelead

Treino de inglês com vídeos: ouvir uma fala por vez, digitar o que entendeu e rever os erros. Roda no próprio PC, sem conta e sem assinatura.

> **Status:** em desenvolvimento. Por enquanto, há só uma página de validação do player. O plano completo está em [PLANO.md](PLANO.md).

> **Uso pessoal:** os Termos de Serviço do YouTube restringem downloads e o acesso automatizado. O vídeo toca no player oficial do YouTube e não é baixado. Este projeto não tem ligação com o YouTube.

## Rodar

Precisa de Python 3.10 ou mais novo.

```text
python -m pip install -e ".[dev]"
typelead
```

Depois, abra http://127.0.0.1:8765. O servidor só atende este computador. Para usar outra porta: `typelead --porta 9000`.

## Testes

```text
python -m pytest
node --test tests/*.test.mjs
```

Os testes em JavaScript precisam do Node e não instalam nada.

## Como está organizado

| Parte | O que faz |
| --- | --- |
| `src/typelead/servidor.py` | Servidor local, com a biblioteca padrão do Python |
| `src/typelead/web/js/player.js` | Conversa com o player do YouTube e toca um trecho exato |
| `src/typelead/web/js/medidas.js` | Contas puras, testadas fora do navegador |
| `src/typelead/web/js/validacao.js` | Página de validação |
| [docs/player.md](docs/player.md) | O que foi medido no player e as decisões |

## Licença

[MIT](LICENSE)
