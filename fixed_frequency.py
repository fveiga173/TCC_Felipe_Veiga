"""Receita exploratória de excitação senoidal com frequência fixa.

As intensidades são derivadas da PSD medida e convertidas para senoide.
RMS igual não significa equivalência de dano ou de resposta dinâmica.
"""
from __future__ import annotations
import io
import json
import math
import zipfile
import numpy as np
import pandas as pd
from psd_recipe import representative_psd, spectral_area, cut_band


def third_octave_bands(low, high):
    """Retorna bandas de 1/3 de oitava completas na faixa de dados.

    Razão entre centros consecutivos = 10**0.1; limites = centro*10**(±0.05).
    Agrupamento é escolha de análise do aplicativo, não exigência da ISO 2247.
    """
    bands=[]
    for index in range(-60,100):
        center=1000.0*10**(index/10)
        edge_low=center*10**(-.05);edge_high=center*10**(.05)
        if edge_low>=low and edge_high<=high:
            bands.append(dict(index=index,center_hz=center,low_hz=edge_low,high_hz=edge_high))
    return bands


def build_fixed_frequency(t, x, fs, intervals, band_low, band_high,
                          freq_mode, selected_frequency=None, intensity_mode='third_octave',
                          welch_seconds=4., overlap=.5):
    """Reduz a excitação medida a uma senoide e conserva o tempo coberto.

    A frequência automática é o centro de 1/3 de oitava que contém mais
    aceleração quadrática média integrada. O modo manual permite representar
    a restrição da mesa ou uma frequência escolhida para avaliar ressonância.
    A intensidade pode reproduzir o RMS local da banda ou o Grms de toda a
    faixa. A segunda opção concentra toda a energia na frequência selecionada.
    """
    f,p,covered,settings,_=representative_psd(t,x,fs,intervals,welch_seconds,overlap)
    f_band,p_band=cut_band(f,p,float(band_low),float(band_high))
    area_total=spectral_area(f_band,p_band)
    if area_total<=0:raise ValueError('PSD sem energia positiva na banda selecionada.')
    bands=third_octave_bands(band_low,band_high)
    if not bands:raise ValueError('A banda escolhida não comporta uma faixa completa de 1/3 de oitava.')
    rows=[]
    for item in bands:
        area=spectral_area(*cut_band(f,p,item['low_hz'],item['high_hz']))
        rows.append({**item,'area_g2':area,'rms_g':math.sqrt(max(area,0.))})
    table=pd.DataFrame(rows)
    most=table.loc[table.area_g2.idxmax()].to_dict()
    if freq_mode=='Banda de 1/3 de oitava mais energética':
        center=float(most['center_hz'])
        selected=dict(center_hz=center,low_hz=float(most['low_hz']),high_hz=float(most['high_hz']))
        selection='Centro da banda completa de 1/3 de oitava com maior integral de PSD'
    elif freq_mode=='Frequência definida pelo usuário':
        center=float(selected_frequency)
        if not np.isfinite(center) or not band_low<=center<=band_high:
            raise ValueError('A frequência escolhida deve estar dentro da banda selecionada.')
        # A comparação de intensidade local usa a banda de 1/3 de oitava ao
        # redor da frequência fixada, limitada ao intervalo observado.
        selected=dict(center_hz=center,low_hz=max(band_low,center*10**(-.05)),
                      high_hz=min(band_high,center*10**(.05)))
        if selected['high_hz']<=selected['low_hz']:
            raise ValueError('A frequência escolhida não forma banda de análise válida.')
        selection='Frequência definida pelo usuário; banda local de 1/3 de oitava para comparar níveis'
    else:raise ValueError('Critério de frequência inválido.')
    local_area=spectral_area(*cut_band(f,p,selected['low_hz'],selected['high_hz']))
    if intensity_mode=='RMS da banda local':
        target_rms=math.sqrt(local_area)
        intensity_desc='RMS da energia medida na banda local de 1/3 de oitava'
    elif intensity_mode=='Grms de toda a faixa':
        target_rms=math.sqrt(area_total)
        intensity_desc='Grms de toda a banda concentrado em uma senoide'
    else:raise ValueError('Critério de intensidade inválido.')
    if target_rms<=0:raise ValueError('A aceleração equivalente calculada é nula.')
    peak=target_rms*math.sqrt(2)
    omega=2*math.pi*center
    # Para senoide, a_pk = (2πf)^2 * (deslocamento_pp/2).
    displacement_pp_mm=2*peak*9.80665/omega**2*1000
    # Faixa de pico declarada para o método A da edição ISO 2247:2000 fornecida.
    iso_a_peak_range=(.5,1.0)
    iso_a_peak_plausible=iso_a_peak_range[0]<=peak<=iso_a_peak_range[1]
    # O deslocamento escolhido também precisaria ser confrontado com a Figura A.1
    # da edição aplicável e com a capacidade real da mesa; não inferimos isso aqui.
    settings.update(dict(duration_s=float(covered.tempo_representado_s.sum()),
                         duration_basis='Soma de amostras cobertas/fs; sem dupla contagem',
                         target_band_hz=[float(band_low),float(band_high)],
                         frequency_hz=center,frequency_selection=selection,
                         intensity_selection=intensity_desc,intensity_basis='senoide equivalente',
                         acceleration_rms_g=target_rms,acceleration_peak_g=peak,
                         displacement_peak_to_peak_mm=displacement_pp_mm,
                         third_octave_local_hz=[selected['low_hz'],selected['high_hz']],
                         measured_local_rms_g=math.sqrt(local_area),
                         measured_total_grms_g=math.sqrt(area_total),
                         acceleration_peak_within_iso2247_2000_method_a_range=iso_a_peak_plausible,
                         iso2247_compliance_claimed=False,
                         broad_spectrum_replaced_by_single_tone=True))
    return dict(frequency_hz=center, acceleration_rms_g=target_rms,
                acceleration_peak_g=peak, displacement_pp_mm=displacement_pp_mm,
                settings=settings, bands=table, intervals=covered,
                source_frequency=f, source_psd=p, band_low=band_low,band_high=band_high)


