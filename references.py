"""Fontes efetivamente consultadas; as traduções não são normas vigentes."""

REFERENCES = [
    dict(id='eagleton1995', citation='EAGLETON, Danny Geoffrey. Creep properties of corrugated fibreboard containers for produce in simulated road transport environment. Master of Engineering, Victoria University of Technology, 1995.',
         sections='4.1, pp. 59–88; B.1–B.3, pp. 154–158; C.1, pp. 163–166; C.4–C.5, pp. 172–174 (paginação impressa).',
         supports='Aquisição, PSD por viagem, janela Hamming, verificação do conjunto e perfil para controlador.',
         url='https://vuir.vu.edu.au/18159/1/EAGLETON_1995compressed.pdf',
         limits='Aquisição por disparo, intervalos mortos e sobrescrita; não reproduz coleta contínua. Zero-padding muda a grade, não a informação do registro.'),
    dict(id='wallin2008', citation='WALLIN, Brian. Desenvolvendo um padrão de vibração randômica. Boletim de Tecnologia e Desenvolvimento de Embalagens, v. 20, n. 1, 2008. Texto baseado no trabalho apresentado no IAPRI 2007.',
         sections='pp. 2–3 (80/20 e simplificação); pp. 5–6 (duração e aplicação).',
         supports='Perfis para diferentes intensidades e seleção do tempo de movimentação.', url='',
         limits='Limiares e perfis são da Amgen. O algoritmo completo de processamento não é fornecido. O aplicativo usa agrupamento próprio explicitado.'),
    dict(id='kipp2009', citation='DANTAS, Tiago B. H. Equivalência do ensaio de vibração: quantas horas de ensaio equivalem a quantos quilômetros de transporte? Boletim de Tecnologia e Desenvolvimento de Embalagens, v. 21, n. 2, 2009. Tradução adaptada de William Kipp, ISTA Con 2000.',
         sections='pp. 3–5.', supports='G_ensaio = G_original sqrt(T_original/T_ensaio); recomendação histórica 5:1; correlação experimental.', url='',
         limits='Não há equivalência universal horas/km. O limite histórico não assegura dano equivalente.'),
    dict(id='shires2012', citation='SHIRE, David [Shires na referência do original]. Compressão do tempo em ensaios de vibração randômica. Tradução Mauricio Bordin. Boletim de Tecnologia e Desenvolvimento de Embalagens, v. 24, n. 1, 2012.',
         sections='pp. 1–5. Original referenciado: On the time compression (test acceleration) of broadband random vibration tests, DOI 10.1002/pts.915, publicado online em 2010.',
         supports='Modelo T_ensaio/T_original = (G_original/G_ensaio)^k; influência da distribuição temporal e de k.',
         url='https://doi.org/10.1002/pts.915',
         limits='A fonte consultada é o resumo traduzido. k não é determinado pela aceleração medida; mecanismos de falha podem ser não lineares e não obedecer ao modelo.'),
    dict(id='dunno2016', citation='DUNNO, Kyle. Técnicas para reduzir o tempo de simulação de vibrações em laboratório. Tradução Mauricio Bordin. Boletim de Tecnologia e Desenvolvimento de Embalagens, v. 28, n. 2, 2016. Trabalho apresentado no ISTA TransPack 2014.',
         sections='pp. 6–10, Tabelas 1–3.', supports='Comparação experimental entre aumento da intensidade, faixas de probabilidade e síntese não estacionária/não gaussiana.', url='',
         limits='Refrigeradores específicos; avaliação visual de danos; 15 h de viagem e 8 h 09 min armazenados com sobrescrita. Faixas do SaverXware não são reproduzidas automaticamente por percentis de Grms.'),
    dict(id='astm2006', citation='ASTM INTERNATIONAL. ASTM D4728-06: Standard Test Method for Random Vibration Testing of Shipping Containers. 2006. Edição fornecida para este projeto.',
         sections='8.2–8.4 e 10.2–10.5; Appendix X1, Tables X1.1 e X1.3.', supports='Representatividade, controle na mesa, tempo pleno e cautela com compressão.', url='',
         limits='Edição adotada não é declaração de norma atual. Curvas são comparativas; não certificam o ensaio.'),
    dict(id='rouillard2021', citation='ROUILLARD et al. The case for reviewing laboratory-based road transport simulations for packaging optimisation. Packaging Technology and Science, 34(6), 339–351, 2021. DOI 10.1002/pts.2563.',
         sections='Discussão sobre representatividade dos ensaios e medições de transporte.', supports='Perfis locais e variabilidade do ambiente; limites das simulações genéricas.',
         url='https://doi.org/10.1002/pts.2563', limits='Referência de fundamentação; não define parâmetros Welch ou um expoente k para o produto.'),
    dict(id='scipy', citation='SciPy. Documentação oficial de scipy.signal.welch e scipy.signal.get_window. Consulta em 12 out. 2026.',
         sections='Parameters e Notes.', supports='Densidade unilateral, janelas periódicas, média e normalização espectral.',
         url='https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html', limits='Parâmetros e faixas são escolhas do projeto; versões efetivas acompanham as exportações.'),
]


