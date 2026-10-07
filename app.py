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
    fmin = max(float(f_rep[1]), 0.01); fmax = min(fs/2, 1000.)
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
        fig.update_layout(
            title="PSD representativa e perfis de referência",
            xaxis={
                "title":"Frequência (Hz)", "type":"log", "range":[0, 3],
                "tickmode":"array", "tickvals":[1, 10, 100, 1000],
                "ticktext":["1", "10", "100", "1000"],
                "showgrid":True, "gridcolor":"#555555", "gridwidth":1,
                "minor":{"showgrid":True, "dtick":0.1, "gridcolor":"#c8c8c8", "griddash":"dot"},
            },
            yaxis={
                "title":"PSD (g²/Hz)", "type":"log", "range":[-5, -1],
                "tickmode":"array", "tickvals":[1e-5, 1e-4, 1e-3, 1e-2, 1e-1],
                "ticktext":["0.00001", "0.0001", "0.001", "0.01", "0.1"],
                "showgrid":True, "gridcolor":"#555555", "gridwidth":1,
                "minor":{"showgrid":True, "dtick":0.1, "gridcolor":"#c8c8c8", "griddash":"dot"},
            },
            height=540, legend={"orientation":"h"}, margin={"l":80, "r":30, "t":70, "b":80},
        )
        st.plotly_chart(fig, use_container_width=True)
        if results:
            out=pd.DataFrame(results)
            st.dataframe(out, use_container_width=True, hide_index=True)
            st.info("Os Grms do ensaio e dos perfis são integrados na faixa selecionada e na cobertura disponível de cada curva. Proximidade entre esses valores é apenas uma comparação de nível global: não representa similaridade de forma nem conformidade normativa. O perfil medido é a PSD representativa, média dos segmentos.")
            st.download_button("Baixar comparação CSV", out.to_csv(index=False).encode("utf-8-sig"), "comparacao_psd.csv", "text/csv")
        else: st.warning("A faixa escolhida não sobrepõe os breakpoints normativos com pontos experimentais suficientes.")
        expdf=pd.DataFrame({"frequency_Hz":f_rep,"psd_representative_segment_mean_g2_per_Hz":psd_rep})
        st.download_button("Baixar PSD experimental CSV", expdf.to_csv(index=False).encode("utf-8-sig"), "psd_experimental.csv", "text/csv")

