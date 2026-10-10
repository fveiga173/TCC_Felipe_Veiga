"""Núcleo científico da receita PSD, independente do Streamlit.

Convenções: aceleração em g, PSD unilateral em g²/Hz, tempo em s.
Nenhuma função infere equivalência de dano nem acelera a exposição.
As tolerâncias da simplificação são critérios de projeto, não normativos.
"""
from __future__ import annotations
import hashlib
import io
import json
import zipfile
import zlib
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.signal import welch, get_window

VERSION = '3.1.0'


def installed_version(package):
    """Registra dependências instaladas e identifica as ausentes no ambiente."""
    try:
        return version(package)
    except PackageNotFoundError:
        return 'não instalado'


def parse_metadata(text):
    """Aceita TXT ou comentários do conversor. O último status prevalece."""
    result = {}
    for line in text.splitlines():
        line = line.strip().lstrip('#').strip()
        if '=' in line:
            key, value = line.split('=', 1)
            result[key.strip()] = value.strip()
    return result


def load_binary(binary, report):
    """Verifica o par BIN/TXT antes de construir tempo nominal e converter Z.

    CRC verifica correspondência de bytes, não calibração. A sequência de
    tempos n/fs é construída: sua regularidade não mede jitter do sensor.
    """
    m = parse_metadata(report.decode('utf-8-sig'))
    required = ['status', 'format', 'time_basis', 'error_code', 'fifo_overflows',
                'samples', 'sample_rate_nominal_hz', 'lsb_per_g', 'crc32',
                'dlpf_cfg', 'accel_range_g', 'duration_arduino_ms', 'saturation_samples']
    if any(k not in m for k in required):
        raise ValueError('TXT incompleto: faltam campos do diagnóstico v4.')
    if m['status'] != 'OK' or m['format'] != 'MPUZ_RAW_LE_V1' or m['time_basis'] != 'sample_index_nominal':
        raise ValueError('Formato desconhecido ou coleta não encerrada com OK.')
    if int(m['error_code']) != 0 or int(m['fifo_overflows']) != 0:
        raise ValueError('O TXT informa falha ou transbordamento. Não gerar receita.')
    n, fs, scale = int(m['samples']), float(m['sample_rate_nominal_hz']), float(m['lsb_per_g'])
    if n < 16 or fs != 500 or scale != 8192 or int(m['dlpf_cfg']) != 2 or int(m['accel_range_g']) != 4:
        raise ValueError('Configuração diferente do firmware v4 verificado (500 Hz, ±4 g, DLPF 2).')
    if len(binary) != 2*n or zlib.crc32(binary) != int(m['crc32']):
        raise ValueError('BIN e TXT divergentes: quantidade de bytes ou CRC32 incorreto.')
    if float(m['duration_arduino_ms']) <= 0 or int(m['saturation_samples']) < 0:
        raise ValueError('Duração ou contador inválido no diagnóstico.')
    raw = np.frombuffer(binary, dtype='<i2')
    m['integrity_verified'] = True
    m['sha256_bin'] = hashlib.sha256(binary).hexdigest()
    m['sha256_txt'] = hashlib.sha256(report).hexdigest()
    m['rate_vs_arduino_hz'] = n/(float(m['duration_arduino_ms'])/1000)
    m['rail_samples_recomputed'] = int(np.sum((raw == -32768) | (raw == 32767)))
    return pd.DataFrame({'time_s': np.arange(n)/fs, 'accel_z_g': raw.astype(float)/scale}), m


def spectral_area(f, p, interpolation='linear'):
    """Integra exatamente cada interpolante: linear ou potência (log-log).

    Log-log: S(f)=S0*(f/f0)^b. Para b=-1, a primitiva é logarítmica.
    A área tem unidade g²; apenas sua raiz é Grms.
    """
    f, p = np.asarray(f, float), np.asarray(p, float)
    if len(f) < 2 or f.shape != p.shape or not np.all(np.isfinite(f)) or not np.all(np.isfinite(p)) or np.any(np.diff(f) <= 0) or np.any(p < 0):
        raise ValueError('Espectro inválido para integração.')
    if interpolation == 'linear':
        return float(np.trapezoid(p, f))
    if interpolation != 'log-log' or np.any(f <= 0) or np.any(p <= 0):
        raise ValueError('Log-log exige frequências e densidades estritamente positivas.')
    logr = np.log(f[1:]/f[:-1])
    k = np.log(p[1:]/p[:-1])/logr + 1
    terms = np.empty_like(k)
    special = np.abs(k) < 1e-10
    terms[special] = p[:-1][special]*f[:-1][special]*logr[special]
    terms[~special] = p[:-1][~special]*f[:-1][~special]*np.expm1(k[~special]*logr[~special])/k[~special]
    return float(terms.sum())


