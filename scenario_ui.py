"""Interface opcional de níveis e duração, subordinada à receita PSD medida."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from vibration_scenarios import analyze_epochs, build_plans, export_plans, NOTICE
from psd_recipe import interpolate


@st.cache_data(show_spinner=False, max_entries=2)
def cached_epochs(t, x, result, seconds, acquisition_key):
    # A chave de origem inclui SHA256 e seleção; não depende somente da
    # amostragem parcial usada pelo cache do Streamlit em arrays grandes.
    return analyze_epochs(t, x, result, seconds)


def render_scenarios(t, x, base_result, context, status, reasons):
    st.subheader('Níveis de intensidade e duração do ensaio')
    enabled=st.checkbox('Analisar perfis por intensidade e cenários de duração',key='enable_scenarios')
    if not enabled:
        st.caption('Ative para comparar o perfil médio, dois níveis, compressão por intensidade e seleção de períodos mais intensos.')
        return
    st.info(NOTICE)
    min_seconds=base_result['settings']['nperseg']/base_result['settings']['fs_hz']
    with st.expander('Ajustar blocos e classificação',expanded=False):
        seconds=st.number_input('Duração do bloco de intensidade (s)',min_value=float(min_seconds),
                                value=float(max(10., min_seconds)),step=1.,key='epoch_seconds')
        rule=st.selectbox('Regra de agrupamento',['Percentil temporal de Grms','Limiar manual de Grms'],key='epoch_rule')
        quantile=.8; threshold=None
        if rule=='Percentil temporal de Grms':
            quantile=st.number_input('Percentil de corte (%)',min_value=1.,max_value=99.,value=80.,step=5.,key='epoch_quantile')/100
        else:
            threshold=st.number_input('Limiar de Grms na banda (g)',min_value=0.,value=.1,step=.01,key='epoch_threshold')
        st.caption('P80 divide blocos pelo Grms integrado na mesma banda; empates ficam juntos. Não reproduz os espectros de probabilidade do SaverXware. Nenhum limiar publicado é aplicado automaticamente.')
    chosen=st.radio('Proposta de duração', ['Referência sem redução','Dois níveis sem redução',
                    'Compressão por aumento de intensidade','Seleção de alta intensidade'],key='scenario_choice')
    plan_id={'Referência sem redução':'referencia','Dois níveis sem redução':'niveis',
             'Compressão por aumento de intensidade':'compressao','Seleção de alta intensidade':'selecao'}[chosen]
    factor=1.; k=2.
    if plan_id=='compressao':
        a,b=st.columns(2)
        factor=a.number_input('Fator de compressão T₀/Tₜ',min_value=1.,max_value=5.,value=2.,step=.5,key='compression_factor')
        k=b.number_input('Expoente k assumido',min_value=1.,max_value=12.,value=2.,step=.5,key='compression_k')
        st.caption('k=2 é hipótese inicial. A faixa de 1–5 para compressão segue recomendação histórica; não assegura equivalência ou atendimento da capacidade da mesa.')
    reason=st.text_area('Justificativa do cenário e uso pretendido',key='scenario_reason',
                        placeholder='Documente o objetivo e por que esta duração/intensidade deve ser avaliada.')
    try:
        key=(context.get('sha256_input',''),context.get('start_s'),context.get('end_s'))
        analysis=cached_epochs(t,x,base_result,seconds,key)
        fit=base_result['simplification']
        result=build_plans(analysis,factor,k,quantile,threshold,fit['mode'],fit['tolerance_db'],fit['max_points'])
    except (ValueError,TypeError,OverflowError) as exc:
        st.error(f'Não foi possível analisar os cenários: {exc}');return
    selected=next(p for p in result['plans'] if p['id']==plan_id)
    st.caption(f"Classificação na banda {analysis['settings']['band_hz'][0]:g}–{analysis['settings']['band_hz'][1]:g} Hz. "
               f"Limiar: {result['settings']['threshold_grms_g']:.6g} g; alta intensidade: {100*result['settings']['high_duration_fraction']:.2f}% do tempo coberto.")
    blocks=result['blocks']; colors={'Baixa intensidade':'#247ba0','Alta intensidade':'#d95f02'}
    fig=go.Figure()
    for group in blocks.grupo.unique():
        rows=blocks[blocks.grupo==group]
        fig.add_trace(go.Scattergl(x=(rows.inicio_s+rows.fim_s)/2,y=rows.grms_banda_g,
                                  name=group,mode='markers',marker={'color':colors[group]},
                                  customdata=rows[['duracao_s','pico_dinamico_g','fator_crista']],
                                  hovertemplate='t=%{x:.3f} s<br>Grms=%{y:.6f} g<br>Duração=%{customdata[0]:.3f} s<br>Pico dinâmico=%{customdata[1]:.5f} g<br>Fator de crista=%{customdata[2]:.3f}<extra>%{fullData.name}</extra>'))
    fig.add_hline(y=result['settings']['threshold_grms_g'],line_dash='dash')
    fig.update_layout(title='Grms por bloco na banda do ensaio',xaxis_title='Tempo na seleção (s)',yaxis_title='Grms (g)',height=350)
    st.plotly_chart(fig,width='stretch')
    a,b,c=st.columns(3)
    a.metric('Exposição coberta nos blocos',f"{analysis['settings']['epoch_duration_s_covered']:.3f} s")
    b.metric('Duração proposta',f"{selected['duration_s']:.3f} s")
    c.metric('Tempo retirado por intensidade',f"{selected['excluded_low_intensity_s']:.3f} s")
    if analysis['settings']['epoch_tail_excluded_s']>1e-8:
        st.warning(f"A divisão em blocos excluiu mais {analysis['settings']['epoch_tail_excluded_s']:.6g} s de caudas sem janela completa. Todos os cenários abaixo usam essa mesma cobertura.")
    summary=[]
    for plan in result['plans']:
        summary.append({'Cenário':plan['label'],'Tempo pleno (s)':plan['duration_s'],
                        'Perfis':len(plan['profiles']),'Tempo retirado (s)':plan['excluded_low_intensity_s'],
                        'Grms dos perfis (g)':', '.join(f"{p['proposed_grms_g']:.6g}" for p in plan['profiles']),
                        'Validação experimental':'Pendente'})
    st.dataframe(pd.DataFrame(summary),hide_index=True)
    if not selected['profiles']:
        st.warning('Nenhum bloco acima do limiar: não há perfil de alta intensidade para esta seleção. Ajuste o critério ou escolha outra proposta.');return
    plot=go.Figure(go.Scatter(x=analysis['frequency'],y=analysis['psd'],name='PSD média dos blocos',mode='lines',line={'dash':'dash'}))
    for p in selected['profiles']:
        profile=p['profile']; grid=np.geomspace(profile.frequency_Hz.iloc[0],profile.frequency_Hz.iloc[-1],1000)
        plot.add_trace(go.Scatter(x=grid,y=interpolate(profile.frequency_Hz,profile.psd_g2_per_Hz,grid,p['simplification']['mode']),
                                 name=p['label'],mode='lines'))
    plot.update_layout(xaxis={'type':'log','title':'Frequência (Hz)'},yaxis={'type':'log','title':'PSD (g²/Hz)'},height=390)
    st.plotly_chart(plot,width='stretch')
    for item in selected['assumptions']:st.caption(item)
    with st.expander('Memória de cálculo, sensibilidade e blocos'):
        st.latex(r'C=T_0/T_t,\quad G_t=G_0C^{1/k},\quad S_t(f)=S_0(f)C^{2/k}')
        st.write('Sensibilidade à hipótese de k para o fator escolhido:')
        st.dataframe(result['sensitivity'],hide_index=True)
        st.write('Fração mantida de um índice hipotético de exposição ∑T·Grmsᵏ — não é fração de dano:')
        st.dataframe(result['retained_index'],hide_index=True)
        st.dataframe(blocks,hide_index=True)
        st.dataframe(analysis['excluded'],hide_index=True)
        st.caption('Pico, fator de crista e curtose são diagnósticos do sinal com média local removida na banda registrada inteira. Não eliminam choques automaticamente nem caracterizam ensaios de impacto.')
        st.caption('Partida e transições são adicionais. A PSD média de blocos pode diferir da PSD Welch do trecho inteiro por limites, cobertura e janelas que atravessariam as fronteiras.')
    pending=list(reasons)
    if not reason.strip():pending.append('Justificativa do cenário de duração não registrada.')
    if any(not p['simplification']['passed'] for p in selected['profiles']):
        pending.append('Um perfil não atende ao erro de representação escolhido; ampliar pontos ou rever critério.')
    if (blocks.janelas_welch<2).any():pending.append('Há blocos com apenas um periodograma; revisar variabilidade da estimativa.')
    state='DEMONSTRACAO' if status=='DEMONSTRACAO' else ('ESTUDO_PRELIMINAR' if pending else 'PROPOSTA_PARA_REVISAO_TECNICA')
    export_context=dict(context,scenario_justification=reason)
    payload,meta=export_plans(result,export_context,state,pending,plan_id)
    st.download_button('Baixar cenários, perfis e guia (ZIP)',payload,f'cenarios_v4_{plan_id}_{state.lower()}.zip',
                       'application/zip',key='scenarios_zip')
    st.caption(f'Status documental: {state}. ZIP inclui alternativas independentes, perfis, durações, blocos, exclusões, fórmulas, ressalvas e referências. Nenhum cenário está validado experimentalmente pelo aplicativo.')