with tabs[2]:
    st.subheader("Ensaio senoidal comprimido — mesa de curso fixo")
    st.markdown("Com a hipótese de movimento vertical senoidal ideal e curso pico a pico fixo, o Grms do tom é **Grms(f) = (2πf)² × (curso p-p / 2) / (√2 × g)**. O app redistribui os tempos entre etapas para igualar o Grms global medido no veículo, se houver uma solução dentro da faixa de frequência e do curso informados.")
    st.warning("Confira o tipo de mesa antes de executar: a ASTM D4169 separa a opção aleatória (D4728) da opção senoidal (D999, métodos B/C). Uma mesa descrita como rotativa/reciprocante com curso fixo pode corresponder à D999 A2, de choques repetitivos, que não é um seno puro. Esta conta é uma estimativa harmônica idealizada; no movimento rotativo real, confirme o Grms com acelerômetro na mesa carregada. Igualar apenas o Grms não iguala a PSD, a resposta do produto ou o dano.")
    sample_high = min(fs / 2, float(f_rep[-1]))
    freq_min_allowed = max(5.0, float(f_rep[1]))
    freq_max_allowed = min(50.0, sample_high)
    if freq_max_allowed <= freq_min_allowed:
        st.error("O registro não cobre suficientemente a faixa de 5–50 Hz. Verifique Fs e a duração do segmento PSD.")
    else:
        cfg1, cfg2, cfg3 = st.columns(3)
        stroke_pp_mm = cfg1.number_input("Curso pico a pico da mesa (mm)", min_value=0.1, max_value=200.0, value=25.4, step=0.1)
        f_low = cfg2.number_input("Frequência mínima (Hz)", min_value=freq_min_allowed, max_value=freq_max_allowed, value=freq_min_allowed, key="sine_low")
        f_high = cfg3.number_input("Frequência máxima (Hz)", min_value=f_low, max_value=freq_max_allowed, value=freq_max_allowed, key="sine_high")
        cfg4, cfg5 = st.columns(2)
        n_bands = cfg4.number_input("Número de etapas de frequência", min_value=2, max_value=30, value=8, step=1)
        total_s = cfg5.number_input("Duração total comprimida (s; mínimo 5 s)", min_value=5.0, value=300.0, step=30.0)

        target_high = min(50.0, sample_high)
        if sample_high < 50.0:
            st.warning(f"Este registro cobre até {sample_high:.2f} Hz; o Grms alvo será calculado somente de 5 a {target_high:.2f} Hz, não na faixa completa de 5–50 Hz.")
        vehicle_mask = (f_rep >= 5.0) & (f_rep <= target_high)
        vehicle_grms = float(np.sqrt(np.trapezoid(psd_rep[vehicle_mask], f_rep[vehicle_mask]))) if vehicle_mask.sum() >= 2 else 0.0
        target = st.number_input(f"Grms alvo do veículo na banda 5–{target_high:g} Hz", min_value=0.001, max_value=100.0, value=max(0.001, vehicle_grms), step=0.01, format="%.4f", help="Calculado automaticamente da PSD representativa na faixa disponível até 50 Hz; pode ser editado.")

        edges = np.geomspace(f_low, f_high, int(n_bands) + 1)
        centers = np.sqrt(edges[:-1] * edges[1:])
        band_power = []
        for left, right in zip(edges[:-1], edges[1:]):
            band_f = np.linspace(left, right, 100)
            band_log_psd = np.interp(np.log10(band_f), np.log10(f_rep[1:]), np.log10(np.maximum(psd_rep[1:], 1e-30)))
            band_power.append(float(np.trapezoid(10**band_log_psd, band_f)))
        band_power = np.asarray(band_power)
        if band_power.sum() <= 0:
            st.error("Não há potência espectral positiva na faixa selecionada.")
        else:
            measured_shares = band_power / band_power.sum()
            stroke_peak_m = stroke_pp_mm / 2000.0
            bench_grms = ((2 * np.pi * centers) ** 2 * stroke_peak_m) / (np.sqrt(2) * 9.80665)
            bench_g2 = bench_grms ** 2
            base_grms = float(np.sqrt(np.dot(measured_shares, bench_g2)))
            achievable_min, achievable_max = float(np.min(bench_grms)), float(np.max(bench_grms))
            dwell_shares = measured_shares.copy()
            feasible = achievable_min - 1e-9 <= target <= achievable_max + 1e-9
            if feasible:
                base_g2 = float(np.dot(measured_shares, bench_g2))
                target_g2 = target ** 2
                if target_g2 > base_g2 + 1e-12:
                    idx = int(np.argmax(bench_g2)); endpoint_g2 = float(bench_g2[idx])
                    lam = (target_g2 - base_g2) / (endpoint_g2 - base_g2) if endpoint_g2 > base_g2 else 0.0
                    dwell_shares = (1-lam) * measured_shares
                    dwell_shares[idx] += lam
                elif target_g2 < base_g2 - 1e-12:
                    idx = int(np.argmin(bench_g2)); endpoint_g2 = float(bench_g2[idx])
                    lam = (base_g2 - target_g2) / (base_g2 - endpoint_g2) if base_g2 > endpoint_g2 else 0.0
                    dwell_shares = (1-lam) * measured_shares
                    dwell_shares[idx] += lam
            predicted = float(np.sqrt(np.dot(dwell_shares, bench_g2)))
            if not feasible:
                st.error(f"Não é possível atingir {target:.4g} Grms apenas redistribuindo os tempos: com curso de {stroke_pp_mm:.1f} mm p-p e a faixa selecionada, os tons ficam entre {achievable_min:.4g} e {achievable_max:.4g} Grms. O mínimo da faixa escolhida já excede ou o máximo não alcança o alvo.")
                st.caption(f"Com tempos ponderados pela energia medida, o Grms teórico seria {base_grms:.4g} g. Para atingir alvo abaixo do mínimo seria necessário reduzir o curso, adicionar períodos sem vibração (o que não equivale ao nível de teste) ou usar outra mesa/configuração.")
            else:
                st.success(f"Grms teórico da sequência: {predicted:.4g} g — alvo: {target:.4g} g. A distribuição de tempos foi ajustada para fechar o Grms global, preservando o perfil medido como ponto de partida.")
            dwell = total_s * dwell_shares
            disp_peak_mm = stroke_pp_mm / 2
            table = pd.DataFrame({
                "Etapa": np.arange(1, len(centers) + 1),
                "Frequência (Hz)": centers,
                "Tempo (s)": dwell,
                "Grms teórico do tom": bench_grms,
                "Fração de tempo (%)": dwell_shares * 100,
                "Ponderação PSD medida (%)": measured_shares * 100,
                "Curso (mm p-p)": stroke_pp_mm,
                "Deslocamento pico (mm)": disp_peak_mm,
            })
            st.dataframe(table.round(4), use_container_width=True, hide_index=True)
            if feasible:
                st.download_button("Baixar cronograma senoidal CSV", table.to_csv(index=False).encode("utf-8-sig"), "cronograma_senoidal_grms_alvo.csv", "text/csv")
            st.caption(f"A PSD fornece a ponderação inicial dos tempos por potência de cada banda. Como o modelo mantém o curso, o Grms teórico de cada tom cresce com f²; os tempos são redistribuídos para que a média quadrática global chegue ao alvo quando viável. Registro original: {t[-1]-t[0]:.1f} s; teste comprimido: {total_s:.1f} s. Transições/rampas, impactos e movimento multiaxial da mesa real não entram nesta conta.")

