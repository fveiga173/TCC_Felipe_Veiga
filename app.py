import io
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from scipy.signal import welch

# Curvas de referência documentadas no projeto
ASTM_D4728_TRUCK = np.array([[1,.00005],[4,.01],[16,.01],[40,.001],[80,.001],[200,.00001]], float)
ISO_13355 = np.array([[3,.0005],[6,.012],[18,.012],[40,.001],[200,.0005]], float)
ISTA_3E = np.array([[1,.00005],[4,.01],[16,.01],[40,.001],[80,.001],[200,.00001]], float)
NORMS = {
    'ASTM D4728 — Truck (Appendix X1)': ASTM_D4728_TRUCK,
    'ISO 13355 — perfil indicativo': ISO_13355,
    'ISTA 3E (2005)': ISTA_3E,
}

def read_csv(file):
    raw=file.getvalue()
    for sep in [',',';','\t']:
        try:
            df=pd.read_csv(io.BytesIO(raw), sep=sep)
            if df.shape[1]>=2: return df
        except Exception: pass
    raise ValueError('Não foi possível identificar o separador do CSV.')

def fs_from_time(df, col):
    t=pd.to_numeric(df[col], errors='coerce').dropna().to_numpy()
    dt=np.diff(t); dt=dt[(dt>0)&np.isfinite(dt)]
    if len(dt)==0: raise ValueError('Não foi possível estimar Fs.')
    return 1/np.median(dt)

