# Analisador de vibração — TCC

Aplicativo Streamlit para importar CSV do registrador Arduino e inspecionar sinal, FFT, PSD experimental representativa (média de segmentos), Grms e comparação com perfis de referência ASTM D4728, ISO 13355 e ISTA 3E.

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

O app tenta detectar separador e cabeçalho automaticamente. O CSV deve conter `time_s` em segundos e os eixos de aceleração em g. Na interface, selecione somente o eixo; a duração do segmento PSD pode ser ajustada. Exemplo:

```csv
time_s,ax,ay,az
0.000,0.014,-0.021,1.002
0.010,0.017,-0.019,0.998
```

O app estima `Fs = 1/mediana(Δt)`. Se o firmware exportar tempo em milissegundos (`time_ms`), converta a coluna para segundos e nomeie-a `time_s` antes de importar.

## Método e interpretação

- Remove-se a componente média do eixo selecionado.
- A FFT com janela Hann é exibida para inspeção espectral.
- A PSD representativa é a média aritmética das PSDs de segmentos completos consecutivos, sem sobreposição. O app a usa como resumo espectral do teste; “média de segmentos” descreve a operação e não significa que o sinal temporal foi filtrado ou ajustado à curva normativa.
- Os perfis normativos são definidos por breakpoints e conectados por interpolação log-log (lei de potência). Isso é somente a representação computacional entre pontos e não afirma que as normas aplicaram suavização.
- O app mostra uma tabela compacta com o Grms do ensaio medido e o Grms integrado de cada perfil de referência na faixa selecionada.
- Proximidade numérica não demonstra conformidade. A conformidade depende de requisitos completos da edição aplicável, configuração e procedimento de ensaio.

## Proveniência dos perfis

Os breakpoints embutidos são os transcritos na conversa do projeto a partir de ASTM D4728-06, Appendix X1, Table X1.1 (Truck); ISO 13355, perfil indicativo apresentado na Table X1.3 da cópia da ASTM citada; e ISTA 3E (2005), Random Vibration Spectrum. Para ASTM existe PDF no diretório `sources/`. Não há cópias independentes da ISO 13355 nem ISTA 3E neste projeto. Confira os valores, a edição e as condições de aplicação na publicação oficial/licenciada antes de citar ou usar para qualificar um ensaio. Os breakpoints ASTM Truck e ISTA 3E usados aqui são equivalentes conforme a transcrição de referência disponível.

## Limitações

Este é um analisador de apoio ao TCC, não um instrumento certificado nem uma ferramenta de declaração de conformidade. Amostragem irregular, aliasing, orientação/montagem do sensor, calibração, faixa dinâmica e transientes podem afetar os resultados. A advertência de jitter aparece na interface quando a variação dos intervalos de amostragem excede 5%. Verifique que a frequência de Nyquist cobre a banda de interesse e que a aquisição não saturou.
