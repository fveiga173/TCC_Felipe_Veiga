# Curva PSD e breakpoints de ensaio — versão 5.0

Aplicativo Streamlit do TCC de Felipe Veiga. A entrega principal é uma tabela
**frequência (Hz) × PSD (g²/Hz)**, com inclinação para o próximo ponto, curva
reconstruída, Grms, duração representada e comparação com perfis publicados.

O protocolo apoia a definição de solicitações para desenvolver e avaliar
embalagens. O foco é a mesa de vibração aleatória controlada por PSD.

## Usar

1. Envie BIN e TXT correspondentes, ou CSV com `time_s` e um eixo de aceleração.
2. Confira contexto, banda e processamento. O início é **1–200 Hz**, limitado a 200 Hz ou Nyquist, se menor.
3. O perfil principal começa pelos **10% mais intensos** do tempo coberto pelos
   blocos. O percentual é ajustável; é possível usar todos os blocos ou seu
   complemento de menor intensidade.
4. Edite a tabela por PSD ou por inclinação. Curva, Grms, erro e comparação
   acompanham a tabela atual. Também é possível importar duas colunas CSV.
5. Escolha referências, confira a banda comum e registre as justificativas.
6. Exporte o CSV de breakpoints e o ZIP com a memória de cálculo.

A demonstração sintética tem 1000 s a 1000 Hz e aumento de intensidade nos
últimos 100 s. Seus resultados são identificados como `DEMONSTRACAO`.

## Seleção por intensidade

Blocos iniciais de 10 s, sem sobreposição, classificados pelo Grms integrado na
mesma banda da receita. São incluídos os blocos de maior Grms até atingir o
percentual de tempo solicitado; empates numéricos permanecem juntos. A fração
real pode exceder a solicitada, por isso as duas são informadas.

A PSD do grupo é a média **linear ponderada pela duração coberta**. Não é uma
média aritmética de Grms, um percentil por frequência nem um envelope de picos.
As amostras não são concatenadas através de interrupções.

Os 10% de Rissi et al. (2008) são uma estimativa dos eventos retidos pelo
sistema de gatilho/max-overwrite. A seleção deste aplicativo é um procedimento
próprio para registros contínuos, com indicador e algoritmo explícitos.

Períodos suaves permanecem nos dados de origem e na caracterização global. A
receita representa somente os blocos selecionados; ela não recebe automaticamente
a duração de toda a viagem. Efeitos cumulativos e resposta do produto exigem
consideração própria.

## PSD e breakpoints

- Welch: Hann periódica inicial, 4 s, 50% de sobreposição; Hamming disponível.
- Média constante removida por janela; PSD unilateral em g²/Hz, sem zero-padding.
- Janelas nunca atravessam blocos de classificação ou segmentos da aquisição.
- Tempo coberto = N/fs; sobreposição Welch não duplica exposição. Caudas são registradas.
- Grms experimental: raiz da integral do interpolante linear da PSD na banda.
- Breakpoints: interpolação por leis de potência em log-log e integral analítica.
- A aproximação automática conserva a área e adiciona pontos por desvio espectral
  na grade de avaliação. Pontos podem estar entre bins, sem criar informação
  espectral adicional. O critério inicial é 1 dB, com até 160 pontos.
- Se o limite de pontos não atende ao erro escolhido, o aplicativo informa a
  falha. Esse é um critério numérico do estudo, não tolerância da mesa.
- Edições manuais têm seu próprio erro e Grms, sem reescala silenciosa.
- Slope da linha atual para a próxima: `10*log10(S2/S1)/log2(f2/f1)`.
  A última linha fica sem inclinação. Não usar 20 para PSD.

Nyquist e filtros configurados não comprovam banda calibrada. A remoção da média
não corrige mudanças de orientação ou calibração.

## Referências disponíveis

39 perfis em `data/psd_catalog.json`, com origem, edição, tabela/figura,
contexto, seleção e limitações:

| Família | Perfis | Banda original |
|---|---:|---|
| D4169 histórico 2016: baixo/médio/alto | 3 | 1–200 Hz |
| D4169 histórico 2014: I/II/III | 3 | 1–200 Hz |
| Coreia 2020: suspensão e intensidade | 4 | 1–250 Hz |
| Coreia 2024: última milha | 1 | 1–200 Hz |
| D4728-06: exemplos por suspensão/carga | 4 | 1–100 Hz |
| ISO 13355 reproduzido na D4728-06 | 1 | 3–200 Hz |
| Rissi 2008: composto vertical digitalizado | 1 | 1–375 Hz adotados |
| Hungria: Böröcz e Singh 2018, perfil proposto digitalizado | 1 | 1–200 Hz |

A comparação numérica usa **uma única banda comum a todas as referências
selecionadas**, sem extrapolar ou normalizar curvas. Se ISO for selecionada
em um estudo de 1–50 Hz, a comparação passa a 3–50 Hz. São informados Grms na
banda comum, razão de intensidade e distância descritiva de forma em dB.

A curva de Rissi é uma aproximação gráfica, não tabela numérica dos autores:
Grms digitalizado de 0,6217 g em 1–375 Hz versus 0,6284 g publicado; a banda
exata da integral original não está explicitada. Em 1–50 Hz, cerca de 0,3357 g.
A proximidade global não valida cada ordenada. Ver metadados de digitalização.

## BIN/TXT V1 e V2

