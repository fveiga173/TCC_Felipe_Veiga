"""Rissi 2008: 14 curvas verticais aproximadas, nunca dados originais.

Uso: python digitize_all.py fonte.pdf pasta_saida
Requer PyMuPDF, numpy, Pillow e matplotlib. Sem normalizacao ao Grms publicado.
"""
from pathlib import Path
import sys, json, csv, hashlib
import fitz
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Imagem na ordem pdfimages; figura, pagina PDF, nome, Grms Tabela 4,
# ordenadas manuais do primeiro segmento pouco cromatico (x0+[0,40,80]).
SPECS = [
 (10,7,11,'Passo Fundo (RS)',.3449,[177,200,227]),
 (11,8,11,'Rio de Janeiro (RJ)',.4291,[151,150,151]),
 (12,9,12,'Campinas (SP)',.5591,[204,216,229]),
 (13,10,12,'Santos (SP)',.7206,[182,185,189]),
 (14,11,13,'São Paulo (SP)',.5706,[226,216,210]),
 (15,12,13,'Lages (SC)',.3142,[217,212,209]),
 (16,13,14,'Curitiba (PR)',.7621,[194,209,223]),
 (17,14,14,'Videira (SC)',.4193,[230,235,241]),
 (18,15,15,'Goiânia (GO)',.2127,[284,289,295]),
 (19,16,15,'Salvador (BA)',.6804,[174,187,201]),
 (20,17,16,'Videira (SC) → Belo Horizonte (MG)',.5393,[233,220,208]),
 (21,18,16,'Videira (SC) → Rio Verde (GO)',.6943,[214,219,226]),
 (22,19,17,'Goiânia (GO) → Salvador (BA)',1.1239,[232,239,248]),
 (24,21,19,'Brasil — composto',.6284,None),
]

def integrate(f,p):
    ratios=f[1:]/f[:-1];k=np.log(p[1:]/p[:-1])/np.log(ratios)+1
    term=np.empty_like(k);special=np.abs(k)<1e-9
    term[special]=np.log(ratios[special])
    term[~special]=np.expm1(k[~special]*np.log(ratios[~special]))/k[~special]
    return float(np.sqrt(np.sum(p[:-1]*f[:-1]*term)))

def band(f,p,high):
    ff=np.r_[1.,f[(f>1)&(f<high)],high]
    return ff,10**np.interp(np.log10(ff),np.log10(f),np.log10(p))

def simplify(f,p,tol=.5):
    x=np.log10(f);y=10*np.log10(p);keep={0,len(f)-1};pending=[(0,len(f)-1)]
    while pending:
        a,b=pending.pop()
        if b-a<2:continue
        error=np.abs(y[a:b+1]-np.interp(x[a:b+1],[x[a],x[b]],[y[a],y[b]]))
        j=a+int(error.argmax())
        if error[j-a]>tol:keep.add(j);pending.extend([(a,j),(j,b)])
    ix=sorted(keep)
    return f[ix],p[ix],float(np.max(np.abs(y-np.interp(x,x[ix],y[ix]))))

def extract(arr,rd=35,gd=28,anchors=None):
    r,g,b=arr.astype(float).transpose(2,0,1)
    yy,xx=np.where((g-r>15)&(b-r>15)&(r>100)&(r<220))
    x0,x1,y0,y1=int(xx.min()-1),int(xx.max()+1),int(yy.min()-1),int(yy.max()+1)
    # Coordenadas conferidas da Figura 21, usadas na extracao anterior.
    if anchors is None:x0,x1,y0,y1=123,929,40,510
    mask=(b-r>rd)&(b-g>gd)&(g-r>-12)&(r<110)&(g<140)
    end=x0+(x1-x0)*np.log10(375)/3
    xs=np.arange(x0,int(np.ceil(end))+9)
    ys=np.array([np.median(np.flatnonzero(mask[y0+1:y1,x]))+y0+1
                 if mask[y0+1:y1,x].sum()>=2 else np.nan for x in xs])
    known=np.isfinite(ys)
    high=min(375.,10**(3*(xs[known][-1]-x0)/(x1-x0)))
    if anchors is not None:
        for dx,y in zip([0,40,80],anchors):ys[dx]=y
    ys=np.interp(xs,xs[np.isfinite(ys)],ys[np.isfinite(ys)])
    f=10**(3*(xs-x0)/(x1-x0));p=10**(-6*(ys-y0)/(y1-y0))
    return *band(f,p,high),xs,ys,known,[x0,x1,y0,y1]

def writecsv(path,rows,header):
    with path.open('w',newline='',encoding='utf-8-sig') as s:
        w=csv.writer(s);w.writerow(header);w.writerows(rows)

