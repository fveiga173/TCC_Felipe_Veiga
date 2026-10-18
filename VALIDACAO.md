# Verificação da versão 5.0.0 — 18/10/2026

## Testes automatizados

41 testes unittest aprovados, incluindo cinco fluxos AppTest da interface.
Cobrem integrais analíticas, senoides conhecidas, média temporal de potência,
seleção dos 10% por duração, empates, complementos de intensidade, caudas,
interrupções, V1/V2, corrupção, prefixo incompleto, inclinações, edição da
tabela, exportação, referências e banda comum. Os módulos científicos legados
também continuam verificados.

O teste de lacunas aplica um salto de DC de aproximadamente 999 g entre dois
segmentos sintéticos: a análise independente mantém a potência da senoide e
não cria energia baixa artificial na fronteira. O teste de pico estreito
verifica forma e Grms; conservar a área sozinho não basta.

AppTest verifica demonstração, banda inválida, mudança da banda comum para
3–50 Hz ao incluir ISO, edição de PSD e slope, atualização da tabela e reset,
perfil inválido sem download obsoleto, seleção e cenário opcional, além de
upload V2 sem fechamento e com prefixos íntegros.

Ambiente utilizado: Python 3.12, numpy 2.3.5, scipy 1.17.0, pandas 2.2.3,
plotly 6.9.0 e streamlit 1.66.0. Não foi verificada toda combinação permitida
pelos intervalos de dependências. Versões efetivas acompanham a exportação.

## Arquivos reais fornecidos pelo autor

Executados no fluxo completo AppTest: upload → CRC/segmentos → análise →
seleção → breakpoints → comparação → exportação. Sem exceções não tratadas.
Parâmetros: 1–50 Hz, Hann periódica, Welch 4 s/50%, blocos de 10 s, seleção
alta solicitada de 10%, erro admitido de 1 dB e máximo de 80 pontos.

| Arquivo | Amostras verificadas | Segmentos | Fechamento | Cobertura (s nominais) | Seleção (s nominais) | Pontos | Erro (dB) | Critério 1 dB |
|---|---:|---:|---|---:|---:|---:|---:|---|
| TEST007 | 120,005 | 5 | sim | 118.000 | 14.000 | 80 | 1.8450 | não atendido |
| TEST010 | 4,853,635 | 21 | sim | 4822.000 | 484.000 | 23 | 0.9968 | atendido |
| TEST011 | 11,278,862 | 44 | não | 11214.000 | 1130.000 | 2 | 0.9759 | atendido |

Todos os CRCs aplicáveis conferem. TEST011 permanece INCOMPLETE; todos os
bytes do BIN anexado estão cobertos pelos checkpoints válidos. TEST007 e
TEST010 mantêm REVIEW no diagnóstico original. Nenhum TXT foi alterado.
Os 10% efetivos variam por blocos inteiros e empates, conforme o relatório.

O critério não atendido em TEST007 é apresentado como aviso, sem declarar
êxito numérico ou alterar a PSD para escondê-lo. Limites de pontos e tolerância
podem ser ajustados pelo pesquisador. Esses registros são ensaios funcionais,
não uma campanha representativa do transporte rodoviário.

Dados BIN/TXT privados não foram adicionados ao repositório.

## Arquivo sintético de tamanho equivalente a 24 horas

- 86,400,000 amostras int16, 1000 Hz nominais: 172,800,000 bytes.
- 288 segmentos, 8640 blocos analisados; 86400 s nominais cobertos.
- Seleção: 8640 s, 10.0% do tempo coberto.
- Leitura/conferência local: aproximadamente 0.22 s.
- Análise e duas aproximações: aproximadamente 12.26 s.
- Pico de RSS do processo local: aproximadamente 368.2 MiB.
- Com 80 pontos: erro de 2.902 dB, acima de 1 dB; falha de critério corretamente sinalizada.
- Permitindo 200 pontos: 144 pontos, erro de 0.970 dB; critério atendido.

O sinal sintético contém um pico estreito e ruído; o número de pontos depende
da forma, estatística e tolerância. A conferência utiliza o BIN int16 sem
converter o arquivo inteiro para float ou construir seu vetor de tempo.
O processamento é computacional: não comprova aquisição física de 24 h,
autonomia da alimentação ou recursos garantidos na hospedagem Streamlit.

## Catálogo e exportação

17 perfis com proveniência. A integral log-log do perfil coreano 2020 de molas
na classe superior reproduz aproximadamente 0,47281 g. A comparação com ISO
reproduzido em D4728-06 utiliza 3–50 Hz para todas as linhas, sem extrapolar
para 1–3 Hz. Inclinações de aproximadamente +6/0/−6 dB/oct foram conferidas
no exemplo 20/50/800/2000 Hz fornecido como referência de apresentação.

A exportação foi reaberta para comparar os níveis com a tabela atual, duração,
seleção, referências, segmentação e estado. A edição manual é mantida no CSV;
seu Grms e erro são recalculados sem normalização silenciosa. O cenário de
compressão mantém rótulo de modelo não validado e não altera a curva principal.

## Limite da verificação

A verificação confirma implementação e consistência, sem avaliar avarias,
calibrar o sensor, certificar o ensaio ou comprovar equivalência de dano.
A reprodução física e a capacidade da mesa com a carga requerem verificação
experimental própria. A disponibilidade hospedada depende da aplicação
Streamlit conectada à branch main e de seus recursos.