with tabs[3]:
    st.markdown("""
### Processamento
- O CSV deve conter `time_s` em segundos; o eixo de aceleração é tratado como g. **Fs = 1/mediana(Δt)**.
- A média do sinal é removida antes da análise.
- PSD representativa: média aritmética das PSDs de segmentos completos e consecutivos, sem sobreposição. Essa média reduz a variabilidade estatística entre segmentos e é usada como representação do teste; não modifica o sinal temporal nem a PSD individual dos segmentos.
- O Grms é a raiz da integral numérica da PSD representativa. A tabela resume somente Grms do ensaio e dos perfis na faixa selecionada; não substitui o Grms global publicado nem avalia todos os requisitos de ensaio.
- A aba “Teste senoidal” assume movimento harmônico vertical ideal de curso pico a pico fixo e calcula o Grms teórico de cada tom. Ela ajusta os tempos para igualar o Grms global do veículo quando isso é matematicamente possível no intervalo selecionado; em mesa rotativa/reciprocante real, confirme o Grms com acelerômetro. Não iguala a PSD por banda nem estabelece equivalência de resposta/dano ou conformidade.

### Fontes e limites
- **ASTM D4728-06**, Random Vibration Testing of Shipping Containers, Appendix X1, Table X1.1 e Table X1.3. Arquivo de referência no projeto: `sources/1 - ASTM-D4728-06-Random-vibration-test(1).pdf`.
- **ISO 13355**, perfil indicativo transcrito na Table X1.3 da ASTM D4728 fornecida. O projeto não contém cópia separada da ISO.
- **ISTA 3E (2005)**, Random Vibration Spectrum, valores transcritos da referência discutida na conversa. O projeto não contém cópia separada da ISTA.

Confirme edição, tabela, breakpoints e condições de aplicação nas publicações oficiais antes de reproduzir valores em texto acadêmico. ASTM D4169 é uma prática de planos sequenciais de ensaio de embalagens: inclui opção aleatória por D4728 e opção senoidal por D999 métodos B/C. A mesa rotativa de curso fixo pode corresponder a D999 método A2 (choque repetitivo), uma modalidade distinta. O catálogo ASTM de D4728 informa que não há equivalência direta geral entre ensaios aleatórios e senoidais. Curso de 25,4 mm e faixa 5–50 Hz são parâmetros informados para a mesa, não propriedades universais da D4169.

Para transformar aleatório em senoidal com equivalência de fadiga, é necessário avaliar dano potencial/FDS e resposta da estrutura, além de hipóteses sobre amortecimento e propriedades de fadiga. Pahor Kos, Slavič e Boltežar (2015) comparam sweep-sine e excitação aleatória por um modelo baseado em dano e dados de resposta estrutural: https://doi.org/10.1155/2014/340545. O cronograma simplificado deste app é somente uma distribuição exploratória de tempos, não implementa esse método.
""")