def main():
    source,out=map(Path,sys.argv[1:3]);out.mkdir(parents=True,exist_ok=True)
    doc=fitz.open(source);images=[]
    for page in doc:
        # Ordenacao do PDF igual a pdfimages (ordem de exibicao da pagina).
        for info in page.get_image_info(xrefs=True):images.append(doc.extract_image(info['xref'])['image'])
    profiles=[];summary=[];allrows=[];pixelrows=[]
    fig,axes=plt.subplots(7,2,figsize=(15,25))
    for ax,spec in zip(axes.flat,SPECS):
        i,number,page,name,published,anchors=spec
        import io
        arr=np.array(Image.open(io.BytesIO(images[i])).convert('RGB'))
        f,p,xs,ys,known,cal=extract(arr,anchors=anchors)
        ff,pp=band(f,p,200);fb,pb,err=simplify(f,p);f200,p200,e200=simplify(ff,pp)
        key=f'rissi2008_vertical_fig{number:02}'
        fullgrms=integrate(f,p);bpgrms=integrate(fb,pb)
        sensitivity=[integrate(*extract(arr,rd,gd,anchors)[:2]) for rd,gd in [(30,23),(35,28),(40,33)]]
        profile=dict(id=key,name=f'Rissi 2008 — {name} — vertical (digitalizado)',kind='digitized_approximation',
            source=dict(title='Measurement and analysis of truck transport environment in Brazil',author='Rissi; Singh; Burgess; Singh',year=2008,doi='10.1002/pts.797',url='https://digitalcommons.calpoly.edu/it_fac/47/',edition_note='Cópia anterior à revisão por pares; aproximação gráfica, não tabela original.'),
            locator=f'Figura {number}, página PDF {page}; Tabelas 3 e 4',
            context='Composto dos 13 percursos.' if number==21 else ('Distribuição metropolitana.' if number<=16 else 'Transporte de longa distância.'),
            method='Curva azul vertical por mediana de cor; primeiro segmento pouco cromático com âncoras manuais. Calibração log-log; simplificação 0,5 dB; sem normalização de Grms. Banda desde 1 Hz até o último pixel identificado, limitada a 375 Hz, não banda original de integral comprovada.',
            interpolation='power_law_log_log',frequency_Hz=fb.tolist(),psd_g2_per_Hz=pb.tolist(),
            grms_full_reported_g=published,grms_full_recalculated_g=bpgrms,min_frequency_Hz=1.,max_frequency_Hz=float(f[-1]),point_count=len(fb),
            digitization=dict(figure=number,pdf_page=page,calibration_xy=cal,manual_early_y=anchors,color_mask=[35,28,-12,110,140],pixel_columns=len(xs),interpolated_columns=int((~known).sum()),
                grms_dense_g=fullgrms,grms_1_200_g=integrate(ff,pp),difference_from_published_percent=100*(fullgrms/published-1),simplification_max_error_db=err,simplification_area_difference_percent=100*((bpgrms/fullgrms)**2-1),threshold_sensitivity_grms=sensitivity),
            limitations='Gatilho/max-overwrite; autores estimam 10% superiores da viagem. Não é média contínua nem norma. Grms publicado tem banda exata não explicitada. Pixels, cruzamentos e interpolação geram incerteza não quantificada; tolerância de simplificação não mede erro da digitalização. Goiânia é GO; SC/SA na legenda da Figura 19 são inconsistências tipográficas.')
        profiles.append(profile)
        writecsv(out/f'{key}_breakpoints_1a200Hz.csv',zip(f200,p200),['frequency_Hz','psd_g2_per_Hz'])
        writecsv(out/f'{key}_breakpoints_1a375Hz.csv',zip(fb,pb),['frequency_Hz','psd_g2_per_Hz'])
        summary.append([name,number,page,published,fullgrms,bpgrms,100*(fullgrms/published-1),integrate(ff,pp),len(fb),len(f200),err,float(f[-1])])
        allrows.extend([name,number,float(a),float(b)] for a,b in zip(fb,pb))
        pixelrows.extend([number,int(x),float(y),int(k)] for x,y,k in zip(xs,ys,known))
        ax.imshow(arr);ax.plot(xs,ys,color='#ff321d',lw=.85);ax.set_axis_off();ax.set_title(f'Fig. {number}: {name}\nPublicado {published:.4f} g | digitalizado {fullgrms:.4f} g',fontsize=10)
    fig.suptitle('Rissi et al. (2008): conferência das 14 curvas VERTICAIS\nTraçado extraído em vermelho; outras direções excluídas',fontsize=16)
    fig.tight_layout(rect=(0,0,1,.975));fig.savefig(out/'conferencia_14_curvas_verticais.png',dpi=140);plt.close(fig)
    writecsv(out/'resumo_14_perfis_verticais.csv',summary,['perfil','figura','pagina_PDF','Grms_publicado_g','Grms_digitalizado_1a375_g','Grms_breakpoints_1a375_g','diferenca_publicado_percent','Grms_digitalizado_1a200_g','breakpoints_1a375','breakpoints_1a200','erro_simplificacao_max_dB','limite_superior_efetivo_Hz'])
    writecsv(out/'todos_breakpoints_verticais_1a375Hz.csv',allrows,['perfil','figura','frequency_Hz','psd_g2_per_Hz'])
    writecsv(out/'coordenadas_pixels.csv',pixelrows,['figura','x_pixel','y_pixel','cor_detectada'])
    (out/'perfis_e_proveniencia.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),profiles=profiles),ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
