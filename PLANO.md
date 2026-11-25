# typelead

Treino de inglês com vídeos.

A pessoa escolhe um vídeo, ouve uma fala por vez e digita o que entendeu. O programa corrige, descobre por que ela errou e traz o trecho de volta no dia certo.

O repositório se chama `typelead`; a pasta local continua `04-englishVideos`.

## Objetivo

- **Uso pessoal:** treinar escuta e vocabulário de inglês todos os dias, com vídeos de que o Lucas gosta.
- **Repertório:** mostrar um produto completo, com Python, SQL, interface web, processamento de fala local e testes.

## O que nos diferencia

A ideia de digitar junto com vídeos já existe em outros sites. O que este projeto tenta fazer melhor:

1. **Falas de tamanho bom.** A legenda original traz linhas de 1 palavra e linhas de 35. O programa junta as curtas e divide as longas.
2. **Lacunas escolhidas por motivo.** Esconde as palavras que valem a pena treinar, conforme o nível e o histórico de erros. Por enquanto, elas são sorteadas; a escolha depende do banco de palavras (sessão 52).
3. **Diagnóstico do erro.** Separa erro de digitação, palavra desconhecida e palavra conhecida que o ouvido não pegou.
4. **Revisão espaçada com o trecho original.** A palavra errada volta dias depois, no áudio em que apareceu.
5. **Sem cota de minutos e sem assinatura.** Roda no PC; os dados são do usuário e saem para o Anki.
6. **Aceita qualquer link do YouTube**, com ou sem legenda. Os limites estão mais abaixo.

## Modos

| Modo | O que a pessoa faz | Quando entra |
| --- | --- | --- |
| Tudo oculto | Ouve e completa a fala inteira, vendo quantas letras tem cada palavra | Primeira versão utilizável |
| Lacunas | Igual, com algumas palavras sorteadas à mostra | Primeira versão utilizável |
| Texto livre | Ouve e digita a fala inteira, sem pista | Primeira versão utilizável |
| Revisão | Refaz os trechos vencidos | Segunda etapa |
| Assistir | Vê o vídeo com a legenda que acompanha | Segunda etapa |
| Repetição em voz alta | Grava a própria fala e compara | Depois da v1.0 |

## Decisões

- **Formato:** programa local que abre no navegador, em `http://localhost`. Não há servidor na internet, conta nem login.
- **Servidor:** Python com FastAPI. Guarda os dados, prepara as falas e escolhe lacunas e revisões.
- **Interface:** HTML, CSS e JavaScript em módulos, sem framework nem etapa de build no começo. A correção letra a letra fica no navegador, porque precisa responder na hora; os testes usam o `node --test`.
- **Banco:** SQLite, com SQL escrito à mão. É parte do objetivo de currículo.
- **Vídeo:** player oficial incorporado do YouTube, ou arquivo do próprio PC na tag `<video>`. O programa não baixa o vídeo do YouTube. Quando o dono proíbe a incorporação, entra a extensão.
- **Transcrição:** faster-whisper, reaproveitando o que foi medido no transcritor de aulas. Na GTX 1050 Ti, `large-v3-turbo` em `int8`. Aqui será usado o tempo de cada palavra. A velocidade foi medida em português; em inglês será medida na sessão 44.
- **Tradução:** OPUS-MT inglês-português, no processador, pelo CTranslate2 que o faster-whisper já traz. Só quando a pessoa pede.
- **Revisão espaçada:** algoritmo FSRS, pela biblioteca `fsrs` (licença MIT).
- **IA paga:** nenhuma no caminho principal. Explicações começam por um dicionário offline.

## Qualquer link do YouTube

Requisito do Lucas: colar o link de qualquer vídeo do YouTube e praticar. Dois problemas precisam de solução: conseguir o texto e conseguir tocar.

**Formatos de link:** `watch`, `youtu.be`, Shorts, lives gravadas, `embed`, YouTube Music, versão de celular, com `t=` ou dentro de uma playlist. Todos viram o mesmo identificador de vídeo.

**Texto**, na ordem em que o programa tenta:

1. **Legenda do autor**, lida pelo link com o yt-dlp, sem baixar o vídeo.
2. **Legenda automática** do YouTube, do mesmo jeito. Erra mais; a tela avisa.
3. **Transcrição local.** Se não há legenda, ou se o YouTube recusar o pedido, o programa grava o som da aba enquanto o vídeo toca, com autorização da pessoa, e o Whisper transcreve no PC. Leva a duração do vídeo. O som gravado é apagado depois da transcrição.

