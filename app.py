"""Análise de vibração de transporte — versão 3.1, 2026-10-10.
Executar: streamlit run app.py
"""
import io
import hashlib
from psd_recipe import load_binary, parse_metadata
from recipe_ui import render_recipe
from freq_recipe_ui import render_fixed_recipe
import json
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.signal import welch
import streamlit as st

PROFILES = {
    'ASTM D4728-06 — Truck (X1.1)': ([1,4,16,40,80,200], [5e-5,.01,.01,.001,.001,1e-5], .52),
    'ISO 13355 — reproduzido na ASTM D4728-06 (X1.3)': ([3,6,18,40,200], [.0005,.012,.012,.001,.0005], .59),
}

def read_csv(data):
    df = pd.read_csv(io.BytesIO(data), sep=None, engine='python', comment='#')
    df.columns = df.columns.str.strip()
    return df

def number_series(s):
    return pd.to_numeric(s.astype(str).str.replace(',', '.', regex=False), errors='coerce').to_numpy(float)

# 1. Diagnóstico: examinar tempos sem ordenar, eliminar ou inventar amostras.
def diagnose(t, x):
    finite = np.isfinite(t) & np.isfinite(x)
    tf = t[np.isfinite(t)]
    dt = np.diff(tf)
    pos = dt[dt > 0]
    if len(pos) < 2:
        raise ValueError('Não há intervalos positivos suficientes para analisar o tempo.')
    med = float(np.median(pos))
    return dict(n=len(t), invalid=int((~finite).sum()), duplicates=int((dt==0).sum()),
                reversals=int((dt<0).sum()), median_dt=med, fs_median=1/med,
                fs_mean=(len(t)-1)/(t[-1]-t[0]) if finite.all() and t[-1]>t[0] else None,
                duration=float(tf[-1]-tf[0]), jitter=float(np.std(pos)/np.mean(pos)*100),
                max_dt=float(pos.max()), gaps=int((pos>1.5*med).sum()))

def integrate_band(f, p, low, high, loglog=False):
    """Inclui limites exatos; referência integrada por lei de potência."""
    if not f[0] <= low < high <= f[-1]:
        raise ValueError('Banda fora da cobertura do espectro.')
    grid = np.r_[low, f[(f>low)&(f<high)], high]
    if loglog:
        vals = np.exp(np.interp(np.log(grid), np.log(f), np.log(p)))
        ratio = grid[1:]/grid[:-1]
        b = np.log(vals[1:]/vals[:-1])/np.log(ratio)
        k = b+1
        terms = np.empty_like(k)
        flat = np.abs(k)<1e-10
        terms[flat] = vals[:-1][flat]*grid[:-1][flat]*np.log(ratio[flat])
        terms[~flat] = vals[:-1][~flat]*grid[:-1][~flat]*np.expm1(k[~flat]*np.log(ratio[~flat]))/k[~flat]
        return float(terms.sum())
    vals = np.interp(grid, f, p)
    return float(np.trapezoid(vals, grid))

# 2. Estimativa espectral para inspeção e comparação normativa.
# A receita usa nperseg fixo entre trechos no módulo psd_recipe.py.
def spectrum(x, fs, seconds, overlap):
    n = min(len(x), max(16, round(seconds*fs)))
    ov = min(n-1, round(n*overlap))
    step = n-ov
    starts = np.arange(0, len(x)-n+1, step)
    f,p = welch(x, fs=fs, window='hann', nperseg=n, noverlap=ov,
                detrend='constant', scaling='density', average='mean')
    used = int(starts[-1]+n)
    return f,p,dict(nperseg=n, noverlap=ov, segments=len(starts), unused=len(x)-used,
                   segment_seconds=n/fs, bin_spacing=fs/n, enbw_hz=1.5*fs/n)

