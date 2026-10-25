"""Reprocessamento rastreável de TEST014: limpeza exploratória e PSD em 1–200 Hz.
Execute na raiz do repositório: python tools/reprocess_200hz.py BIN TXT DIRETORIO_SAIDA
Não envia arquivos brutos ao GitHub. Dependências já constam no aplicativo.
"""
import sys,json,zlib,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.signal import butter,sosfiltfilt
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from acquisition import read_binary
from psd_workflow import analyze_recording,select_intensity,automatic_profile,assess_profile
from psd_recipe import spectral_area
from psd_catalog import load_catalog,compare_profiles

def run(binary,report,out):
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 data=Path(binary).read_bytes();txt=Path(report).read_text();rec=read_binary(data,txt)
 meta=dict(l.split('=',1) for l in txt.splitlines() if '=' in l and not l.startswith('segment='))
 assert rec.metadata['integrity_verified'] and rec.metadata['session_closed_verified']
 sos=butter(4,[1,200],fs=1000,btype='bandpass',output='sos');rows=[];tails=0
 for line in txt.splitlines():
  if not line.startswith('segment='):continue
  sid,a,b,t,u,reason,crc=map(int,line.split('=')[1].split(','));tails+=(b-a)%10000
  for i in range(a,b-9999,10000):
   raw=rec.raw[i:i+10000];v=raw.astype(float)/8192;y=sosfiltfilt(sos,v)
   rms=float(np.sqrt(np.mean(y*y)));peak=float(np.max(np.abs(y)));kurt=float(np.mean(y**4)/rms**4) if rms else 0
   rows.append(dict(source_segment=sid,first_original=i,end_original=i+10000,start_ms=round(t+(i-a)*(u-t)/(b-a)),stop_ms=round(t+(i+10000-a)*(u-t)/(b-a)),grms_1_200=rms,peak_1_200=peak,kurtosis=kurt,crest=peak/rms if rms else 0,saturated=int(np.count_nonzero(np.abs(v)>=3.99))))
 w=pd.DataFrame(rows);impact=(w['kurtosis']>10)|(w.crest>8)|(w.saturated>0);bad=impact.to_numpy().copy()
 for j in np.flatnonzero(impact):
  for k in (j-1,j+1):
   if 0<=k<len(w) and abs(w.start_ms.iloc[k]-w.start_ms.iloc[j])<15000:bad[k]=True
 keep=(w.start_ms>=36000000)&(w.grms_1_200>=.03)&~bad
 w['decision']=np.where(keep,'retained_candidate',np.where(w.start_ms<36000000,'installation_or_night',np.where(bad,'suspected_impact_and_margin','low_intensity')))
 crc=0;count=0;segments=[]
 with (out/'TCC_Veiga_2026_Serra_Gaucha_1a200Hz.BIN').open('wb') as f:
  for row in w[keep].itertuples():
   block=data[2*row.first_original:2*row.end_original];f.write(block);crc=zlib.crc32(block,crc)
   segments.append(f'segment={len(segments)+1},{count},{count+10000},{row.start_ms},{row.stop_ms},0,{crc}');count+=10000
 header=['format=MPUZ_RAW_LE_V2','firmware=derived_selection_TEST014_1_200Hz','time_basis=sample_index_nominal_per_segment']
 for k in ['sample_rate_nominal_hz','sample_rate_divider','who_am_i','lsb_per_g','gyro_dlpf_cfg','accel_dlpf_cfg','gyro_fchoice_b','accel_range_g']:header.append(k+'='+meta[k])
 header+=['selection_band_hz=1,200','selection_status=CANDIDATE_REVIEW_REQUIRED','source_crc32='+meta['crc32'],'source_duration_arduino_ms='+meta['duration_arduino_ms'],'source_fifo_overflows='+meta['fifo_overflows'],'segment_columns=id,first_sample,end_sample_exclusive,start_arduino_ms,stop_arduino_ms,reason,crc32_prefix']
 derived='\n'.join(header+segments+[f'samples={count}',f'crc32={crc}','error_code=2','fifo_overflows='+meta['fifo_overflows'],'i2c_errors=0','sd_errors=0','storage_integrity_uncertain=0','status=REVIEW','session_closed=1'])+'\n'
 (out/'TCC_Veiga_2026_Serra_Gaucha_1a200Hz.TXT').write_text(derived)
 clean=read_binary((out/'TCC_Veiga_2026_Serra_Gaucha_1a200Hz.BIN').read_bytes(),derived)
 analysis=analyze_recording(clean,1,200,10,4,.5,'hann');selected=select_intensity(analysis,10)
 profile,fit=automatic_profile(selected,tolerance_db=1,max_points=80)
 if not fit["passed"]:profile,fit=automatic_profile(selected,tolerance_db=1,max_points=160)
 profile.to_csv(out/'breakpoints_Serra_Gaucha_1a200Hz.csv',index=False,float_format='%.12g')
 pd.DataFrame({'frequency_Hz':selected['frequency'],'psd_selected_g2_per_Hz':selected['psd'],'psd_all_retained_g2_per_Hz':selected['all_psd']}).to_csv(out/'PSD_medida_1a200Hz.csv',index=False)
 selected['blocks'].to_csv(out/'blocos_e_selecao_10porcento.csv',index=False)
 w.to_csv(out/'mapa_de_cortes_1a200Hz.csv',index=False)
 refs=[r for r in load_catalog() if r['id']!='tcc_veiga_2026_serra_gaucha']
 comparison,band=compare_profiles(selected,profile,refs);comparison.to_csv(out/'comparacao_referencias_1a200Hz.csv',index=False)
 summary=dict(band_hz=[1,200],source_sha256=hashlib.sha256(data).hexdigest(),source_crc32=int(meta['crc32']),source_samples=rec.samples,source_closed=True,source_segments=len(rec.segments),source_fifo_overflows=int(meta['fifo_overflows']),retained_windows=int(keep.sum()),retained_s=count/1000,source_tail_excluded_s=tails/1000,selected_settings=selected['settings'],selected_grms=float(spectral_area(selected['frequency'],selected['psd'])**.5),all_retained_grms=float(spectral_area(selected['frequency'],selected['all_psd'])**.5),breakpoints=len(profile),fit=fit,comparison_common_band_hz=band,derivative_crc32=crc)
 (out/'memoria_de_calculo_1a200Hz.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=lambda v:v.item() if hasattr(v,'item') else str(v)))
 np.savez(out/'qa_temporal.npz',times=w.start_ms.to_numpy()/3600000,rms=w.grms_1_200.to_numpy(),keep=keep.to_numpy())
 print(json.dumps({k:v for k,v in summary.items() if k not in ('selected_settings','fit')},ensure_ascii=False));print('SELECTION',selected['settings']);print('FIT',fit)
 return summary
if __name__=='__main__':run(*sys.argv[1:])
