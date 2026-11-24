# Divisão das falas: o que foi medido

Medição de 24 de novembro de 2026, com legendas de vídeos reais. Só números foram guardados.

## O tempo de cada palavra

Para dividir uma fala, é preciso saber quando cada palavra é dita, e a legenda do autor só informa o tempo da fala inteira. Dividir esse tempo conforme o tamanho das palavras, comparado com a legenda automática do mesmo vídeo:

| Vídeo | Palavras que casam | Começo da fala (mediana, 90%) | Dentro da fala (mediana, 90%) |
| --- | ---: | --- | --- |
| `TLPdxz2wioA` | 561 de 590 | 157 ms, 271 ms | 255 ms, 520 ms |
| `iG9CE55wbtY` | 2982 de 3125 | 450 ms, 1195 ms | 711 ms, 1457 ms |
| `UF8uR6Z6KLc` | 2231 de 2298 | 460 ms, 810 ms | 536 ms, 959 ms |

É o bastante para cortar no meio de outra palavra. **Decisão:** o texto vem do autor, que é correto, e o tempo, da automática, que é por palavra. As duas são alinhadas como em um `diff`; palavra sem par fica entre as vizinhas. Se menos de 60% casarem, nada muda.

**Limite:** os tempos da automática foram tomados como referência, sem conferir com o som. O erro deles não foi medido; por isso há uma margem de 0,15 s em cada ponta.

## O tamanho das falas

| Vídeo | | Falas | Com 1 palavra | Com mais de 12 | De 4 a 10 palavras |
| --- | --- | ---: | ---: | ---: | ---: |
| `TLPdxz2wioA` | legenda | 125 | 23 | 1 | 61% |
| | dividida | 89 | 0 | 0 | 76% |
| `at_f98qOGY0` | legenda | 15 | 2 | 0 | 66% |
| | dividida | 11 | 0 | 0 | 81% |
| `iG9CE55wbtY` | legenda | 383 | 3 | 40 | 68% |
| | dividida | 413 | 0 | 0 | 85% |
| `UF8uR6Z6KLc` | legenda | 244 | 1 | 49 | 63% |
| | dividida | 287 | 1 | 0 | 86% |

Nenhuma palavra se perdeu, se repetiu ou trocou de lugar. A fala terminar no fim da frase pouco mudou (de 66% para 61% na palestra, por exemplo): frases longas passam a ser cortadas em vírgulas e conjunções.

## Como os cortes são escolhidos

Programação dinâmica: cada corte e cada tamanho têm um custo, e o programa acha a divisão de menor custo total. Uma regra gulosa, que corta na primeira pausa boa, deixaria sobras de uma palavra no fim.

- Cortar no fim da frase não custa nada; depois de vírgula custa pouco; depois de um artigo custa caro.
- Falas de 4 a 10 palavras e até 6 s não custam nada; fora disso, o custo cresce depressa.
- Um silêncio de 2,5 s sempre separa.
- Sem tempo por palavra, cortar dentro da fala original custa mais.

Os pesos foram escolhidos à mão e conferidos nestes vídeos. O uso real vai dizer se precisam mudar.

Em um vídeo com 20 mil palavras, mais de duas horas, o alinhamento leva 3,7 s e a divisão, 0,8 s.
