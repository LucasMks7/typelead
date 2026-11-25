# Tradução: o que foi medido

Medição de 24 de novembro de 2026, no processador do mesmo computador das outras medidas.

| Medida | Valor |
| --- | --- |
| Tamanho do modelo | 236 MB, baixado em 14 s |
| Carregar | 0,7 s |
| Traduzir uma fala de 3 a 12 palavras | 0,09 a 0,17 s |

**Decisão:** o modelo [opus-mt-tc-big-en-pt](https://huggingface.co/Helsinki-NLP/opus-mt-tc-big-en-pt), da Universidade de Helsinque, na conversão [gow-solucoes/opus-mt-en-pt-ct2](https://huggingface.co/gow-solucoes/opus-mt-en-pt-ct2) para o CTranslate2 em `int8`. A licença é [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). O processador basta, e a placa de vídeo fica para a transcrição.

**Procedência.** O projeto usa uma conversão de terceiros. O `model.bin` dela é idêntico, pelo SHA-256, ao de outra conversão independente, e os arquivos `source.spm` e `target.spm` são idênticos aos originais. A revisão é fixa no código.

## Onde erra

Cada fala é traduzida sozinha, sem o contexto das vizinhas. Exemplos do que saiu:

| Fala | Tradução | |
| --- | --- | --- |
| But your divorce isn't even final yet. | Mas seu divórcio ainda nem é definitivo. | certa |
| She has a better chance of sprouting wings | Ela tem uma chance melhor de brotar asas. | aceitável |
| I'm gonna go out on a limb and say, | Eu vou sair em um membro e dizer: | errada: é "vou arriscar dizer" |
| KEEP EACH OTHER COMPANY | MANTER CADA OUTRA EMPRESA | errada; em minúsculas, "Façam companhia um ao outro." |

Expressões idiomáticas saem ao pé da letra, e a tela avisa que a tradução é automática. Texto todo em maiúsculas passa para minúsculas antes de traduzir. Não foi feita uma avaliação com muitas falas.

## Referência

Tiedemann, J. e Thottingal, S. (2020). *OPUS-MT: Building open translation services for the World*. EAMT 2020.
