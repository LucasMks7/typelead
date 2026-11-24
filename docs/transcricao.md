# Transcrição pelo som da aba: o que foi medido

Medições de 24 de novembro de 2026, em um notebook com GTX 1050 Ti (4 GB), faster-whisper 1.2.1, CTranslate2 4.9.1, cálculo em `int8`.

## Gabarito

Dezesseis frases em inglês escritas para o teste, ditas pela voz do Windows, cada uma em um arquivo. O silêncio das pontas foi cortado pela energia, e as frases foram juntadas com pausas de 0,15 a 1,2 s. Assim, o começo e o fim de cada frase são conhecidos: 49,7 s, 138 palavras e 27 sinais de pontuação.

A primeira tentativa usou os instantes que a própria voz informa por palavra. Vieram incompletos e errados, e foram descartados.

**É um gabarito fácil:** voz sintética, limpa e devagar. Serve para comparar opções e medir bordas, não para prever o erro em um vídeo real.

## O que cada opção muda

| Opção | Resultado no `large-v3-turbo` |
| --- | --- |
| `vad_filter` ligado | começo da frase até 730 ms adiantado; pontuação 21 de 27 |
| Sem o texto anterior (`condition_on_previous_text=False`) | pontuação cai até 14 de 27 e palavras se repetem na emenda (até 145) |
| Frase de exemplo (`initial_prompt`) | em ruído, o modelo escreve a própria frase de exemplo |
| `hallucination_silence_threshold=2` | não evitou nenhuma invenção e piorou a pontuação |
| **Com o texto anterior e mais nada** | **27 de 27 e 138 palavras, nos três deslocamentos testados** |

`no_speech_prob` deu 0,0 nas frases inventadas, então não serve para achá-las. O detector de voz (Silero) deu 0 s de fala em música e em ruído, e 49 s na fala com música junto.

**Decisão:** o detector não filtra o áudio. Ele escolhe as regiões a transcrever (as separadas por mais de 8 s sem voz são independentes) e julga o que foi escrito: frase curta onde não há voz é descartada. Com menos de 15% de voz detectada, vai tudo, porque pode ser canto.

## Bordas

O Whisper termina a palavra até 230 ms antes de o som acabar. Cortar ali engoliria a última sílaba. As bordas são encostadas no som pela energia. Resultado final, no módulo, em milissegundos (menor / mediana / maior):

| Áudio | Palavras certas | Pontuação | Começo da frase | Fim da frase | Velocidade |
| --- | ---: | ---: | --- | --- | ---: |
| Limpo | 138/138 | 27/27 | -60 / -50 / -40 | -40 / +20 / +40 | 6,5x |
| Música 18 dB abaixo | 138/138 | 27/27 | -440 / -100 / -50 | -40 / +40 / +190 | 6,6x |
| Música 6 dB abaixo | 138/138 | 27/27 | -450 / -150 / +10 | +20 / +90 / +160 | 6,7x |
| Ruído 12 dB abaixo | 138/138 | 27/27 | -450 / -170 / -10 | +20 / +70 / +160 | 6,6x |
| 20 s de música e depois fala | 137/138 | 27/27 | -60 / -50 / +2 | +10 / +20 / +40 | 9,1x |
| Só música, só ruído | nada escrito | | | | |
| Silêncio | recusado com explicação | | | | |

Com música, o começo pode incluir até 450 ms da pausa anterior: incomoda menos que cortar a palavra.

## No navegador

O áudio do gabarito foi tocado dentro da página para uma faixa de som, com uma pausa de 4 s no meio, gravado, enviado e transcrito: 138 palavras, 27 sinais, 550 KB em 54 s. Depois da pausa, os tempos continuaram certos.

- **Atraso constante de cerca de 90 ms:** começo entre +30 e +107 ms, fim entre +87 e +148 ms. É o caminho do som até o gravador.
- **O `MediaRecorder` só começa quando chega som.** Com a aba em silêncio, o programa esperaria para sempre antes de dar play. Uma fonte muda mantém o som contínuo.

## Limites

- **O som de um vídeo real pela aba ainda não foi transcrito.** Depende de autorização no Chrome.
- Não medidos: canto, várias pessoas ao mesmo tempo, sotaques, vídeo longo, anúncio de verdade e aba escondida.
- O descarte do que se ouve com o vídeo parado foi testado com marcas simuladas.
