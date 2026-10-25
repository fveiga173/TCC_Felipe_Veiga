"""Curva PSD e breakpoints para ensaios de transporte — v5.0.1."""
import html
import hashlib
import io
import json
from dataclasses import replace
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from acquisition import read_binary, read_csv_recording, synthetic_recording
from psd_recipe import VERSION, interpolate
from psd_workflow import (analyze_recording, select_intensity, automatic_profile,
                          breakpoint_table, profile_from_slopes, assess_profile, export_workflow)
from psd_catalog import load_catalog, compare_profiles
from references import references_markdown


def download_csv(label,frame,name,key=None):
    st.download_button(label,frame.to_csv(index=False,float_format='%.12g').encode('utf-8-sig'),name,'text/csv',key=key)


def psd_figure(selected,profile,references=()):
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=selected['frequency'],y=selected['all_psd'],name='Todos os blocos analisáveis',line=dict(color='#9aa8b7',width=1.2)))
    fig.add_trace(go.Scatter(x=selected['frequency'],y=selected['psd'],name='Este teste — PSD dos blocos selecionados',line=dict(color='#2677b8',width=1.8)))
    grid=np.geomspace(profile.frequency_Hz.iloc[0],profile.frequency_Hz.iloc[-1],2000)
    fig.add_trace(go.Scatter(x=grid,y=interpolate(profile.frequency_Hz,profile.psd_g2_per_Hz,grid,'log-log'),
                             name='Curva de ensaio proposta',line=dict(color='#e68126',width=2.7)))
    fig.add_trace(go.Scatter(x=profile.frequency_Hz,y=profile.psd_g2_per_Hz,name='Breakpoints',mode='markers',
                             marker=dict(color='#e68126',size=7),hovertemplate='%{x:.4g} Hz<br>%{y:.5g} g²/Hz<extra>Breakpoint</extra>'))
    low,high=float(grid[0]),float(grid[-1])
    for r in references:
        lo,hi=max(low,r['frequency_Hz'][0]),min(high,r['frequency_Hz'][-1])
        if lo>=hi: continue
        ff=np.geomspace(lo,hi,900)
        fig.add_trace(go.Scatter(x=ff,y=interpolate(r['frequency_Hz'],r['psd_g2_per_Hz'],ff,'log-log'),
                                 name=r['name'],line=dict(width=1.4,dash='dot')))
    fig.update_layout(xaxis=dict(type='log',title='Frequência (Hz)',range=[np.log10(low),np.log10(high)]),
                      yaxis=dict(type='log',title='PSD (g²/Hz)'),height=530,margin=dict(t=20,b=25),
                      legend=dict(orientation='h',yanchor='top',y=-.17),hovermode='x unified')
    return fig


def render_psd_plot(fig, key, config=None):
    """Gráfico com altura própria e legenda independente em três colunas."""
    palette=['#636efa','#EF553B','#00cc96','#ab63fa','#FFA15A','#19d3f3',
             '#FF6692','#B6E880','#FF97FF','#FECB52']
    entries=[]
    for i,trace in enumerate(fig.data):
        color=trace.line.color or trace.marker.color or palette[i % len(palette)]
        trace.update(line_color=color)
        name=html.escape(str(trace.name))
        dash='dotted' if trace.line.dash and trace.line.dash!='solid' else 'solid'
        swatch=(f'<span style="width:10px;height:10px;border-radius:50%;background:{color};flex-shrink:0"></span>'
                if trace.mode=='markers' else
                f'<span style="width:25px;border-top:2px {dash} {color};flex-shrink:0"></span>')
        entries.append(f'<div style="display:flex;gap:8px;align-items:center;min-width:0;padding:5px 2px">{swatch}<span style="overflow-wrap:anywhere">{name}</span></div>')
    fig.update_layout(showlegend=False,height=650,margin=dict(t=25,b=65,l=65,r=25))
    st.plotly_chart(fig,width='stretch',key=key,config=config or {})
    st.markdown('<div aria-label="Legenda das curvas PSD" style="max-height:220px;overflow-y:auto;padding:8px 12px;border:1px solid rgba(128,128,128,.25);border-radius:6px;font-size:12px;line-height:1.35"><div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));column-gap:18px">'+''.join(entries)+'</div></div>',unsafe_allow_html=True)