def rms_blocks(t, x, seconds):
    """Blocos por tempo real. RMS dinâmico: média local removida.
    Pesos de integração trapezoidal respeitam intervalos reais; não reconstroem lacunas.
    """
    rows=[]
    edges=np.r_[np.arange(t[0],t[-1],seconds), t[-1]]
    for left,right in zip(edges[:-1],edges[1:]):
        # Busca de limites evita percorrer todo o registro em cada janela.
        # Isso mantém o mesmo cálculo em coletas de uma hora ou mais.
        i=np.searchsorted(t,left,side='right');j=np.searchsorted(t,right,side='left')
        tt=np.r_[left,t[i:j],right]
        xx=np.r_[np.interp(left,t,x),x[i:j],np.interp(right,t,x)]
        dur=right-left
        mean=np.trapezoid(xx,tt)/dur
        rms=np.sqrt(np.trapezoid((xx-mean)**2,tt)/dur)
        rows.append([left-t[0],right-t[0],dur,mean,rms,int(np.searchsorted(t,right,side='left')-np.searchsorted(t,left,side='left'))])
    return pd.DataFrame(rows,columns=['inicio_s','fim_s','duracao_s','media_g','rms_dinamico_g','amostras'])

def display_indices(y, limit=20000):
    """Reduz somente o desenho, preservando mínimo/máximo por bloco.
    PSD, RMS e exportações continuam usando todas as amostras.
    """
    y=np.asarray(y)
    if len(y)<=limit:return np.arange(len(y))
    size=int(np.ceil(len(y)/(limit//2)))
    count=len(y)//size;blocks=y[:count*size].reshape(count,size)
    starts=np.arange(count)*size
    return np.unique(np.r_[0,starts+blocks.argmin(axis=1),starts+blocks.argmax(axis=1),np.arange(count*size,len(y))])

def line_plot(x,y,title,xlabel,ylabel):
    idx=display_indices(y)
    fig=go.Figure(go.Scattergl(x=np.asarray(x)[idx],y=np.asarray(y)[idx],mode='lines'))
    fig.update_layout(title=title,xaxis_title=xlabel,yaxis_title=ylabel,height=360)
    return fig

def csv_download(label, df, filename):
    st.download_button(label,df.to_csv(index=False).encode('utf-8-sig'),filename,'text/csv')

def demo_data():
    fs=500.;t=np.arange(15000)/fs
    rng=np.random.default_rng(42)
    amplitude=np.where(t<15,.12,.30)
    z=1+amplitude*np.sin(2*np.pi*8*t)+.07*np.sin(2*np.pi*35*t)+rng.normal(0,.015,len(t))
    return pd.DataFrame({'time_s':t,'accel_z_g':z})

# 3. Interface: origem → qualidade → análise → prescrição documentada.
def main():
    st.set_page_config(page_title='Veiga | Análise de vibração',layout='wide')
    st.title('Análise de vibração de transporte')
    st.caption('Caracterizar o percurso → definir duas receitas → verificar a execução · v3.1')
    with st.sidebar:
        st.header('Dados')
        uploaded=st.file_uploader('CSV ou BIN do sensor',type=['csv','bin'])
        report_file=st.file_uploader('TXT do diagnóstico (obrigatório com BIN)',type=['txt'])
        demo=st.checkbox('Usar demonstração sintética',value=False)
        source=st.selectbox('Contexto da aquisição',['Teste manual / funcional','Transporte em veículo','Mesa vibratória','Outro'])
        unit=st.selectbox('Unidade da aceleração',['g','m/s²'])
        fullscale=st.selectbox('Faixa configurada no sensor (em g)',['Não confirmada',2,4,8,16])
        st.caption('Confirme a faixa e os filtros no Arduino. Não deduzimos a configuração apenas do CSV.')
    firmware={}
    input_hash=''
    binary_mode=bool(uploaded and uploaded.name.lower().endswith('.bin') and not demo)
    if demo:
        df=demo_data(); filename='demonstracao_sintetica.csv'
        input_hash=hashlib.sha256(df.to_csv(index=False).encode()).hexdigest()
        st.info('Demonstração sintética de 30 s a 500 Hz: componentes de 8 e 35 Hz e mudança de intensidade aos 15 s. Não representa transporte.')
    elif uploaded:
        raw=uploaded.getvalue();input_hash=hashlib.sha256(raw).hexdigest()
        try:
            if binary_mode:
                if not report_file: st.info('Envie o TXT correspondente ao BIN.');return
                df,firmware=load_binary(raw,report_file.getvalue())
                unit='g';fullscale=4
            else:
                df=read_csv(raw)
                firmware=parse_metadata('\n'.join(line for line in raw.decode('utf-8-sig').splitlines() if line.strip().startswith('#')))
        except Exception as exc: st.error(f'Falha ao ler aquisição: {exc}');return
        filename=uploaded.name
    else:
        st.info('Envie o CSV ou ative a demonstração sintética. Esperado: time_s e pelo menos um eixo de aceleração.')
        return
    nominal=binary_mode or firmware.get('time_basis')=='sample_index_nominal'
    if nominal:
        time_basis='Índice nominal / FIFO'
        st.warning('Tempo nominal por índice: regularidade do CSV não comprova regularidade do sensor. A PSD e a duração usam a taxa do eixo nominal; não há correção automática pelo relógio do Arduino.')
    elif demo:
        time_basis='Sintética conhecida'
    else:
        time_basis=st.selectbox('Origem do eixo temporal',['Não identificada','Tempos medidos pelo Arduino','Índice nominal / FIFO'])
    if binary_mode:
        st.success('BIN + TXT consistentes: estado final OK, sem erro/transbordamento, quantidade e CRC32 conferidos.')
        st.caption(f'Taxa estimada vs. relógio Arduino: {firmware["rate_vs_arduino_hz"]:.6f} Hz. Não é taxa calibrada. BIN já convertido usando 8192 contagens/g e escala ±4 g.')
    if 'time_s' not in df or len(df)<16:
        st.error('São necessárias a coluna time_s em segundos e pelo menos 16 linhas.');return
    columns=[c for c in df if c!='time_s']
    if not columns: st.error('Não há coluna de aceleração.');return
    axis=st.selectbox('Eixo de análise',columns,index=columns.index('accel_z_g') if 'accel_z_g' in columns else 0)
    t=number_series(df.time_s);x=number_series(df[axis])
    if unit=='m/s²':x=x/9.80665
    try:d=diagnose(t,x)
    except ValueError as exc:st.error(str(exc));return
    st.subheader('Qualidade da aquisição')
    cols=st.columns(4)
    for col,label,value in zip(cols,['Amostras','Duração','Taxa média','Taxa pela mediana'],
        [f'{d["n"]:,}',f'{d["duration"]:.3f} s',f'{d["fs_mean"]:.2f} Hz' if d['fs_mean'] else '—',f'{d["fs_median"]:.2f} Hz']):col.metric(label,value)
    quality=pd.DataFrame({'Verificação':['Intervalo mediano (ms)','Maior intervalo (ms)','Variação relativa dos intervalos (%)','Intervalos > 1,5 × mediana','Linhas inválidas','Tempos duplicados','Recuos do relógio'],
        'Resultado':[d['median_dt']*1000,d['max_dt']*1000,d['jitter'],d['gaps'],d['invalid'],d['duplicates'],d['reversals']]})
    st.dataframe(quality,hide_index=True)
    if d['invalid'] or d['duplicates'] or d['reversals']:
        st.error('Sequência inválida para esta análise. Nenhuma linha foi removida ou reordenada. Corrija a aquisição ou selecione externamente um trecho contínuo, preservando o original.');return
    uncertain=d['jitter']>5 or d['gaps']>0
    if uncertain:st.warning('Amostragem irregular: FFT/PSD ficam bloqueadas por padrão. Os limites de 5% e 1,5 × mediana são critérios de triagem do aplicativo, não tolerâncias normativas.')
    finite_x=x[np.isfinite(x)]
    guessed_hits=int(np.sum((finite_x<=-4)|(np.isclose(finite_x,3.99988,atol=.00001,rtol=0))))
    hits=0
    if fullscale!='Não confirmada':
        hits=int(np.sum(np.abs(x)>=float(fullscale)*(1-1/32768)-.00001))
        if hits:st.warning(f'{hits} amostras próximas ou além dos limites da faixa ±{fullscale} g. Possível saturação; os picos não podem ser recuperados por filtragem.')
    elif guessed_hits:
        st.warning(f'{guessed_hits} amostras compatíveis com limite de ±4 g ou além dele. É uma suspeita; confirme a escala e a conversão no Arduino.')
    if source=='Teste manual / funcional' and not demo:
        st.info('Teste manual: resultados para avaliação funcional. Mudanças de inclinação alteram a contribuição da gravidade; remover a média não corrige orientação.')
    st.subheader('Trecho e processamento')
    rel=t-t[0]
    a,b=st.columns(2)
    start=a.number_input('Início do trecho (s)',min_value=0.,max_value=float(rel[-1]),value=0.)
    end=b.number_input('Fim do trecho (s)',min_value=0.,max_value=float(rel[-1]),value=float(rel[-1]))
    mask=(rel>=start)&(rel<=end)
    if end<=start or mask.sum()<16:st.error('Selecione um trecho com pelo menos 16 amostras.');return
    t=t[mask];x=x[mask]; dc=float(np.mean(x));z=x-dc
    a,b,c=st.columns(3)
    seg=a.number_input('Janela Welch (s)',min_value=.1,value=4.,step=.5)
    overlap=b.selectbox('Sobreposição Welch',[50,0,75],format_func=lambda v:f'{v}%')/100
    rms_s=c.number_input('Intervalo do RMS (s)',min_value=.1,value=1.,step=.5)
    st.caption('Hann · média aritmética · remoção da média por segmento · PSD unilateral em g²/Hz. Não é aplicado filtro de suavização ao sinal temporal.')
    spectral_ok=not uncertain
    if uncertain:
        spectral_ok=st.checkbox('Calcular PSD exploratória supondo espaçamento uniforme pela mediana (não corrige a aquisição)',value=False)
    status='EXPLORATORIO — tempo irregular' if uncertain else 'TEMPO REGULAR NA TRIAGEM — banda do sensor ainda requer confirmação'
    tabs=st.tabs(['Sinal e RMS','PSD e normas','Receita PSD','Receita senoidal','Diagnóstico temporal','Método e exportação'])
    with tabs[0]:
        fig=line_plot(t-t[0],x,'Sinal original e componente com média removida','Tempo no trecho (s)','Aceleração (g)')
        fig.data[0].name='Original';fig.data[0].showlegend=True
        idx=display_indices(z)
        fig.add_trace(go.Scattergl(x=(t-t[0])[idx],y=z[idx],name='Média removida',mode='lines'))
        st.caption('Em séries longas, os gráficos temporais mostram mínimos e máximos por bloco para manter a navegação fluida. Cálculos e exportações usam todas as amostras.')
        st.plotly_chart(fig,width='stretch')
        r=rms_blocks(t,x,rms_s)
        duration=t[-1]-t[0]
        weighted_mean=float(np.trapezoid(x,t)/duration)
        rms_t=float(np.sqrt(np.trapezoid((x-weighted_mean)**2,t)/duration))
        a,b,c=st.columns(3);a.metric('Média das amostras',f'{dc:.4f} g');b.metric('RMS das amostras (média removida)',f'{np.std(x):.4f} g');c.metric('RMS ponderado pelo tempo',f'{rms_t:.4f} g')
        st.caption('RMS temporal em toda a banda registrada, sem restrição à banda normativa. A ponderação usa integração trapezoidal nos tempos reais; não recupera dados ausentes.')
        st.plotly_chart(line_plot((r.inicio_s+r.fim_s)/2,r.rms_dinamico_g,'RMS dinâmico por intervalo','Tempo no trecho (s)','RMS (g)'),width='stretch')
        counts,edges=np.histogram(r.rms_dinamico_g,bins=10,weights=r.duracao_s)
        dist=pd.DataFrame({'rms_min_g':edges[:-1],'rms_max_g':edges[1:],'tempo_s':counts,'tempo_percentual':100*counts/counts.sum()})
        st.plotly_chart(go.Figure(go.Bar(x=(edges[:-1]+edges[1:])/2,y=dist.tempo_percentual)).update_layout(title='Distribuição do tempo entre níveis de RMS',xaxis_title='RMS por intervalo (g)',yaxis_title='Tempo (%)'),width='stretch')
        st.caption('Cada intervalo tem sua própria média removida. A distribuição depende da duração escolhida; o último intervalo parcial é ponderado pela duração efetiva.')
        csv_download('Baixar RMS por intervalo',r,'rms_por_intervalo.csv')
        csv_download('Baixar distribuição de níveis',dist,'distribuicao_rms.csv')
    metadata=dict(version='3.0',file=filename,context=source,axis=axis,unit_input=unit,fullscale_g=fullscale,diagnostic=d,status=status,start_s=start,end_s=end,rms_interval_s=rms_s,possible_saturation_count=hits if fullscale!='Não confirmada' else guessed_hits,acquisition_validated=False)
    metadata.update(sha256_input=input_hash,firmware=firmware,time_basis=time_basis,requested_welch_seconds=seg,requested_overlap=overlap)
    metadata['possible_saturation_count']=max(metadata['possible_saturation_count'],int(firmware.get('saturation_samples',0)),int(firmware.get('rail_samples_recomputed',0)))
    with tabs[1]:
        if not spectral_ok:
            st.info('PSD bloqueada pela irregularidade temporal. Use o sinal temporal e o diagnóstico para investigar a aquisição. A opção exploratória está acima.')
        else:
            fs=d['fs_median'];f,p,settings=spectrum(z,fs,seg,overlap);metadata['welch']=settings
            if uncertain:st.error('PSD EXPLORATÓRIA: eixo de frequência calculado com espaçamento uniforme presumido. Não usar como receita de ensaio.')
            st.caption(f'{settings["segments"]} segmentos · duração efetiva {settings["segment_seconds"]:.3f} s · espaçamento espectral {settings["bin_spacing"]:.3f} Hz · largura equivalente da Hann {settings["enbw_hz"]:.3f} Hz · {settings["unused"]} amostras finais fora da PSD ({100*settings["unused"]/len(z):.2f}%).')
            a,b=st.columns(2)
            low=a.number_input('Banda comum: mínimo (Hz)',min_value=.01,max_value=float(f[-1]),value=min(3.,float(f[-1])/2))
            high=b.number_input('Banda comum: máximo (Hz)',min_value=.01,max_value=float(f[-1]),value=min(200.,float(f[-1])))
            st.caption('O máximo matemático não é garantia de banda útil. Confirme filtros, taxa efetiva e resposta do sensor. Dados não são extrapolados até 200 Hz.')
            fig=go.Figure(go.Scatter(x=f[1:],y=p[1:],name='PSD experimental Welch',mode='lines'))
            for name,(ff,pp,_) in PROFILES.items():fig.add_trace(go.Scatter(x=ff,y=pp,name=name,mode='lines+markers',line={'dash':'dash'}))
            fig.update_layout(title='PSD experimental e referências',xaxis={'type':'log','title':'Frequência (Hz)'},yaxis={'type':'log','title':'PSD (g²/Hz)'},height=520,legend={'orientation':'h'})
            if high>low:fig.add_vrect(x0=low,x1=high,fillcolor='lightblue',opacity=.12,line_width=0)
            st.plotly_chart(fig,width='stretch')
            common_low=max(low,3.);common_high=min(high,200.,f[-1])
            if common_high<=common_low:
                st.warning('Não há banda comum válida para comparar todas as referências.')
            else:
                st.write(f'**Comparação comum: {common_low:.3f}–{common_high:.3f} Hz para todas as linhas.**')
                measured=np.sqrt(integrate_band(f,p,common_low,common_high))
                rows=[{'Perfil':'Experimental Welch','Banda mínima (Hz)':common_low,'Banda máxima (Hz)':common_high,'Grms na banda (g)':measured,'Experimental / referência':1.}]
                for name,(ff,pp,overall) in PROFILES.items():
                    reference=np.sqrt(integrate_band(np.array(ff,float),np.array(pp,float),common_low,common_high,True))
                    rows.append({'Perfil':name,'Banda mínima (Hz)':common_low,'Banda máxima (Hz)':common_high,'Grms na banda (g)':reference,'Experimental / referência':measured/reference})
                table=pd.DataFrame(rows);st.dataframe(table,hide_index=True)
                st.caption('Razão de Grms compara intensidade global, não forma espectral nem conformidade. Os valores publicados de 0,52 e 0,59 g se referem às bandas completas das respectivas referências.')
                csv_download('Baixar comparação na banda comum',table,'comparacao_banda_comum.csv')
                cuts=sorted(set([common_low,common_high]+[v for v in [3,10,20,50,100,200] if common_low<v<common_high]))
                bandrows=[]
                for l,h in zip(cuts[:-1],cuts[1:]):
                    energy=integrate_band(f,p,l,h)
                    bandrows.append({'min_Hz':l,'max_Hz':h,'Grms_g':np.sqrt(energy),'fracao_quadratica_percentual':100*energy/measured**2 if measured else 0})
                st.dataframe(pd.DataFrame(bandrows),hide_index=True)
                st.caption('Faixas descritivas do aplicativo, não divisões prescritas por norma. Percentuais referem-se à aceleração quadrática média, não diretamente a dano.')
                metadata['comparison_band_Hz']=[common_low,common_high]
            exported=pd.DataFrame({'frequency_Hz':f,'psd_g2_per_Hz':p,'status':status})
            csv_download('Baixar PSD Welch',exported,'psd_welch.csv')
            with st.expander('FFT de amplitude para inspeção'):
                win=np.hanning(len(z));amp=np.abs(np.fft.rfft(z*win))/win.sum();amp[1:]*=2
                if len(z)%2==0:amp[-1]/=2
                st.plotly_chart(line_plot(np.fft.rfftfreq(len(z),1/fs)[1:],amp[1:],'FFT com janela Hann','Frequência (Hz)','Amplitude aproximada (g)'),width='stretch')
                st.caption('Ferramenta de inspeção de componentes. A amplitude de picos depende do alinhamento espectral; a caracterização aleatória usa PSD.')
    with tabs[2]:
        render_recipe(t,x,d['fs_median'],metadata,uncertain,demo)
    with tabs[3]:
        render_fixed_recipe(t,x,d['fs_median'],metadata,uncertain,demo)
    with tabs[4]:
        dt=np.diff(t)*1000
        st.plotly_chart(line_plot(t[1:]-t[0],dt,'Intervalos entre registros','Tempo no trecho (s)','Δt (ms)'),width='stretch')
        st.caption('O diagnóstico superior considera o arquivo inteiro, mesmo após selecionar um trecho. Mediana e taxa média não substituem a verificação dos intervalos.')
    with tabs[5]:
        st.markdown('''**Escopo:** caracterizar o sinal, comparar referências e gerar propostas de receita PSD e de frequência fixa com duração da exposição coberta. Consulte as abas de receita para critérios, cobertura e justificativas.

**Tratamento:** preserva ordem e valores originais; converte unidade quando solicitado; remove a média para análise dinâmica. Não suaviza o sinal, remove picos ou reamostra automaticamente. Falhas de tempo bloqueiam a análise ou exigem modo exploratório explícito.

**PSD:** Welch com Hann, média aritmética em escala linear e remoção da média de cada segmento. A média dos segmentos representa apenas o trecho selecionado e coberto. Sobreposição de 50% é uma opção metodológica inicial, não requisito normativo. Segmentos longos melhoram espaçamento em frequência e reduzem o número de médias. A PSD não preserva a ordem temporal dos eventos; consulte RMS por intervalo.

**RMS:** o RMS temporal global, o RMS de intervalos com média local removida e o Grms integrado numa banda não são a mesma medida. Janelamento, trechos cobertos, remoção de média e banda precisam coincidir antes de exigir concordância. A integração da PSD experimental usa interpolação linear nos limites; perfis de referência usam integração de leis de potência entre breakpoints.

**Receita senoidal:** centro da banda completa de 1/3 de oitava com maior integral de PSD, ou frequência definida pelo pesquisador; intensidade pelo RMS da banda local (padrão) ou pelo Grms de toda a faixa. A aceleração de pico é √2 vezes o RMS e o deslocamento pico a pico é calculado pela relação cinemática da senoide. Essa discretização é um critério do estudo, não uma exigência da ISO 2247. A receita derivada do percurso é simplificada e não declara conformidade. A ISO 2247:2000 é referência contextual para ensaios de embalagens em baixa frequência; seus métodos e requisitos de corpo de prova não são satisfeitos automaticamente por igualar um nível RMS.

**Fontes das curvas PSD:** ASTM D4728-06, Appendix X1, Table X1.1 (Truck / D4169 Assurance Level II); Table X1.3 (perfil reproduzido de ISO 13355). A segunda curva não confirma uma edição atual da ISO. ISTA 3E não foi incluída como referência independente porque sua transcrição ainda requer verificação documental. Consultar a edição adotada antes de afirmar conformidade.

**Software:** [SciPy — Welch](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html). Similaridade ou proximidade de Grms não demonstra conformidade e não estabelece equivalência de dano.

**Pendências de aquisição:** conferir firmware, frequência efetiva, escala, calibração, filtros, fixação e orientação. A triagem temporal não valida esses itens. Para o TCC, registrar contexto, veículo, carga, posição do sensor e trechos do percurso.''')
        st.download_button('Baixar parâmetros e diagnóstico',json.dumps(metadata,ensure_ascii=False,indent=2).encode(), 'parametros_analise.json','application/json')
        csv_download('Baixar dados do trecho com média removida',pd.DataFrame({'time_s':t,'acceleration_original_g':x,'acceleration_demeaned_g':z}),'trecho_analisado.csv')

if __name__=='__main__':main()
