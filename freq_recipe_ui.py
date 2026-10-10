"""Interface para transformar o percurso em uma receita senoidal simplificada."""
import hashlib
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from fixed_frequency import build_fixed_frequency, export_fixed_bundle


def render_fixed_recipe(t, x, fs, metadata, uncertain, demo):
    st.subheader('Receita para mesa de frequência fixa')
    st.write('A receita reduz a vibração medida a uma senoide. Frequência e aceleração são selecionadas com base na PSD do percurso; o tempo corresponde à exposição coberta.')
    if uncertain:
        st.error('Receita bloqueada: os tempos falharam na triagem. Uma PSD exploratória não libera esta etapa.')
        return

    origin=float(t[0]);rel=t-origin;exposure=float(rel[-1]+1/fs)
    stamp=hashlib.sha256((metadata['file']+str(origin)+str(len(x))+metadata.get('sha256_input','')).encode()).hexdigest()[:12]
    st.caption('Trechos relativos ao início da seleção acima. Intervalos [início, fim), sem sobreposição. A cobertura é considerada depois das janelas Welch completas.')
    intervals=st.data_editor(pd.DataFrame([{'nome':'Trecho 1','inicio_s':0.,'fim_s':exposure}]),
        num_rows='dynamic',hide_index=True,key='fixed_intervals_'+stamp,
        column_config={'inicio_s':st.column_config.NumberColumn('Início (s)',format='%.6f'),
                       'fim_s':st.column_config.NumberColumn('Fim exclusivo (s)',format='%.6f')})

    fs_nyquist=fs/2
    low_default=min(3.,fs_nyquist/3)
    high_default=min(50.,fs_nyquist*.95)
    if high_default<=low_default:
        st.error('A taxa de amostragem não permite selecionar a banda inicial de análise.');return
    a,b=st.columns(2)
    low=a.number_input('Banda para seleção (Hz): mínimo',min_value=.01,max_value=float(fs_nyquist),value=float(low_default),key='fixed_low_'+stamp)
    high=b.number_input('Banda para seleção (Hz): máximo',min_value=.02,max_value=float(fs_nyquist),value=float(high_default),key='fixed_high_'+stamp)
    if high<=low:
        st.error('O limite máximo da banda deve ser maior que o mínimo.')
        return
    st.caption('A banda comum inicial 3–50 Hz é uma escolha de estudo. A banda útil depende da resposta do sensor, filtro, montagem e limites da mesa.')
    a,b=st.columns(2)
    freq_mode=a.selectbox('Critério de frequência',['Banda de 1/3 de oitava mais energética','Frequência definida pelo usuário'],key='fixed_freq_mode_'+stamp)
    intensity_mode=b.selectbox('Critério de intensidade',['RMS da banda local','Grms de toda a faixa'],key='fixed_intensity_mode_'+stamp)
    manual_frequency=None
    if freq_mode=='Frequência definida pelo usuário':
        manual_frequency=st.number_input('Frequência fixa escolhida (Hz)',min_value=float(low),max_value=float(high),value=float((low+high)/2),key='fixed_frequency_'+stamp)
    if intensity_mode=='Grms de toda a faixa':
        st.warning('Esta opção concentra a energia de toda a faixa em uma única senoide. Pode elevar muito a aceleração naquela frequência; a capacidade da mesa e a resposta do conjunto precisam ser verificadas.')
    else:
        st.caption('Padrão recomendado para a primeira proposta: igualar o RMS medido na banda local ao redor da frequência selecionada. Energia fora dessa banda fica excluída.')

    with st.expander('Rastreabilidade, limites e justificativa',expanded=True):
        route=st.text_input('Percurso, veículo, carga e posição do sensor',key='fixed_route_'+stamp)
        reason=st.text_area('Por que este critério de frequência e intensidade representa o objetivo do ensaio?',key='fixed_reason_'+stamp)
        limits=st.text_area('Modelo da mesa e limites confirmados: aceleração, curso, velocidade e carga',key='fixed_limits_'+stamp)
        reviewed=st.checkbox('Conferi aquisição, eixo, banda analisada e compatibilidade mecânica preliminar',key='fixed_reviewed_'+stamp)

    try:
        result=build_fixed_frequency(rel,x,fs,intervals.to_dict('records'),float(low),float(high),freq_mode,
            manual_frequency,intensity_mode,metadata['requested_welch_seconds'],metadata['requested_overlap'])
    except (ValueError,TypeError,KeyError,OverflowError) as exc:
        st.error(f'Não foi possível calcular a receita: {exc}');return

    settings=result['settings'];reasons=[]
    if demo:reasons.append('Demonstração sintética; não representa um percurso.')
    if metadata['context']!='Transporte em veículo':reasons.append('Aquisição ainda não identificada como percurso em veículo.')
    if metadata['possible_saturation_count']:reasons.append('Há indícios de saturação no arquivo original.')
    if metadata['fullscale_g']=='Não confirmada':reasons.append('Escala do sensor não confirmada.')
    if not reviewed:reasons.append('Aquisição, banda ou compatibilidade mecânica ainda não revisadas pelo responsável.')
    if not all(v.strip() for v in [route,reason,limits]):reasons.append('Contexto, justificativa ou limites da mesa incompletos.')
    if metadata.get('time_basis')=='Não identificada':reasons.append('Base temporal não identificada.')
    if metadata.get('time_basis')=='Índice nominal / FIFO' and not metadata.get('firmware',{}).get('integrity_verified'):
        reasons.append('Tempo nominal reconstruído sem verificação de integridade BIN + TXT.')
    state='DEMONSTRACAO' if demo else ('ESTUDO_PRELIMINAR' if reasons else 'PROPOSTA_PARA_REVISAO_TECNICA')
    st.info(f'Status: {state}. A receita não autoriza automaticamente a execução na mesa.')
    for item in reasons:st.warning(item)

    a,b,c,d,e=st.columns(5)
    a.metric('Frequência fixa',f'{result["frequency_hz"]:.4g} Hz')
    b.metric('Aceleração RMS',f'{result["acceleration_rms_g"]:.5g} g')
    c.metric('Aceleração de pico',f'{result["acceleration_peak_g"]:.5g} g')
    d.metric('Deslocamento p-p',f'{result["displacement_pp_mm"]:.5g} mm')
    e.metric('Tempo no nível pleno',f'{settings["duration_s"]:.3f} s')
    st.caption(f'Critério de frequência: {settings["frequency_selection"]}. Critério de intensidade: {settings["intensity_selection"]}. A partida não entra no tempo pleno; nenhum multiplicador de intensidade ou compressão temporal foi aplicado.')

    fig=go.Figure(go.Bar(x=result['bands'].center_hz,y=result['bands'].area_g2,name='Energia integrada (g²)'))
    fig.add_vline(x=result['frequency_hz'],line_dash='dash',annotation_text='Frequência proposta')
    fig.update_layout(title='Energia da PSD por banda de 1/3 de oitava',xaxis={'type':'log','title':'Frequência central (Hz)'},yaxis_title='Integral da PSD (g²)',height=390)
    st.plotly_chart(fig,width='stretch')
    st.dataframe(result['bands'],hide_index=True)
    st.latex(r'a_{pico}=\sqrt{2}a_{RMS},\qquad x_{p-p}=\frac{2a_{pico}g}{(2\pi f)^2}')
    st.write(f'RMS medido na banda local: **{settings["measured_local_rms_g"]:.6g} g** · Grms da faixa inteira: **{settings["measured_total_grms_g"]:.6g} g**.')
    if settings['acceleration_peak_within_iso2247_2000_method_a_range']:
        st.info('O pico calculado está entre 0,5 g e 1,0 g, faixa citada para o método A da ISO 2247:2000. Isso, isoladamente, não demonstra conformidade; geometria de deslocamento, corpo de prova, montagem e procedimento precisam ser conferidos.')
    else:
        st.caption('O pico não está na faixa de 0,5–1,0 g citada para o método A da ISO 2247:2000. Essa comparação é contextual e não é requisito para esta proposta derivada do percurso.')
    st.warning('Uma senoide única não preserva o espectro de banda larga, a sequência dos eventos ou a distribuição dos níveis. Mesmo com RMS igual, não há equivalência demonstrada de resposta, fadiga ou dano. Esta proposta não declara conformidade com a ISO 2247.')

    context=dict(metadata,route=route,selection_reason=reason,machine_limits=limits,reviewed_by_user=reviewed,
                 selected_time_origin_s=origin,coverage_policy='soma de amostras cobertas por Welch')
    payload,report=export_fixed_bundle(result,context,state,reasons)
    st.download_button('Baixar receita senoidal e memória de cálculo (ZIP)',payload,
        f'receita_frequencia_fixa_{state.lower()}.zip','application/zip',key='fixed_recipe_zip')
    st.caption('ZIP com parâmetros propostos, PSD usada, energia por banda, trechos cobertos, JSON e memória de cálculo.')
    with st.expander('Parâmetros completos da receita'):
        st.json(report)
