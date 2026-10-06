# Analisador de vibração — TCC

Aplicativo Streamlit para importar CSV do registrador Arduino e inspecionar sinal, FFT, PSD experimental bruta, PSD experimental representativa (média de segmentos), Grms e comparação com perfis de referência ASTM D4728, ISO 13355 e ISTA 3E.

## Executar

Requer Python 3.10 ou superior.

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

## Formato do CSV

O app tenta detectar separador e cabeçalho automaticamente. Selecione a coluna de tempo, o eixo de aceleração e suas unidades na interface. O firmware `MPU6050_SD_logger.ino` do projeto produz dados de tempo e aceleração por eixo. Exporte o registro como CSV com uma linha de cabeçalho, por exemplo:

```csv
time_ms,ax,ay,az
0,0.014,-0.021,1.002
10,0.017,-0.019,0.998
```

O app estima `Fs = 1/mediana(Δt)`. Em unidade de tempo `Auto`, uma coluna numérica cujo passo mediano seja pelo menos 1 é interpretada como milissegundos (caso comum do `millis()`); verifique isso e escolha explicitamente s, ms ou µs se a inferência não corresponder ao arquivo. A unidade da aceleração pode ser g ou m/s².

## Método e interpretação

- Remove-se a componente média do eixo selecionado.
- A FFT com janela Hann é exibida para inspeção espectral.
- A PSD bruta é uma estimativa de Welch do registro completo. A PSD representativa é a média aritmética das PSDs de segmentos completos consecutivos, sem sobreposição. Ambas ficam visíveis; “média de segmentos” descreve a operação e não significa uma PSD filtrada ou ajustada à curva normativa.
- Os perfis normativos são definidos por breakpoints e conectados por interpolação log-log (lei de potência). Isso é somente a representação computacional entre pontos e não afirma que as normas aplicaram suavização.
- O app compara RMSE em log-PSD, forma espectral (curvas centradas em log-PSD) e razão de Grms experimental/referência, na faixa escolhida e dentro da cobertura do perfil. A tabela inclui os Grms globais publicados como contexto; o cálculo na banda observada não os substitui.
- Proximidade numérica não demonstra conformidade. A conformidade depende de requisitos completos da edição aplicável, configuração e procedimento de ensaio.

## Proveniência dos perfis

Os breakpoints embutidos são os transcritos na conversa do projeto a partir de ASTM D4728-06, Appendix X1, Table X1.1 (Truck); ISO 13355, perfil indicativo apresentado na Table X1.3 da cópia da ASTM citada; e ISTA 3E (2005), Random Vibration Spectrum. Para ASTM existe PDF no diretório `sources/`. Não há cópias independentes da ISO 13355 nem ISTA 3E neste projeto. Confira os valores, a edição e as condições de aplicação na publicação oficial/licenciada antes de citar ou usar para qualificar um ensaio. Os breakpoints ASTM Truck e ISTA 3E usados aqui são equivalentes conforme a transcrição de referência disponível.

## Limitações

Este é um analisador de apoio ao TCC, não um instrumento certificado nem uma ferramenta de declaração de conformidade. Amostragem irregular, aliasing, orientação/montagem do sensor, calibração, faixa dinâmica e transientes podem afetar os resultados. A advertência de jitter aparece na interface quando a variação dos intervalos de amostragem excede 5%. Verifique que a frequência de Nyquist cobre a banda de interesse e que a aquisição não saturou.
