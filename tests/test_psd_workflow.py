"""Invariantes de seleção, lacunas, tabelas e comparação em banda comum."""
import io
import json
import zipfile
import zlib
import unittest
import numpy as np
import pandas as pd
from acquisition import Recording,read_binary,read_csv_recording
from psd_recipe import spectral_area
from psd_catalog import load_catalog,compare_profiles
from psd_workflow import (analyze_recording,select_intensity,automatic_profile,
                          breakpoint_table,profile_from_slopes,assess_profile,export_workflow)


def recording(amplitudes=(.1,.2,.3,.4),fs=100.,seconds=10):
    t=np.arange(round(len(amplitudes)*seconds*fs))/fs
    x=1+np.repeat(amplitudes,round(seconds*fs))*np.sin(2*np.pi*10*t)
    return Recording(x,fs,1.,pd.DataFrame([dict(segment_id=1,first_sample=0,end_sample_exclusive=len(x),reason='teste')]))


def report(raw,closed=True,tail=0):
    n=(len(raw)-tail)//2;mid=n//2
    header='format=MPUZ_RAW_LE_V2\ntime_basis=sample_index_nominal_per_segment\nsample_rate_nominal_hz=1000\nlsb_per_g=8192\naccel_range_g=4\nwho_am_i=112\nsample_rate_divider=0\ngyro_dlpf_cfg=1\naccel_dlpf_cfg=0\ngyro_fchoice_b=0\nstatus=INCOMPLETE\n'
    lines=f'segment=1,0,{mid},0,1000,12,{zlib.crc32(raw[:2*mid])}\nsegment=2,{mid},{n},1100,2100,0,{zlib.crc32(raw[:2*n])}\n'
    final=f'samples={n}\ncrc32={zlib.crc32(raw)}\nstatus=REVIEW\nsession_closed=1\n' if closed else ''
    return (header+lines+final).encode()


class AcquisitionTests(unittest.TestCase):
    def test_closed_review_with_valid_crc_and_gaps(self):
        raw=np.arange(2000,dtype='<i2').tobytes();rec=read_binary(raw,report(raw))
        self.assertEqual(rec.samples,2000)
        self.assertTrue(rec.metadata['session_closed_verified'])
        self.assertEqual(rec.metadata['status'],'REVIEW')
        self.assertEqual(len(rec.segments),2)
        np.testing.assert_allclose(rec.values(20,30),np.arange(20,30)/8192)

    def test_incomplete_prefix_and_unmapped_tail(self):
        prefix=np.arange(2000,dtype='<i2').tobytes();raw=prefix+b'\x01\x00\x02'
        rec=read_binary(raw,report(raw,False,tail=3))
        self.assertEqual(rec.samples,2000)
        self.assertEqual(rec.metadata['unverified_tail_bytes'],3)
        self.assertFalse(rec.metadata['session_closed_verified'])
        self.assertTrue(rec.metadata['integrity_verified'])

    def test_crc_corruption_cannot_be_hidden_by_review(self):
        raw=np.arange(2000,dtype='<i2').tobytes();txt=report(raw)
        for changed in [b'\x01'+raw[1:],raw[:-2]]:
            with self.assertRaises(ValueError):read_binary(changed,txt)
        with self.assertRaises(ValueError):read_binary(raw,txt+b'crc32=1\n')
        with self.assertRaises(ValueError):read_binary(raw,txt+b'segment=2,1001,2000,1100,2100,0,1\n')

    def test_csv_gaps_are_segmented_and_jitter_is_not_repaired(self):
        t=np.r_[np.arange(1000)/100,np.arange(1000)/100+20]
        data=pd.DataFrame(dict(time_s=t,accel_z_g=np.sin(2*np.pi*10*t))).to_csv(index=False).encode()
        rec=read_csv_recording(data);self.assertEqual(len(rec.segments),2)
        a=analyze_recording(rec,1,40,10,2)
        self.assertAlmostEqual(a['settings']['covered_duration_s'],20.)
        t[10]+=.001
        data=pd.DataFrame(dict(time_s=t,accel_z_g=np.ones(len(t)))).to_csv(index=False).encode()
        with self.assertRaises(ValueError):read_csv_recording(data)