def catalog_details(references):
    for r in references:
        with st.expander(r['name']):
            source=r['source']
            st.write(f"**{source['title']}** · {source.get('year','')} · {r['locator']}")
            st.write(source.get('edition_note',''))
            st.write(r.get('context',''))
            if r.get('method'): st.write(r['method'])
            if r.get('limitations'): st.caption(r['limitations'])
            if r.get('figure5_aliases_note'): st.caption(r['figure5_aliases_note'])
            st.markdown(f"[Fonte consultada]({source['url']})")
            st.caption(f"Banda original: {r['frequency_Hz'][0]:g}–{r['frequency_Hz'][-1]:g} Hz. Grms publicado na banda original: {r.get('grms_full_reported_g') or 'não informado'} g. Não confundir esse valor global com o Grms em uma banda comum recortada.")
            st.dataframe(breakpoint_table(r['frequency_Hz'],r['psd_g2_per_Hz']),hide_index=True,height=230)


def editor(selected,tolerance,max_points,seed):
    automatic,auto_fit=automatic_profile(selected,tolerance,max_points)
    if st.session_state.get('_profile_seed')!=seed:
        st.session_state['_profile_seed']=seed
        st.session_state['_working_profile']=automatic
        st.session_state['_editor_generation']=st.session_state.get('_editor_generation',0)+1
        st.session_state['_last_editor_mode']=None
    mode=st.radio('Editar a tabela por',['PSD (g²/Hz)','Inclinação (dB/oct)'],horizontal=True,key='profile_edit_mode')
    if st.session_state.get('_last_editor_mode')!=mode:
        st.session_state['_editor_generation']+=1
        st.session_state['_last_editor_mode']=mode
    if st.button('Restaurar breakpoints automáticos',key='restore_breakpoints'):
        st.session_state['_working_profile']=automatic
        st.session_state['_editor_generation']+=1
    with st.expander('Importar uma tabela própria de breakpoints'):
        imported=st.file_uploader('CSV com frequency_Hz e psd_g2_per_Hz',type=['csv'],key='import_profile_'+seed)
        st.caption('Duas colunas numéricas em Hz e g²/Hz. A banda deve coincidir com a análise. Inclinações são recalculadas.')
        if imported is not None and st.button('Aplicar tabela importada',key='apply_profile_'+seed):
            try:
                frame=pd.read_csv(imported)
                st.session_state['_working_profile']=breakpoint_table(frame.frequency_Hz,frame.psd_g2_per_Hz)
                st.session_state['_editor_generation']+=1
            except (ValueError,KeyError,AttributeError) as exc: st.error(f'Tabela importada inválida: {exc}')
    current=st.session_state['_working_profile']
    key=f'breakpoints_{seed}_{st.session_state["_editor_generation"]}'
    if mode=='PSD (g²/Hz)':
        changed=st.data_editor(current,num_rows='dynamic',hide_index=True,height=330,key=key,
            disabled=['slope_to_next_db_oct'],column_config={
                'frequency_Hz':st.column_config.NumberColumn('Freq (Hz)',format='%.6g',min_value=.000001),
                'psd_g2_per_Hz':st.column_config.NumberColumn('PSD (g²/Hz)',format='%.8g',min_value=1e-300),
                'slope_to_next_db_oct':st.column_config.NumberColumn('Slope ↓ (dB/oct)',format='%.4f')})
        proposed=breakpoint_table(changed.frequency_Hz,changed.psd_g2_per_Hz)
    else:
        initial=st.number_input('PSD do primeiro breakpoint (g²/Hz)',min_value=1e-300,value=float(current.psd_g2_per_Hz.iloc[0]),format='%.10g',key='first_psd_'+key)
        changed=st.data_editor(current[['frequency_Hz','slope_to_next_db_oct']],num_rows='dynamic',hide_index=True,height=330,key=key,
            column_config={'frequency_Hz':st.column_config.NumberColumn('Freq (Hz)',format='%.6g'),
                           'slope_to_next_db_oct':st.column_config.NumberColumn('Slope ↓ (dB/oct)',format='%.4f')})
        if pd.notna(changed.slope_to_next_db_oct.iloc[-1]):
            raise ValueError('A última linha não tem próximo ponto: deixe sua inclinação vazia.')
        proposed=profile_from_slopes(changed.frequency_Hz,initial,changed.slope_to_next_db_oct.iloc[:-1])
        st.dataframe(proposed,hide_index=True,height=230)
    fit=assess_profile(selected,proposed,tolerance)
    changed_values=(proposed.shape!=current.shape or not np.allclose(proposed.iloc[:,:2],current.iloc[:,:2],rtol=1e-12,atol=0.))
    st.session_state['_working_profile']=proposed
    if changed_values:
        # Atualiza também as colunas calculadas do próprio editor, sem deixar
        # inclinações visíveis de uma versão anterior da tabela.
        st.session_state['_editor_generation']+=1
        st.rerun()
    fit['automatic_seed']=auto_fit
    fit['manually_changed']=not (proposed.shape==automatic.shape and np.allclose(proposed.iloc[:,:2],automatic.iloc[:,:2],rtol=1e-12,atol=0.))
    return proposed,fit