def interpolate(f, p, grid, mode):
    if mode == 'linear':
        return np.interp(grid, f, p)
    if mode != 'log-log':
        raise ValueError('Interpolação não reconhecida.')
    return np.exp(np.interp(np.log(grid), np.log(f), np.log(p)))


def cut_band(f, p, low, high):
    """Acrescenta os limites exatos por interpolação linear, sem extrapolar."""
    if not np.isfinite([low, high]).all() or not 0 < low < high <= f[-1] or low < f[0]:
        raise ValueError('Banda inválida ou fora da cobertura do espectro.')
    grid = np.r_[low, f[(f > low) & (f < high)], high]
    return grid, np.interp(grid, f, p)


def representative_psd(t, x, fs, intervals, seconds=4., overlap=.5):
    """Welch por trecho; média linear das PSDs ponderada pela duração coberta.

    Trechos são [início,fim): uma amostra de fronteira não entra duas vezes.
    Não concatenamos trechos descontínuos antes da FFT (isso criaria saltos).
    nperseg é fixo entre trechos. Caudas sem janela completa são documentadas
    e excluídas da duração da receita. A exposição é N_coberto/fs, não a soma
    das durações das janelas sobrepostas.
    """
    t, x = np.asarray(t, float), np.asarray(x, float)
    if t.shape != x.shape or len(t) < 16 or not np.isfinite(t).all() or not np.isfinite(x).all():
        raise ValueError('Sinal inválido.')
    if not np.isfinite(fs) or fs <= 0 or not np.isfinite(seconds) or seconds <= 0 or not 0 <= overlap < 1:
        raise ValueError('Parâmetros de amostragem inválidos.')
    dt = np.diff(t)
    if np.any(dt <= 0) or np.std(dt)/np.mean(dt) > .05 or np.any(dt > 1.5*np.median(dt)):
        raise ValueError('Tempo irregular: receita bloqueada. Nenhuma reamostragem automática.')
    if abs(1/np.median(dt)/fs - 1) > .01:
        raise ValueError('Taxa informada incompatível com o eixo temporal.')
    nper = max(16, round(fs*seconds))
    nov = min(nper-1, round(nper*overlap)); step = nper-nov
    rows, spectra, weights = [], [], []
    last_end = -np.inf
    intervals = list(intervals)
    if not intervals: raise ValueError('Inclua pelo menos um trecho.')
    for row in intervals:
        left, right = float(row['inicio_s']), float(row['fim_s'])
        if not np.isfinite([left, right]).all() or left < t[0]-1e-9 or right > t[-1]+1/fs+1e-8 or right <= left:
            raise ValueError('Trecho fora do registro ou com limites inválidos.')
        if left < last_end-1e-9:
            raise ValueError('Trechos devem estar ordenados e não podem se sobrepor.')
        last_end = right
        a = int(np.searchsorted(t, left, side='left'))
        b = int(np.searchsorted(t, right, side='left'))
        selected = x[a:b]
        if len(selected) < nper:
            raise ValueError('Cada trecho deve conter ao menos uma janela Welch completa.')
        windows = 1+(len(selected)-nper)//step
        covered = nper+(windows-1)*step
        # Hann periódica explícita evita depender do padrão de versões SciPy.
        f, psd = welch(selected[:covered], fs=fs, window=get_window('hann', nper, fftbins=True),
                       nperseg=nper, noverlap=nov, detrend='constant',
                       scaling='density', return_onesided=True, average='mean')
        duration = covered/fs
        weights.append(duration); spectra.append(psd)
        rows.append(dict(nome=str(row.get('nome', 'Trecho')), inicio_s=left, fim_s=right,
                         primeira_amostra=int(a), ultima_amostra_inclusiva=int(a+covered-1),
                         amostras_selecionadas=int(len(selected)), amostras_cobertas=int(covered),
                         tempo_representado_s=duration, cauda_excluida_s=(len(selected)-covered)/fs,
                         janelas_welch=int(windows)))
    averaged = np.average(np.stack(spectra), axis=0, weights=weights)
    settings = dict(fs_hz=float(fs), nperseg=nper, noverlap=nov, window='Hann periódica',
                    detrend='constant', scaling='density', average='mean',
                    bin_spacing_hz=fs/nper, enbw_hz=1.5*fs/nper,
                    duration_s=float(sum(weights)), weighting='tempo coberto por trecho',
                    duration_basis='soma de N_coberto/fs; sem dupla contagem de sobreposição')
    return f, averaged, pd.DataFrame(rows), settings, spectra


