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

tabs = st.tabs(["Sinal e FFT", "PSD e comparação", "Teste senoidal", "Método e fontes"])
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
    st.subheader("Sequência senoidal comprimida — planejamento exploratório")
    st.warning("Uma sequência senoidal de frequência única por vez não reproduz uma PSD aleatória. O cronograma abaixo distribui o tempo de ensaio conforme a fração de potência integrada da PSD medida em cada banda; com amplitude fixa, isso NÃO iguala a PSD por banda nem demonstra dano equivalente. Use como roteiro exploratório, não como ensaio equivalente ou conforme.")
    st.markdown("A equivalência de dano publicada entre excitação aleatória e senoidal requer um modelo de dano e a resposta da estrutura/produto (por exemplo, FDS, amortecimento/resposta e parâmetros de fadiga). A PSD de entrada isolada não determina um tempo senoidal comprimido único.")
    safe_min = max(float(f_rep[1]), 0.1)
    safe_max = min(fs / 2, 200.0, float(f_rep[-1]))
    if safe_max <= safe_min:
        st.warning("A faixa de frequência amostrada é insuficiente para gerar a sequência.")
    else:
        c1, c2, c3 = st.columns(3)
        f_low = c1.number_input("Frequência mínima (Hz)", min_value=safe_min, max_value=safe_max, value=max(safe_min, min(1.0, safe_max)), key="sine_low")
        f_high = c2.number_input("Frequência máxima (Hz)", min_value=f_low, max_value=safe_max, value=safe_max, key="sine_high")
        n_bands = c3.number_input("Número de etapas", min_value=2, max_value=40, value=10, step=1)
        d1, d2 = st.columns(2)
        total_s = d1.number_input("Duração total comprimida (s)", min_value=1.0, value=300.0, step=30.0)
        amp_value = d2.number_input("Amplitude fixa da bancada", min_value=0.001, value=0.1, step=0.01, help="Informe o valor configurado pela bancada e selecione se é pico ou RMS.")
        amp_kind = st.radio("A amplitude informada é", ["g RMS", "g pico"], horizontal=True, key="sine_amp_kind")
        accel_rms = amp_value if amp_kind == "g RMS" else amp_value / np.sqrt(2)
        accel_peak = amp_value * np.sqrt(2) if amp_kind == "g RMS" else amp_value

        edges = np.geomspace(f_low, f_high, int(n_bands) + 1)
        centers = np.sqrt(edges[:-1] * edges[1:])
        band_power = []
        for left, right in zip(edges[:-1], edges[1:]):
            band_f = np.linspace(left, right, 100)
            band_psd = np.interp(np.log10(band_f), np.log10(f_rep[1:]), np.log10(np.maximum(psd_rep[1:], 1e-30)))
            band_power.append(float(np.trapezoid(10**band_psd, band_f)))
        band_power = np.asarray(band_power)
        if band_power.sum() <= 0:
            st.error("Não há potência espectral positiva na faixa selecionada.")
        else:
            shares = band_power / band_power.sum()
            dwell = total_s * shares
            disp_mm = accel_peak * 9.80665 / ((2 * np.pi * centers) ** 2) * 1000
            schedule = pd.DataFrame({
                "Etapa": np.arange(1, len(centers) + 1),
                "Frequência (Hz)": centers,
                "Tempo sugerido (s)": dwell,
                "Potência medida na banda (g²)": band_power,
                "Parcela da potência medida (%)": shares * 100,
                "Amplitude configurada": amp_value,
                "Unidade da amplitude": amp_kind,
                "Deslocamento de pico estimado (mm)": disp_mm,
            })
            st.caption(f"Amplitude considerada: {accel_rms:.4g} g RMS ({accel_peak:.4g} g pico). Deslocamento calculado para seno em aceleração constante; confirme o limite de curso da bancada, especialmente nas menores frequências.")
            st.dataframe(schedule.round(4), use_container_width=True, hide_index=True)
            st.download_button("Baixar cronograma senoidal CSV", schedule.to_csv(index=False).encode("utf-8-sig"), "cronograma_senoidal_exploratorio.csv", "text/csv")
            st.caption("Regra deste cronograma: bandas logarítmicas; frequência de cada etapa no centro geométrico da banda; tempo proporcional à área da PSD representativa nessa banda; duração total igual à informada. A amplitude fixa é apenas registrada e não é sintetizada a partir da PSD.")

with tabs[3]:
    st.markdown("""
### Processamento
- O CSV deve conter `time_s` em segundos; o eixo de aceleração é tratado como g. **Fs = 1/mediana(Δt)**.
- A média do sinal é removida antes da análise.
- PSD representativa: média aritmética das PSDs de segmentos completos e consecutivos, sem sobreposição. Essa média reduz a variabilidade estatística entre segmentos e é usada como representação do teste; não modifica o sinal temporal nem a PSD individual dos segmentos.
- O Grms é a raiz da integral numérica da PSD representativa. A tabela resume somente Grms do ensaio e dos perfis na faixa selecionada; não substitui o Grms global publicado nem avalia todos os requisitos de ensaio.
- A aba “Teste senoidal” cria um cronograma exploratório com frequência em bandas logarítmicas e tempos proporcionais à potência integrada medida em cada banda. Com amplitude fixa, ele não reproduz a PSD de entrada, não preserva a resposta do produto e não é uma equivalência de dano/conformidade.

### Fontes e limites
- **ASTM D4728-06**, Random Vibration Testing of Shipping Containers, Appendix X1, Table X1.1 e Table X1.3. Arquivo de referência no projeto: `sources/1 - ASTM-D4728-06-Random-vibration-test(1).pdf`.
- **ISO 13355**, perfil indicativo transcrito na Table X1.3 da ASTM D4728 fornecida. O projeto não contém cópia separada da ISO.
- **ISTA 3E (2005)**, Random Vibration Spectrum, valores transcritos da referência discutida na conversa. O projeto não contém cópia separada da ISTA.

Confirme edição, tabela, breakpoints e condições de aplicação nas publicações oficiais antes de reproduzir valores em texto acadêmico. Os perfis são referências de comparação, e similaridade não implica conformidade.

Para transformar aleatório em senoidal com equivalência de fadiga, é necessário avaliar dano potencial/FDS e resposta da estrutura, além de hipóteses sobre amortecimento e propriedades de fadiga. Pahor Kos, Slavič e Boltežar (2015) comparam sweep-sine e excitação aleatória por um modelo baseado em dano e dados de resposta estrutural: https://doi.org/10.1155/2014/340545. O cronograma simplificado deste app é somente uma distribuição exploratória de tempos, não implementa esse método.
""")
