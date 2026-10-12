# Verificação da versão 4.0.0 — 12/10/2026

## Software

25 testes de unittest aprovados: integrais analíticas, RMS senoidal, seleção
de banda, conversão senoidal, média temporal de potência, cobertura sem dupla
contagem, caudas, trechos descontínuos, janelas Hann/Hamming, classificação por
tempo e empates, compressão com expoente declarado, exportação e integridade.
AppTest percorreu demonstração, parâmetros inválidos, BIN/TXT, compressão e
seleção sem blocos elegíveis. Sem exceções não tratadas nesses fluxos.

Ambiente de execução: numpy 2.3.5, pandas 2.2.3, scipy 1.17.0,
streamlit 1.65.0, plotly 6.9.0. As versões efetivas de cada execução também
acompanham a exportação; não se afirma verificação de toda combinação permitida.

## Arquivos reais fornecidos pelo autor

| Arquivo | Resultado de integridade/configuração | Resultado de processamento |
|---|---|---|
| TEST000 | 60.234 amostras, CRC32 1021207251, MPU-6500 v6/1000 Hz; aceito | 60,234 s nominais; Welch 60 s cobertos; 6 blocos de 10 s; Grms em 3–50 Hz ≈0,00229470 g |
| TEST045 | 60.258 amostras, CRC32 373969637, MPU-6500 v6/1000 Hz; aceito | 60,258 s nominais; Welch 60 s cobertos; 6 blocos de 10 s; Grms em 3–50 Hz ≈0,00148228 g |
| TEST048 | Estado final REVIEW/falha | Bloqueado antes da geração da receita |

Parâmetros: Hann periódica, janela de 4 s, sobreposição de 50%, banda 3–50 Hz.
Os dados de sensor não foram adicionados ao repositório. TEST000 também foi
executado no fluxo AppTest de upload → caracterização → cenários sem exceção.

Esses arquivos são testes funcionais; os Grms acima não caracterizam transporte
rodoviário representativo, calibração, banda útil ou equivalência de dano.

## Limite da verificação

Verifica implementação e consistência de entradas/saídas. Não realiza ensaio
físico em veículo/mesa, avaliação de produto, calibração ou certificação.
Capacidade do controlador com a carga e correlação experimental são verificações
externas ao aplicativo. A disponibilidade da aplicação hospedada depende do
ambiente Streamlit conectado ao repositório.
