"""Analisador de vibração para TCC — PSD, FFT e Grms.

Os breakpoints normativos são perfis de referência transcritos das fontes indicadas.
A interpolação log-log abaixo é representação computacional entre breakpoints;
não afirma que as normas aplicaram suavização aos dados para obter os perfis.
"""
from io import BytesIO
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from scipy.signal import welch

st.set_page_config(page_title="Análise de vibração", layout="wide")
st.title("Análise de vibração — FFT, PSD e Grms")
st.caption("Ferramenta de apoio ao protocolo experimental do TCC")

# PSD em g²/Hz. ASTM Truck e ISTA 3E são apresentados como breakpoints
# equivalentes conforme a transcrição de referência disponível no projeto/conversa.
PROFILES = {
    "ASTM D4728 — Truck (Appendix X1, Table X1.1)": {
        "f": np.array([1, 4, 16, 40, 80, 200.]),
        "p": np.array([5e-5, 1e-2, 1e-2, 1e-3, 1e-3, 1e-5]), "overall": .52},
    "ISO 13355 — perfil indicativo (Table X1.3 da cópia citada)": {
        "f": np.array([3, 6, 18, 40, 200.]),
        "p": np.array([5e-4, 1.2e-2, 1.2e-2, 1e-3, 5e-4]), "overall": .59},
    "ISTA 3E — Random Vibration Spectrum (2005)": {
        "f": np.array([1, 4, 16, 40, 80, 200.]),
        "p": np.array([5e-5, 1e-2, 1e-2, 1e-3, 1e-3, 1e-5]), "overall": .52},
}

with st.sidebar:
    st.header("Dados e processamento")
    uploaded = st.file_uploader("CSV do registrador Arduino", type=["csv", "txt"])
    st.caption("O arquivo MPU6050_SD_logger.ino do projeto grava tempo e aceleração nos eixos.")

if not uploaded:
    st.info("Envie um CSV para iniciar. Espera-se uma coluna de tempo e ao menos um eixo de aceleração.")
    with st.expander("Fontes e notas metodológicas", expanded=True):
        st.markdown("""
**Perfis embutidos:** ASTM D4728-06, Appendix X1, Table X1.1 (Truck); perfil atribuído à ISO 13355 na Table X1.3 do Appendix X1 da ASTM; ISTA 3E (2005), Random Vibration Spectrum. Breakpoints transcritos a partir das referências associadas ao projeto e da conversa citada. A ISO e a ISTA não foram fornecidas como arquivos independentes neste projeto; confirme valores e edição na cópia licenciada/adotada antes de citar no TCC.

**Método:** a PSD bruta é calculada pelo periodograma de Welch sobre todo o registro. A PSD experimental representativa é a média aritmética das PSDs de segmentos completos, sem sobreposição; ela reduz variabilidade entre estimativas e não é chamada de suavização nem altera o sinal medido. Os gráficos mantêm a PSD bruta visível.

As curvas normativas são especificadas por breakpoints. Entre eles, o app usa interpolação log-log (lei de potência) como representação computacional do perfil, não como alegação de suavização empregada pela norma. O perfil ISTA 3E e ASTM Truck acima têm os mesmos breakpoints conforme a transcrição usada; a comparação resultará igual.

Similaridade espectral não demonstra conformidade. Conformidade depende do método de ensaio, tolerâncias, montagem, duração, faixa, equipamento e demais requisitos da edição aplicável.
""")
    st.stop()

try:
    df = pd.read_csv(uploaded, sep=None, engine="python", comment="#")
except Exception as exc:
    st.error(f"Não foi possível ler o CSV: {exc}"); st.stop()
if df.empty:
    st.error("O CSV não contém dados."); st.stop()

st.subheader("Mapeamento das colunas")
columns = list(df.columns)
def guess_time(cols):
    for c in cols:
        if any(k in str(c).lower() for k in ["time", "tempo", "millis", "timestamp", "seg"]): return c
    return cols[0]