A pessoa também pode abrir um arquivo `.srt` ou `.vtt`, ou um vídeo próprio do PC.

**Reprodução:**

1. **Player incorporado** do YouTube, na tela do programa.
2. **Extensão do Chrome**, para o vídeo cujo dono não permite incorporação: o treino aparece na própria página do YouTube, onde o vídeo pode tocar.

**O que fica de fora:** vídeo privado ou removido, bloqueado no país, pago ou com DRM. Vídeo com restrição de idade ou só para membros depende de a conta da pessoa ter acesso, e só pela extensão. O programa não usa tokens nem plugins para passar por verificações do YouTube. Vídeo sem fala em inglês abre, mas não tem o que praticar.

A API oficial do YouTube não resolve a legenda: ela só permite baixá-la a quem pode editar o vídeo.

**Provado na sessão 41:** o Chrome inclui o som do player incorporado na gravação da aba ([docs/player.md](docs/player.md)).

**Ainda não provado:** se esse som basta para uma boa transcrição (sessão 44) e se a extensão consegue controlar a página do YouTube (sessão 56).

## Dados principais

| Tabela | O que guarda |
| --- | --- |
| `videos` | Origem, título, duração e o ponto em que a pessoa parou |
| `falas` | Início, fim, texto, tradução e ordem dentro do vídeo; trocar a legenda cria outra versão |
| `palavras` | Forma base, frequência no inglês e situação para o usuário |
| `tentativas` | Uma resposta: modo, texto digitado, repetições, velocidade, dicas e duração |
| `itens` | Cada palavra de uma tentativa: a esperada, a digitada e se estava certa |
| `cartoes` | Estado da revisão espaçada de cada palavra ou fala |

## Como descobrir o tipo do erro

| Sinal | Diagnóstico |
| --- | --- |
| Diferença de uma letra, ou tecla vizinha, em palavra já acertada antes | Digitação |
| Acertou depois de reduzir a velocidade ou repetir | Escuta |
| Não acertou nem devagar, ou pediu a tradução | Vocabulário |
| Trocou por palavra de som igual (*their* e *there*) | Homófono |
| `don't` no lugar de `do not`, pontuação ou maiúscula | Não conta como erro |

São regras simples, que podem ser explicadas e testadas. A medida de sucesso é quantas vezes o Lucas discorda do diagnóstico.

## Riscos

| Risco | O que fazer |
| --- | --- |
| O YouTube recusar o pedido da legenda | Transcrever pelo som da aba ou abrir um arquivo de legenda |
| O som gravado da aba não dar uma boa transcrição | Medir na sessão 44; a gravação em si já foi validada |
| O dono do vídeo proibir a incorporação | Detectar o erro do player e avisar logo ao adicionar; a extensão resolve na sessão 56 |
| Erro 153 do player, por falta do cabeçalho `Referer` | Servir por HTTP, nunca por `file://`. Testado: não ocorre |
| O player parar fora do ponto exato | Medido: até 9 ms de atraso, sem precisar de margem ([docs/player.md](docs/player.md)) |
| Legenda fora de sincronia com o áudio | Ajuste de atraso por vídeo |
| O projeto crescer demais antes de ser usado | Versão utilizável na sessão 49; o resto só depois de uso real |

## Cuidados

- Código, textos, nome e visual próprios. Nada é copiado de outro site.
- O repositório nunca leva vídeos, áudios, legendas de terceiros, o banco ou modelos. Os testes usam frases escritas para eles ou material de licença livre.
- Uso pessoal. O README deve avisar que os Termos de Serviço do YouTube restringem o acesso automatizado e os downloads.
- O banco fica em `%APPDATA%`, e os modelos e o ambiente virtual, fora do OneDrive.
- O servidor escuta apenas em `127.0.0.1`.
- Conferir a licença de toda lista de frequência, dicionário e modelo de tradução antes de adotar.

## Pronto quando

- Do link à primeira fala praticada passam menos de 30 segundos, em um vídeo com legenda.
- Em uma lista de 20 links variados (Shorts, live, música, sem legenda, incorporação bloqueada), todo vídeo que a conta consegue assistir pode ser praticado.
- Um vídeo sem legenda pode ser praticado sem serviço pago.
- Os erros de um dia voltam na revisão, com o trecho original.
- O Lucas usou o programa em 10 dias diferentes, e o painel mostra a evolução.

## Depois da v1.0

Repetição em voz alta, explicação com IA opcional, modo de ordenar as palavras, outros idiomas e versão para celular.
