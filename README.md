# Análise de vibração de transporte — versão 3.0

Aplicativo Streamlit para caracterizar aceleração e elaborar uma proposta de
receita para mesa de vibração com controle PSD. Código comentado em português.

## Uso pelo Streamlit

Este repositório mantém `app.py` na raiz e a branch `main` como referência.
Uma aplicação já conectada a esses parâmetros pode receber a atualização pelo
fluxo GitHub → Streamlit. Não é necessário instalar Python no computador para
usar a aplicação hospedada. Caso a atualização não apareça, confira os logs e
reinicie a aplicação no painel do Streamlit.

A hospedagem e sua configuração de acesso são administradas separadamente do
repositório. Os uploads do sensor são processados pela aplicação; não são
adicionados ao GitHub. O aplicativo não grava medições em disco por iniciativa
própria, não envia comandos à mesa e não faz upload a serviços adicionais.

## Fluxo de análise

1. Carregar CSV ou BIN + TXT do firmware v4 e informar o contexto da aquisição.
2. Conferir qualidade, escala, base temporal e orientação do sensor.
3. Examinar sinal bruto, componente sem média, RMS, PSD e referências.
4. Abrir **Receita PSD**, selecionar trechos, banda e interpolação do controlador.
5. Registrar justificativas, comparar o perfil proposto e exportar o pacote.

**Usar demonstração sintética** permite apresentar o procedimento sem medições
reais. O resultado permanece identificado como DEMONSTRACAO.

## Receita PSD e fundamentos

- Welch por trecho com Hann periódica, remoção da média por janela, PSD
  unilateral, média aritmética e unidades g²/Hz.
- Média das PSDs em escala linear ponderada pelo tempo coberto de cada trecho.
- Trechos [início,fim) sem sobreposição; trechos descontínuos não são concatenados
  antes do cálculo espectral. Parâmetros Welch fixos entre trechos.
- Tempo representado = soma(N coberto/fs). Caudas sem janela completa são
  excluídas e documentadas. Janelas sobrepostas não duplicam o tempo.
- Grms = raiz da integral da PSD na banda. Não há extrapolação de frequência.
- Redução de pontos pelo erro espectral e ajuste numérico que conserva a área.
  O fator aplicado e as diferenças por subfaixas ficam disponíveis.
- Interpolação linear ou log-log. Integração analítica do interpolante,
  incluindo o caso de lei de potência com expoente -1.
- Erro em dB avaliado nos bins e em 8 subintervalos entre bins. É um critério
  de representação do projeto, não tolerância normativa do controlador.
- Duração no nível pleno igual à exposição coberta. Partida não incluída.
  Não há aumento de intensidade, compressão temporal ou equivalência de dano.

A banda inicial 3–50 Hz é uma escolha de estudo, não declaração de banda útil
calibrada. Perfil médio não preserva ordem temporal, impactos individuais ou
distribuição de amplitudes. As diferenças de Grms entre trechos ajudam a avaliar
a necessidade de receitas em blocos. A receita da mesa convencional é etapa futura.

## Aquisição e estados

BIN + TXT: verifica último status, erros, transbordamentos, tamanho e CRC32.
Compatibilidade: MPUZ_RAW_LE_V1, 500 Hz, ±4 g, 8192 contagens/g, DLPF_CFG=2.
O tempo n/500 é nominal e não mede jitter. A estimativa N/T do Arduino é exibida,
mas não substitui automaticamente a taxa nominal nem representa calibração.

CSV: exige `time_s` e uma coluna de aceleração. Comentários do conversor são
lidos, mas não permitem verificar o CRC do BIN a partir do CSV. Use o par
original para conferir integridade em aquisições FIFO.

- DEMONSTRACAO: dados sintéticos.
- ESTUDO_PRELIMINAR: dados funcionais, documentação incompleta, indícios de
  saturação, diagnóstico pendente ou erro de representação acima do escolhido.
- PROPOSTA_PARA_REVISAO_TECNICA: documentação declarada e critérios atendidos;
  não equivale a autorização de execução, calibração ou conformidade normativa.

O responsável deve conferir limites da mesa com a carga (força, curso, velocidade,
aceleração), orientação, resposta em frequência e base temporal. O software
registra essa revisão, mas não calcula os limites mecânicos do equipamento.

## Exportação rastreável

ZIP com perfil genérico CSV, PSD representativa, cobertura por trecho,
comparação por subfaixas, receita JSON e memória de cálculo em Markdown.
Inclui status, configurações, justificativas, hashes de entrada/código e versões.
O formato não é específico de fabricante: conferir importação, unidades,
interpolação e limites no controlador.

## Organização e testes

- `app.py`: interface e caracterização.
- `psd_recipe.py`: núcleo científico, leitura binária e exportação.
- `recipe_ui.py`: interface da prescrição e justificativas.
- `tests/`: verificações analíticas, integridade e fluxo Streamlit.

Dez testes cobrem integrais conhecidas, RMS senoidal, ponderação temporal,
cobertura, dados inválidos, simplificação, integridade binária, exportação e
interface com AppTest. Execute no ambiente de desenvolvimento:

```bash
python -m unittest discover -s tests -v
```

Os testes de software não substituem validação experimental no veículo e na mesa.

## Execução local opcional

Se desejar no futuro, instale Python 3.12 e abra o terminal **na pasta do código**.
No Windows com o launcher instalado:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

## Referências

- ASTM D4728-06: seções 8.2, 8.3 e 10.2–10.4, edição adotada no projeto.
- Rouillard et al. (2021), Packaging Technology and Science 34(6), 339–351.
  DOI: 10.1002/pts.2563.
- https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html
- https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest

Curvas de comparação: ASTM D4728-06 X1.1 (Truck) e ISO 13355 reproduzida em
X1.3 da mesma ASTM. Não constituem verificação de edição atual da ISO.