time_col = st.selectbox("Coluna de tempo", columns, index=columns.index(guess_time(columns)))
numeric = [c for c in columns if c != time_col and pd.to_numeric(df[c], errors="coerce").notna().sum()]
if not numeric: st.error("Não encontrei coluna numérica de aceleração."); st.stop()
axis_col = st.selectbox("Eixo de aceleração", numeric)
unit = st.selectbox("Unidade dos valores", ["g", "m/s²"], help="Convertemos m/s² para g antes do cálculo.")
time_unit = st.selectbox("Unidade da coluna de tempo", ["Auto", "s", "ms", "µs"])
segment_s = st.number_input("Duração do segmento para PSD representativa (s)", min_value=0.1, value=4.0, step=0.5)

def time_seconds(series, mode):
    s = series.astype(str).str.strip()
    if mode == "Auto":
        vals = pd.to_numeric(s.str.replace(",", ".", regex=False), errors="coerce")
        if vals.notna().mean() > .9:
            med = float(vals.diff().dropna().median())
            # Inferência para contadores inteiros comuns do firmware; permite ajuste manual.
            scale = 1e-3 if med >= 1 else 1.
            return vals.to_numpy(float) * scale
        parsed = pd.to_datetime(series, errors="coerce")
        return (parsed - parsed.iloc[0]).dt.total_seconds().to_numpy()
    vals = pd.to_numeric(s.str.replace(",", ".", regex=False), errors="coerce").to_numpy(float)
    return vals * {"s": 1, "ms": 1e-3, "µs": 1e-6}[mode]

t = time_seconds(df[time_col], time_unit)
x = pd.to_numeric(df[axis_col], errors="coerce").to_numpy(float)
valid = np.isfinite(t) & np.isfinite(x)
t, x = t[valid], x[valid]
order = np.argsort(t); t, x = t[order], x[order]
unique = np.r_[True, np.diff(t) > 0]; t, x = t[unique], x[unique]
if len(t) < 16: st.error("São necessários ao menos 16 pontos válidos."); st.stop()
dt = np.diff(t)
dt = dt[np.isfinite(dt) & (dt > 0)]
if len(dt) < 2: st.error("A coluna de tempo não permite estimar Fs."); st.stop()
fs = 1 / np.median(dt)
jitter = np.std(dt) / np.mean(dt) * 100
if unit == "m/s²": x = x / 9.80665
x = x - np.mean(x)
st.caption(f"Fs estimada: **{fs:.4g} Hz** (mediana dos intervalos de tempo) · {len(x):,} amostras · duração {t[-1]-t[0]:.2f} s · variação relativa do intervalo {jitter:.2f}%")
if jitter > 5: st.warning("Intervalo de amostragem variável (>5%). Welch pressupõe amostragem uniforme; interprete os resultados com cautela.")

nperseg = min(len(x), max(16, int(round(segment_s * fs))))
if nperseg < 16: st.error("Segmento menor que 16 amostras."); st.stop()
freq, psd_raw = welch(x, fs=fs, window="hann", nperseg=len(x), noverlap=0, detrend="constant", scaling="density")
_, psd_full = welch(x, fs=fs, window="hann", nperseg=nperseg, noverlap=0, detrend="constant", scaling="density")
segments = [x[i:i+nperseg] for i in range(0, len(x)-nperseg+1, nperseg)]
segment_psds = [welch(s, fs=fs, window="hann", nperseg=nperseg, noverlap=0, detrend="constant", scaling="density")[1] for s in segments]
psd_rep = np.mean(segment_psds, axis=0) if segment_psds else psd_full
f_rep = welch(x[:nperseg], fs=fs, window="hann", nperseg=nperseg, noverlap=0, detrend="constant", scaling="density")[0]
grms_time = float(np.sqrt(np.mean(x*x)))
grms_psd = float(np.sqrt(np.trapezoid(psd_raw, freq)))

