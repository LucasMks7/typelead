# Player do YouTube: o que foi medido

Medição de 24 de novembro de 2026, no Chrome para Windows, com a página de validação servida em `http://127.0.0.1:8765` e o vídeo *Big Buck Bunny*, da Blender Foundation (`aqz-KE-bpKQ`, licença Creative Commons), sem som e em velocidade normal.

## O player toca em uma página local?

Sim. O erro 153, que aparece quando o YouTube não recebe o `Referer`, não ocorreu. O servidor envia `Referrer-Policy: strict-origin-when-cross-origin`, e a página é aberta por HTTP, não por `file://`.

## Onde o trecho para

O programa consulta o tempo a cada 10 ms e pede a pausa ao chegar ao fim. A diferença é entre o fim pedido e o tempo em que o player ficou parado:

| Trecho | Repetições | Menor | Mediana | Maior |
| --- | ---: | ---: | ---: | ---: |
| 60 s a 63 s | 10 | 6 ms | 7 ms | 9 ms |
| 60 s a 61 s | 3 | 5 ms | 8 ms | 9 ms |

No trecho de 3 segundos, o começo ficou de 7 a 29 ms depois do pedido (mediana de 8,5 ms).

**Conferência:** o player só manda o tempo a cada 270 ms, mais ou menos; entre um aviso e outro, a biblioteca do YouTube estima. Para não confiar na estimativa, as mensagens brutas foram lidas: na pausa, o player informou 61,008 s e 61,009 s para um fim pedido de 61 s. Bate com a tabela.

**Decisão:** não é preciso antecipar a pausa. O erro é menor que a duração de um som da fala; o limite da precisão será o tempo da legenda, não o player.

## Códigos de erro

Um identificador que não existe devolveu o código **150**, e não o 100 que eu esperava. O 150 também é o código de incorporação proibida, então ele sozinho não diz qual dos dois aconteceu, e a mensagem do programa cita as duas possibilidades.

## Limites da medição

- Um vídeo, um computador, aba visível. Com a aba escondida, o navegador atrasa os relógios, e a pausa atrasaria junto.
- Não foram medidos: velocidade reduzida, vídeo com anúncio, Shorts e live gravada.
- A medida é o tempo informado pelo player. O atraso do som até a caixa ou o fone não entra nela.

## Som da aba

Ainda não testado. A página de validação tem o botão; o Chrome exige que uma pessoa autorize.
