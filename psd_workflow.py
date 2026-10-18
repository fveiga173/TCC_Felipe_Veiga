"""Blocos independentes, seleção temporal por intensidade e receita PSD auditável."""
import io
import json
import hashlib
import zipfile
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from scipy.signal import welch, get_window
from psd_recipe import VERSION, cut_band, spectral_area, interpolate, installed_version
from references import references_markdown


def analyze_recording(recording, low=1., high=50., epoch_seconds=10., welch_seconds=4., overlap=.5, window='hann'):
    fs = float(recording.fs)
    if not np.isfinite([low, high, epoch_seconds, welch_seconds, overlap, fs]).all() or not 0 < low < high <= fs/2:
        raise ValueError('Banda inválida ou fora do limite de Nyquist.')
    if epoch_seconds<=0 or welch_seconds<=0:
        raise ValueError('Durações de bloco e janela devem ser positivas.')
    nper, block_n = max(16, round(welch_seconds*fs)), round(epoch_seconds*fs)
    if block_n < nper or nper < 16 or not 0 <= overlap < 1 or window not in ('hann','hamming'):
        raise ValueError('O bloco deve conter uma janela Welch completa; confira janela e sobreposição.')
    if nper>int((recording.segments.end_sample_exclusive-recording.segments.first_sample).max()):
        raise ValueError('Nenhum segmento contém uma janela Welch completa. Diminua a janela ou confira os dados.')
    nov = min(nper-1, round(nper*overlap)); step = nper-nov
    w = get_window(window,nper,fftbins=True)
    rows, spectra, excluded = [], [], []
    for seg in recording.segments.itertuples():
        for a in range(int(seg.first_sample), int(seg.end_sample_exclusive), block_n):
            end = min(a+block_n,int(seg.end_sample_exclusive)); count = end-a
            covered = nper+((count-nper)//step)*step if count >= nper else 0
            if count > covered:
                excluded.append(dict(segment_id=int(seg.segment_id), first_sample=a+covered,
                                     end_sample_exclusive=end, excluded_s=(count-covered)/fs,
                                     reason='Cauda sem janela Welch completa'))
            if not covered: continue
            values = recording.values(a,a+covered)
            f, p = welch(values,fs=fs,window=w,nperseg=nper,noverlap=nov,detrend='constant',
                         scaling='density',return_onesided=True,average='mean')
            ff, pp = cut_band(f,p,low,high)
            dynamic = values-values.mean(); temporal = float(np.sqrt(np.mean(dynamic**2)))
            rows.append(dict(block_id=len(rows)+1, segment_id=int(seg.segment_id), first_sample=a,
                             end_sample_exclusive=a+covered, nominal_position_s=a/fs,
                             duration_s=covered/fs, samples=covered, welch_windows=1+(covered-nper)//step,
                             grms_band_g=float(np.sqrt(spectral_area(ff,pp))), rms_recorded_band_g=temporal,
                             peak_dynamic_g=float(np.max(np.abs(dynamic))),
                             kurtosis_pearson=float(np.mean(dynamic**4)/temporal**4) if temporal else 0.))
            spectra.append(pp)
    if not rows: raise ValueError('Nenhum segmento contém uma janela Welch completa. Diminua a janela ou confira os dados.')
    blocks = pd.DataFrame(rows); spectra = np.stack(spectra)
    durations = blocks.duration_s.to_numpy()
    settings = dict(fs_hz=fs, low_hz=float(low), high_hz=float(high), epoch_seconds=float(epoch_seconds),
                    welch_seconds=float(welch_seconds), nperseg=nper, noverlap=nov, window=window,
                    bin_spacing_hz=fs/nper, enbw_hz=float(fs*np.sum(w*w)/np.sum(w)**2),
                    average='mean',detrend='constant',scaling='density',epochs_overlap=False,
                    covered_duration_s=float(durations.sum()), acquired_nominal_exposure_s=recording.exposure_s,
                    tail_excluded_s=float(recording.exposure_s-durations.sum()),
                    classification_quantity='Grms integrado na banda de análise por bloco',
                    weighting='média linear das PSDs ponderada por duração coberta; sem concatenar amostras')
    return dict(frequency=ff,spectra=spectra,blocks=blocks,
                all_psd=np.average(spectra,axis=0,weights=durations),settings=settings,
                excluded=pd.DataFrame(excluded,columns=['segment_id','first_sample','end_sample_exclusive','excluded_s','reason']))


def select_intensity(analysis, percentage=10., all_blocks=False, complement=False):
    if not np.isfinite(percentage) or not 0 < percentage <= 100:
        raise ValueError('Percentual deve estar entre 0 e 100.')
    blocks = analysis['blocks'].copy()
    levels = blocks.grms_band_g.to_numpy(); durations = blocks.duration_s.to_numpy()
    target = durations.sum()*percentage/100
    order = np.argsort(-levels,kind='stable')
    rank = min(int(np.searchsorted(np.cumsum(durations[order]),target,side='left')),len(order)-1)
    threshold = float(levels[order[rank]])
    # Empates numéricos de mesma intensidade ficam juntos. Não arbitramos
    # registros quase idênticos só para obter exatamente 10%.
    high = (levels > threshold) | np.isclose(levels,threshold,rtol=1e-10,atol=1e-12)
    mask = np.ones(len(blocks),bool) if all_blocks else (~high if complement else high)
    if not mask.any(): raise ValueError('Nenhum bloco nesta classe; ajuste o percentual ou selecione todos os blocos.')
    blocks['selected'] = mask
    psd = np.average(analysis['spectra'][mask],axis=0,weights=durations[mask])
    settings = dict(analysis['settings'],selection='Todos os blocos' if all_blocks else ('Complemento de menor intensidade' if complement else 'Alta intensidade'),
                    requested_high_percentage=float(percentage), threshold_grms_g=threshold,
                    selected_duration_s=float(durations[mask].sum()),
                    selected_duration_percentage=float(100*durations[mask].sum()/durations.sum()),
                    selected_blocks=int(mask.sum()), total_blocks=len(blocks),
                    ties='Grms iguais com rtol=1e-10 e atol=1e-12 mantidos juntos; blocos inteiros',
                    rissi_equivalence_claimed=False, damage_equivalence_claimed=False)
    return dict(frequency=analysis['frequency'],psd=psd,all_psd=analysis['all_psd'],blocks=blocks,
                settings=settings,excluded=analysis['excluded'])


def breakpoint_table(f,p):
    f,p = np.asarray(f,float),np.asarray(p,float)
    validate_profile(f,p)
    slopes = np.r_[10*np.log10(p[1:]/p[:-1])/np.log2(f[1:]/f[:-1]),np.nan]
    return pd.DataFrame(dict(frequency_Hz=f,psd_g2_per_Hz=p,slope_to_next_db_oct=slopes))


def validate_profile(f,p,band=None):
    f,p = np.asarray(f,float),np.asarray(p,float)
    if len(f)<2 or f.shape != p.shape or not np.isfinite(f).all() or not np.isfinite(p).all() or np.any(f<=0) or np.any(p<=0) or np.any(np.diff(f)<=0):
        raise ValueError('Breakpoints inválidos: use frequências positivas crescentes e PSD positiva, sem linhas vazias.')
    if band is not None and not np.allclose([f[0],f[-1]],band,rtol=1e-9,atol=1e-9):
        raise ValueError('Primeiro e último breakpoints devem coincidir com os limites da banda de análise.')


def profile_from_slopes(f,first_psd,slopes):
    f=np.asarray(f,float); slopes=np.asarray(slopes,float)
    if len(slopes) != len(f)-1 or not np.isfinite(slopes).all() or not np.isfinite(first_psd) or first_psd<=0 or np.any(f<=0) or np.any(np.diff(f)<=0):
        raise ValueError('Inclinações inválidas: informe uma por intervalo e PSD inicial positiva.')
    logs = np.r_[np.log10(first_psd),np.log10(first_psd)+np.cumsum(slopes*np.log2(f[1:]/f[:-1])/10)]
    if np.max(logs)>300 or np.min(logs)<-300: raise ValueError('Inclinações produzem PSD fora da faixa numérica.')
    return breakpoint_table(f,10**logs)


def assess_profile(selected,profile,tolerance_db=1.):
    f,p = selected['frequency'],selected['psd']
    ff,pp = profile.frequency_Hz.to_numpy(float),profile.psd_g2_per_Hz.to_numpy(float)
    validate_profile(ff,pp,[f[0],f[-1]])
    grid=np.unique(np.r_[ff,np.concatenate([np.linspace(a,b,9) for a,b in zip(f[:-1],f[1:])])])
    truth=np.interp(grid,f,p)
    if np.any(truth<=0): raise ValueError('PSD de origem nula na banda; não foi criado piso artificial para calcular dB.')
    error=10*np.log10(interpolate(ff,pp,grid,'log-log')/truth)
    source=spectral_area(f,p); proposed=spectral_area(ff,pp,'log-log')
    return dict(input_grms=float(np.sqrt(source)),recipe_grms=float(np.sqrt(proposed)),
                max_error_db=float(np.max(np.abs(error))),tolerance_db=float(tolerance_db),
                passed=bool(np.max(np.abs(error))<=tolerance_db),points=len(ff),
                area_difference_percent=float(100*(proposed/source-1)),interpolation='log-log',
                validation_grid='8 subintervalos por intervalo experimental, mais todos os breakpoints')


def automatic_profile(selected,tolerance_db=1.,max_points=80):
    """Aproxima a PSD linear em uma grade 8x e permite pontos entre bins.

    Escolher somente bins originais pode impedir uma aproximação log-log de
    cumprir a tolerância entre bins, mesmo usando todos eles. Os novos pontos
    são valores do interpolante medido, não novas informações espectrais.
    """
    f,p=np.asarray(selected['frequency'],float),np.asarray(selected['psd'],float)
    validate_profile(f,p)
    if not np.isfinite(tolerance_db) or tolerance_db<=0 or max_points<2:
        raise ValueError('Tolerância e limite de pontos inválidos.')
    grid=np.unique(np.concatenate([np.linspace(a,b,9) for a,b in zip(f[:-1],f[1:])]))
    truth=np.interp(grid,f,p);target=spectral_area(f,p);keep={0,len(grid)-1}
    while True:
        idx=sorted(keep);ff=grid[idx];pp=truth[idx]
        scale=target/spectral_area(ff,pp,'log-log');pp=pp*scale
        raw_errors=10*np.log10(interpolate(ff,truth[idx],grid,'log-log')/truth)
        errors=np.abs(raw_errors+10*np.log10(scale))
        if np.max(errors)<=tolerance_db or len(keep)>=min(max_points,len(grid)):break
        # Escolher pelo desvio antes do ajuste global de área encontra picos
        # estreitos cedo. Usar o erro já normalizado pode gastar todos os
        # pontos em vales enquanto a energia do pico ainda está ausente.
        candidates=np.abs(raw_errors);candidates[idx]=-np.inf
        keep.add(int(np.argmax(candidates)))
    profile=breakpoint_table(ff,pp)
    fit=assess_profile(selected,profile,tolerance_db)
    fit.update(mode='log-log',scale_factor=float(scale),max_points=int(max_points),
               method='Maior erro na grade 8x; pontos podem estar entre bins; área preservada')
    return profile,fit


def export_workflow(selected,profile,fit,recording,context,comparison,references,status,scenario=None):
    meta=dict(version=VERSION,created_utc=datetime.now(timezone.utc).isoformat(),status=status,
              context=context,acquisition=recording.metadata,acquisition_notices=recording.notices,
              settings=selected['settings'],profile_assessment=fit,
              duration_full_level_s=selected['settings']['selected_duration_s'],
              time_compression_factor=1.,intensity_multiplier=1.,damage_equivalence_claimed=False,
              machine_authorization=False,
              slope_convention='Da linha atual para a próxima; última linha vazia; 10*log10(PSD2/PSD1)/log2(f2/f1)',
              duration_basis='Soma de amostras cobertas/fs dos blocos selecionados; pausas e caudas excluídas',
              reference_comparison='Valores na banda comum declarada; sem normalização das referências',
              numerical_grid_is_not_sensor_calibration=True,scenario=scenario,
              software={p:installed_version(p) for p in ['numpy','scipy','pandas','plotly','streamlit']},
              catalog_sha256=hashlib.sha256(Path(__file__).with_name('data').joinpath('psd_catalog.json').read_bytes()).hexdigest(),
              code_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')})
    memo=f'''# Receita PSD - memória de cálculo

Status: {status}. Versão: {VERSION}.

## Resultado
- Banda: {profile.frequency_Hz.iloc[0]:g}-{profile.frequency_Hz.iloc[-1]:g} Hz.
- Grms da PSD dos blocos selecionados: {fit['input_grms']:.9g} g.
- Grms da curva de breakpoints: {fit['recipe_grms']:.9g} g.
- Duração no nível pleno: {meta['duration_full_level_s']:.6f} s.
- Pontos: {len(profile)}. Interpolação: lei de potência em eixos log-log.
- Erro máximo na grade: {fit['max_error_db']:.6g} dB. Critério do estudo: {fit['tolerance_db']:.6g} dB.
- Diferença de área: {fit['area_difference_percent']:.6g}%.

## Seleção e exposição
Regra: {selected['settings']['selection']}. Percentual alto solicitado: {selected['settings']['requested_high_percentage']:g}%.
Fração efetiva selecionada: {selected['settings']['selected_duration_percentage']:.6g}%.
Os blocos são inteiros, não sobrepostos; empates são preservados. O indicador é o Grms na banda declarada.
O percentual se refere ao tempo coberto pelos blocos analisáveis, não a períodos sem registro ou sem janela completa.
Isso não reproduz o gatilho e o max-overwrite de Rissi: os 10% daquele artigo são uma estimativa dos eventos retidos.

## Cálculo
Welch é aplicado separadamente dentro de cada bloco e de cada segmento de aquisição, sem atravessar lacunas.
Janela {selected['settings']['window']}, nperseg={selected['settings']['nperseg']}, noverlap={selected['settings']['noverlap']}.
Média constante removida por janela, PSD unilateral e densidade em g²/Hz. Sem zero-padding ou remoção automática de picos.
S(f)=soma(Tj*Sj(f))/soma(Tj), ponderada em escala linear por duração coberta.
Grms=raiz(integral S(f) df). PSD experimental integrada linearmente; breakpoints e referências por leis de potência.
Inclinação=10*log10(S2/S1)/log2(f2/f1), da linha atual para a próxima. Não usar 20 para densidade de potência.
A curva automática conserva a área da origem durante a simplificação. Edições manuais são avaliadas sem reescala automática.

## Interpretação
A duração corresponde somente aos blocos selecionados. Aplicar o perfil intenso durante a viagem inteira exige justificativa adicional.
Partida e acomodação da mesa não estão incluídas no tempo pleno. Nenhuma equivalência de dano foi demonstrada.
O Grms e a forma espectral devem ser examinados juntos. Uma comparação bibliográfica não comprova conformidade normativa.
Tempos de BIN são nominais por segmento; registros do Arduino não são timestamps de cada amostra.
Sem fechamento final V2, somente prefixos/segmentos com CRC válido são utilizados; caudas sem checkpoint são excluídas.
Verificar unidades, interpolação, carga e capacidade da mesa ao importar o CSV genérico em um controlador.
'''
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for name,frame in [('perfil_psd.csv',profile),('perfil_freq_psd.csv',profile[['frequency_Hz','psd_g2_per_Hz']]),
                           ('blocos_classificados.csv',selected['blocks']),('caudas_excluidas.csv',selected['excluded']),
                           ('segmentos_aquisicao.csv',recording.segments),('comparacao_referencias.csv',comparison),
                           ('psd_selecionada.csv',pd.DataFrame({'frequency_Hz':selected['frequency'],'psd_g2_per_Hz':selected['psd']})),
                           ('psd_todos_blocos.csv',pd.DataFrame({'frequency_Hz':selected['frequency'],'psd_g2_per_Hz':selected['all_psd']}))]:
            z.writestr(name,frame.to_csv(index=False,float_format='%.12g'))
        z.writestr('receita.json',json.dumps(meta,ensure_ascii=False,indent=2,allow_nan=False))
        z.writestr('referencias_selecionadas.json',json.dumps(references,ensure_ascii=False,indent=2,allow_nan=False))
        z.writestr('memoria_calculo.md',memo)
        z.writestr('referencias.md',references_markdown())
        if scenario:
            from vibration_scenarios import compression_factors
            factors=compression_factors(scenario['factor'],scenario['k'])
            extra=breakpoint_table(profile.frequency_Hz,profile.psd_g2_per_Hz*factors['psd_multiplier'])
            z.writestr('cenario_MODELO_NAO_VALIDADO/perfil_psd.csv',extra.to_csv(index=False,float_format='%.12g'))
    return out.getvalue(),meta