tabs = st.tabs(["Sinal e FFT", "PSD e comparação", "Método e fontes"])
with tabs[0]:
    sig = go.Figure(); sig.add_trace(go.Scatter(x=t-t[0], y=x, name="Aceleração", mode="lines"))
    sig.update_layout(title="Aceleração (componente média removida)", xaxis_title="Tempo (s)", yaxis_title="Aceleração (g)", height=350); st.plotly_chart(sig, use_container_width=True)
    nfft = len(x); yf = np.abs(np.fft.rfft(x * np.hanning(nfft))) * 2 / np.sum(np.hanning(nfft)); xf = np.fft.rfftfreq(nfft, 1/fs)
    fftfig = go.Figure(go.Scatter(x=xf[1:], y=yf[1:], mode="lines", name="FFT")); fftfig.update_layout(title="Amplitude espectral (janela Hann)", xaxis_title="Frequência (Hz)", yaxis_title="Amplitude (g, aprox.)", xaxis_type="log", yaxis_type="log", height=350); st.plotly_chart(fftfig, use_container_width=True)
    a,b,c = st.columns(3); a.metric("Grms no tempo", f"{grms_time:.4g} g"); b.metric("Grms integrado da PSD bruta", f"{grms_psd:.4g} g"); c.metric("Segmentos completos", str(len(segments)))
    st.caption("FFT de amplitude para inspeção. Welch fornece a PSD e o Grms espectral; pequenas diferenças em relação ao Grms temporal decorrem de janelamento/estimativa.")

with tabs[1]:
    fmin = max(float(f_rep[1]), 0.01); fmax = min(fs/2, 200.)
    if fmax <= fmin: st.warning("Faixa amostral insuficiente para comparar os perfis (limite superior <= inferior).")
    else:
        low = st.number_input("Frequência mínima de comparação (Hz)", min_value=fmin, max_value=fmax, value=max(fmin, 1.0), key="low")
        high = st.number_input("Frequência máxima de comparação (Hz)", min_value=low, max_value=fmax, value=fmax, key="high")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=freq[1:], y=psd_raw[1:], name="PSD experimental bruta (Welch — registro completo)", mode="lines", line={"width":1, "color":"#9aa0a6"}))
        fig.add_trace(go.Scatter(x=f_rep[1:], y=psd_rep[1:], name="PSD experimental representativa (média de segmentos)", mode="lines", line={"width":2, "color":"#1769aa"}))
        fgrid = np.geomspace(low, high, 500)
        def interp_loglog(fp, pp, fq):
            return 10 ** np.interp(np.log10(fq), np.log10(fp), np.log10(pp))
        results=[]
        obs = np.interp(np.log10(fgrid), np.log10(f_rep[1:]), np.log10(np.maximum(psd_rep[1:], 1e-30)))
        for name, prof in PROFILES.items():
            mask = (fgrid >= prof["f"][0]) & (fgrid <= prof["f"][-1])
            if mask.sum() < 2: continue
            ref = interp_loglog(prof["f"], prof["p"], fgrid[mask])
            fig.add_trace(go.Scatter(x=fgrid[mask], y=ref, name=name, mode="lines", line={"dash":"dash"}))
            valid_obs = (f_rep >= fgrid[mask][0]) & (f_rep <= fgrid[mask][-1]) & (psd_rep > 0)
            ff = f_rep[valid_obs]
            if len(ff) < 2: continue
            ref_obs = interp_loglog(prof["f"], prof["p"], ff)
            log_meas = np.log10(psd_rep[valid_obs]); log_ref = np.log10(ref_obs)
            rmse = float(np.sqrt(np.mean((log_meas-log_ref)**2)))
            shape_rmse = float(np.sqrt(np.mean(((log_meas-log_meas.mean())-(log_ref-log_ref.mean()))**2)))
            exp_grms = float(np.sqrt(np.trapezoid(psd_rep[valid_obs], ff)))
            ref_grms = float(np.sqrt(np.trapezoid(ref_obs, ff)))
            results.append({"Perfil":name,"RMSE log₁₀ PSD (décadas)":rmse,"RMSE de forma (décadas)":shape_rmse,"Grms exp. na faixa":exp_grms,"Grms perfil na faixa":ref_grms,"Razão Grms exp./perfil":exp_grms/ref_grms if ref_grms else np.nan,"Grms publicado (referência)":prof["overall"]})
        fig.update_layout(title="PSD experimental e perfis de referência", xaxis_title="Frequência (Hz)", yaxis_title="PSD (g²/Hz)", xaxis_type="log", yaxis_type="log", height=540, legend={"orientation":"h"}); st.plotly_chart(fig, use_container_width=True)
        if results:
            out=pd.DataFrame(results).sort_values("RMSE log₁₀ PSD (décadas)")
            st.dataframe(out, use_container_width=True, hide_index=True)
            st.info("RMSE menor indica maior proximidade numérica da PSD na faixa escolhida; RMSE de forma remove o nível médio em log-PSD. Razão Grms compara energia integrada na faixa observada. Nenhuma dessas métricas estabelece conformidade normativa.")
            st.download_button("Baixar comparação CSV", out.to_csv(index=False).encode("utf-8-sig"), "comparacao_psd.csv", "text/csv")
        else: st.warning("A faixa escolhida não sobrepõe os breakpoints normativos com pontos experimentais suficientes.")
        expdf=pd.DataFrame({"frequency_Hz":f_rep,"psd_raw_full_record_g2_per_Hz":np.interp(f_rep, freq, psd_raw),"psd_representative_segment_mean_g2_per_Hz":psd_rep})
        st.download_button("Baixar PSD experimental CSV", expdf.to_csv(index=False).encode("utf-8-sig"), "psd_experimental.csv", "text/csv")

