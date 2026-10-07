"""Analisador de vibração para TCC — PSD, FFT e Grms.

Os breakpoints normativos são perfis de referência transcritos das fontes indicadas.
A interpolação log-log abaixo é representação computacional entre breakpoints;
não afirma que as normas aplicaram suavização aos dados para obter os perfis.
"""
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
    st.info("Envie um CSV com a coluna `time_s` (segundos) e ao menos um eixo de aceleração em g.")
    with st.expander("Fontes e notas metodológicas", expanded=True):
        st.markdown("""
**Perfis embutidos:** ASTM D4728-06, Appendix X1, Table X1.1 (Truck); perfil atribuído à ISO 13355 na Table X1.3 do Appendix X1 da ASTM; ISTA 3E (2005), Random Vibration Spectrum. Breakpoints transcritos a partir das referências associadas ao projeto e da conversa citada. A ISO e a ISTA não foram fornecidas como arquivos independentes neste projeto; confirme valores e edição na cópia licenciada/adotada antes de citar no TCC.

**Método:** a PSD experimental representativa é a média aritmética das PSDs de segmentos completos, sem sobreposição. Ela resume o conteúdo espectral do teste e reduz a variabilidade entre segmentos. Não remove frequências do sinal temporal.

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
if "time_s" not in df.columns:
    st.error("O CSV precisa conter a coluna `time_s`, com o tempo em segundos.")
    st.stop()
st.caption("Tempo: `time_s` (s) · aceleração: g")
time_col = "time_s"
numeric = [c for c in df.columns if c != time_col and pd.to_numeric(df[c], errors="coerce").notna().sum()]
if not numeric: st.error("Não encontrei coluna numérica de aceleração."); st.stop()
axis_col = st.selectbox("Eixo de aceleração", numeric)
segment_s = st.number_input("Duração do segmento para PSD representativa (s)", min_value=0.1, value=4.0, step=0.5)

t = pd.to_numeric(df[time_col].astype(str).str.replace(",", ".", regex=False), errors="coerce").to_numpy(float)
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
        fig.add_trace(go.Scatter(x=f_rep[1:], y=psd_rep[1:], name="PSD experimental representativa (média de segmentos)", mode="lines", line={"width":2, "color":"#1769aa"}))
        fgrid = np.geomspace(low, high, 500)
        def interp_loglog(fp, pp, fq):
            return 10 ** np.interp(np.log10(fq), np.log10(fp), np.log10(pp))
        results=[]
        measured_band = (f_rep >= low) & (f_rep <= high) & (psd_rep >= 0)
        measured_grms = float(np.sqrt(np.trapezoid(psd_rep[measured_band], f_rep[measured_band]))) if measured_band.sum() >= 2 else np.nan
        results.append({"Perfil":"Ensaio medido — média de segmentos", "Grms":measured_grms})
        for name, prof in PROFILES.items():
            mask = (fgrid >= max(prof["f"][0], low)) & (fgrid <= min(prof["f"][-1], high))
            if mask.sum() < 2: continue
            ref = interp_loglog(prof["f"], prof["p"], fgrid[mask])
            fig.add_trace(go.Scatter(x=fgrid[mask], y=ref, name=name, mode="lines", line={"dash":"dash"}))
            results.append({"Perfil":name,"Grms":float(np.sqrt(np.trapezoid(ref, fgrid[mask])))})
        fig.update_layout(title="PSD representativa e perfis de referência", xaxis_title="Frequência (Hz)", yaxis_title="PSD (g²/Hz)", xaxis_type="log", yaxis_type="log", height=540, legend={"orientation":"h"}); st.plotly_chart(fig, use_container_width=True)
        if results:
            out=pd.DataFrame(results)
            st.dataframe(out, use_container_width=True, hide_index=True)
            st.info("Os Grms do ensaio e dos perfis são integrados na faixa selecionada e na cobertura disponível de cada curva. Proximidade entre esses valores é apenas uma comparação de nível global: não representa similaridade de forma nem conformidade normativa. O perfil medido é a PSD representativa, média dos segmentos.")
            st.download_button("Baixar comparação CSV", out.to_csv(index=False).encode("utf-8-sig"), "comparacao_psd.csv", "text/csv")
        else: st.warning("A faixa escolhida não sobrepõe os breakpoints normativos com pontos experimentais suficientes.")
        expdf=pd.DataFrame({"frequency_Hz":f_rep,"psd_representative_segment_mean_g2_per_Hz":psd_rep})
        st.download_button("Baixar PSD experimental CSV", expdf.to_csv(index=False).encode("utf-8-sig"), "psd_experimental.csv", "text/csv")

with tabs[2]:
    st.markdown("""
### Processamento
- O CSV deve conter `time_s` em segundos; o eixo de aceleração é tratado como g. **Fs = 1/mediana(Δt)**.
- A média do sinal é removida antes da análise.
- PSD representativa: média aritmética das PSDs de segmentos completos e consecutivos, sem sobreposição. Essa média reduz a variabilidade estatística entre segmentos e é usada como representação do teste; não modifica o sinal temporal nem a PSD individual dos segmentos.
- O Grms é a raiz da integral numérica da PSD representativa. A tabela resume somente Grms do ensaio e dos perfis na faixa selecionada; não substitui o Grms global publicado nem avalia todos os requisitos de ensaio.

### Fontes e limites
- **ASTM D4728-06**, Random Vibration Testing of Shipping Containers, Appendix X1, Table X1.1 e Table X1.3. Arquivo de referência no projeto: `sources/1 - ASTM-D4728-06-Random-vibration-test(1).pdf`.
- **ISO 13355**, perfil indicativo transcrito na Table X1.3 da ASTM D4728 fornecida. O projeto não contém cópia separada da ISO.
- **ISTA 3E (2005)**, Random Vibration Spectrum, valores transcritos da referência discutida na conversa. O projeto não contém cópia separada da ISTA.

Confirme edição, tabela, breakpoints e condições de aplicação nas publicações oficiais antes de reproduzir valores em texto acadêmico. Os perfis são referências de comparação, e similaridade não implica conformidade.
""")
