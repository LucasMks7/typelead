# Legendas: o que foi medido

Medição de 24 de novembro de 2026, com o yt-dlp 2026.11.23, de uma conexão doméstica e sem login. Cada vídeo foi consultado uma vez; nenhum vídeo foi baixado.

| Vídeo | Tempo | Legenda usada | Falas | Palavras por fala (mín., mediana, máx.) |
| --- | ---: | --- | ---: | --- |
| `TLPdxz2wioA`, cena de série | 3,1 s | do autor | 125 | 1, 5, 13 |
| `at_f98qOGY0`, comercial de 60 s | 3,7 s | automática | 15 | 1, 7, 9 |
| `iG9CE55wbtY`, palestra de 20 min | 2,3 s | do autor | 383 | 1, 8, 17 |
| `jNQXAC9IVRw`, vídeo de 19 s | 1,9 s | do autor | 5 | 3, 9, 11 |
| `UF8uR6Z6KLc`, discurso de 15 min | 2,4 s | do autor | 244 | 1, 9, 18 |
| `aqz-KE-bpKQ`, animação | 2,0 s | nenhuma | – | – |
| `aaaaaaaaaaa` | – | vídeo inexistente, recusado com explicação | – | – |

Nas falas devolvidas, nenhuma ficou fora de ordem, sem duração ou com colchetes e marcas no texto.

## Decisões

- **Formato json3.** É o único dos oferecidos que traz o tempo de cada palavra na legenda automática. O VTT automático repete cada linha até três vezes.
- **`en-orig` antes de `en`.** Na lista de automáticas, `en` pode ser a tradução de um vídeo em outro idioma. O endereço com `tlang=` é sempre recusado, porque o texto não é o que se ouve.
- **Sem escolher formato de vídeo** (`process=False`). O yt-dlp avisa que faltam formatos por não resolver um desafio em JavaScript; isso não afeta a legenda.
- **Falta de legenda não é erro.** O vídeo ainda pode ser transcrito pelo som da aba. Só vira erro o que impede de usar o vídeo.
- **O YouTube informa se a incorporação é permitida** (`playable_in_embed`), então dá para avisar antes de abrir o player.

## Limites

- Sete consultas não mostram o que acontece com uso intenso. O YouTube pode recusar a qualquer momento; o programa avisa e segue para a transcrição.
- Nenhum vídeo da amostra tinha incorporação proibida, restrição de idade ou bloqueio de região. Esses casos só têm teste com mensagens simuladas.
- Parênteses curtos são tratados como descrição de som. Uma fala entre parênteses se perderia.