with tabs[2]:
    st.markdown("""
### Processamento
- O tempo é convertido para segundos e **Fs = 1/mediana(Δt)**. Em modo Auto, valores de tempo numéricos com passo mediano ≥1 são tratados como milissegundos (comum no `millis()` do Arduino); confira e ajuste a unidade quando necessário.
- A média do sinal é removida antes da análise. Valores em m/s² são convertidos para g.
- PSD bruta: estimativa de Welch do registro completo, janela Hann. PSD representativa: média aritmética das PSDs de segmentos completos e consecutivos, sem sobreposição; a PSD bruta permanece exibida para preservar picos e variações do registro.
- O Grms da PSD é a raiz da integral numérica da densidade espectral. A tabela também mostra energia integrada na banda de comparação, não o valor global publicado para qualificar um ensaio.
- RMSE log-PSD é a raiz da média do erro quadrático em log₁₀(g²/Hz), calculado nos bins observados que caem na banda comparável e dentro do domínio do perfil. O RMSE de forma centraliza cada curva em log antes da comparação. Razão Grms é experimental/referência na mesma banda.

### Fontes e limites
- **ASTM D4728-06**, Random Vibration Testing of Shipping Containers, Appendix X1, Table X1.1 e Table X1.3. Arquivo de referência no projeto: `sources/1 - ASTM-D4728-06-Random-vibration-test(1).pdf`.
- **ISO 13355**, perfil indicativo transcrito na Table X1.3 da ASTM D4728 fornecida. O projeto não contém cópia separada da ISO.
- **ISTA 3E (2005)**, Random Vibration Spectrum, valores transcritos da referência discutida na conversa. O projeto não contém cópia separada da ISTA.

Confirme edição, tabela, breakpoints e condições de aplicação nas publicações oficiais antes de reproduzir valores em texto acadêmico. Os perfis são referências de comparação, e similaridade não implica conformidade.
""")