class WorkflowTests(unittest.TestCase):
    def test_known_band_rms_and_duration_weighted_power(self):
        rec=recording();a=analyze_recording(rec,1,40,10,2,.5)
        np.testing.assert_allclose(a['blocks'].grms_band_g,np.array([.1,.2,.3,.4])/np.sqrt(2),atol=1e-9)
        self.assertAlmostEqual(spectral_area(a['frequency'],a['all_psd']),np.mean(np.array([.1,.2,.3,.4])**2)/2,places=10)
        self.assertEqual(a['settings']['covered_duration_s'],40.)

    def test_top_ten_percent_and_whole_block_granularity(self):
        a=analyze_recording(recording(tuple(np.arange(1,11)/10)),1,40,10,2)
        s=select_intensity(a,10)
        self.assertEqual(s['settings']['selected_duration_s'],10.)
        self.assertEqual(s['settings']['selected_duration_percentage'],10.)
        self.assertEqual(s['blocks'].loc[s['blocks'].selected,'block_id'].tolist(),[10])
        a=analyze_recording(recording(),1,40,10,2)
        self.assertEqual(select_intensity(a,10)['settings']['selected_duration_percentage'],25.)

    def test_ties_stay_together_and_complement_preserves_total_exposure(self):
        a=analyze_recording(recording((.1,.2,.4,.4)),1,40,10,2)
        s=select_intensity(a,10);c=select_intensity(a,10,complement=True)
        self.assertEqual(s['settings']['selected_duration_s'],20.)
        self.assertEqual(s['settings']['selected_duration_s']+c['settings']['selected_duration_s'],40.)
        area=(spectral_area(s['frequency'],s['psd'])*20+spectral_area(c['frequency'],c['psd'])*20)/40
        self.assertAlmostEqual(area,spectral_area(a['frequency'],a['all_psd']),places=12)

    def test_no_spectral_window_crosses_segment_boundary(self):
        fs=100.;t=np.arange(1000)/fs
        x=np.r_[1+.1*np.sin(2*np.pi*10*t),1000+.1*np.sin(2*np.pi*10*t)]
        segments=pd.DataFrame([dict(segment_id=1,first_sample=0,end_sample_exclusive=1000),dict(segment_id=2,first_sample=1000,end_sample_exclusive=2000)])
        rec=Recording(x,fs,1.,segments);a=analyze_recording(rec,1,40,10,2)
        self.assertEqual(a['blocks'].segment_id.tolist(),[1,2])
        self.assertAlmostEqual(spectral_area(a['frequency'],a['all_psd']),.1**2/2,places=10)

    def test_tails_and_welch_overlap_are_not_exposure(self):
        rec=recording((.2,),seconds=10.5)
        a=analyze_recording(rec,1,40,10,4,.5)
        self.assertEqual(a['settings']['covered_duration_s'],10.)
        self.assertEqual(a['settings']['tail_excluded_s'],.5)
        self.assertEqual(a['excluded'].excluded_s.sum(),.5)

    def test_slopes_round_trip_and_psd_uses_ten_log(self):
        f=[20,50,800,2000];p=[.026,.1614843,.1614843,.026]
        table=breakpoint_table(f,p)
        self.assertAlmostEqual(table.slope_to_next_db_oct.iloc[0],6.,places=5)
        self.assertTrue(np.isnan(table.slope_to_next_db_oct.iloc[-1]))
        inverse=profile_from_slopes(f,p[0],table.slope_to_next_db_oct.iloc[:-1])
        np.testing.assert_allclose(inverse.psd_g2_per_Hz,p,rtol=1e-12)
        for ff,pp in [([1,1],[.01,.02]),([2,1],[.01,.02]),([1,2],[.01,0]),([1,2],[.01,np.nan])]:
            with self.assertRaises(ValueError):breakpoint_table(ff,pp)

    def test_manual_change_reports_area_instead_of_rescaling(self):
        f=np.linspace(1,50,197);p=.005+.005*np.exp(-((f-12)/3)**2)
        selected=dict(frequency=f,psd=p)
        profile,_=automatic_profile(selected,.5,100)
        old=assess_profile(selected,profile,.5)
        changed=breakpoint_table(profile.frequency_Hz,profile.psd_g2_per_Hz*4)
        new=assess_profile(selected,changed,.5)
        self.assertAlmostEqual(new['recipe_grms']/old['recipe_grms'],2.)
        self.assertAlmostEqual(new['area_difference_percent'],300.,places=8)

    def test_narrow_peak_is_retained_when_simplification_preserves_area(self):
        fs=1000.;t=np.arange(10000)/fs;rng=np.random.default_rng(12)
        x=1+.3*np.sin(2*np.pi*8*t)+rng.normal(0,.004,len(t))
        rec=Recording(x,fs,1.,pd.DataFrame([dict(segment_id=1,first_sample=0,end_sample_exclusive=len(x))]))
        s=select_intensity(analyze_recording(rec));profile,fit=automatic_profile(s,max_points=200)
        self.assertTrue(fit['passed'])
        self.assertLess(abs(profile.frequency_Hz.iloc[int(np.argmax(profile.psd_g2_per_Hz))]-8),.25)
        self.assertAlmostEqual(spectral_area(profile.frequency_Hz,profile.psd_g2_per_Hz,'log-log'),spectral_area(s['frequency'],s['psd']),places=10)

    def test_catalog_reference_rms_and_common_band(self):
        catalog=load_catalog();self.assertEqual(len(catalog),18)
        leaf=next(r for r in catalog if r['id']=='korea_2020_leaf_spring_high')
        self.assertAlmostEqual(np.sqrt(spectral_area(leaf['frequency_Hz'],leaf['psd_g2_per_Hz'],'log-log')),.472810,places=5)
        f=np.linspace(1,50,197);p=np.full(len(f),.01);selected=dict(frequency=f,psd=p)
        profile=breakpoint_table([1,50],[.01,.01])
        refs=[r for r in catalog if r['id'] in ['iso13355_reproduced_2006','rissi2008_vertical_digitized']]
        table,band=compare_profiles(selected,profile,refs)
        self.assertEqual(table.iloc[0].reference_id,'this_test_selected')
        self.assertAlmostEqual(table.iloc[0].shape_distance_db,0,places=12)
        self.assertAlmostEqual(table.iloc[0].proposed_to_reference_grms,1,places=12)
        self.assertEqual(band,[3.,50.])
        np.testing.assert_allclose(table.proposed_grms_common_g,np.sqrt(.47))
        self.assertTrue((table.common_low_Hz==3).all())

    def test_measurement_row_without_references_uses_measured_psd(self):
        selected=dict(frequency=np.array([1.,10.,50.]),psd=np.array([.01,.01,.01]))
        profile=breakpoint_table([1,50],[.04,.04])
        table,band=compare_profiles(selected,profile,[])
        self.assertEqual(band,[1.,50.])
        self.assertEqual(len(table),1)
        self.assertAlmostEqual(table.iloc[0].reference_grms_common_g,.7)
        self.assertAlmostEqual(table.iloc[0].proposed_to_reference_grms,2.)
        self.assertAlmostEqual(table.iloc[0].shape_distance_db,0.,places=10)

    def test_hungary_digitized_reference_integral_and_provenance(self):
        row=next(r for r in load_catalog() if r['id']=='hungary_borocz_singh_2018_digitized')
        self.assertEqual(len(row['frequency_Hz']),12)
        self.assertEqual(row['frequency_Hz'][0],1.)
        self.assertEqual(row['frequency_Hz'][-1],200.)
        self.assertAlmostEqual(np.sqrt(spectral_area(row['frequency_Hz'],row['psd_g2_per_Hz'],'log-log')),.38447,places=4)
        self.assertIn('Digitalização',row['method'])

    def test_export_keeps_selection_reference_provenance_and_current_table(self):
        rec=recording();a=analyze_recording(rec,1,40,10,2);s=select_intensity(a,25)
        profile,_=automatic_profile(s,max_points=200);fit=assess_profile(s,profile)
        refs=[load_catalog()[0]];comparison,band=compare_profiles(s,profile,refs)
        payload,meta=export_workflow(s,profile,fit,rec,{'file':'synthetic'},comparison,refs,'DEMONSTRACAO')
        with zipfile.ZipFile(io.BytesIO(payload)) as z:
            actual=pd.read_csv(io.BytesIO(z.read('perfil_psd.csv')))
            np.testing.assert_allclose(actual.psd_g2_per_Hz,profile.psd_g2_per_Hz)
            saved=json.loads(z.read('receita.json')); self.assertEqual(saved['duration_full_level_s'],10.)
            self.assertFalse(saved['damage_equivalence_claimed'])
            self.assertEqual(json.loads(z.read('referencias_selecionadas.json'))[0]['id'],refs[0]['id'])
            self.assertIn('segmentos_aquisicao.csv',z.namelist())
            self.assertIn('blocos_classificados.csv',z.namelist())


if __name__=='__main__':unittest.main()
