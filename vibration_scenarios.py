"""Cenários de ensaio: cálculo explícito, sem declaração de equivalência de dano.

Os percentis são do Grms integrado por bloco na MESMA banda. Não são os
espectros de probabilidade proprietários do SaverXware, nem síntese SVS.
Nenhum pico é automaticamente removido e períodos parados não são inferidos.
"""
from __future__ import annotations
import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.signal import get_window, welch
from psd_recipe import VERSION, cut_band, spectral_area, simplify_psd, installed_version
from references import REFERENCES, references_markdown

NOTICE = 'Proposta de ensaio baseada em modelo, pendente de validação experimental.'


def compression_factors(factor, k):
    """C=T0/Tt; amplitude=C^(1/k); PSD=C^(2/k), forma preservada.

    O intervalo 1–5 é uma política desta versão baseada na recomendação
    histórica de Kipp; não é limite metrológico ou garantia de validade.
    """
    if not np.isfinite([factor, k]).all() or not 1 <= factor <= 5 or k <= 0:
        raise ValueError('Use fator entre 1 e 5 e expoente k positivo e finito.')
    amplitude = float(factor**(1/k))
    power = float(amplitude**2)
    if not np.isfinite([amplitude, power]).all():
        raise ValueError('Os parâmetros produzem multiplicador não finito.')
    return dict(time_compression_factor=float(factor), basquin_exponent_k=float(k),
                acceleration_multiplier=amplitude, psd_multiplier=power,
                formula='Gt=G0*C**(1/k); St(f)=S0(f)*C**(2/k); Tt=T0/C')