def simplify_psd(f, p, mode='log-log', tolerance_db=1., max_points=80):
    """Seleciona breakpoints pelo maior erro nos bins e conserva a área.

    A cada iteração, os níveis são multiplicados por uma constante para que
    a área do interpolante coincida com a área linear da PSD de origem.
    Isso corrige apenas o erro de representação, não intensifica o ensaio.
    Também avaliamos pontos internos de cada intervalo (grade 8x); o erro
    relatado é nessa grade, não um limite analítico contínuo nem uma
    tolerância de controle da mesa. O limite de pontos pode impedir êxito.
    """
    f, p = np.asarray(f, float), np.asarray(p, float)
    if mode not in ['linear', 'log-log'] or tolerance_db <= 0 or max_points < 2:
        raise ValueError('Parâmetros de simplificação inválidos.')
    target_area = spectral_area(f, p)
    if target_area <= 0 or np.any(p <= 0) or np.any(f <= 0):
        raise ValueError('PSD nula ou não positiva na banda: não adicionar piso artificial para gerar receita.')
    keep = {0, len(f)-1}
    grid = np.unique(np.concatenate([np.linspace(a,b,9) for a,b in zip(f[:-1],f[1:])]))
    truth = np.interp(grid, f, p)
    while True:
        idx = sorted(keep); ff, pp = f[idx], p[idx]
        scale = target_area/spectral_area(ff, pp, mode)
        pp = pp*scale
        recon = interpolate(ff, pp, grid, mode)
        errors = 10*np.log10(recon/truth)
        maximum = float(np.max(np.abs(errors)))
        if maximum <= tolerance_db or len(keep) >= min(max_points, len(f)):
            break
        # Escolhe o maior erro que ainda possui um bin original disponível.
        available = np.array([i for i in range(len(f)) if i not in keep])
        worst_freq = grid[np.argmax(np.abs(errors))]
        candidate = int(available[np.argmin(np.abs(f[available]-worst_freq))])
        keep.add(candidate)
    result = dict(mode=mode, points=len(ff), scale_factor=float(scale),
                  max_error_db=maximum, tolerance_db=float(tolerance_db),
                  passed=bool(maximum <= tolerance_db), max_points=int(max_points),
                  input_grms=float(np.sqrt(target_area)),
                  recipe_grms=float(np.sqrt(spectral_area(ff, pp, mode))),
                  validation_grid='8 subintervalos por intervalo original; inclui bins e limites')
    return ff, pp, result


def build_recipe(t, x, fs, intervals, low, high, seconds=4., overlap=.5,
                 mode='log-log', tolerance_db=1., max_points=80):
    f, p, rows, settings, spectra = representative_psd(t, x, fs, intervals, seconds, overlap)
    band_f, band_p = cut_band(f, p, low, high)
    ff, pp, fit = simplify_psd(band_f, band_p, mode, tolerance_db, max_points)
    rows['grms_banda_g'] = [np.sqrt(spectral_area(*cut_band(f,s,low,high))) for s in spectra]
    # Verificação por subfaixas ajuda a detectar redistribuição espectral,
    # mesmo quando o Grms global foi preservado exatamente.
    cuts = sorted(set([low,high]+[v for v in [5,10,20,50,100,200] if low<v<high]))
    bands = []
    for l,h in zip(cuts[:-1],cuts[1:]):
        origin = spectral_area(*cut_band(f,p,l,h))
        grid = np.r_[l,ff[(ff>l)&(ff<h)],h]
        approx = spectral_area(grid,interpolate(ff,pp,grid,mode),mode)
        bands.append(dict(min_Hz=l,max_Hz=h,grms_origem_g=float(np.sqrt(origin)),
                          grms_receita_g=float(np.sqrt(approx)),erro_area_percentual=100*(approx/origin-1)))
    return dict(frequency=band_f, psd=band_p, profile=pd.DataFrame({'frequency_Hz':ff,'psd_g2_per_Hz':pp}),
                intervals=rows, settings=settings, simplification=fit, bands=pd.DataFrame(bands))


