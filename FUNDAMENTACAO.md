# Fundamentação e decisões da versão 4.0

Produto do TCC: guia prático reproduzível de aquisição, processamento,
caracterização e definição de parâmetros. Sensor rigidamente fixado ao piso do
veículo, com orientação/contexto documentados. Medições manuais ou em mochila
são exploratórias. Não executa ensaios de paletes, avalia dano, certifica
embalagens ou modifica normas.

## Fontes efetivamente consultadas

| Fonte | Localização | Aplicação |
|---|---|---|
| Eagleton, dissertação de mestrado, 1995 | 4.1, pp. 59–88; B.1–B.3, pp. 154–158; C.1, pp. 163–166 | Configuração, PSD por viagem, Hamming, verificação do conjunto |
| Wallin, Desenvolvendo um padrão de vibração randômica, CETEA v.20 n.1, 2008 | pp. 2–3 e 5–6 | Perfis em níveis, durações e simplificação para controlador |
| Dantas, tradução adaptada de Kipp, Equivalência do ensaio de vibração, v.21 n.2, 2009 | pp. 3–5 | Modelo k=2, exposição e recomendação histórica 5:1 |
| Shire, Compressão do tempo em ensaios de vibração randômica, v.24 n.1, 2012 | pp. 1–5 | k como hipótese e distribuição de intensidade |
| Dunno, Técnicas para reduzir o tempo de simulação de vibrações em laboratório, v.28 n.2, 2016 | pp. 6–10, Tabelas 1–3 | Comparação de amplificação, faixas e síntese não estacionária |
| ASTM D4728-06, edição fornecida | 8.2–8.4, 10.2–10.5, Appendix X1 | Dados representativos, controle, tempo pleno, cautela com compressão |
| Rouillard et al., 2021, DOI 10.1002/pts.2563 | Discussão das simulações laboratoriais | Representatividade local e limites dos perfis genéricos |
| SciPy, Welch/get_window | Parameters e Notes, consulta 12/10/2026 | Janelas periódicas, densidade unilateral e normalização |

Referências completas em `references.py` e nas exportações. O original Shires,
DOI 10.1002/pts.915, é referência do resumo traduzido consultado; não se afirma
leitura do original integral. A tradução identifica Shire na capa e Shires na
referência final; a diferença é registrada.

## Limites das fontes

Eagleton usa disparo, intervalo morto e sobrescrita; seus registros não
representam uma coleta contínua completa. Integral da PSD = g²; RMS = sua raiz.
Zero-padding de 500 para 512 muda a grade, sem adicionar informação. Filtro
digital posterior não elimina aliasing da aquisição. Hamming/1 s/0% nesta
aplicação não replica filtros e hardware do EDR.

Wallin oferece o caso 80/20; limiares 0,04 e 0,167 Grms pertencem à Amgen.
Não são critérios universais de ruído/movimento. Aqui P80 é quantil temporal
ponderado de Grms na banda; empates ficam juntos e a proporção real é exibida.

Shire/Shires discute um modelo semelhante a fadiga, sem confirmar k=2 para
todos os conjuntos. PSD/Grms não identificam o expoente ou mecanismo de falha.
sum(T*Grms^k) é apenas comparação hipotética escalar da exposição.

Dunno encontrou dano excessivo ao elevar 0,195 para aproximadamente 0,44 Grms
durante 3 h. Sequências de 4 h 08 min e 2 h 42 min corresponderam aos danos dos
refrigeradores; 11 min e 2 min não produziram os danos esperados. São resultados
visuais daquele produto/montagem/viagem. Armazenou 8 h 09 min de uma viagem
de 15 h com sobrescrita. A tradução não define integralmente o algoritmo do
SaverXware: 90%→99% não é simplesmente pegar os 10% maiores Grms de outro arquivo.

Síntese SVS usa distribuição estatística para controlar o sinal da mesa.
Dois perfis não são síntese não gaussiana e não garantem distribuição de
amplitudes. Gaussianidade é do processo temporal, não da PSD; uma PSD pode
caracterizar processos não gaussianos.

## Convenções de implementação

1. Mesmos fs, nperseg, janela, overlap e banda em todos os blocos.
2. PSD média em escala linear com peso de duração; não média aritmética de Grms.
3. Caudas documentadas; trechos descontínuos não concatenados.
4. Duração N_coberto/fs, sem contar sobreposição Welch duas vezes.
5. Referência dos cenários baseada na cobertura dos blocos, distinta da receita.
6. Compressão C=T0/Tt: amplitude ×C^(1/k), PSD ×C^(2/k), frequência preservada.
   Não comprime o eixo do arquivo nem reamostra a aceleração.
7. Seleção mantém tempos e intensidades dos grupos restantes, sem compensação
   automática. Tempo retirado acompanha cada saída.
8. Fator numérico da simplificação conserva área; não é aumento físico do ensaio.
9. Picos amostrados, sem reconstrução por interpolação. Fator de crista não
   dispara exclusão automática nem cria ensaio de impacto no escopo do TCC.
10. Senoide permanece exploratória e não recebe a compressão da vibração aleatória.

## Ressalva nas saídas

**Proposta de ensaio baseada em modelo, pendente de validação experimental.**

Estados indicam documentação/critérios de cálculo. Não afirmam calibração,
conformidade, dano equivalente ou autorização da mesa. Verificar capacidade com
carga e comparar experimentalmente resposta/dano para alegar equivalência.
