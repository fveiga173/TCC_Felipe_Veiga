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
- Os limites mínimo e máximo da faixa controlam a integração do Grms e a comparação; a PSD completa permanece visível. Uma faixa de frequência define banda de análise, não identifica se a fonte foi o pavimento, motor ou transmissão.
- A aba “Teste senoidal” usa como padrão curso de 25,4 mm pico a pico, permite editar o curso, limita a faixa inicialmente a 5–50 Hz e exige teste de pelo menos 5 s. Sob a hipótese de deslocamento vertical harmônico ideal, calcula o Grms teórico de cada frequência e redistribui os tempos para tentar igualar o Grms medido do veículo na mesma faixa. Se o alvo estiver fora do intervalo de Grms alcançável, não exporta um cronograma como se fosse equivalente.
- O curso fixo e o modo rotativo/reciprocante de uma mesa não garantem movimento senoidal vertical ideal. Confirme o modelo/modo no manual e meça o Grms com acelerômetro na mesa carregada. ASTM D4169 separa a opção aleatória (D4728) da opção senoidal (D999 B/C); uma mesa rotary-reciprocating de curso fixo pode ser D999 A2, de choques repetitivos. A conversão teórica abaixo não é conformidade nem equivalência de dano.
- Proximidade numérica não demonstra conformidade. A conformidade depende de requisitos completos da edição aplicável, configuração e procedimento de ensaio.

## Proveniência dos perfis

Os breakpoints embutidos são: ASTM D4728-06, Appendix X1, Table X1.1 (Truck); ISO 13355, Annex A, Table A.1, conforme imagem de referência enviada; e ISTA 3E (2005), Random Vibration Spectrum. Para ASTM existe PDF no diretório `sources/`. Não há cópias independentes da ISO 13355 nem ISTA 3E neste projeto. Confira os valores, a edição e as condições de aplicação na publicação oficial/licenciada antes de citar ou usar para qualificar um ensaio. Os breakpoints ASTM Truck e ISTA 3E usados aqui são equivalentes conforme a transcrição de referência disponível.

## Limitações

Este é um analisador de apoio ao TCC, não um instrumento certificado nem uma ferramenta de declaração de conformidade. Amostragem irregular, aliasing, orientação/montagem do sensor, calibração, faixa dinâmica e transientes podem afetar os resultados. A advertência de jitter aparece na interface quando a variação dos intervalos de amostragem excede 5%. Verifique que a frequência de Nyquist cobre a banda de interesse e que a aquisição não saturou.

Sob a hipótese de movimento senoidal, o Grms por frequência é calculado a partir do deslocamento pico a pico como `Grms = (2πf)² × (curso p-p / 2) / (√2 × g)`. A equivalência de dano entre ensaio aleatório e senoidal exige um modelo de fadiga e resposta estrutural (por exemplo, FDS, amortecimento e resposta do produto); a PSD medida sozinha não define um cronograma equivalente. ASTM D4728 declara que não há equivalência direta geral entre aleatório e senoidal. Ver Pahor Kos, Slavič e Boltežar (2015), [Fatigue Damage for Sweep-Sine and Random Accelerated Vibration Testing](https://doi.org/10.1155/2014/340545).

O acelerômetro na carroceria registra a resposta total no local: a contribuição do pavimento pode coexistir com motor e transmissão. A literatura relaciona explicitamente vibração veicular à excitação do pavimento e do motor ([Du et al., 2020](https://doi.org/10.1080/10298436.2020.1830092)). Para atribuir componentes ao motor, é necessário RPM/tacômetro sincronizado; order tracking com várias referências de rotação e acelerômetros em pontos distintos foi estudado por [Blough (SAE, 2005)](https://doi.org/10.4271/2005-01-2265). Sem esses dados, o aplicativo reporta o resultado total medido e não filtra faixas presumidas como motor.
