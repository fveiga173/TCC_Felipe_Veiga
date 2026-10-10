"""Testes de invariantes físicos e de integridade, executáveis com unittest."""
import io
import json
from pathlib import Path
import unittest
import zipfile
import zlib
import numpy as np
from psd_recipe import (spectral_area, simplify_psd, build_recipe,
                        representative_psd, load_binary, export_bundle)

class ScientificTests(unittest.TestCase):
    def test_analytical_integrals(self):
        # PSD constante: área = nível × largura; potência f^-1: logaritmo.
        self.assertAlmostEqual(spectral_area([2,10],[.01,.01]), .08)
        self.assertAlmostEqual(spectral_area([2,10],[.5,.1],'log-log'), np.log(5))
        self.assertAlmostEqual(spectral_area([1,4],[1,16],'log-log'),21.)

    def test_known_sine_rms(self):
        fs=500.;t=np.arange(10000)/fs;x=1+.3*np.sin(2*np.pi*10*t)
        r=build_recipe(t,x,fs,[dict(inicio_s=0,fim_s=20)],3,50,max_points=200)
        self.assertAlmostEqual(r['simplification']['input_grms'],.3/np.sqrt(2),places=6)
        self.assertAlmostEqual(r['simplification']['recipe_grms'],.3/np.sqrt(2),places=6)
        self.assertEqual(r['settings']['duration_s'],20.)

    def test_duration_weighted_psd_and_half_open_intervals(self):
        fs=100.;t=np.arange(3000)/fs
        x=np.where(t<10,.2,.4)*np.sin(2*np.pi*10*t)
        f,p,rows,settings,spectra=representative_psd(t,x,fs,[dict(inicio_s=0,fim_s=10),dict(inicio_s=10,fim_s=30)],2,0)
        self.assertAlmostEqual(spectral_area(f,p),(.2**2/2*10+.4**2/2*20)/30,places=10)
        self.assertEqual(rows.amostras_cobertas.sum(),len(t))
        self.assertEqual(settings['duration_s'],30.)

    def test_tail_and_overlap_do_not_inflate_exposure(self):
        fs=100.;t=np.arange(1050)/fs;x=np.sin(2*np.pi*10*t)
        _,_,rows,s,_=representative_psd(t,x,fs,[dict(inicio_s=0,fim_s=10.5)],4,.5)
        self.assertEqual(s['duration_s'],10.)
        self.assertEqual(rows.cauda_excluida_s.iloc[0],.5)
        self.assertEqual(rows.janelas_welch.iloc[0],4)
        with self.assertRaises(ValueError):
            representative_psd(t,x,fs,[dict(inicio_s=0,fim_s=8),dict(inicio_s=7,fim_s=10)],2)

    def test_irregular_and_zero_signal_rejected(self):
        t=np.arange(2000)/100.;x=np.ones(2000)
        with self.assertRaises(ValueError):build_recipe(t,x,100,[dict(inicio_s=0,fim_s=20)],3,40)
        t[900:]+=.1
        with self.assertRaises(ValueError):representative_psd(t,x,100,[dict(inicio_s=0,fim_s=20)])

    def test_simplification_preserves_area_and_reports_failure(self):
        f=np.linspace(3,50,189);p=.01+.15*np.exp(-((f-20)/1.4)**2)
        for mode in ['linear','log-log']:
            ff,pp,info=simplify_psd(f,p,mode,tolerance_db=.5,max_points=80)
            self.assertTrue(info['passed'])
            self.assertAlmostEqual(spectral_area(f,p),spectral_area(ff,pp,mode),places=10)
            self.assertLess(len(ff),len(f))
        self.assertFalse(simplify_psd(f,p,max_points=2)[2]['passed'])

    def test_binary_crc_final_status_and_diagnostics(self):
        raw=np.zeros(100,dtype='<i2').tobytes()
        report=('status=INCOMPLETE\nformat=MPUZ_RAW_LE_V1\ntime_basis=sample_index_nominal\n'
                'samples=100\nsample_rate_nominal_hz=500\nlsb_per_g=8192\n'
                f'crc32={zlib.crc32(raw)}\nerror_code=0\nfifo_overflows=0\n'
                'dlpf_cfg=2\naccel_range_g=4\nduration_arduino_ms=200\nsaturation_samples=0\nstatus=OK\n').encode()
        frame,meta=load_binary(raw,report)
        self.assertEqual(len(frame),100);self.assertTrue(meta['integrity_verified'])
        for badraw,badreport in [(raw[:-1],report),(b'\x01'+raw[1:],report),
                                  (raw,report+b'status=INCOMPLETE\n'),(raw,report+b'fifo_overflows=1\n')]:
            with self.assertRaises(ValueError):load_binary(badraw,badreport)

    def test_export_matches_profile(self):
        fs=100.;t=np.arange(2000)/fs
        x=np.random.default_rng(1).normal(size=len(t))
        result=build_recipe(t,x,fs,[dict(inicio_s=0,fim_s=20)],3,40)
        data,meta=export_bundle(result,{'test':True},'DEMONSTRACAO',['Dado sintético'])
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            saved=json.loads(z.read('receita.json'))
            self.assertEqual(saved['status'],'DEMONSTRACAO')
            self.assertEqual(saved['duration_s'],20.)
            self.assertIn(b'DEMONSTRACAO',z.read('perfil_psd.csv'))
            self.assertEqual(len(z.namelist()),6)

if __name__=='__main__':unittest.main()
