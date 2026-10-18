# Fundamentação e decisões da versão 5.0

A entrega do TCC é a curva de ensaio definida por tabela Hz × g²/Hz,
inclinações, Grms e duração, a partir de medições próprias e comparação
rastreável com normas e campanhas anteriores.

## Relação com o problema industrial

A proteção insuficiente pode favorecer avarias; reforço excessivo aumenta
custo e consumo de materiais. Medir o ambiente e justificar o ensaio apoia o
projeto da embalagem. O programa não verifica dano de produto ou economia de
material: essas conclusões dependem de experimentação específica.

## Fontes e contribuição

| Fonte | Aplicação | Limite relevante |
|---|---|---|
| Eagleton, 1995, cap. 4 e apêndices B/C | Aquisição → PSD → perfil para controlador; Hamming e verificação do conjunto | Disparo, intervalo morto e sobrescrita; não replica nossa coleta contínua |
| ASTM D4728-06 fornecida, 8.2–8.4 e 10.2–10.5 | Representatividade, controle, partida e duração | Edição identificada; igualdade de Grms não certifica o ensaio |
| Rissi et al., 2008, DOI 10.1002/pts.797 | Referência brasileira e foco em registros intensos | Os 10% são estimativa de retenção por gatilho/max-overwrite; curva aproximada por digitalização |
| Park/Choi/Jung, 2020, DOI 10.3390/app10196754 | Perfis por suspensão/intensidade e tabelas de breakpoints | Composição própria por pontos elevados; veículos descarregados |
| Kim/Horvath/Lee/Lee, 2024, DOI 10.3390/app14083245 | Perfil composto de última milha com 17 breakpoints | Seul e veículos/seleção específicos |
| Lansmont, justificativa D4169, rev. 22/09/2016 | Perfis históricos baixo/médio/alto e comparação com 2014 | Não comprova texto normativo vigente; manter famílias separadas |
| Rouillard et al., 2021, DOI 10.1002/pts.2563 | Variabilidade e representatividade das simulações | Não fornece um expoente universal de dano |
| Wallin, CETEA 20(1), 2008 | Diferentes níveis de intensidade e duração | Limiares Amgen não são universais |
| Dantas/Kipp, CETEA 21(2), 2009; Shire/Shires, 24(1), 2012 | Discussão de duração e expoente assumido | O original DOI 10.1002/pts.915 é citado pela tradução; não se afirma leitura integral do original |
| Dunno, CETEA 28(2), 2016 | Métodos de redução e diferença de resposta/dano | Resultados específicos de produto/montagem; algoritmo SaverXware não integralmente fornecido |
| Hanly/enDAQ | Construção e simplificação de perfis; examinar forma além de Grms | Orientação técnica; VRS não implementada nesta versão |
| SciPy, documentação de Welch/get_window | Normalização espectral e janela periódica explícita | Parâmetros iniciais são escolhas do estudo |

Fontes completas em `references.py`; contexto de cada curva em
`data/psd_catalog.json`. Os PDFs consultados não são redistribuídos no repositório.

## Decisões implementadas

1. Banda inicial de estudo: 1–50 Hz; aquisição nominal permanece 1000 Hz no MPU-6500.
2. Classificação por Grms na banda, em blocos iniciais de 10 s. Seleção inicial
   dos 10% superiores por tempo coberto, mantendo blocos inteiros e empates.
   Percentual e duração efetivos são sempre apresentados.
3. A implementação de ranking não é o algoritmo de Rissi nem uma reprodução
   dos métodos de conexão de pontos elevados dos artigos coreanos.
4. Welch independente por bloco e segmento: Hann ou Hamming periódicas,
   nperseg fixo, densidade unilateral e média aritmética linear.
5. Média de PSDs ponderada por duração coberta. Nunca média aritmética de Grms.
6. Caudas excluídas e documentadas; nenhuma janela cruza uma lacuna. Sobreposição
   espectral não duplica a duração representada.
7. Breakpoints interpolados por leis de potência em log-log. Seleção adaptativa
   de pontos na grade 8x; pode usar frequências entre bins, sem alegar nova
   resolução. Grms preservado na aproximação automática.
8. O próximo ponto é escolhido pelo desvio antes do ajuste de área, evitando
   que o ajuste global esconda a falta de um pico estreito na aproximação.
9. Edição por PSD ou slope: níveis, curva, métricas e comparação são recalculados.
   Edições manuais não são normalizadas para forçar o Grms de origem.
10. Comparação em interseção única para todos os perfis escolhidos. Razão de
    Grms descreve intensidade; RMS do erro em dB sem nível médio descreve forma.
11. Perfil intenso recebe a duração dos blocos selecionados, não da viagem inteira.
12. O cenário opcional de duração usa hipóteses explícitas: C=T0/Tt, amplitude
    multiplicada por C^(1/k), PSD por C^(2/k). Não estabelece dano equivalente.
13. O V2 permite analisar prefixos verificados, mantendo REVIEW/INCOMPLETE e
    limites de segmentos. Falha de integridade não é convertida em OK.

## Limites da interpretação

A PSD média não mantém ordem temporal, impactos individuais ou distribuição de
amplitudes. Um processo não gaussiano também pode ter PSD; calcular PSD não
exige remover seus extremos. O programa não aplica filtro automático de picos.

Mesmo Grms não garante mesma resposta de uma embalagem. A intensidade por
bloco também não identifica, sozinha, os mecanismos de dano do produto.
Trechos suaves podem contribuir por duração ou ressonância. A seleção e os
modelos devem ser justificados com o objetivo e os resultados da campanha.

Rissi é uma aproximação gráfica identificada como tal, com Grms global próximo
mas não idêntico ao publicado. Sua largura de banda de cálculo informada de
1,875 Hz limita interpretações finas da forma abaixo de 3 Hz. O perfil de uma
campanha não constitui norma de uma região.

Calibração, resposta do sensor, fixação, orientação, frequência efetiva, capacidade
da mesa com carga e avaliação de avarias exigem verificações próprias. O foco
atual é a mesa aleatória controlada por PSD; não há equivalência atribuída à mesa
senoidal. A conclusão do TCC deve distinguir cálculo, funcionamento do sistema,
reprodução física em laboratório e eventual avaliação da embalagem.
