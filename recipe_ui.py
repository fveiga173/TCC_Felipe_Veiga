"""Interface da receita PSD. Cálculos puros e testáveis em psd_recipe.py."""
import hashlib
import json
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from psd_recipe import build_recipe, export_bundle
from scenario_ui import render_scenarios


def render_recipe(t, x, fs, metadata, uncertain, demo):
    st.subheader('Receita para mesa com controle PSD')
    st.write('A receita usa a PSD medida para definir o perfil da mesa e conserva a exposição coberta pelos trechos selecionados.')
    if uncertain:
        st.error('Receita bloqueada: os tempos falharam na triagem. A opção de PSD exploratória não libera esta etapa.')
        return
    # Chave muda junto com a seleção: o editor não conserva limites de outro arquivo.
    origin=float(t[0]); rel=t-origin; exposure=float(rel[-1]+1/fs)
    stamp=hashlib.sha256((metadata['file']+str(origin)+str(len(x))+metadata.get('sha256_input','')).encode()).hexdigest()[:12]
    table=pd.DataFrame([{'nome':'Trecho 1','inicio_s':0.,'fim_s':exposure}])
    low=3.
    high=50.
    mode='log-log'
    tolerance=1.
    max_points=80
    # A configuração completa permanece disponível, mas começa recolhida para
    # manter o fluxo principal centrado nos resultados que o TCC precisa.
    with st.expander('Ajustar trechos e perfil do controlador',expanded=False):
        st.caption('Os trechos são relativos ao início da seleção acima. Sobreposições entre trechos não são permitidas.')
        table=st.data_editor(pd.DataFrame([{'nome':'Trecho 1','inicio_s':0.,'fim_s':exposure}]),
                             num_rows='dynamic',hide_index=True,key='intervals_'+stamp,
                             column_config={'inicio_s':st.column_config.NumberColumn('Início (s)',format='%.6f'),
                                            'fim_s':st.column_config.NumberColumn('Fim exclusivo (s)',format='%.6f')})
        a,b=st.columns(2)
        low=a.number_input('Frequência mínima (Hz)',min_value=.01,value=3.,key='recipe_low')
        high=b.number_input('Frequência máxima (Hz)',min_value=.02,value=50.,key='recipe_high')
        a,b,c=st.columns(3)
        mode=a.selectbox('Interpolação usada pela mesa',['log-log','linear'],key='recipe_mode')
        tolerance=b.number_input('Erro da simplificação (dB)',min_value=.05,max_value=10.,value=1.,step=.25,key='recipe_tolerance')
        max_points=c.number_input('Máximo de pontos do controlador',min_value=2,max_value=500,value=80,step=10,key='recipe_points')
        st.caption('Faixa inicial de estudo: 3–50 Hz. Confirme faixa útil e formato aceito no controlador; o limite de Nyquist não comprova resposta do sensor.')
    with st.expander('Registrar percurso, mesa e justificativas',expanded=False):
        route=st.text_input('Percurso, veículo, carga e posição do sensor',key='recipe_route_'+stamp)
        selection_reason=st.text_area('Justificativa dos trechos e das exclusões',key='recipe_selection_'+stamp)
        band_reason=st.text_area('Justificativa da banda e da base temporal',help='Documente resposta do sensor, filtros, taxa adotada e limitações.',key='recipe_band_reason_'+stamp)
        setup=st.text_area('Mesa, carga de ensaio e verificação de capacidade',help='Registre modelo/controlador, interpolação, força, curso, velocidade e aceleração admissíveis para a carga. Valores não são inferidos pelo aplicativo.',key='recipe_setup_'+stamp)
        reviewed=st.checkbox('Conferi a aquisição, a orientação do eixo e a adequação da banda para este estudo',key='recipe_reviewed_'+stamp)
    # Resultado é recalculado a partir dos parâmetros atuais; evita download
    # de uma receita antiga após alteração silenciosa dos controles.
    try:
        result=build_recipe(rel,x,fs,table.to_dict('records'),float(low),float(high),
                            metadata['requested_welch_seconds'],metadata['requested_overlap'],
                            mode,float(tolerance),int(max_points),metadata.get('requested_window','hann'))
    except (ValueError,TypeError,KeyError,OverflowError) as exc:
        st.error(f'Não foi possível gerar o perfil: {exc}');return
    fit=result['simplification']; settings=result['settings']
    reasons=[]
    if demo: reasons.append('Sinal sintético para demonstração; não representa um percurso.')
    if metadata['context']!='Transporte em veículo': reasons.append('Origem não identificada como transporte em veículo.')
    if metadata['possible_saturation_count']: reasons.append('Há indícios de saturação no arquivo original.')
    if metadata['fullscale_g']=='Não confirmada': reasons.append('Escala do sensor não confirmada.')
    if not reviewed: reasons.append('Aquisição, orientação e banda ainda não conferidas pelo responsável.')
    if not all(v.strip() for v in [route,selection_reason,band_reason,setup]): reasons.append('Documentação do percurso, seleção, banda ou mesa incompleta.')
    if metadata.get('time_basis')=='Não identificada': reasons.append('Base temporal não identificada.')
    if metadata.get('time_basis')=='Índice nominal / FIFO' and not metadata.get('firmware',{}).get('integrity_verified'):
        reasons.append('Tempo reconstruído por índice: use BIN + TXT para verificar integridade e diagnóstico.')
    if not fit['passed']: reasons.append('Limite de pontos insuficiente para atender ao erro espectral escolhido.')
    if (result['intervals'].janelas_welch<2).any(): reasons.append('Um trecho possui apenas um periodograma; a média espectral exige revisão.')
    state='DEMONSTRACAO' if demo else ('ESTUDO_PRELIMINAR' if reasons else 'PROPOSTA_PARA_REVISAO_TECNICA')
    st.info(f'Status: {state}. A proposta ainda precisa ser revisada com os dados do percurso e os limites da mesa.')
    for reason in reasons:st.warning(reason)
    a,b,c,d=st.columns(4)
    a.metric('Grms de origem',f'{fit["input_grms"]:.5f} g')
    b.metric('Grms da receita',f'{fit["recipe_grms"]:.5f} g')
    c.metric('Tempo no nível pleno',f'{settings["duration_s"]:.3f} s')
    d.metric('Pontos do perfil',fit['points'])
    st.caption('Duração baseada na exposição coberta. Partida não incluída; não foi aplicado aumento de intensidade nem compressão temporal.')
    # Densificação serve apenas ao desenho do interpolante configurado.
    from psd_recipe import interpolate
    profile=result['profile'];grid=np.geomspace(low,high,2000)
    fig=go.Figure(go.Scatter(x=result['frequency'],y=result['psd'],name='PSD representativa',mode='lines'))
    fig.add_trace(go.Scatter(x=grid,y=interpolate(profile.frequency_Hz,profile.psd_g2_per_Hz,grid,mode),name='Perfil proposto',mode='lines'))
    fig.add_trace(go.Scatter(x=profile.frequency_Hz,y=profile.psd_g2_per_Hz,name='Pontos para configuração',mode='markers'))
    fig.update_layout(xaxis={'type':'log','title':'Frequência (Hz)'},yaxis={'type':'log','title':'PSD (g²/Hz)'},height=440)
    st.plotly_chart(fig,width='stretch')
    with st.expander('Tabela para configuração e detalhes do cálculo',expanded=False):
        st.dataframe(profile,hide_index=True)
        st.write(f'Erro máximo da simplificação: {fit["max_error_db"]:.3f} dB · fator de ajuste para preservar a área: {fit["scale_factor"]:.6f}. Esses valores descrevem a aproximação numérica do perfil, não a tolerância de controle da mesa.')
        st.latex(r'S_{rep}(f)=\frac{\sum_j T_j S_j(f)}{\sum_j T_j},\quad G_{rms}=\sqrt{\int_{f_{min}}^{f_{max}} S_{rep}(f)\,df}')
        st.write(f'Welch: {settings["nperseg"]} pontos, {settings["noverlap"]} de sobreposição; espaçamento {settings["bin_spacing_hz"]:.4f} Hz. Duração = soma das amostras cobertas/fs. As janelas sobrepostas não duplicam a exposição.')
        st.dataframe(result['intervals'],hide_index=True)
        st.dataframe(result['bands'],hide_index=True)
        st.caption('Caudas excluídas e lacunas entre trechos não entram no tempo da receita. Perfil médio não mantém sequência, distribuição temporal de níveis ou impactos individuais. A diferença de Grms entre trechos ajuda a avaliar a necessidade futura de receitas em blocos.')
    context=dict(metadata,route=route,selection_reason=selection_reason,band_reason=band_reason,
                 machine_setup=setup,reviewed_by_user=reviewed,selected_time_origin_s=origin,
                 interpolation=mode,coverage_policy='somente amostras cobertas por Welch')
    payload,report=export_bundle(result,context,state,reasons)
    st.download_button('Baixar receita e memória de cálculo (ZIP)',payload,
                       f'receita_psd_{state.lower()}.zip','application/zip',key='recipe_zip')
    st.caption('ZIP: perfil genérico CSV, PSD de origem, trechos, comparação por bandas, parâmetros JSON, memória de cálculo e referências. Conferir o formato de importação do controlador.')
    with st.expander('Parâmetros completos da receita'):
        st.json(report)
    render_scenarios(rel,x,result,context,state,reasons)

