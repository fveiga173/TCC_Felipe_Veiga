"""Invariantes de exposição, potência, classificação e integridade v6."""
import io
import json
import unittest
import zipfile
import zlib
import numpy as np
import pandas as pd
from psd_recipe import VERSION, build_recipe, load_binary, spectral_area
from vibration_scenarios import analyze_epochs, build_plans, compression_factors, export_plans, weighted_percentile


def signal_result(amplitudes=(.1,.1,.2,.4), count_per_level=1000, fs=100., window='hann'):
    t=np.arange(count_per_level*len(amplitudes))/fs
    x=1+np.repeat(amplitudes,count_per_level)*np.sin(2*np.pi*10*t)
    base=build_recipe(t,x,fs,[dict(inicio_s=0,fim_s=len(t)/fs)],3,40,seconds=2.,overlap=.5,
                      mode='linear',max_points=200,window=window)
    return t,x,base


class ScenarioTests(unittest.TestCase):
    def test_known_epoch_rms_power_and_coverage(self):
        t,x,base=signal_result()
        a=analyze_epochs(t,x,base,10.)
        np.testing.assert_allclose(a['blocks'].grms_banda_g,np.array([.1,.1,.2,.4])/np.sqrt(2),atol=1e-9)
        expected=np.mean(np.array([.1,.1,.2,.4])**2)/2
        self.assertAlmostEqual(spectral_area(a['frequency'],a['psd']),expected,places=12)
        self.assertEqual(a['blocks'].amostras.sum(),len(x))
        self.assertEqual(a['settings']['epoch_duration_s_covered'],40.)
        # O pico é o máximo AMOSTRADO: em 10 Hz/100 Hz nenhum ponto chega
        # exatamente ao pico contínuo. O diagnóstico não inventa esse pico.
        sampled_peak=np.max(np.abs(np.sin(2*np.pi*10*np.arange(1000)/100)))
        np.testing.assert_allclose(a['blocks'].fator_crista,sampled_peak*np.sqrt(2),atol=1e-10)

    def test_hamming_is_normalized_and_shared_by_epochs(self):
        t,x,base=signal_result(window='hamming')
        a=analyze_epochs(t,x,base,10.)
        self.assertEqual(a['settings']['window_key'],'hamming')
        np.testing.assert_allclose(a['blocks'].grms_banda_g,np.array([.1,.1,.2,.4])/np.sqrt(2),atol=1e-9)

    def test_compression_scales_psd_not_frequency_or_waveform(self):
        t,x,base=signal_result();a=analyze_epochs(t,x,base)
        result=build_plans(a,factor=5.,k=2.,mode='linear',max_points=200)
        reference=result['plans'][0]['profiles'][0];compressed=result['plans'][1]['profiles'][0]
        np.testing.assert_array_equal(reference['profile'].frequency_Hz,compressed['profile'].frequency_Hz)
        np.testing.assert_allclose(compressed['profile'].psd_g2_per_Hz,5*reference['profile'].psd_g2_per_Hz)
        self.assertAlmostEqual(compressed['proposed_grms_g']/reference['proposed_grms_g'],np.sqrt(5))
        self.assertEqual(compressed['duration_s'],8.)
        # Conservação do índice APENAS sob o modelo de nível único assumido.
        for k in [2.,4.,6.]:
            m=compression_factors(5,k)
            self.assertAlmostEqual(m['acceleration_multiplier']**k/5,1.)
        self.assertFalse(result['plans'][1]['damage_equivalence_claimed'])

    def test_time_weighted_percentile_and_ties(self):
        self.assertEqual(weighted_percentile([.1,.2,.3],[80,10,10],.8),.1)
        t,x,base=signal_result(amplitudes=(.1,.1,.1,.1))
        a=analyze_epochs(t,x,base)
        # Empates exatos: blocos com mesma estatística não são divididos por ranking.
        a['blocks']['grms_banda_g']=.1
        result=build_plans(a,quantile=.8,mode='linear',max_points=200)
        self.assertEqual(result['settings']['high_duration_fraction'],0.)
        self.assertEqual(result['plans'][3]['profiles'],[])
        with self.assertRaises(ValueError):export_plans(result,{},'ESTUDO_PRELIMINAR',[],'selecao')

    def test_selection_duration_and_grouped_energy(self):
        t,x,base=signal_result();a=analyze_epochs(t,x,base)
        result=build_plans(a,threshold_g=.15,mode='linear',max_points=200)
        levels=result['plans'][2];selection=result['plans'][3]
        self.assertEqual(levels['duration_s'],40.)
        self.assertEqual(selection['duration_s'],10.)
        self.assertEqual(selection['excluded_low_intensity_s'],30.)
        area=sum(p['proposed_grms_g']**2*p['duration_s'] for p in levels['profiles'])/40
        self.assertAlmostEqual(area,spectral_area(a['frequency'],a['psd']),places=10)
        self.assertEqual(selection['profiles'][0]['psd_multiplier'],1.)

    def test_discontinuous_intervals_and_additional_tails(self):
        t=np.arange(5000)/100.;x=np.sin(2*np.pi*10*t)
        base=build_recipe(t,x,100.,[dict(nome='A',inicio_s=0,fim_s=15),dict(nome='B',inicio_s=30,fim_s=45)],3,40,seconds=4.,mode='linear',max_points=200)
        a=analyze_epochs(t,x,base,9.)
        ids=np.concatenate([np.arange(r.primeira_amostra,r.fim_amostra_exclusivo) for r in a['blocks'].itertuples()])
        self.assertEqual(len(np.unique(ids)),len(ids))
        self.assertFalse(((ids>=1500)&(ids<3000)).any())
        self.assertAlmostEqual(a['blocks'].duracao_s.sum()+a['excluded'].tempo_excluido_s.sum(),base['settings']['duration_s'])

    def test_zero_intensity_block_does_not_invent_noise(self):
        t,x,base=signal_result(amplitudes=(0.,0.,.2,.4))
        result=build_plans(analyze_epochs(t,x,base),threshold_g=.01,mode='linear',max_points=200)
        low=result['plans'][2]['profiles'][0]
        self.assertEqual(low['proposed_grms_g'],0.)
        self.assertEqual(low['duration_s'],20.)
        self.assertEqual(low['simplification']['mode'],'linear')

    def test_export_preserves_model_and_validation_labels(self):
        t,x,base=signal_result();result=build_plans(analyze_epochs(t,x,base),5,4,threshold_g=.15,mode='linear',max_points=200)
        data,meta=export_plans(result,{'sha256_input':'synthetic'},'DEMONSTRACAO',['Dados sintéticos'],'compressao')
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            saved=json.loads(z.read('cenarios.json'))
            self.assertEqual(saved['version'],VERSION)
            self.assertEqual(saved['settings']['basquin_exponent_k'],4.)
            self.assertFalse(saved['damage_equivalence_claimed'])
            self.assertTrue(saved['experimental_validation_pending'])
            self.assertIn('dunno2016',[r['id'] for r in saved['references']])
            profile=pd.read_csv(io.BytesIO(z.read('compressao/perfil_1.csv')))
            self.assertTrue((profile.validation=='PENDENTE').all())
            self.assertTrue((profile.status=='DEMONSTRACAO').all())
            self.assertAlmostEqual(spectral_area(profile.frequency_Hz,profile.psd_g2_per_Hz),spectral_area(result['plans'][1]['profiles'][0]['profile'].frequency_Hz,result['plans'][1]['profiles'][0]['profile'].psd_g2_per_Hz),places=10)

    def test_invalid_parameters(self):
        for factor,k in [(6,2),(0,2),(2,0),(np.nan,2)]:
            with self.assertRaises(ValueError):compression_factors(factor,k)
        t,x,base=signal_result()
        with self.assertRaises(ValueError):analyze_epochs(t,x,base,1.)

    def test_binary_v6_serial_report_and_config(self):
        raw=np.arange(100,dtype='<i2').tobytes()
        fields=dict(format='MPUZ_RAW_LE_V1',time_basis='sample_index_nominal',sample_rate_nominal_hz=1000,
                    sample_rate_divider=0,who_am_i=112,lsb_per_g=8192,gyro_dlpf_cfg=1,accel_dlpf_cfg=0,
                    gyro_fchoice_b=0,accel_range_g=4,samples=100,crc32=zlib.crc32(raw),error_code=0,
                    fifo_overflows=0,saturation_samples=0,duration_arduino_ms=100,status='OK')
        report=('16:00:00.123 -> status=INCOMPLETE\n'+'\n'.join(f'16:00:01.123 -> {k}={v}' for k,v in fields.items())).encode()
        frame,meta=load_binary(raw,report)
        self.assertTrue(meta['integrity_verified'])
        self.assertEqual(meta['rate_vs_arduino_hz'],1000.)
        self.assertEqual(frame.time_s.iloc[-1],.099)
        for key,value in [('who_am_i',104),('sample_rate_divider',7),('accel_dlpf_cfg',1),('status','REVIEW'),('fifo_overflows',1)]:
            with self.assertRaises(ValueError):load_binary(raw,report+f'\n{key}={value}'.encode())


if __name__=='__main__':unittest.main()