def export_bundle(result, context, status, reasons):
    """Pacote auditável: perfil genérico + cálculos + contexto + hashes.

    Não é um formato proprietário de controlador. O status acompanha todas
    as linhas do CSV para não perder a identificação de estudo/demonstração.
    """
    meta = dict(version=VERSION, created_utc=datetime.now(timezone.utc).isoformat(),
                status=status, reasons=reasons, context=context, settings=result['settings'],
                simplification=result['simplification'], band_hz=[float(result['frequency'][0]),float(result['frequency'][-1])],
                duration_s=result['settings']['duration_s'], intensity_multiplier=1., time_compression_factor=1.,
                damage_equivalence_claimed=False, machine_authorization=False,
                limitations=['Perfil médio não preserva ordem, impactos individuais ou distribuição de amplitudes.',
                             'Banda restrita; sem extrapolação ou correção da resposta do sensor.',
                             'Tempo depende da base de amostragem adotada.',
                             'Conferir capacidade da mesa, carga e configuração do controlador antes da execução.'],
                software={k:installed_version(k) for k in ['numpy','scipy','pandas','streamlit','plotly']},
                code_sha256={name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                             for name in ['app.py','psd_recipe.py','recipe_ui.py','fixed_frequency.py','freq_recipe_ui.py']})
    duration=meta['duration_s']; fit=result['simplification']
    explanation = f'''# Memória de cálculo da receita PSD\n\nStatus: {status}\n\n## Prescrição proposta\n- Direção: eixo informado no contexto; vertical depende da montagem.\n- Banda: {meta['band_hz'][0]:.6g} a {meta['band_hz'][1]:.6g} Hz.\n- Grms de origem: {fit['input_grms']:.8g} g.\n- Grms do perfil: {fit['recipe_grms']:.8g} g.\n- Tempo no nível pleno: {duration:.6f} s ({duration/60:.6f} min).\n- Interpolação entre pontos: {fit['mode']}.\n- Subida gradual não incluída no tempo pleno.\n\n## Cálculo\n1. Welch por trecho, Hann periódica, média removida por janela e densidade unilateral.\n2. PSD representativa = soma(Tj × PSDj)/soma(Tj), em escala linear.\n3. Tj = amostras cobertas/fs; caudas excluídas constam em trechos.csv.\n4. Grms = raiz da integral de PSD na banda, em g²/Hz.\n5. Redução por maior erro espectral, seguida de preservação da área.\n6. Fator de ajuste numérico dos níveis: {fit['scale_factor']:.8g}.\n7. Maior erro na grade de avaliação: {fit['max_error_db']:.6g} dB.\n8. Critério de projeto: {fit['tolerance_db']:.6g} dB; atendido: {fit['passed']}.\n\nTempo de exposição preservado, sem compressão e sem equivalência de dano.\nO ajuste de área compensa a simplificação; não amplia o Grms de origem.\nA duração e a PSD representam somente os trechos cobertos nesta medição.\nO perfil médio não mantém a sequência temporal nem impactos individuais.\n\n## Pendências\n'''+ '\n'.join('- '+r for r in reasons or ['Proposta para revisão técnica; execução depende de verificação da mesa.'])+'''

## Base metodológica
- ASTM D4728-06: 8.2 (dados representativos), 8.3 (controle na mesa), 10.2 (partida), 10.3 (tempo pleno), 10.4 (cautela com compressão).
- Rouillard et al. (2021), Packaging Technology and Science 34(6), 339–351. DOI: 10.1002/pts.2563.
- SciPy, scipy.signal.welch: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html

Os parâmetros Welch e a tolerância de simplificação são escolhas do projeto.
Este pacote não declara conformidade normativa ou aprovação metrológica.
O CSV é genérico; conferir colunas, unidades e interpolação na importação.
Detalhes de origem, justificativas, configurações e hashes: receita.json.
'''
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        profile=result['profile'].copy();profile['status']=status
        z.writestr('perfil_psd.csv',profile.to_csv(index=False,float_format='%.12g'))
        z.writestr('psd_representativa.csv',pd.DataFrame({'frequency_Hz':result['frequency'],'psd_g2_per_Hz':result['psd']}).to_csv(index=False,float_format='%.12g'))
        z.writestr('trechos.csv',result['intervals'].to_csv(index=False,float_format='%.12g'))
        z.writestr('comparacao_subfaixas.csv',result['bands'].to_csv(index=False,float_format='%.12g'))
        z.writestr('receita.json',json.dumps(meta,ensure_ascii=False,indent=2,allow_nan=False))
        z.writestr('memoria_calculo.md',explanation)
    return out.getvalue(), meta
