"""Teste funcional da interface Streamlit usando o AppTest oficial."""
from pathlib import Path
import unittest
from streamlit.testing.v1 import AppTest

ROOT=Path(__file__).resolve().parents[1]

class InterfaceTests(unittest.TestCase):
    def test_demo_and_invalid_band(self):
        at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run()
        self.assertFalse(at.exception)
        next(c for c in at.checkbox if c.label=='Usar demonstração sintética').check().run()
        self.assertFalse(at.exception)
        self.assertEqual(len(at.tabs),5)
        self.assertTrue(any('DEMONSTRACAO' in i.value for i in at.info))
        at.number_input(key='recipe_low').set_value(60.).run()
        self.assertFalse(at.exception)
        self.assertTrue(any('Banda inválida' in e.value for e in at.error))
        at.number_input(key='recipe_low').set_value(3.).run()
        at.selectbox(key='recipe_mode').set_value('linear').run()
        self.assertFalse(at.exception)
        at.number_input(key='recipe_points').set_value(2).run()
        self.assertTrue(any('Limite de pontos' in w.value for w in at.warning))

    def test_binary_upload_flow(self):
        # AppTest não injeta uploads diretamente. Substituímos apenas a origem
        # dos bytes; todo o parser, diagnóstico, cálculo e UI são executados.
        script='''
import sys, io, zlib
sys.path.insert(0,ROOT)
import numpy as np
import app
fs=500;n=5000
a=np.rint(8192*(1+.2*np.sin(2*np.pi*10*np.arange(n)/fs))).astype('<i2')
raw=a.tobytes()
report=f"status=INCOMPLETE\\nformat=MPUZ_RAW_LE_V1\\ntime_basis=sample_index_nominal\\nsamples={n}\\nsample_rate_nominal_hz=500\\nlsb_per_g=8192\\ncrc32={zlib.crc32(raw)}\\nerror_code=0\\nfifo_overflows=0\\ndlpf_cfg=2\\naccel_range_g=4\\nduration_arduino_ms=10000\\nsaturation_samples=0\\nstatus=OK\\n".encode()
class Upload(io.BytesIO):
 def __init__(self,data,name):super().__init__(data);self.name=name
app.st.file_uploader=lambda label,**kw: Upload(report,'TEST.TXT') if 'diagnóstico' in label else Upload(raw,'TEST.BIN')
app.main()
'''.replace('ROOT',repr(str(ROOT)))
        at=AppTest.from_string(script,default_timeout=30).run()
        self.assertFalse(at.exception)
        self.assertTrue(any('CRC32 conferidos' in e.value for e in at.success))
        self.assertTrue(any('ESTUDO_PRELIMINAR' in e.value for e in at.info))
        # Uma declaração de contexto não deve, sozinha, validar a proposta.
        next(s for s in at.selectbox if s.label=='Contexto da aquisição').set_value('Transporte em veículo').run()
        self.assertFalse(at.exception)
        self.assertTrue(any('ESTUDO_PRELIMINAR' in e.value for e in at.info))

if __name__=='__main__':unittest.main()