def show_builtin_profile(catalog):
    """Abre a tabela autoral congelada; não apresenta reconstrução como PSD bruta."""
    baseline=catalog[0]
    st.header(baseline['name'])
    profile=breakpoint_table(baseline['frequency_Hz'],baseline['psd_g2_per_Hz'])
    from psd_recipe import spectral_area
    grms=float(np.sqrt(spectral_area(profile.frequency_Hz,profile.psd_g2_per_Hz,'log-log')))
    a,b,c=st.columns(3)
    a.metric('Grms do perfil incorporado',f'{grms:.5f} g')
    b.metric('Breakpoints',len(profile))
    c.metric('Banda do perfil',f'{profile.frequency_Hz.iloc[0]:g}–{profile.frequency_Hz.iloc[-1]:g} Hz')
    st.caption('Perfil autoral incorporado. Curva reconstruída da tabela exportada; não é uma nova análise do BIN. Para comparar uma nova medição, envie seu BIN + TXT ou CSV na lateral.')
    by_id={r['id']:r for r in catalog[1:]}
    ids=st.multiselect('Referências para comparar com o perfil incorporado',list(by_id),
        default=list(by_id),
        format_func=lambda k:by_id[k]['name'],key='builtin_references')
    refs=[by_id[k] for k in ids]
    fig=go.Figure()
    grid=np.geomspace(profile.frequency_Hz.iloc[0],profile.frequency_Hz.iloc[-1],2000)
    values=interpolate(profile.frequency_Hz,profile.psd_g2_per_Hz,grid,'log-log')
    fig.add_trace(go.Scatter(x=grid,y=values,name=baseline['name'],line=dict(color='#e68126',width=3)))
    fig.add_trace(go.Scatter(x=profile.frequency_Hz,y=profile.psd_g2_per_Hz,name='Breakpoints',mode='markers',marker=dict(color='#e68126',size=6)))
    for ref in refs:
        lo=max(float(grid[0]),ref['frequency_Hz'][0]);hi=min(float(grid[-1]),ref['frequency_Hz'][-1])
        if lo<hi:
            f=np.geomspace(lo,hi,500)
            fig.add_trace(go.Scatter(x=f,y=interpolate(ref['frequency_Hz'],ref['psd_g2_per_Hz'],f,'log-log'),name=ref['name'],line=dict(dash='dot')))
    fig.update_layout(xaxis=dict(type='log',title='Frequência (Hz)'),yaxis=dict(type='log',title='PSD (g²/Hz)'),height=540,legend=dict(orientation='h',y=-.2))
    render_psd_plot(fig,key='builtin_psd_plot')
    selected=dict(frequency=grid,psd=values)
    comparison,band=compare_profiles(selected,profile,refs)
    comparison.loc[comparison.reference_id=='this_test_selected','reference']=baseline['name']+' — reconstruído'
    comparison.loc[comparison.reference_id=='this_test_selected','kind']='builtin_reconstructed'
    comparison.loc[comparison.reference_id=='this_test_selected','reference_grms_full_g']=grms
    st.caption('Grms completo de cada perfil, na banda indicada ao lado. Bandas diferentes representam conteúdos de frequência diferentes; estes valores não são uma comparação em banda igual.')
    st.dataframe(comparison[['reference','native_band_Hz','reference_grms_full_g']].rename(columns={'reference':'Referência','native_band_Hz':'Banda do perfil (Hz)','reference_grms_full_g':'Grms do perfil completo (g)'}),hide_index=True,column_config={'Grms do perfil completo (g)':st.column_config.NumberColumn(format='%.5f')})
    with st.expander('Comparação espectral na mesma banda'):
        st.caption(f'Métricas calculadas em {band[0]:g}–{band[1]:g} Hz, sem normalização. Este recorte não altera o Grms completo mostrado acima.')
        st.dataframe(comparison[['reference','reference_grms_common_g','proposed_to_reference_grms','shape_distance_db']].rename(columns={'reference':'Referência','reference_grms_common_g':'Grms na banda comum (g)','proposed_to_reference_grms':'TCC / referência na banda comum','shape_distance_db':'Distância de forma (dB)'}),hide_index=True)
    download_csv('Baixar comparação dos perfis',comparison,'comparacao_perfis.csv',key='download_builtin_comparison')
    with st.expander('Tabela de breakpoints do perfil incorporado'):
        st.dataframe(profile,hide_index=True)
    download_csv('Baixar perfil incorporado (CSV)',profile,'TCC_Veiga_2026_Serra_Gaucha.csv',key='download_builtin_profile')
    catalog_details([baseline,*refs])


