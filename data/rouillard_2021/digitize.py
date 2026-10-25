"""Digitalização manual rastreável da Figura 5; coordenadas em pixels da imagem 1210x917 embutida no PDF."""
from pathlib import Path
import numpy as np,json,csv
ROOT=Path(__file__).resolve().parent
CURVES=[
('astm_d4728_1987_rouillard_digitized','ASTM D4728 Truck 1987',[(203,663),(416,368),(667,368),(822,508),(944,508),(1106,789)],'black'),
('astm_d4728_2001_level2_ista3k_2011_rouillard_digitized','ASTM D4728 nível 2 (2001) / ISTA 3K Rough Surface (2011)',[(172,690),(416,368),(667,368),(822,508),(944,508),(1106,789)],'gray'),
('ista3a_road_2005_rouillard_digitized','ISTA 3A Over-the-Road Trailer (2005)',[(172,530),(367,326),(457,326),(516,508),(610,508),(650,424),(733,424),(761,508),(778,508),(831,441),(937,441),(1082,789)],'#c00000'),
('ista3a_pickup_2005_rouillard_digitized','ISTA 3A Pick-up and Delivery Vehicle (2005)',[(172,508),(367,293),(416,293),(516,582),(624,582),(650,508),(733,508),(767,648),(862,648),(922,467),(984,467),(1106,689)],'#ff6600'),
('ista2ab_2011_rouillard_digitized','ISTA 2A/B (2011)',[(172,648),(416,368),(984,368),(1106,508)],'red'),
('ista2c_level1_2011_rouillard_digitized','ISTA 2C Level 1 (2011)',[(294,571),(416,291),(457,291),(516,480),(595,351),(862,579),(984,579)],'#ff7700'),
('ista3hk_air_2011_rouillard_digitized','ISTA 3H/K Air Ride (2011)',[(172,514),(294,375),(367,389),(457,571),(578,571),(650,473),(773,545),(862,504),(984,613)],'#7030a0')]
def values(points):
 a=np.array(points,float);return 10**((a[:,0]-172)/406),10**(-2-(a[:,1]-368)/(421/3))
def integral(f,p):
 m=np.log(p[1:]/p[:-1])/np.log(f[1:]/f[:-1]);q=m+1;l=np.log(f[1:]/f[:-1]);return np.sum(p[:-1]*f[:-1]*np.where(abs(q)<1e-9,l,np.expm1(q*l)/np.where(abs(q)<1e-9,1,q)))
def build():
 profiles=[]
 with (ROOT/'breakpoints_rouillard2021_DIGITALIZADOS.csv').open('w',newline='',encoding='utf-8-sig') as h:
  w=csv.writer(h);w.writerow(['profile_id','profile_name','frequency_Hz','psd_g2_per_Hz','slope_to_next_db_oct'])
  for ident,name,points,color in CURVES:
   f,p=values(points);sl=10*np.log10(p[1:]/p[:-1])/np.log2(f[1:]/f[:-1]);rms=float(np.sqrt(integral(f,p)))
   for i in range(len(f)):w.writerow([ident,name,float(f[i]),float(p[i]),float(sl[i]) if i<len(sl) else ''])
   profiles.append(dict(id=ident,name=name+' — histórico / digitalizado de Rouillard',kind='historical_digitized_test_profile',source=dict(title='The Case for Reviewing Laboratory-based Road Transport Simulations for Packaging Optimisation',author='Rouillard et al.',year=2021,url='https://doi.org/10.1002/pts.2563'),locator='Figura 5, p.10 impressa (página 11 do PDF fornecido)',context='Perfil histórico de ensaio reproduzido na revisão; datas são as da legenda. Não é uma medição de campo nova nem confirmação da edição vigente.',method='Digitalização manual dos vértices visíveis em pixels; calibração log-log. Frequência: x=172 em 1 Hz, x=578 em 10 Hz, x=984 em 100 Hz; PSD: y=368 em 0.01 e y=789 em 1e-5 g²/Hz. Sem normalização de amplitude.',interpolation='power_law_log_log',frequency_Hz=f.tolist(),psd_g2_per_Hz=p.tolist(),grms_full_reported_g=None,grms_full_calculated_g=rms,limitations='Aproximação gráfica; espessura de traço, sobreposição e arredondamento de pixels limitam precisão. Nenhuma extrapolação além do trecho visível: inícios e finais podem refletir recorte da figura, sobretudo na borda inferior. Grms calculado apenas na banda digitalizada; não atribuir ao protocolo completo.',digitization=dict(pixel_vertices=points,image_width=1210,image_height=917,scaling_applied=False)))
 (ROOT/'perfis_digitizados.json').write_text(json.dumps(profiles,ensure_ascii=False,indent=2)+'\n')
 return profiles
if __name__=='__main__':
 rows=build();print([(r['id'],len(r['frequency_Hz']),round(r['grms_full_calculated_g'],5)) for r in rows])
