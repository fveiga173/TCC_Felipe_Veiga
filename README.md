# Análise de vibração de transporte — versão 4.0

Aplicativo Streamlit para o TCC de Felipe Veiga: aquisição de baixo custo,
caracterização de vibrações no piso do veículo e elaboração de um guia prático
reproduzível de parâmetros de ensaio. Código e memória de cálculo em português.

O aplicativo não avalia danos, não certifica embalagens, não prevê vida útil e
não comanda a mesa. Equivalência de dano exige validação experimental para o produto/situação.

## Uso no Streamlit

`app.py` permanece na raiz e `main` é a referência. Uma aplicação conectada a
esses parâmetros recebe a atualização pelo fluxo GitHub → Streamlit. Não é
necessário instalar Python para usar a aplicação hospedada. Se necessário,
consultar os logs ou reiniciar a aplicação no painel do Streamlit.

Os uploads são processados em memória e não são adicionados ao GitHub nem
enviados a serviços adicionais. O cache da análise por blocos é limitado a duas
entradas por processo, usa SHA256 da origem e não grava em disco. Hospedagem e
controle de acesso são administrados separadamente do código.

## Fluxo em três etapas

1. **Caracterizar percurso:** leitura, diagnóstico, sinal temporal, RMS por
   intervalo, PSD e comparação com referências na mesma banda.
2. **Definir receitas:** perfil PSD de referência e, opcionalmente, análise de
   níveis e cenários de duração. Receita senoidal exploratória em aba própria,
   com limites explícitos e sem compressão de tempo.
3. **Guia e exportação:** parâmetros, justificativas, critérios, fontes e hashes.

Demonstração sintética: 60 s a 1000 Hz, componentes de 8 e 35 Hz e mudança
de intensidade aos 40 s. Saídas rotuladas DEMONSTRACAO.

## Aquisição BIN + TXT

Verifica status final OK, ausência de erro/transbordamento, quantidade de bytes,
CRC32, conversão e configuração. Aceita prefixos do monitor serial; o último
status do TXT prevalece.

| Perfil suportado | Configuração exigida no TXT |
|---|---|
| Legado v4, MPU-6050 | 500 Hz, ±4 g, 8192 contagens/g, DLPF_CFG=2; WHO_AM_I ausente ou 0x68 |
| v6, MPU-6500 | WHO_AM_I=112/0x70, 1000 Hz, ±4 g, 8192 contagens/g, divider=0, gyro_dlpf_cfg=1, accel_dlpf_cfg=0, gyro_fchoice_b=0 |

Formato `MPUZ_RAW_LE_V1`: um int16 little-endian de Z por amostra.
Tempo `sample_index_nominal`: índice n/fs, sem medição de jitter do sensor.
Estimativa N/T do Arduino não substitui a taxa nominal automaticamente.
CRC e configuração dos registradores não são calibração metrológica.

CSV exige `time_s` e aceleração. Metadados comentados são lidos; coleta
incompleta, erro ou overflow bloqueia parâmetros. CSV não revalida CRC do BIN.

## PSD de referência

- Welch por trecho: Hann periódica padrão, Hamming periódica opcional.
- Inicial: 4 s, 50% de sobreposição, média removida por janela, PSD unilateral
  g²/Hz, média aritmética em escala linear. São escolhas do projeto.
- Sem zero-padding. Espaçamento fs/N e ENBW da janela são documentados.
- Média de PSDs ponderada pelo tempo coberto. Trechos descontínuos não são
  concatenados antes da FFT; intervalos [início,fim) não se sobrepõem.
- Tempo = N_coberto/fs; sobreposição Welch não duplica exposição; caudas são
  excluídas e documentadas. Partida não entra no tempo pleno.
- Grms = sqrt(integral da PSD na banda), sem extrapolação de frequência.
- Simplificação por erro espectral com preservação da área do interpolante;
  linear ou log-log com integração analítica, incluindo expoente -1.
- Erro em dB nos bins e oito subintervalos entre bins é critério de
  representação do projeto, não tolerância normativa de controle da mesa.

Banda inicial 3–50 Hz é faixa de estudo; Nyquist, filtro configurado e ausência
de overflow não comprovam banda calibrada ou ausência de aliasing. Remover a
média não corrige mudanças de orientação/gravidacional durante a coleta.

## Níveis e cenários de duração

Ativar **Analisar perfis por intensidade e cenários de duração** na receita PSD.
Usa os trechos e a mesma banda/janela/taxa da receita. Blocos começam em 10 s,
sem sobreposição entre blocos; caudas sem janela completa são registradas.
A referência dos cenários é recalculada na cobertura desses blocos.

