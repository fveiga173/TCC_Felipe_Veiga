"""Referências com proveniência e comparação restrita à banda comum."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from psd_recipe import spectral_area, interpolate
from psd_workflow import validate_profile


def load_catalog():
    data=json.loads(Path(__file__).with_name('data').joinpath('psd_catalog.json').read_text(encoding='utf-8'))
    for row in data['profiles']:
        validate_profile(row['frequency_Hz'],row['psd_g2_per_Hz'])
    return data['profiles']


def curve_band(f,p,low,high,mode='log-log'):
    f,p=np.asarray(f,float),np.asarray(p,float)
    if not f[0]<=low<high<=f[-1]: raise ValueError('Banda fora da cobertura; nenhuma extrapolação aplicada.')
    grid=np.r_[low,f[(f>low)&(f<high)],high]
    return grid,interpolate(f,p,grid,mode)


def compare_profiles(selected,profile,references):
    """Todas as linhas usam a mesma interseção, inclusive a PSD medida."""
    if not references: return pd.DataFrame(),None
    low=max(float(selected['frequency'][0]),float(profile.frequency_Hz.iloc[0]),
            max(float(r['frequency_Hz'][0]) for r in references))
    high=min(float(selected['frequency'][-1]),float(profile.frequency_Hz.iloc[-1]),
             min(float(r['frequency_Hz'][-1]) for r in references))
    if high<=low: raise ValueError('Não há banda comum entre o perfil e todas as referências escolhidas.')
    observed_area=spectral_area(*curve_band(selected['frequency'],selected['psd'],low,high,'linear'))
    proposed_area=spectral_area(*curve_band(profile.frequency_Hz,profile.psd_g2_per_Hz,low,high),'log-log')
    grid=np.geomspace(low,high,512)
    proposed=interpolate(profile.frequency_Hz,profile.psd_g2_per_Hz,grid,'log-log')
    rows=[]
    for r in references:
        ff,pp=r['frequency_Hz'],r['psd_g2_per_Hz']
        area=spectral_area(*curve_band(ff,pp,low,high),'log-log')
        expected=interpolate(ff,pp,grid,'log-log')
        delta=10*np.log10(proposed/expected)
        rows.append(dict(reference_id=r['id'],reference=r['name'],kind=r['kind'],
                         common_low_Hz=low,common_high_Hz=high,
                         reference_grms_common_g=float(np.sqrt(area)),
                         selected_grms_common_g=float(np.sqrt(observed_area)),
                         proposed_grms_common_g=float(np.sqrt(proposed_area)),
                         proposed_to_reference_grms=float(np.sqrt(proposed_area/area)),
                         shape_distance_db=float(np.sqrt(np.mean((delta-delta.mean())**2))),
                         mean_level_difference_db=float(delta.mean()),
                         published_full_grms_g=r.get('grms_full_reported_g'),
                         native_low_Hz=float(ff[0]),native_high_Hz=float(ff[-1])))
    return pd.DataFrame(rows),[low,high]