# Fontes incorporadas à seleção por intensidade e ao catálogo da versão 5.
REFERENCES.extend([
    dict(id='rissi2008', citation='RISSI, G. O.; SINGH, S. P.; BURGESS, G.; SINGH, J. Measurement and analysis of truck transport environment in Brazil. Packaging Technology and Science, 21(4), 231–246, 2008. DOI 10.1002/pts.797.',
         sections='Metodologia e seleção antes da Figura 21; Figura 21/Tabela 4, p. 19 da cópia pública.',
         supports='Referência brasileira e justificativa para examinar trechos de maior intensidade. Perfil vertical composto aproximado por digitalização.',
         url='https://digitalcommons.calpoly.edu/it_fac/47/',
         limits='Cópia identificada como anterior à revisão por pares. Os 10% são estimativa da retenção por gatilho/max-overwrite, não o algoritmo de ranking deste aplicativo. Pontos digitalizados não são tabela dos autores.'),
    dict(id='korea2020', citation='PARK, J.; CHOI, S.; JUNG, H. M. Measurement and Analysis of Vibration Levels for Truck Transport Environment in Korea. Applied Sciences, 10(19), 6754, 2020. DOI 10.3390/app10196754.',
         sections='Tabelas 8 e 9, pp. 15–16.', supports='Perfis por suspensão e classes de intensidade; tabela de breakpoints como parâmetro de ensaio.',
         url='https://doi.org/10.3390/app10196754', limits='Veículos descarregados; seleção e composição próprias do estudo. A média ponderada do aplicativo não reproduz o método de conexão de pontos elevados dos autores.'),
    dict(id='korea2024', citation='KIM, S.; HORVATH, L.; LEE, S.; LEE, S. Measurement and Analysis of Last-Mile Parcel Delivery Truck Vibration Levels in Korea. Applied Sciences, 14(8), 3245, 2024. DOI 10.3390/app14083245.',
         sections='Tabela 3, p. 10.', supports='Exemplo de perfil composto com 17 breakpoints e influência de baixas frequências.',
         url='https://doi.org/10.3390/app14083245', limits='Última milha em Seul, veículos e seleção específicos; não é padrão nacional universal.'),
    dict(id='lansmont2016', citation='LANSMONT. ASTM D4169 Truck Profile Update Rationale, revisão de 22 set. 2016.',
         sections='Tabela 2, p. 6; comparação histórica, p. 8.', supports='Curvas históricas de 2014 e níveis baixo/médio/alto de 2016, mantidos separados no catálogo.',
         url='https://www.lansmont.com/sites/default/files/wp-content/uploads/2016/06/ASTM-D4169-Truck-Profile-Update-Rationale-Rev.-3-9-22-16.pdf', limits='Justificativa histórica; não comprova a edição normativa vigente. Níveis de 2014 não são as três intensidades da revisão de 2016.'),
    dict(id='endaq', citation='HANLY, Steve. How to Develop a Vibration Test Standard (PSD) from Experimental Data. enDAQ.',
         sections='Seleção de regimes, redução de breakpoints e comparação por resposta espectral.', supports='Fluxo medição → PSD → perfil simplificado e necessidade de examinar forma além de Grms.',
         url='https://blog.endaq.com/how-to-develop-a-vibration-test-standard-psd-from-experimental-data', limits='Orientação técnica; não fornece equivalência universal de dano. Verificação VRS não está implementada nesta versão.'),
])



def references_markdown():
    return '\n\n'.join(f"- **{r['id']}** — {r['citation']} {r['sections']}\n  Aplicação: {r['supports']}\n  Limite: {r['limits']}" + (f"\n  Endereço: {r['url']}" if r['url'] else '') for r in REFERENCES)