def export_fixed_bundle(result, context, status, reasons):
    """Gera memória de cálculo para revisão, sempre rotulada com seu status."""
    s=result['settings']
    explanation=f'''# Receita de frequência fixa derivada do percurso\n\nStatus: {status}\n\n## Parâmetros propostos\n- Frequência senoidal fixa: {s['frequency_hz']:.8g} Hz.\n- Aceleração RMS da senoide: {s['acceleration_rms_g']:.8g} g.\n- Aceleração de pico: {s['acceleration_peak_g']:.8g} g.\n- Deslocamento pico a pico calculado: {s['displacement_peak_to_peak_mm']:.8g} mm.\n- Tempo no nível pleno: {s['duration_s']:.8g} s ({s['duration_s']/60:.6g} min).\n- Critério de frequência: {s['frequency_selection']}.\n- Critério de intensidade: {s['intensity_selection']}.\n\n## Cálculo e aproximação\nPSD foi estimada por Welch em cada trecho. A intensidade local é a raiz da integral da PSD na banda de 1/3 de oitava centrada na frequência escolhida.\nGrms da faixa analisada: {s['measured_total_grms_g']:.8g} g; RMS local: {s['measured_local_rms_g']:.8g} g.\nUma senoide de aceleração RMS a_rms tem pico √2 a_rms. Para movimento senoidal, deslocamento pico a pico = 2 a_pico g/(2πf)².\nO tempo é a soma do tempo realmente coberto nas janelas, não o número de janelas sobrepostas. A partida não entra no tempo pleno.\n\nA redução de um espectro de banda larga a uma frequência única descarta o conteúdo nas demais frequências, a ordem temporal e a distribuição dos níveis. A igualdade de RMS não comprova igualdade de resposta, fadiga ou dano.\nNão foi aplicado multiplicador de intensidade nem compressão temporal.\n\n## Comparação normativa\nA ISO 2247:2000 descreve excitação senoidal de baixa frequência para embalagens completas e cargas unitizadas. No método A, o corpo de prova permanece sem separação, e a aceleração de pico indicada é de 0,5 g a 1,0 g com frequência e deslocamento associados ao Anexo A. O pico calculado {'está' if s['acceleration_peak_within_iso2247_2000_method_a_range'] else 'não está'} nessa faixa; essa comparação, isoladamente, não demonstra atendimento. Frequência, deslocamento, equipamento, montagem e restante do procedimento também precisam ser conformes. O método B busca separações repetitivas mediante subida de frequência a partir de 2 Hz e depende de observação experimental; não é inferido deste perfil.\n\n## Contexto e itens para revisão\n'''+ '\n'.join('- '+str(k)+': '+str(v) for k,v in context.items())+'\n\n## Pendências\n'+'\n'.join('- '+x for x in reasons or ['Conferir capacidade da mesa e método de ensaio antes da execução.'])+'''

Referência: ISO. ISO 2247:2000. Packaging — Complete, filled transport packages and unit loads — Vibration tests at fixed low frequency. Geneva: ISO, 2000.

Esta é uma proposta experimental simplificada. Não é declaração de conformidade com ISO 2247 nem equivalência à vibração rodoviária.
'''
    meta=dict(version='3.1.0',status=status,settings=s,context=context,reasons=reasons,
              limitations=['Excitação de frequência única substitui conteúdo multibanda.',
                           'RMS igual não demonstra equivalência de dano.',
                           'O deslocamento calculado deve caber na mesa e ser conferido com a norma aplicável.',
                           'ISO 2247:2000 possui requisitos de corpo de prova e procedimento não verificados aqui.'],
              iso2247_compliance_claimed=False)
    mem=io.BytesIO()
    with zipfile.ZipFile(mem,'w',zipfile.ZIP_DEFLATED) as z:
        profile=pd.DataFrame([dict(status=status,frequency_Hz=result['frequency_hz'],
            acceleration_rms_g=result['acceleration_rms_g'],acceleration_peak_g=result['acceleration_peak_g'],
            displacement_peak_to_peak_mm=result['displacement_pp_mm'],duration_s=s['duration_s'])])
        z.writestr('receita_frequencia_fixa.csv',profile.to_csv(index=False,float_format='%.12g'))
        z.writestr('energia_por_terco_de_oitava.csv',result['bands'].to_csv(index=False,float_format='%.12g'))
        z.writestr('trechos_cobertos.csv',result['intervals'].to_csv(index=False,float_format='%.12g'))
        z.writestr('psd_faixa_analisada.csv',pd.DataFrame({'frequency_Hz':result['source_frequency'],'psd_g2_per_Hz':result['source_psd']}).to_csv(index=False,float_format='%.12g'))
        z.writestr('receita.json',json.dumps(meta,ensure_ascii=False,indent=2,allow_nan=False))
        z.writestr('memoria_calculo.md',explanation)
    return mem.getvalue(),meta
