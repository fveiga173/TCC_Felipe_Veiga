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


def references_markdown():
    return '\n\n'.join(f"- **{r['id']}** — {r['citation']} {r['sections']}\n  Aplicação: {r['supports']}\n  Limite: {r['limits']}" + (f"\n  Endereço: {r['url']}" if r['url'] else '') for r in REFERENCES)