| Formato | Política |
|---|---|
| V1 | Exige fechamento OK, sem erro/overflow, tamanho e CRC final válidos. Não contém mapa para recuperar lacunas. |
| V2 / firmware v7 | Confere cada prefixo/segmento e seus limites. Aceita REVIEW com segmentos válidos. Sem fechamento final, usa somente o prefixo coberto por checkpoints válidos. |

Configurações suportadas: MPU-6500, 1000 Hz nominais, ±4 g, 8192 contagens/g,
accel DLPF 0, gyro DLPF 1, FCHOICE 0, divisor 0; e legado MPU-6050 500 Hz/DLPF 2.
Z int16 little-endian, 2 bytes por amostra. CRC não é calibração.

O estado original do TXT permanece explícito. Cauda sem checkpoint não entra
na análise. CRC incorreto ou limites inconsistentes bloqueiam o processamento.
Um registro repetido de segmento adota a última linha completa, com aviso e
nova conferência de CRC e limites, como no protocolo de recuperação v7.

A base temporal é nominal por segmento. O índice acumulado é usado apenas
como posição na sequência de dados; não representa pausas reais nem permite
contar perdas exatas. Não se ajusta automaticamente a taxa pelo relógio Arduino.

O BIN permanece int16 e é convertido em pequenos blocos, sem construir um vetor
de tempo ou um DataFrame de toda a coleta. Foi verificado um arquivo sintético
de 172,8 MB; recursos e limites da hospedagem ainda influenciam o uso real.
Uploads são mantidos na sessão de análise; não são gravados no repositório.

CSV: tempos positivos crescentes, variação local até 1% em relação à mediana;
lacunas maiores que 1,5× a mediana separam segmentos. Não há ordenação, remoção
de linhas ou reamostragem automática. A triagem temporal não valida o sensor.

## Exportações

- `perfil_psd.csv`: frequência, PSD e slope para a próxima linha.
- `perfil_freq_psd.csv`: somente as duas colunas para adaptação ao controlador.
- PSD selecionada e PSD de todos os blocos cobertos.
- Blocos classificados, índices das amostras, durações, segmentos e caudas.
- Comparação e referências escolhidas, com valores e proveniência.
- `receita.json`: aquisição, seleção, processamento, versão, hashes e contexto.
- Memória de cálculo e bibliografia.

Não há formato proprietário de controlador implementado. A imagem dos gráficos
pode ser obtida pelo botão de câmera do Plotly.

## Estudo opcional de duração

Um cenário adicional permite `C=T0/Tt`, `Gt=G0*C^(1/k)` e `St= S0*C^(2/k)`,
com k assumido. Fica separado da receita principal, identificado como modelo
não validado. Não demonstra equivalência de dano; não transforma seleção de
registros em compressão equivalente.

## Executar e verificar

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
python -m unittest discover -s tests -v
```

`app.py` permanece na raiz e `main` continua sendo a referência para uma
aplicação Streamlit já conectada ao repositório. Ver `VALIDACAO.md` e
`FUNDAMENTACAO.md`. Módulos científicos da v4 foram preservados para
compatibilidade; a interface atual concentra-se na receita PSD.

A tabela inclui a linha **Este teste — PSD dos blocos selecionados** do arquivo carregado, na mesma banda das referências. Hungria: 12 breakpoints aproximados da Figura 3.7 (p.44) da tese de Böröcz; cerca de 0,38447 Grms reconstruídos versus 0,388 publicado, sem normalização.

## Versão 6: perfil autoral padrão
A abertura exibe TCC Veiga 2026 - Serra Gaucha, exatamente pelos breakpoints fornecidos pelo autor. O perfil é a primeira referência do catálogo e acompanha o programa. Uploads de novos BIN/TXT ou CSV usam o fluxo de análise e já podem comparar com o TCC. O perfil congelado é reconstruído da tabela; os BIN/TXT pessoais não são redistribuídos. Fonte, seleção e limitações ficam visíveis.

## Perfis históricos da Figura 5 de Rouillard (2021)
Sete digitalizações manuais (56 pontos) adicionais, com edição e limites visíveis preservados. Os vértices em pixels, CSV e script estão em data/rouillard_2021. Não são tabelas originais das normas nem substituem suas edições. Grms calculado somente na banda visível; não extrapolar os extremos cortados pela figura. A linha azul D4169-16 média já existente recebeu a nota de associações da legenda. ISO permaneceu com sua fonte anterior.

## Revisão 6.2 — banda 1–200 Hz
O perfil incorporado foi reprocessado a partir do TEST014 original, incluindo limpeza exploratória e seleção dos 10% refeitas na banda de 1–200 Hz. Grms 0,299838544 g; 96 breakpoints; 10970 s retidos e 1100 s selecionados. O limite padrão e máximo da análise é 200 Hz (ou Nyquist se menor). O perfil anterior de 1–50 Hz permanece em data/history, fora do catálogo ativo. O script tools/reprocess_200hz.py permite reproduzir com os arquivos brutos locais, que não são publicados. A banda de cálculo não constitui validação metrológica do sensor.

## Revisão 6.3 — Rissi por operação

Treze perfis verticais das Figuras 7–19 acrescentados ao composto já existente. Fonte, figura, contexto e divergências globais declarados em `data/rissi_2008/LEIA-ME.md`. Aproximações gráficas; não tabelas originais nem normas.
