# Histórico de versões

## 6.3.0 — 25/10/2026

- Treze PSDs verticais de Rissi: dez regiões metropolitanas e três rotas longas.
- Catálogo com 39 perfis; composto anterior preservado sem duplicação.
- CSVs em 1–200 Hz e banda ampla até 375 Hz, calibração e conferência reproduzível.
- Divergências globais maiores que 5% sinalizadas; sem normalização de níveis.

## 6.2.0 — 25/10/2026

- Reprocessamento do TEST014 original em 1–200 Hz, com limpeza e seleção de intensidade revistas.
- Perfil incorporado: 0,29984 Grms, 96 breakpoints, erro máximo 0,95435 dB.
- Análise padrão e limite máximo de 200 Hz; perfil anterior preservado em histórico.


## 6.1.0 — 25/10/2026

- Sete perfis históricos digitalizados da Figura 5 de Rouillard et al. (2021), com 56 pontos e rastreabilidade por pixels.
- Catálogo com 26 perfis; limites visíveis sem extrapolação; notas de incerteza na interface.


## 6.0.0 — 24/10/2026

- Perfil TCC Veiga 2026 - Serra Gaucha abre por padrão sem upload.
- Perfil autoral como primeira referência, com tabela congelada e proveniência.
- Upload de novos testes mantém comparação com o perfil incorporado.


## 5.0.1 — 24/10/2026

- Linha Este teste na comparação numérica e identificação no gráfico, respeitando banda comum.
- Perfil húngaro proposto por Böröcz e Singh (2018), digitalizado da tese, com proveniência e ressalvas.


## 5.0.0 — 18/10/2026

- Fluxo principal centrado na tabela de breakpoints, curva PSD, Grms e duração.
- Banda inicial 1–50 Hz; seleção inicial dos 10% mais intensos por tempo coberto, ajustável, com blocos inteiros e empates explícitos.
- Editor por frequência/PSD ou slope, importação CSV e recálculo de curvas, erros, comparações e exportações.
- Catálogo de 17 perfis, incluindo Coreia 2020/2024, curvas históricas e Rissi digitalizado com ressalvas.
- Comparação em banda comum sem extrapolação ou normalização das referências.
- Leitura V2 com CRC por segmento, tratamento de prefixos incompletos e preservação das lacunas; V1 permanece estrito.
- Conversão do BIN em blocos e verificação computacional de arquivo de 172,8 MB.
- Exportação rastreável de perfil, seleção, segmentos, referências e memória de cálculo.
- Estudos de compressão opcionais e identificados como modelo não validado, separados da curva principal.
- Interface concentrada em mesa PSD; código científico legado preservado.
- 41 testes automatizados aprovados e fluxo completo verificado com TEST007/010/011.

# Histórico

## 4.0.0 — 12/10/2026

Base: main, commit `1b0f84e9e9ad970d89bc5260bafd6ef0e1eb9111`, com as
alterações posteriores à 3.2 de receita senoidal e simplificação do fluxo.

- BIN/TXT v6 MPU-6500 a 1000 Hz, mantendo v4 de 500 Hz.
- Prefixos do monitor serial; bloqueio de metadados CSV com falha.
- Hamming opcional; janela, ENBW e taxa registradas explicitamente.
- Blocos não sobrepostos com Grms na banda, picos, fator de crista e curtose.
- Percentil temporal ou limiar manual sem exclusão automática de eventos.
- Referência, dois níveis, compressão com k declarado e seleção de intensidade.
- Cobertura/caudas registradas; sensibilidade a k; separação de ajuste numérico
  do perfil e aumento físico da intensidade.
- Exportação de sequências, blocos, exclusões, fórmulas, fontes e ressalvas.
- Guia de fundamentação e revisão das premissas.

Foco no guia prático: sem executar bancada, calcular dano, certificar ou alegar
equivalência sem validação experimental.