Grms por bloco é integrado na banda. RMS temporal, pico amostrado, fator de
crista e curtose usam o sinal com média local removida na banda registrada
inteira. Não acionam exclusão automática de eventos.

P80 inicial é quantil EMPÍRICO de Grms ponderado pelo tempo: baixos <= limiar,
altos > limiar. Empates ficam juntos; a proporção obtida pode diferir de 80/20.
Há limiar manual opcional; nenhum limiar publicado é aplicado automaticamente.

| Alternativa | Intensidade | Duração |
|---|---|---|
| Referência sem redução | PSD média dos blocos | Toda cobertura dos blocos |
| Dois níveis sem redução | PSD média de cada grupo | Cobertura de cada grupo |
| Compressão por intensidade | PSD ×C^(2/k) | T_original/C |
| Seleção de alta intensidade | PSD média dos blocos mantidos | Soma de suas durações, sem amplificação |

Alternativas independentes: não combinamos descarte com amplificação. Dois
níveis não preservam cronologia e não são síntese SVS ou reprodução do
algoritmo de espectros de probabilidade do SaverXware.

```
C = T_original / T_ensaio
G_ensaio = G_original * C**(1/k)
PSD_ensaio(f) = PSD_original(f) * C**(2/k)
```

k=2 é hipótese, não medido pelo sensor. Para C=5: Grms ×sqrt(5), PSD ×5;
frequências e forma preservadas. C=1–5 segue recomendação HISTÓRICA de Kipp,
sem garantia de equivalência, norma atual ou capacidade da bancada.
Sensibilidade a k=2,3,4,5,6 e ao k informado é exportada.

Índice sum(Tj*Grms_j**k) compara a exposição hipotética mantida para k=2,4,6;
não é dano ou vida útil e não contempla resposta espectral/mecanismo de falha.
Toda saída recebe **Proposta de ensaio baseada em modelo, pendente de validação
experimental**. Ver FUNDAMENTACAO.md.

## Receita senoidal exploratória

Centro de 1/3 de oitava com maior integral de PSD, ou frequência manual.
Intensidade pelo RMS local (padrão) ou concentração do Grms da faixa inteira.
Pico = sqrt(2)*RMS; deslocamento p-p = 2*a_pico*g/(2πf)². Sem compressão de
tempo. RMS igual não comprova resposta ou dano equivalente. ISO 2247:2000 é
referência contextual, sem declaração de conformidade automática.

## Estados e exportação

- DEMONSTRACAO: dados sintéticos.
- ESTUDO_PRELIMINAR: documentação ou critério pendente, incluindo saturação
  ou erro de representação acima do escolhido.
- PROPOSTA_PARA_REVISAO_TECNICA: documentação declarada e critérios atendidos;
  não autoriza execução ou comprova calibração, dano ou conformidade.

Todos os cenários: `experimental_validation_pending=true`,
`damage_equivalence_claimed=false`, `machine_authorization=false`.
Conferir força, curso, velocidade, aceleração, carga e controlador da mesa.

ZIP de referência: perfil genérico CSV, PSD, trechos, subfaixas, JSON, memória
e referências. ZIP de cenários: alternativas, sequências, blocos, exclusões,
sensibilidade, índice hipotético e guia com hipóteses/fontes/hashes.
Formato genérico: conferir unidades/interpolação antes de importar na mesa.

## Desenvolvimento

`app.py`: caracterização; `psd_recipe.py`/`recipe_ui.py`: receita PSD;
`vibration_scenarios.py`/`scenario_ui.py`: níveis e cenários;
`references.py`/`FUNDAMENTACAO.md`: fontes e limites;
`fixed_frequency.py`/`freq_recipe_ui.py`: proposta senoidal.

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m streamlit run app.py
```

Testes de integrais, RMS, potência, cobertura, percentis, CRC e fluxo AppTest
não substituem validação experimental. Versões efetivas acompanham a exportação.

## Referências

Eagleton (1995); Wallin/CETEA (2008); Kipp/Dantas (2009); Shire/Shires,
resumo traduzido (2012; original referenciado DOI 10.1002/pts.915); Dunno (2016);
ASTM D4728-06; Rouillard et al. (2021), DOI 10.1002/pts.2563; documentação SciPy.
Identificação detalhada: FUNDAMENTACAO.md e exportações.

Curvas: ASTM D4728-06 X1.1 (Truck) e ISO 13355 reproduzida em X1.3 da mesma
ASTM. Não verifica edição atual da ISO; proximidade de Grms não é conformidade.
ISTA 3E não é adicionada como curva independente sem transcrição verificada.
