# Analisador de vibração para TCC — versão 2.0

Extraia o ZIP numa pasta. No terminal dessa pasta:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

A versão anterior pode ser mantida em outra pasta. O arquivo original enviado foi preservado.

CSV: coluna time_s em segundos e uma ou mais colunas de aceleração. Eixo Z é selecionado por padrão quando existe. Informe unidade e escala conforme o firmware. A opção de demonstração gera um sinal sintético, sem precisar enviar arquivo.

## Fluxo
1. Diagnosticar aquisição e identificar o contexto (manual, veículo ou mesa).
2. Selecionar trecho e configurar janelas Welch e RMS.
3. Inspecionar sinal original, RMS no tempo e distribuição ponderada pela duração.
4. Comparar PSD e Grms numa banda comum e exportar dados e parâmetros.

## Limites importantes
- Intervalos irregulares bloqueiam a PSD por padrão. É possível habilitar explicitamente uma análise exploratória com Fs pela mediana; ela não corrige a irregularidade e não deve fundamentar ensaios.
- Triagem: variação relativa dos intervalos >5% ou algum intervalo >1,5 vezes a mediana. Esses valores não são tolerâncias normativas.
- Linhas inválidas, tempos duplicados ou regressivos não são descartados silenciosamente.
- Diagnóstico temporal e Fs consideram o arquivo inteiro. Selecionar um trecho não elimina os alertas originais.
- Nenhuma reamostragem, remoção de picos ou filtragem automática é aplicada.
- RMS temporal usa toda a banda adquirida; Grms de comparação usa a banda comum indicada. Não são diretamente intercambiáveis.
- RMS por intervalo remove a média local. A distribuição usa duração real, incluindo o último intervalo parcial.
- A média de Welch exclui o remanescente que não forma um segmento completo; a interface informa sua extensão.
- Perfis ASTM e ISO foram conferidos nas tabelas X1.1 e X1.3 da ASTM D4728-06 fornecida. A ISO é identificada como reprodução nessa fonte. ISTA aguarda confirmação documental.
- Sem validação de calibração, banda útil ou representatividade de percurso. Receitas e duração de ensaio pertencem à próxima etapa do TCC.

## Arquivo TEST019
O teste manual de 4.800 amostras apresenta duração de 23,091 s, taxa média aproximada de 207,83 amostras/s e taxa pela mediana de 225,02 Hz. Não demonstra aquisição uniforme a 500 Hz. Há indícios de limite ±4 g. Conferir o código Arduino antes de definir a coleta em veículo.
