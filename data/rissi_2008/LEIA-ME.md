# Rissi et al. (2008): 14 PSDs verticais digitalizadas

DOI 10.1002/pts.797. Cópia pública anterior à revisão por pares: https://digitalcommons.calpoly.edu/it_fac/47/

10 regiões metropolitanas (Figuras 7–16), 3 trajetos de longa distância (17–19) e composto brasileiro (21). Somente a direção vertical azul; sem curvas lateral ou longitudinal. Páginas PDF 11–17 e 19.

São aproximações gráficas, não tabelas originais nem normas. Coordenadas calibradas em eixos log-log. Mediana dos pixels azuis escuros por coluna; mínimo de dois pixels para reduzir falsas identificações. Lacunas interpoladas em coordenadas logarítmicas. Primeiro segmento pouco cromático: três âncoras manuais em x0, x0+40 e x0+80 pixels, explicitadas no script e JSON. Simplificação com tolerância de 0,5 dB contra a malha extraída; sem reescala de área nem ajuste ao Grms publicado. Essa tolerância não quantifica a incerteza da digitalização.

Cada perfil tem CSV em 1–200 Hz. A extração ampla vai de 1 Hz até no máximo 375 Hz (metade dos 750 amostras/s informados no artigo). Onde o último pixel azul termina antes, o limite efetivo é menor: consultar resumo/JSON. Arquivos com sufixo 1a375Hz significam ATÉ 375 Hz; a última frequência do arquivo é o limite efetivo. Não extrapolar até 1000 Hz apenas porque o eixo desenhado termina nesse valor.

O Grms publicado é transcrito da Tabela 4. A banda exata da sua integral não foi comprovada; diferenças com a integração gráfica não isolam erros de digitalização. Passo Fundo, Curitiba e Videira–Rio Verde têm divergência superior a 5% e ficam explicitamente sinalizados para uso exploratório. Proximidade de Grms não valida cada frequência; não se fornecem intervalos de incerteza metrológica. Há sensibilidade aos limiares de cor no JSON. Casas decimais adicionais existem para reproduzir cálculos.

O composto já existente no aplicativo foi preservado, sem duplicação. O pacote reextrai a Figura 21 com filtro de cor mais restritivo, portanto sua curva pode diferir ligeiramente do composto anteriormente publicado. Ambos permanecem identificados. Os 13 novos perfis são adicionados ao catálogo, totalizando 39 incluindo o perfil autoral. Referências aparecem selecionadas por padrão em sessão nova. O Grms principal usa a banda nativa de cada curva; comparação homogênea deve usar o Grms na banda comum.

O artigo usa gatilho e max-overwrite; estima que os espectros representem os 10% superiores da viagem. Não são médias contínuas de toda a viagem. Não transferir os níveis de uma operação para outra sem avaliar veículo, carga, suspensão, velocidade e percurso. Carga/distância/veículo da Tabela 3 constam no JSON. Goiânia é GO e Salvador é BA; SC/SA na legenda da Figura 19 são inconsistências tipográficas.

Reprodução: python digitize_all.py arquivo_Rissi.pdf pasta_saida. Requer PyMuPDF, numpy, Pillow e matplotlib. O script gera o núcleo da extração; o JSON entregue acrescenta os contextos da Tabela 3 e os avisos de divergência.

Uso no TCC: “Os perfis verticais das Figuras 7–19 e 21 de Rissi et al. (2008) foram reconstruídos por digitalização gráfica em eixos logarítmicos. Os pontos obtidos constituem aproximações, com identificação da figura de origem e conferência global por integração da PSD. As divergências em relação aos Grms publicados foram mantidas e declaradas, sem normalização dos níveis.”