def psd_welch(x, fs, nperseg):
    x=x-np.mean(x)
    nperseg=min(nperseg,len(x))
    return welch(x,fs=fs,window='hann',nperseg=nperseg,noverlap=nperseg//2,detrend='constant',scaling='density')

def grms(f,p,fmin,fmax):
    m=(f>=fmin)&(f<=fmax)
    return np.sqrt(np.trapezoid(p[m],f[m])) if m.sum()>1 else np.nan

def interp_ref(freq, curve):
    m=(freq>=curve[:,0].min())&(freq<=curve[:,0].max())
    if m.sum()<5: return m,np.array([])
    p=10**np.interp(np.log10(freq[m]),np.log10(curve[:,0]),np.log10(curve[:,1]))
    return m,p

def similarity(f,p,curve):
    m,pr=interp_ref(f,curve)
    if m.sum()<5: return None
    pm=np.maximum(p[m],1e-16); pr=np.maximum(pr,1e-16)
    lm=np.log10(pm); lr=np.log10(pr)
    abs_rmse=np.sqrt(np.mean((lm-lr)**2))
    sm=lm-lm.mean(); sr=lr-lr.mean()
    shape_rmse=np.sqrt(np.mean((sm-sr)**2))
    return {'fmin':f[m].min(),'fmax':f[m].max(),'abs_rmse':abs_rmse,'shape_rmse':shape_rmse,'abs_score':100*np.exp(-abs_rmse),'shape_score':100*np.exp(-shape_rmse)}

st.set_page_config(page_title='Veiga Vibration Analyzer',layout='wide')
st.title('Veiga Vibration Analyzer')
st.caption('FFT • PSD • GRMS • comparação com referências de transporte rodoviário')

up=st.file_uploader('Selecione o CSV do Arduino',type=['csv','CSV'])
if up is None:
    st.info('Carregue um CSV para iniciar.'); st.stop()

df=read_csv(up)
num=[c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
time_candidates=[c for c in df.columns if str(c).lower() in {'time_s','time','tempo','tempo_s','timestamp','timestamp_s'}]
time_col=st.sidebar.selectbox('Coluna de tempo',df.columns.tolist(),index=df.columns.tolist().index(time_candidates[0]) if time_candidates else 0)
try: fs_auto=fs_from_time(df,time_col)
except Exception: fs_auto=100.0
fs=st.sidebar.number_input('Fs usada [Hz]',min_value=.1,value=float(fs_auto),format='%.4f')
signals=[c for c in num if c!=time_col]
axis=st.sidebar.selectbox('Eixo / sinal',signals)
nperseg=st.sidebar.selectbox('Nperseg — Welch',[x for x in [512,1024,2048,4096,8192] if x<=len(df)] or [min(256,len(df))])
nyq=fs/2
fmin=st.sidebar.number_input('Frequência mínima [Hz]',min_value=0.,value=1.)
fmax=st.sidebar.number_input('Frequência máxima [Hz]',min_value=fmin+.01,max_value=float(nyq),value=float(max(fmin+.01,min(nyq,200.))))

x=pd.to_numeric(df[axis],errors='coerce').dropna().to_numpy(); xac=x-x.mean()
t=np.arange(len(x))/fs
f_fft=np.fft.rfftfreq(len(x),1/fs); X=np.fft.rfft(xac); amp=np.abs(X)/len(x); amp[1:-1]*=2
f_psd,p=psd_welch(x,fs,nperseg); G=grms(f_psd,p,fmin,fmax)

cols=st.columns(5)
for c,label,val in zip(cols,['Amostras','Duração','Fs','Nyquist','GRMS'],[f'{len(x):,}',f'{len(x)/fs/60:.2f} min',f'{fs:.3f} Hz',f'{nyq:.3f} Hz',f'{G:.5f} g']): c.metric(label,val)

st.subheader('1. Sinal no domínio do tempo')
fig=go.Figure(go.Scatter(x=t,y=xac,mode='lines',name=axis)); fig.update_layout(xaxis_title='Tempo [s]',yaxis_title='Aceleração AC [g]',height=400); st.plotly_chart(fig,use_container_width=True)

st.subheader('2. FFT')
m=(f_fft>=max(fmin,.01))&(f_fft<=fmax)
fig=go.Figure(go.Scatter(x=f_fft[m],y=amp[m],mode='lines',name='FFT')); fig.update_layout(xaxis_type='log',yaxis_type='log',xaxis_title='Frequência [Hz]',yaxis_title='Amplitude [g]',height=450); st.plotly_chart(fig,use_container_width=True)

st.subheader('3. PSD — ensaio × referências')
m=(f_psd>=max(fmin,.01))&(f_psd<=fmax)
fig=go.Figure(go.Scatter(x=f_psd[m],y=p[m],mode='lines',name=f'Ensaio — {axis}',line={'width':2}))
for name,curve in NORMS.items():
    q=(curve[:,0]>=max(fmin,.01))&(curve[:,0]<=fmax)
    if q.sum()>=2: fig.add_trace(go.Scatter(x=curve[q,0],y=curve[q,1],mode='lines+markers',name=name))
fig.update_layout(xaxis_type='log',yaxis_type='log',xaxis_title='Frequência [Hz]',yaxis_title='PSD [g²/Hz]',height=550); st.plotly_chart(fig,use_container_width=True)

st.subheader('4. Similaridade espectral')
rows=[]
for name,curve in NORMS.items():
    r=similarity(f_psd,p,curve)
    rows.append({'Referência':name,'Faixa comum [Hz]':f"{r['fmin']:.2f}–{r['fmax']:.2f}" if r else 'Insuficiente','RMSE absoluto [décadas]':r['abs_rmse'] if r else np.nan,'Similaridade nível + forma [%]':r['abs_score'] if r else np.nan,'RMSE forma [décadas]':r['shape_rmse'] if r else np.nan,'Similaridade de forma [%]':r['shape_score'] if r else np.nan})
sim=pd.DataFrame(rows); st.dataframe(sim,use_container_width=True,hide_index=True)
if sim['Similaridade nível + forma [%]'].notna().any():
    best=sim.loc[sim['Similaridade nível + forma [%]'].idxmax(),'Referência']; st.success(f'Mais semelhante matematicamente: **{best}**')
st.warning("'Mais semelhante' não significa 'conforme à norma'. É um ranking matemático da PSD medida contra as referências.")

st.subheader('5. GRMS')
grows=[{'Referência':'Ensaio','Faixa [Hz]':f'{fmin:.2f}–{fmax:.2f}','GRMS [g]':G}]
for name,curve in NORMS.items():
    lo=max(fmin,curve[:,0].min()); hi=min(fmax,curve[:,0].max())
    if hi>lo:
        fd=np.geomspace(lo,hi,3000); _,pr=interp_ref(fd,curve); grows.append({'Referência':name,'Faixa [Hz]':f'{lo:.2f}–{hi:.2f}','GRMS [g]':np.sqrt(np.trapezoid(pr,fd))})
st.dataframe(pd.DataFrame(grows),use_container_width=True,hide_index=True)

with st.expander('Metodologia incorporada'):
    st.markdown('''**FFT:** transformada rápida de Fourier após remoção da média.\n\n**PSD:** método de Welch, janela Hann, 50% de sobreposição.\n\n**GRMS:** raiz da integral da PSD na faixa selecionada.\n\n**Referências:** ASTM D4728-06 Appendix X1 Table X1.1 (Truck), ISO 13355 profile reproduzido em Table X1.3 da ASTM D4728-06 e ISTA 3E (2005).\n\nA comparação é feita somente na faixa comum entre o ensaio e a referência.''')

st.subheader('6. Exportação')
summary=pd.DataFrame({'Parâmetro':['Arquivo','Eixo','Amostras','Duração [s]','Fs [Hz]','Nyquist [Hz]','Média [g]','RMS AC [g]','GRMS [g]','Faixa [Hz]'], 'Valor':[up.name,axis,len(x),len(x)/fs,fs,nyq,x.mean(),np.sqrt(np.mean(xac**2)),G,f'{fmin}–{fmax}']})
st.download_button('Baixar resumo CSV',summary.to_csv(index=False).encode(),file_name='resumo_analise_vibracao.csv',mime='text/csv')
st.download_button('Baixar PSD CSV',pd.DataFrame({'frequency_Hz':f_psd,'PSD_g2_per_Hz':p}).to_csv(index=False).encode(),file_name='PSD_ensaio.csv',mime='text/csv')
