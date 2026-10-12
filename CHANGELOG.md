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
