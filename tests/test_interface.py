"""Fluxos completos da interface, incluindo uploads V2 e atualização do perfil."""
from pathlib import Path
import unittest
import numpy as np
from streamlit.testing.v1 import AppTest

ROOT=Path(__file__).resolve().parents[1]


class InterfaceTests(unittest.TestCase):
    def demo(self):
        at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run()
        self.assertFalse(at.exception)
        next(c for c in at.checkbox if c.label=='Usar demonstração sintética').check().run()
        self.assertFalse(at.exception)
        return at

    def test_primary_delivery_default_band_and_invalid_band(self):
        at=self.demo()
        self.assertEqual(at.number_input(key='recipe_low').value,1.)
        self.assertEqual(at.selectbox(key='selection_mode').value,'Alta intensidade')
        self.assertEqual(at.number_input(key='high_percentage').value,10.)
        self.assertEqual(at.tabs[0].label,'1 · Curva e breakpoints')
        self.assertTrue(any('DEMONSTRACAO' in item.value for item in at.info))
        self.assertEqual(at.session_state['_analysis']['settings']['covered_duration_s'],1000.)
        at.number_input(key='recipe_low').set_value(60.).run()
        self.assertFalse(at.exception)
        self.assertTrue(any('Banda inválida' in e.value for e in at.error))
        at.number_input(key='recipe_low').set_value(1.).run()
        at.number_input(key='recipe_points').set_value(2).run()
        self.assertTrue(any('Limite de pontos' in w.value for w in at.warning))

    def test_catalog_common_band_and_edit_modes(self):
        at=self.demo()
        at.multiselect(key='reference_ids').set_value(['iso13355_reproduced_2006','rissi2008_vertical_digitized']).run()
        self.assertFalse(at.exception)
        self.assertTrue(any('3–50 Hz' in item.value for item in at.info))
        at.multiselect(key='reference_ids').set_value(['hungary_borocz_singh_2018_digitized']).run()
        self.assertFalse(at.exception)
        self.assertTrue(any('Este teste' in str(frame.value) and 'Hungria' in str(frame.value) for frame in at.dataframe))
        before=at.session_state['_working_profile'].copy()
        at.radio(key='profile_edit_mode').set_value('Inclinação (dB/oct)').run()
        self.assertFalse(at.exception)
        np.testing.assert_allclose(at.session_state['_working_profile'].psd_g2_per_Hz,before.psd_g2_per_Hz)
        initial=next(i for i in at.number_input if i.label=='PSD do primeiro breakpoint (g²/Hz)')
        initial.set_value(float(before.psd_g2_per_Hz.iloc[0]*2)).run()
        self.assertFalse(at.exception)
        np.testing.assert_allclose(at.session_state['_working_profile'].psd_g2_per_Hz,2*before.psd_g2_per_Hz)
        at.button(key='restore_breakpoints').click().run()
        np.testing.assert_allclose(at.session_state['_working_profile'].psd_g2_per_Hz,before.psd_g2_per_Hz)

    def test_selection_and_optional_compression_do_not_change_main_intensity(self):
        at=self.demo();selected=at.session_state['_working_profile'].copy()
        at.checkbox(key='enable_compression').check().run()
        self.assertFalse(at.exception)
        at.number_input(key='compression_factor').set_value(5.).run()
        self.assertFalse(at.exception)
        np.testing.assert_allclose(at.session_state['_working_profile'].psd_g2_per_Hz,selected.psd_g2_per_Hz)
        self.assertTrue(any('MODELO NÃO VALIDADO' in item.value for item in at.info))
        at.selectbox(key='selection_mode').set_value('Todos os blocos').run()
        self.assertFalse(at.exception)
        self.assertFalse(at.session_state['_working_profile'].equals(selected))

    def test_psd_cell_edit_updates_calculated_slope_and_blocks_stale_invalid_profile(self):
        at=self.demo();before=at.session_state['_working_profile'].copy()
        key=f"breakpoints_{at.session_state['_profile_seed']}_{at.session_state['_editor_generation']}"
        at.session_state[key]={'edited_rows':{0:{'psd_g2_per_Hz':float(before.psd_g2_per_Hz.iloc[0]*2)}},'added_rows':[],'deleted_rows':[]}
        at.run();self.assertFalse(at.exception)
        after=at.session_state['_working_profile']
        self.assertAlmostEqual(after.psd_g2_per_Hz.iloc[0],2*before.psd_g2_per_Hz.iloc[0])
        self.assertNotEqual(after.slope_to_next_db_oct.iloc[0],before.slope_to_next_db_oct.iloc[0])
        key=f"breakpoints_{at.session_state['_profile_seed']}_{at.session_state['_editor_generation']}"
        at.session_state[key]={'edited_rows':{0:{'frequency_Hz':60.}},'added_rows':[],'deleted_rows':[]}
        at.run();self.assertFalse(at.exception)
        self.assertTrue(any('Perfil inválido' in e.value for e in at.error))
        self.assertFalse(any(getattr(x,'label','')=='Baixar receita PSD completa (ZIP)' for x in at.get('download_button')))

    def test_v2_incomplete_verified_prefix_is_accepted(self):
        script='''
import sys, io, zlib
sys.path.insert(0, ROOT)
import numpy as np
import app
fs=1000;n=40000
x=8192*(1+.1*np.sin(2*np.pi*8*np.arange(n)/fs))
raw=x.astype('<i2').tobytes()
report=(f"format=MPUZ_RAW_LE_V2\\ntime_basis=sample_index_nominal_per_segment\\nsample_rate_nominal_hz=1000\\nlsb_per_g=8192\\naccel_range_g=4\\nwho_am_i=112\\nsample_rate_divider=0\\ngyro_dlpf_cfg=1\\naccel_dlpf_cfg=0\\ngyro_fchoice_b=0\\nstatus=INCOMPLETE\\nfifo_overflows_so_far=1\\nsegment=1,0,20000,500,20400,12,{zlib.crc32(raw[:40000])}\\nsegment=2,20000,40000,20500,40400,0,{zlib.crc32(raw)}\\n").encode()
class Upload(io.BytesIO):
 def __init__(self,data,name):super().__init__(data);self.name=name
app.st.file_uploader=lambda label,**kw: (Upload(report,'TEST.TXT') if 'diagnóstico' in label else (Upload(raw,'TEST.BIN') if 'sensor' in label else None))
app.main()
'''.replace('ROOT',repr(str(ROOT)))
        at=AppTest.from_string(script,default_timeout=30).run()
        self.assertFalse(at.exception)
        self.assertTrue(any('CRC32 conferidos' in item.value for item in at.success))
        self.assertEqual(len(at.session_state['_analysis']['blocks']),4)
        self.assertTrue(any('INCOMPLETE' in item.value for item in at.markdown))
        self.assertTrue(any('ESTUDO_PRELIMINAR' in item.value for item in at.info))


if __name__=='__main__':unittest.main()