def main():
    st.set_page_config(page_title='Veiga | Curva PSD e breakpoints',page_icon='📈',layout='wide')
    st.title('Curva PSD e breakpoints de ensaio')
    st.caption('Medição de transporte → seleção por intensidade → curva proposta → comparação com referências · v6.3')
    catalog=load_catalog()
    with st.sidebar:
        st.header('Comparar novo teste')
        uploaded=st.file_uploader('CSV ou BIN do sensor',type=['csv','bin'])
        report_file=st.file_uploader('TXT do diagnóstico (obrigatório com BIN)',type=['txt'])
        demo=bool(st.session_state.get('_test_demo',False))  # fixture interna de testes; produção usa apenas uploads
        source=st.selectbox('Contexto da aquisição',['Teste manual / funcional','Transporte em veículo','Mesa vibratória','Outro'])
        unit=st.selectbox('Unidade do CSV',['g','m/s²'])
        fullscale=st.selectbox('Escala confirmada do CSV (g)',['Não confirmada',2,4,8,16])
    try:
        if demo:
            if '_demo_recording' not in st.session_state: st.session_state['_demo_recording']=synthetic_recording()
            recording=st.session_state['_demo_recording']; filename='demonstracao_sintetica_1000s'
            stamp=recording.metadata['sha256_input']
            st.info('DEMONSTRAÇÃO: sinal sintético de 1000 s, com aumento de intensidade nos últimos 100 s. Não representa uma campanha de transporte.')
        elif uploaded is not None:
            filename=uploaded.name
            if filename.lower().endswith('.bin'):
                if report_file is None: st.info('Envie o TXT correspondente ao BIN para conferir integridade e segmentos.'); return
                data=uploaded.getbuffer(); report=report_file.getvalue()
                stamp=hashlib.sha256(data).hexdigest()+hashlib.sha256(report).hexdigest()
                if st.session_state.get('_loaded_stamp')!=stamp:
                    st.session_state['_loaded_recording']=read_binary(data,report)
                    st.session_state['_loaded_stamp']=stamp
                recording=st.session_state['_loaded_recording'];fullscale=4
            else:
                data=uploaded.getvalue();base=hashlib.sha256(data).hexdigest()+unit
                if st.session_state.get('_csv_base')!=base:
                    st.session_state['_csv_default']=read_csv_recording(data,unit=unit)
                    st.session_state['_csv_base']=base
                default=st.session_state['_csv_default']
                with st.sidebar: axis=st.selectbox('Eixo do CSV',default.metadata['columns'],key='csv_axis_'+base[:12])
                stamp=base+axis
                if axis==default.metadata['axis']: recording=default
                elif st.session_state.get('_loaded_stamp')==stamp: recording=st.session_state['_loaded_recording']
                else:
                    recording=read_csv_recording(data,axis,unit)
                    st.session_state['_loaded_recording']=recording;st.session_state['_loaded_stamp']=stamp
        else:
            show_builtin_profile(catalog)
            return
    except (ValueError,KeyError,TypeError,UnicodeError) as exc:
        st.error(f'Falha ao ler aquisição: {exc}');return
    if recording.metadata.get('integrity_verified'):
        st.success(f'BIN + TXT: quantidade e CRC32 conferidos em {len(recording.segments)} segmento(s).')
    for notice in recording.notices: st.caption(notice)
    rails=int(recording.metadata.get('rail_samples_recomputed',0))
    if recording.metadata.get('format')=='CSV' and fullscale!='Não confirmada':
        clip_key=(stamp,float(fullscale))
        if st.session_state.get('_clip_key')!=clip_key:
            st.session_state['_clip_count']=sum(int(np.count_nonzero(np.abs(recording.raw[i:i+1000000])>=.98*float(fullscale))) for i in range(0,recording.samples,1000000))
            st.session_state['_clip_key']=clip_key
        rails=int(st.session_state['_clip_count'])
    with st.sidebar:
        st.header('Curva de ensaio')
        low=st.number_input('Frequência mínima (Hz)',min_value=.01,value=1.,step=.5,key='recipe_low')
        cap=min(200.,float(recording.fs)/2)
        if st.session_state.get('_band_revision')!='1_200_20261025':
            st.session_state.pop('recipe_high',None)
            st.session_state['_band_revision']='1_200_20261025'
        if st.session_state.get('recipe_high',cap)>cap: st.session_state['recipe_high']=cap
        high=st.number_input('Frequência máxima (Hz)',min_value=.02,max_value=cap,value=cap,step=5.,key='recipe_high')
        selection_mode=st.selectbox('Trechos usados no perfil',['Alta intensidade','Todos os blocos','Complemento de menor intensidade'],key='selection_mode')
        percent=st.number_input('Tempo de alta intensidade (%)',min_value=.1,max_value=100.,value=10.,step=1.,key='high_percentage')
        with st.expander('Processamento e simplificação'):
            epoch=st.number_input('Bloco de intensidade (s)',min_value=.1,value=10.,step=1.,key='epoch_seconds')
            seconds=st.number_input('Janela Welch (s)',min_value=.1,value=4.,step=.5,key='welch_seconds')
            overlap=st.selectbox('Sobreposição Welch (%)',[50,0,75],key='overlap')/100
            window=st.selectbox('Janela espectral',['hann','hamming'],key='welch_window')
            tolerance=st.number_input('Erro espectral admitido (dB)',min_value=.05,max_value=10.,value=1.,step=.25,key='recipe_tolerance')
            max_points=st.number_input('Máximo de breakpoints automáticos',min_value=2,max_value=500,value=160,step=5,key='recipe_points')
        with st.expander('Recortar a medição'):
            st.caption('Posição nominal acumulada por amostras, em segundos; não é o relógio da viagem. Segmentos continuam separados.')
            crop=st.checkbox('Aplicar recorte nominal',key='crop_enabled')
            if crop:
                start=st.number_input('Início nominal (s)',min_value=0.,value=0.,key='crop_start_'+stamp[:12])
                end=st.number_input('Fim nominal exclusivo (s)',min_value=.001,value=float(recording.samples/recording.fs),key='crop_end_'+stamp[:12])
                if not 0<=start<end<=recording.samples/recording.fs:
                    st.error('Recorte fora da medição ou com limites inválidos.');return
                segments=recording.segments.copy()
                segments.first_sample=np.maximum(segments.first_sample,round(start*recording.fs))
                segments.end_sample_exclusive=np.minimum(segments.end_sample_exclusive,round(end*recording.fs))
                segments=segments[segments.end_sample_exclusive>segments.first_sample]
                processing_recording=replace(recording,segments=segments)
            else: processing_recording=recording;start=0.;end=recording.samples/recording.fs
    analysis_key=hashlib.sha256(json.dumps([stamp,low,high,epoch,seconds,overlap,window,start,end]).encode()).hexdigest()
    try:
        if st.session_state.get('_analysis_key')!=analysis_key:
            with st.spinner('Calculando PSD por blocos, sem atravessar interrupções…'):
                analysis=analyze_recording(processing_recording,low,high,epoch,seconds,overlap,window)
            st.session_state['_analysis']=analysis;st.session_state['_analysis_key']=analysis_key
        analysis=st.session_state['_analysis']
        selected=select_intensity(analysis,percent,selection_mode=='Todos os blocos',selection_mode=='Complemento de menor intensidade')
    except (ValueError,TypeError,OverflowError) as exc: st.error(f'Não foi possível gerar a PSD: {exc}');return
    settings=selected['settings']
    st.caption(f"Banda de estudo: {low:g}–{high:g} Hz · classificação pelo Grms nessa banda · blocos de {epoch:g} s · Welch {seconds:g} s, {100*overlap:g}% de sobreposição. Confirme a banda útil do conjunto sensor/mesa.")
    tabs=st.tabs(['1 · Curva e breakpoints','2 · Comparar referências','3 · Aquisição e seleção','4 · Método e exportação'])
    seed=hashlib.sha256(json.dumps([analysis_key,selection_mode,percent,tolerance,max_points]).encode()).hexdigest()[:16]
    with tabs[0]:
        st.subheader('Tabela que define a curva de ensaio')
        st.caption('Edite frequência e PSD, ou a inclinação para o próximo ponto. A curva, o Grms, a comparação e os downloads seguem a tabela atual.')
        try: profile,fit=editor(selected,tolerance,int(max_points),seed)
        except (ValueError,TypeError,OverflowError) as exc: st.error(f'Perfil inválido: {exc}');return
        a,b,c,d=st.columns(4)
        a.metric('Grms da curva proposta',f'{fit["recipe_grms"]:.5f} g')
        b.metric('Grms dos blocos selecionados',f'{fit["input_grms"]:.5f} g')
        c.metric('Tempo representado no nível pleno',f'{settings["selected_duration_s"]:.3f} s')
        d.metric('Breakpoints',len(profile))
        render_psd_plot(psd_figure(selected,profile),key='main_psd_plot',config={'toImageButtonOptions':{'format':'png','filename':'curva_psd_breakpoints','scale':2}})
        st.write(f"**Seleção efetiva: {settings['selected_duration_percentage']:.2f}% do tempo coberto**, {settings['selected_blocks']} de {settings['total_blocks']} blocos. Duração mantida dos blocos selecionados; sem aumento automático de intensidade.")
        if not fit['passed']: st.warning(f"Limite de pontos ou edição atual não atende ao erro escolhido: {fit['max_error_db']:.2f} dB > {tolerance:g} dB. Ajuste a tabela ou a simplificação.")
        st.caption(f"Erro máximo na grade: {fit['max_error_db']:.3f} dB · diferença de área: {fit['area_difference_percent']:+.3f}%. São critérios numéricos do estudo, não tolerâncias de controle da mesa.")
        download_csv('Baixar tabela de breakpoints (CSV)',profile,'breakpoints_psd.csv',key='download_breakpoints')
    with tabs[1]:
        st.subheader('Curva proposta e perfis publicados')
        by_id={r['id']:r for r in catalog}
        ids=st.multiselect('Curvas de referência',list(by_id),default=list(by_id),
                           format_func=lambda k:by_id[k]['name'],key='reference_ids')
        chosen=[by_id[k] for k in ids]
        try: comparison,common=compare_profiles(selected,profile,chosen)
        except ValueError as exc: st.error(str(exc));comparison=pd.DataFrame();common=None
        render_psd_plot(psd_figure(selected,profile,chosen),key='reference_psd_plot',config={'toImageButtonOptions':{'format':'png','filename':'comparacao_psd_referencias','scale':2}})
        if common:
            st.info(f'Comparação numérica na mesma banda para todas as curvas: {common[0]:g}–{common[1]:g} Hz. Grms globais publicados aparecem nos detalhes das fontes.')
            if common!=[low,high]: st.caption('A faixa foi reduzida à interseção das referências escolhidas; não foram inventados valores fora da cobertura.')
            labels={'reference':'Referência','native_band_Hz':'Banda do perfil (Hz)','reference_grms_full_g':'Grms do perfil completo (g)',
                    'selected_grms_full_g':'Grms medido completo (g)','proposed_grms_full_g':'Grms proposto completo (g)'}
            st.dataframe(comparison[list(labels)].rename(columns=labels),hide_index=True,column_config={'Grms do perfil completo (g)':st.column_config.NumberColumn(format='%.5f')})
            st.caption('Valores completos na banda de cada perfil; bandas distintas não são equivalentes. As métricas abaixo usam somente a banda comum.')
            with st.expander('Comparação espectral na mesma banda'):
                st.dataframe(comparison[['reference','reference_grms_common_g','proposed_grms_common_g','proposed_to_reference_grms','shape_distance_db']],hide_index=True)
                st.caption('Distância de forma: RMS do erro em dB após retirar o nível médio, em 512 frequências logarítmicas. A razão de Grms também usa a banda comum, sem normalização das curvas.')
            download_csv('Baixar comparação dos perfis',comparison,'comparacao_referencias.csv',key='download_comparison')
        elif not chosen: st.info('Escolha referências para comparar os perfis na banda comum.')
        st.caption('Os perfis da Figura 5 de Rouillard são digitalizações históricas limitadas ao trecho visível, não tabelas normativas originais. Perfis históricos mantêm a edição identificada. Hungria e Rissi são perfis digitalizados, não tabelas numéricas originais. Rissi é uma aproximação digitalizada da Figura 21, com seleção por gatilho/max-overwrite; não é tabela numérica original nem média contínua da viagem.')
        st.caption('Este teste representa a PSD dos blocos selecionados do arquivo carregado; a curva proposta é sua aproximação por breakpoints.')
        catalog_details(chosen)
    with tabs[2]:
        a,b,c,d=st.columns(4)
        a.metric('Amostras verificadas/disponíveis',f'{recording.samples:,}')
        b.metric('Segmentos da aquisição',len(recording.segments))
        c.metric('Tempo coberto pelos blocos',f'{settings["covered_duration_s"]:.3f} s')
        d.metric('Caudas excluídas da análise',f'{settings["tail_excluded_s"]:.3f} s')
        if recording.metadata.get('format')=='MPUZ_RAW_LE_V2':
            st.write(f"Estado original: **{recording.metadata.get('status')}** · fechamento final confirmado: **{'sim' if recording.metadata.get('session_closed_verified') else 'não'}** · overflows registrados: **{recording.metadata.get('fifo_overflows',recording.metadata.get('fifo_overflows_so_far','—'))}**.")
            st.caption('O estado original foi preservado. Um V2 incompleto pode ser estudado somente até os checkpoints cujo CRC confira. As perdas exatas continuam desconhecidas.')
        if rails: st.warning('Há amostras no limite ou próximas da escala; revisar saturação antes de interpretar níveis e forma espectral.')
        blocks=selected['blocks']
        fig=go.Figure(go.Scattergl(x=blocks.nominal_position_s,y=blocks.grms_band_g,mode='markers',
                         marker=dict(color=np.where(blocks.selected,'#e68126','#93a4b5')),name='Grms por bloco',
                         customdata=blocks[['segment_id','duration_s','selected']],
                         hovertemplate='Posição nominal: %{x:.3f} s<br>Grms: %{y:.5f} g<br>Segmento %{customdata[0]}<br>Duração %{customdata[1]} s<br>Selecionado: %{customdata[2]}<extra></extra>'))
        fig.update_layout(height=330,xaxis_title='Posição nominal acumulada por amostras (s)',yaxis_title=f'Grms em {low:g}–{high:g} Hz (g)')
        st.plotly_chart(fig,width='stretch',key='intensity_plot')
        st.caption('Laranja: blocos selecionados. Eixo nominal acumulado não inclui a duração real das interrupções. O percentual pode exceder o solicitado por blocos inteiros e empates.')
        st.dataframe(blocks,hide_index=True,height=270)
        with st.expander('Segmentos, caudas e metadados originais'):
            st.dataframe(recording.segments,hide_index=True)
            st.dataframe(selected['excluded'],hide_index=True)
            st.json(recording.metadata)
        download_csv('Baixar seleção de blocos',blocks,'blocos_classificados.csv',key='download_blocks')
    with tabs[3]:
        st.subheader('Documentar e exportar a receita')
        route=st.text_area('Percurso, veículo, suspensão, carga e montagem do sensor',key='route_'+stamp[:12])
        justification=st.text_area('Justificativa da seleção, banda e duração',key='justification_'+stamp[:12])
        setup=st.text_area('Mesa, controlador, carga de ensaio e limites de operação',key='machine_'+stamp[:12])
        reviewed=st.checkbox('Conferi origem, orientação, escala e adequação da banda para este estudo',key='reviewed_'+stamp[:12])
        scenario=None
        with st.expander('Estudo opcional de redução de duração por modelo'):
            enabled=st.checkbox('Incluir cenário de aumento de intensidade',key='enable_compression')
            st.caption('Cenário adicional, dependente de expoente assumido e validação para o produto. A seleção por intensidade e a amplificação são decisões distintas; a curva principal permanece na intensidade medida.')
            if enabled:
                from vibration_scenarios import compression_factors
                factor=st.number_input('Fator de redução do tempo C',min_value=1.,max_value=5.,value=2.,step=.5,key='compression_factor')
                k=st.number_input('Expoente k assumido',min_value=.5,max_value=30.,value=2.,step=.5,key='compression_k')
                factors=compression_factors(factor,k)
                scenario=dict(factor=factor,k=k,**factors,proposed_duration_s=settings['selected_duration_s']/factor,
                              proposed_grms_g=fit['recipe_grms']*factors['acceleration_multiplier'],
                              damage_equivalence_claimed=False,experimental_validation_pending=True)
                st.info(f"MODELO NÃO VALIDADO: {scenario['proposed_duration_s']:.3f} s, {scenario['proposed_grms_g']:.5f} g. Não demonstra equivalência de dano.")
                st.latex(r'T_t=T_0/C,\quad G_t=G_0 C^{1/k},\quad S_t(f)=S_0(f)C^{2/k}')
        pending=[]
        if source!='Transporte em veículo':pending.append('Contexto não identificado como campanha de transporte.')
        if not reviewed or not all(x.strip() for x in [route,justification,setup]):pending.append('Documentação ou revisão do responsável incompleta.')
        if fullscale=='Não confirmada' and not demo:pending.append('Escala do CSV não confirmada.')
        if not fit['passed']:pending.append('Erro de simplificação/edição acima do critério escolhido.')
        if rails:pending.append('Há indícios de saturação na aquisição.')
        if recording.metadata.get('format')=='MPUZ_RAW_LE_V2' and not recording.metadata.get('session_closed_verified'):
            pending.append('V2 sem fechamento final: receita restrita aos prefixos verificados por CRC.')
        state='DEMONSTRACAO' if demo else ('ESTUDO_PRELIMINAR' if pending else 'PROPOSTA_PARA_REVISAO_TECNICA')
        st.info(f'Status da receita: {state}. A proposta documenta o perfil; a execução depende da verificação do conjunto mesa/carga/controlador.')
        if pending:
            for reason in pending:st.caption(reason)
        context=dict(file=filename,source=source,input_stamp=stamp,fullscale_g=fullscale,route=route,justification=justification,
                     machine_setup=setup,reviewed=reviewed,pending=pending,possible_saturation_count=rails,nominal_crop_s=[start,end],comparison_band_Hz=common)
        payload,report=export_workflow(selected,profile,fit,recording,context,comparison,chosen,state,scenario)
        st.download_button('Baixar receita PSD completa (ZIP)',payload,f'receita_psd_v5_{state.lower()}.zip','application/zip',key='recipe_zip')
        st.caption('ZIP: tabela de breakpoints, PSD selecionada e global, blocos, segmentos, caudas, comparação, fontes e memória de cálculo. O CSV com duas colunas é genérico; conferir o formato do controlador.')
        with st.expander('Método e premissas do TCC'):
            st.markdown('''O trabalho transforma medições de transporte em parâmetros de ensaio para apoiar o projeto e a avaliação de embalagens: proteção insuficiente favorece avarias; reforço excessivo aumenta custo e consumo de material.

**Seleção:** o perfil principal começa pelos 10% mais intensos do tempo coberto, ajustáveis pelo pesquisador. Grms por bloco na banda declarada; blocos inteiros, empates preservados. Essa é uma implementação própria de seleção em coleta contínua. Os 10% discutidos por Rissi são uma estimativa dos eventos retidos por gatilho e max-overwrite, e não o mesmo algoritmo.

**PSD:** Welch em cada bloco e segmento independente. A média linear é ponderada pela duração coberta. Nenhum pico é removido automaticamente; caudas sem janela completa e interrupções são documentadas. Remover a média constante por janela não corrige mudanças de orientação, deriva ou calibração.

**Breakpoints:** interpolação por leis de potência em eixos log-log; inclinação com 10·log₁₀ para PSD. O último slope fica vazio. A aproximação automática conserva área; uma edição manual mostra seu próprio Grms e erro, sem reescala silenciosa.

**Comparação:** todos os Grms da tabela usam a interseção das bandas das referências escolhidas. Forma e intensidade são medidas distintas. Mesmos Grms não garantem mesma resposta de produto/embalagem. A origem, edição e seleção de cada referência acompanham a exportação.

**Duração:** exposição nominal dos blocos selecionados, sem dupla contagem de sobreposição Welch. Um perfil de alta intensidade não recebe automaticamente toda a duração da viagem. Modelos de redução de tempo dependem de hipóteses e validação experimental.

**Escopo:** mesa aleatória controlada por PSD. Os resultados não atribuem equivalência a uma mesa senoidal, conformidade normativa ou redução comprovada de avarias. Um perfil da campanha não constitui norma regional.''')
            st.markdown(references_markdown())
        with st.expander('Parâmetros completos exportados'): st.json(report)


if __name__=='__main__':main()
