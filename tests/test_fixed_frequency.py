"""Verificações dos cálculos e das limitações da receita senoidal."""
import io
import json
import math
import unittest
import zipfile
import numpy as np
from fixed_frequency import build_fixed_frequency, export_fixed_bundle


class FixedFrequencyTests(unittest.TestCase):
    def setUp(self):
        self.fs=500.
        self.t=np.arange(30000)/self.fs
        # Componentes conhecidas e nível vertical constante, removido no PSD.
        self.x=1.+.20*np.sin(2*np.pi*10*self.t)+.10*np.sin(2*np.pi*40*self.t)
        self.intervals=[dict(nome='Trecho contínuo',inicio_s=0.,fim_s=60.)]

    def test_auto_frequency_and_local_rms(self):
        r=build_fixed_frequency(self.t,self.x,self.fs,self.intervals,3,50,
            'Banda de 1/3 de oitava mais energética',intensity_mode='RMS da banda local',welch_seconds=2.)
        self.assertAlmostEqual(r['frequency_hz'],10.,places=8)
        self.assertAlmostEqual(r['acceleration_rms_g'],.20/math.sqrt(2),places=4)
        self.assertAlmostEqual(r['acceleration_peak_g'],.20,places=4)
        expected_mm=2*.20*9.80665/(2*math.pi*r['frequency_hz'])**2*1000
        self.assertAlmostEqual(r['displacement_pp_mm'],expected_mm,places=7)
        self.assertAlmostEqual(r['settings']['duration_s'],60.)
        self.assertFalse(r['settings']['iso2247_compliance_claimed'])

    def test_total_band_option_concentrates_energy(self):
        r=build_fixed_frequency(self.t,self.x,self.fs,self.intervals,3,50,
            'Frequência definida pelo usuário',20.,'Grms de toda a faixa',2.)
        self.assertAlmostEqual(r['frequency_hz'],20.)
        self.assertGreater(r['acceleration_rms_g'],.15)
        self.assertTrue(r['settings']['broad_spectrum_replaced_by_single_tone'])

    def test_invalid_frequency_and_zero_energy(self):
        with self.assertRaises(ValueError):
            build_fixed_frequency(self.t,self.x,self.fs,self.intervals,3,50,
                'Frequência definida pelo usuário',60.,'RMS da banda local',2.)
        with self.assertRaises(ValueError):
            build_fixed_frequency(self.t,np.ones_like(self.t),self.fs,self.intervals,3,50,
                'Banda de 1/3 de oitava mais energética',intensity_mode='RMS da banda local',welch_seconds=2.)

    def test_export_documents_approximation_and_norm(self):
        r=build_fixed_frequency(self.t,self.x,self.fs,self.intervals,3,50,
            'Banda de 1/3 de oitava mais energética',intensity_mode='RMS da banda local',welch_seconds=2.)
        payload,meta=export_fixed_bundle(r,{'percurso':'teste sintético'},'DEMONSTRACAO',['Dados sintéticos'])
        self.assertFalse(meta['iso2247_compliance_claimed'])
        with zipfile.ZipFile(io.BytesIO(payload)) as z:
            self.assertEqual(len(z.namelist()),6)
            recipe=json.loads(z.read('receita.json'))
            memo=z.read('memoria_calculo.md').decode()
            self.assertIn('igualdade de resposta, fadiga ou dano',memo)
            self.assertNotIn('está não cair',memo)
            self.assertFalse(recipe['iso2247_compliance_claimed'])
            self.assertIn(b'DEMONSTRACAO',z.read('receita_frequencia_fixa.csv'))


if __name__=='__main__':unittest.main()