def analyze_epochs(t, x, base_result, epoch_seconds=10.):
    """Divide cada trecho coberto em blocos temporais sem sobreposição.

    Welch dentro do bloco conserva nperseg, janela, sobreposição e banda.
    Caudas sem janela completa são excluídas e exportadas. As exposições
    nunca são somadas pelo número de janelas Welch sobrepostas.
    """
    t, x = np.asarray(t, float), np.asarray(x, float)
    settings = base_result['settings']; fs = float(settings['fs_hz'])
    nper, nov = int(settings['nperseg']), int(settings['noverlap'])
    if not np.isfinite(epoch_seconds) or epoch_seconds*fs < nper:
        raise ValueError('O bloco de intensidade deve conter pelo menos uma janela Welch.')
    if t.shape != x.shape or not np.isfinite(t).all() or not np.isfinite(x).all():
        raise ValueError('Sinal inválido para análise por blocos.')
    block_n = round(epoch_seconds*fs); step = nper-nov
    w = get_window(settings.get('window_key', 'hann'), nper, fftbins=True)
    low, high = float(base_result['frequency'][0]), float(base_result['frequency'][-1])
    rows, spectra, excluded = [], [], []
    for segment_id, interval in base_result['intervals'].iterrows():
        left = int(interval.primeira_amostra); end = int(interval.ultima_amostra_inclusiva)+1
        for a in range(left, end, block_n):
            b = min(a+block_n, end); count = b-a
            covered = nper+((count-nper)//step)*step if count >= nper else 0
            if count > covered:
                excluded.append(dict(trecho=str(interval.nome), primeira_amostra=a+covered,
                                     fim_amostra_exclusivo=b, tempo_excluido_s=(count-covered)/fs,
                                     motivo='Cauda do bloco sem janela Welch completa'))
            if not covered:
                continue
            values = x[a:a+covered]; dynamic = values-values.mean()
            temporal_rms = float(np.sqrt(np.mean(dynamic**2)))
            peak = float(np.max(np.abs(dynamic)))
            f, psd = welch(values, fs=fs, window=w, nperseg=nper, noverlap=nov,
                           detrend='constant', scaling='density', average='mean', return_onesided=True)
            ff, pp = cut_band(f, psd, low, high)
            spectra.append(pp)
            rows.append(dict(bloco=len(rows)+1, trecho=str(interval.nome), trecho_id=int(segment_id),
                             inicio_s=float(t[a]-t[0]), fim_s=float(t[a]-t[0]+covered/fs),
                             primeira_amostra=a, fim_amostra_exclusivo=a+covered, amostras=covered,
                             duracao_s=covered/fs, grms_banda_g=float(np.sqrt(spectral_area(ff, pp))),
                             rms_temporal_g=temporal_rms, pico_dinamico_g=peak,
                             fator_crista=peak/temporal_rms if temporal_rms > 0 else 0.,
                             curtose_pearson=float(np.mean(dynamic**4)/temporal_rms**4) if temporal_rms > 0 else 0.,
                             estatistica_temporal_definida=bool(temporal_rms > 0),
                             janelas_welch=1+(covered-nper)//step))
    if not rows:
        raise ValueError('Nenhum bloco contém uma janela Welch completa.')
    blocks = pd.DataFrame(rows); spectra = np.stack(spectra)
    average = np.average(spectra, axis=0, weights=blocks.duracao_s)
    represented = float(blocks.duracao_s.sum()); selected = float(settings['duration_s'])
    return dict(frequency=ff, spectra=spectra, psd=average, blocks=blocks,
                excluded=pd.DataFrame(excluded, columns=['trecho','primeira_amostra','fim_amostra_exclusivo','tempo_excluido_s','motivo']),
                settings=dict(settings, epoch_requested_seconds=float(epoch_seconds),
                              epoch_duration_s=float(block_n/fs), epoch_duration_s_covered=represented,
                              epoch_tail_excluded_s=selected-represented,
                              band_hz=[low, high],
                              classification_quantity='Grms integrado na banda por bloco coberto',
                              diagnostic_quantity='pico, RMS, fator de crista e curtose do sinal com média local removida; banda registrada inteira',
                              epochs_overlap=False))


def weighted_percentile(values, weights, quantile):
    """Quantil empírico por tempo: menor valor com acumulado >= q.

    Empates permanecem no mesmo grupo; a fração obtida pode diferir de q.
    Não usamos média aritmética de Grms para obter o Grms de uma PSD média.
    """
    values, weights = np.asarray(values, float), np.asarray(weights, float)
    if values.shape != weights.shape or not len(values) or not 0 < quantile < 1:
        raise ValueError('Percentil ou vetores inválidos.')
    if not np.isfinite(values).all() or not np.isfinite(weights).all() or np.any(weights <= 0):
        raise ValueError('Valores e pesos devem ser finitos, com pesos positivos.')
    order = np.argsort(values, kind='stable')
    index = min(int(np.searchsorted(np.cumsum(weights[order]), quantile*weights.sum(), side='left')), len(values)-1)
    return float(values[order[index]])


def build_plans(analysis, factor=1., k=2., quantile=.8, threshold_g=None,
                mode='log-log', tolerance_db=1., max_points=80):
    """Gera quatro alternativas independentes; não combina exclusão e amplificação.

    A referência de comparação é recalculada na cobertura DOS BLOCOS para
    que todos os cenários comparem o mesmo conjunto. Perfil por grupo =
    média linear das PSDs ponderada por tempo, nunca percentil bin a bin.
    """
    multipliers = compression_factors(factor, k)
    blocks = analysis['blocks'].copy(); f = analysis['frequency']
    durations = blocks.duracao_s.to_numpy(float); grms = blocks.grms_banda_g.to_numpy(float)
    if threshold_g is None:
        threshold = weighted_percentile(grms, durations, quantile)
        rule = f'Percentil temporal P{100*quantile:g}; baixos <= limiar, altos > limiar; empates preservados'
    else:
        threshold = float(threshold_g)
        if not np.isfinite(threshold) or threshold < 0:
            raise ValueError('Limiar deve ser não negativo e finito.')
        rule = 'Limiar manual de Grms; baixos <= limiar, altos > limiar'
    high = grms > threshold; blocks['grupo'] = np.where(high, 'Alta intensidade', 'Baixa intensidade')
    total = float(durations.sum()); all_mask = np.ones(len(blocks), bool)

    def profile(label, mask, compression=1., power=1.):
        origin = np.average(analysis['spectra'][mask], axis=0, weights=durations[mask])
        if spectral_area(f, origin) == 0:
            # Zero é um resultado possível de trecho constante; não criamos
            # piso de ruído para permitir logaritmos. Sua duração é mantida.
            ff, pp = f[[0,-1]], np.zeros(2)
            fit=dict(mode='linear',points=2,scale_factor=1.,max_error_db=0.,tolerance_db=tolerance_db,
                     passed=True,max_points=max_points,input_grms=0.,recipe_grms=0.,zero_energy=True)
        else:
            ff, pp, fit = simplify_psd(f, origin, mode, tolerance_db, max_points)
        return dict(label=label, source_psd=origin, frequency=f,
                    profile=pd.DataFrame({'frequency_Hz':ff,'psd_g2_per_Hz':pp*power}),
                    original_duration_s=float(durations[mask].sum()), duration_s=float(durations[mask].sum()/compression),
                    original_grms_g=float(np.sqrt(spectral_area(f, origin))),
                    proposed_grms_g=float(np.sqrt(spectral_area(ff, pp*power, fit['mode']))),
                    psd_multiplier=float(power), acceleration_multiplier=float(np.sqrt(power)),
                    simplification=fit, block_ids=blocks.loc[mask, 'bloco'].astype(int).tolist())

    reference = profile('PSD média dos blocos', all_mask)
    compressed = profile('PSD com intensidade aumentada', all_mask, factor, multipliers['psd_multiplier'])
    grouped = [profile(label, mask) for label, mask in [('Baixa intensidade', ~high), ('Alta intensidade', high)] if mask.any()]
    selected = [profile('Alta intensidade mantida', high)] if high.any() else []
    def plan(plan_id, label, items, removed, assumptions):
        return dict(id=plan_id, label=label, profiles=items, duration_s=float(sum(p['duration_s'] for p in items)),
                    original_covered_duration_s=total, excluded_low_intensity_s=float(removed),
                    experimental_validation_pending=True, damage_equivalence_claimed=False,
                    machine_authorization=False, notice=NOTICE, assumptions=assumptions)
    plans = [
        plan('referencia', 'Referência sem redução', [reference], 0., ['Perfil médio; não preserva a ordem ou a distribuição temporal dos níveis.']),
        plan('compressao', 'Compressão por aumento de intensidade', [compressed], 0.,
             [f'Modelo de Basquin com k={k:g}; fator T0/Tt={factor:g}.',
              'Resposta e mecanismo de falha não foram medidos; 5:1 é recomendação histórica, sem garantia de equivalência.']),
        plan('niveis', 'Perfis em dois níveis, sem redução', grouped, 0.,
             ['Agrupamento por Grms na banda; durações mantidas; sequência baixa/alta proposta não preserva cronologia.',
              'Abordagem inspirada em Wallin, com algoritmo próprio; não constitui síntese SVS.']),
        plan('selecao', 'Seleção de alta intensidade', selected, float(durations[~high].sum()),
             ['Períodos de baixa intensidade são retirados sem compensação de intensidade.',
              'Não reproduz o algoritmo de espectros de probabilidade do SaverXware; requer validação para o produto.',
              'Tempo curto pode omitir efeitos cumulativos importantes.'])
    ]
    sensitivity = pd.DataFrame([dict(k=kk, fator_compressao=factor, tempo_ensaio_s=total/factor,
                                    multiplicador_aceleracao=factor**(1/kk), multiplicador_psd=factor**(2/kk),
                                    grms_proposto_g=reference['original_grms_g']*factor**(1/kk)) for kk in sorted(set([2.,3.,4.,5.,6.,float(k)]))])
    # Índice relativo sob hipótese de acumulação sum(t*Grms**k). É uma
    # análise de sensibilidade, NÃO fração de dano medida ou prevista.
    scaled = grms/grms.max() if grms.max() > 0 else grms
    fractions = []
    for kk in [2,4,6]:
        contributions = durations*scaled**kk; denom = float(contributions.sum())
        fractions.append(dict(k=kk, fracao_indice_mantida=float(contributions[high].sum()/denom) if denom > 0 else 0.,
                              modelo='sum(Tj*Grms_j**k); índice relativo hipotético, sem dano calculado'))
    return dict(plans=plans, blocks=blocks, settings=dict(analysis['settings'], classification_rule=rule,
                threshold_grms_g=threshold, quantile_requested=float(quantile) if threshold_g is None else None,
                high_duration_fraction=float(durations[high].sum()/total), **multipliers),
                sensitivity=sensitivity, retained_index=pd.DataFrame(fractions), analysis=analysis)


def export_plans(result, context, status, reasons, selected_plan_id):
    """Exporta alternativas, perfis, critérios, exclusões e evidências em ZIP."""
    selected = next(p for p in result['plans'] if p['id'] == selected_plan_id)
    if not selected['profiles']:
        raise ValueError('Nenhum bloco acima do limiar; o cenário não pode ser exportado.')
    meta = dict(version=VERSION, created_utc=datetime.now(timezone.utc).isoformat(), status=status,
                notice=NOTICE, selected_plan=selected_plan_id, settings=result['settings'], context=context,
                reasons=list(reasons), damage_equivalence_claimed=False, conformity_claimed=False,
                machine_authorization=False, experimental_validation_pending=True, references=REFERENCES,
                software={n:installed_version(n) for n in ['numpy','scipy','pandas','streamlit','plotly']},
                code_sha256={n:hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest()
                             for n in ['app.py','psd_recipe.py','recipe_ui.py','vibration_scenarios.py','scenario_ui.py','references.py']}, plans=[])
    rows=[]; out=io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for plan in result['plans']:
            item={key:val for key,val in plan.items() if key != 'profiles'}; item['profiles']=[]
            for index, p in enumerate(plan['profiles'], 1):
                name=f"{plan['id']}/perfil_{index}.csv"
                saved=p['profile'].assign(status=status,scenario=plan['id'],duration_s=p['duration_s'],
                                         validation='PENDENTE',damage_equivalence_claimed=False)
                z.writestr(name,saved.to_csv(index=False,float_format='%.12g'))
                item['profiles'].append({key:val for key,val in p.items() if key not in ['profile','source_psd','frequency']})
                item['profiles'][-1]['file']=name
                rows.append(dict(cenario=plan['id'],perfil=p['label'],arquivo=name,duracao_s=p['duration_s'],
                                 grms_g=p['proposed_grms_g'],multiplicador_psd=p['psd_multiplier'],
                                 interpolacao=p['simplification']['mode'],status=status,validacao='PENDENTE'))
            meta['plans'].append(item)
        z.writestr('sequencias_propostas.csv',pd.DataFrame(rows).to_csv(index=False,float_format='%.12g'))
        z.writestr('blocos_classificados.csv',result['blocks'].to_csv(index=False,float_format='%.12g'))
        z.writestr('caudas_excluidas.csv',result['analysis']['excluded'].to_csv(index=False,float_format='%.12g'))
        z.writestr('sensibilidade_k.csv',result['sensitivity'].to_csv(index=False,float_format='%.12g'))
        z.writestr('indice_hipotetico_mantido.csv',result['retained_index'].to_csv(index=False,float_format='%.12g'))
        source=result['analysis']
        z.writestr('psd_origem_blocos.csv',pd.DataFrame({'frequency_Hz':source['frequency'],'psd_g2_per_Hz':source['psd']}).to_csv(index=False,float_format='%.12g'))
        z.writestr('cenarios.json',json.dumps(meta,ensure_ascii=False,indent=2,allow_nan=False))
        explanation=f'''# Guia de cenários de ensaio — versão {VERSION}

Status: {status}

{NOTICE}

Cenário selecionado: {selected['label']}. Duração plena: {selected['duration_s']:.6f} s.
Partida e transições entre níveis não estão incluídas na duração plena.
As alternativas são independentes: este aplicativo não combina amplificação com descarte.

## Procedimento reproduzível
1. Selecionar trechos contínuos de medição no piso do veículo e declarar base temporal e banda útil.
2. Dividir cada trecho coberto em blocos de {result['settings']['epoch_duration_s']:.6g} s, sem sobreposição entre blocos.
3. Welch por bloco: {result['settings']['window']}, {result['settings']['nperseg']} pontos, média removida por janela, PSD unilateral g²/Hz.
4. Calcular Grms = sqrt(integral(PSD df)) na banda {result['settings']['band_hz']} Hz.
5. Classificação: {result['settings']['classification_rule']}. Limiar: {result['settings']['threshold_grms_g']:.8g} g.
6. Média de PSDs em escala linear com peso de duração coberta; os Grms NÃO são promediados aritmeticamente.
7. Simplificar cada perfil preservando sua área e documentando o erro de representação. Esse ajuste não é compressão.
8. Para compressão: C=T0/Tt; Gt=G0*C^(1/k); St(f)=S0(f)*C^(2/k). k={result['settings']['basquin_exponent_k']:.6g} é hipótese, não estimado do sensor.
9. Para seleção: preservar as durações dos blocos mantidos, sem aumentar intensidade. Exportar todo tempo descartado.

Cobertura dos blocos: {result['settings']['epoch_duration_s_covered']:.6f} s.
Caudas adicionais excluídas nesta divisão: {result['settings']['epoch_tail_excluded_s']:.6f} s.
Consultar a cobertura da receita de origem para outras caudas e intervalos não selecionados.

## Limitações
Não há previsão de dano, vida útil, certificação ou autorização automática da mesa.
É necessário verificar a capacidade da mesa com a carga e validar resposta ou dano para alegar equivalência.
Percentis temporais de Grms não são percentis espectrais bin a bin nem o algoritmo do SaverXware.
Perfis em níveis não constituem síntese não gaussiana SVS e não conservam a cronologia.
Picos e fator de crista usam a banda registrada inteira; a classificação usa a banda PSD declarada.
Nenhum pico ou suposta parada foi removido automaticamente.
Um fator <=5 não garante validade: Dunno observou dano excessivo com o aumento da intensidade.
Índice sum(T*Grms^k) é apenas comparação hipotética de exposição; não estima dano real.

## Pendências
'''+'\n'.join('- '+r for r in reasons)+ '\n\n## Referências e aplicações\n\n'+references_markdown()
        z.writestr('guia_cenarios.md',explanation)
    return out.getvalue(),meta
