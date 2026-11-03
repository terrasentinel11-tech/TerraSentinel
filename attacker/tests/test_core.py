from pathlib import Path
import csv
import hashlib
import numpy as np
import rasterio
import pytest
from black_pixel_agri.demo import create
from black_pixel_agri.raster import read_scene,export_tiff,sha256
from black_pixel_agri.engine import run,compatible_attacks,ATTACKS
from black_pixel_agri.visuals import preview
from black_pixel_agri.dataset import build

@pytest.fixture(scope='module')
def farm(tmp_path_factory):
    return create(tmp_path_factory.mktemp('scenes')/'farm.tif')

def test_scene_explicit_bands(farm):
    x=read_scene(farm)
    assert x.pixels.shape==(13,256,256)
    assert x.calibrated
    assert x.names['B08']==7

def test_original_unchanged(farm):
    initial=sha256(farm)
    run(farm,attack='cloud_injection')
    assert sha256(farm)==initial

@pytest.mark.parametrize('name', ['field_patch_replacement','copy_move_clone','fake_drought_proxy',
    'vegetation_recovery_proxy','fake_harvest_proxy','cloud_injection','cloud_shadow_combined',
    'atmospheric_haze','scanline_stripes','single_band_ndvi','band_misregistration','calibration_gain'])
def test_attack_raster_and_mask(farm,name):
    res=run(farm,attack=name)
    assert res.attack==name
    assert res.output.shape==res.scene.pixels.shape
    assert res.output.dtype==res.scene.pixels.dtype
    assert res.changed_mask.dtype==bool
    expected=np.any(res.output!=res.scene.pixels,axis=0)&res.scene.valid
    assert np.array_equal(expected,res.changed_mask)
    assert res.changed_mask.any()
    assert np.array_equal(res.output[:,~res.selected_mask],res.scene.pixels[:,~res.selected_mask])

def test_manual_no_substitution(farm):
    with pytest.raises(ValueError,match='does not support'):
        run(farm,attack='field_patch_replacement',coverage='global')

def test_auto_has_reason(farm):
    ranked=compatible_attacks(read_scene(farm))
    assert ranked and all('reason' in item for item in ranked)
    result=run(farm,attack='auto')
    assert result.attack in ATTACKS

def test_repeatable(farm):
    a=run(farm,attack='cloud_injection',seed=81)
    b=run(farm,attack='cloud_injection',seed=81)
    assert np.array_equal(a.output,b.output)
    assert np.array_equal(a.changed_mask,b.changed_mask)

def test_metadata_only(farm,tmp_path):
    res=run(farm,attack='georeference_shift')
    assert not res.changed_mask.any()
    assert res.geo_transform != res.scene.profile['transform']
    export_tiff(res.scene,tmp_path/'moved.tif',res.output,transform=res.geo_transform)
    with rasterio.open(farm) as o,rasterio.open(tmp_path/'moved.tif') as n:
        assert o.transform!=n.transform
        assert np.array_equal(o.read(),n.read())

def test_preview_same_scene(farm,tmp_path):
    result=run(farm,attack='field_patch_replacement')
    out=preview(result,tmp_path/'preview.png')
    from PIL import Image
    w,h=Image.open(out).size
    assert w>3*256 and h>256

def test_no_scale_rejects_spectral(farm,tmp_path):
    with rasterio.open(farm) as f:
        profile=f.profile.copy();arr=f.read();descriptions=f.descriptions
    with rasterio.open(tmp_path/'unscaled.tif','w',**profile) as ds:
        ds.write(arr)
        for i,d in enumerate(descriptions,1):ds.set_band_description(i,d)
    with pytest.raises(ValueError,match='scale'):
        run(tmp_path/'unscaled.tif',attack='fake_drought_proxy')

def test_pair_dataset_and_resume(tmp_path):
    src=tmp_path/'src';src.mkdir()
    for i in range(4):create(src/f'{i}.tif',seed=i+30)
    dst=tmp_path/'out'
    first=build([src],dst,total=3,attacks=['cloud_injection','atmospheric_haze'],selection='auto')
    assert first['completed_pairs']==3
    before=(dst/'dataset_summary.csv').read_bytes()
    repeated=build([src],dst,total=3,attacks=['cloud_injection','atmospheric_haze'],selection='auto')
    assert repeated['completed_pairs']==3
    assert (dst/'dataset_summary.csv').read_bytes()==before
    with (dst/'dataset_summary.csv').open(newline='') as f:rows=list(csv.DictReader(f))
    assert len(rows)==3
    for r in rows:
        original=dst/r['original_path'];attacked=dst/r['attacked_path'];pp=dst/r['preview_path']
        assert all(f.exists() for f in [original,attacked,pp])
        assert original.parent.name==r['attack']
        assert sha256(Path(r['source']))==sha256(original)
        with rasterio.open(original) as x,rasterio.open(attacked) as y:
            assert x.shape==y.shape and x.count==y.count and x.dtypes==y.dtypes and x.crs==y.crs

def test_manual_dataset_requires_one(tmp_path):
    with pytest.raises(ValueError,match='one attack'):
        build([],tmp_path/'out',total=1,selection='manual',attacks=['cloud_injection','atmospheric_haze'])

def test_incompatible_image_rejection(tmp_path):
    import rasterio
    from rasterio.transform import from_origin
    path=tmp_path/'rgb.tif'
    with rasterio.open(path,'w',driver='GTiff',height=32,width=32,count=3,dtype='uint8',transform=from_origin(0,0,1,1)) as ds:
        ds.write(np.full((3,32,32),127,dtype='uint8'))
    with pytest.raises(ValueError,match='Required bands missing'):
        run(path,attack='fake_drought_proxy')

def test_campaign_config_change_refused(tmp_path):
    src=tmp_path/'sources';src.mkdir();create(src/'farm.tif')
    target=tmp_path/'target'
    first=build([src],target,total=1,attacks=['cloud_injection'],selection='manual')
    assert first['completed_pairs']==1
    with pytest.raises(ValueError,match='different settings'):
        build([src],target,total=2,attacks=['atmospheric_haze'],selection='manual')


def test_metadata_preview_and_mask(farm,tmp_path):
    r=run(farm,attack='georeference_shift')
    assert r.manifest['edited_pixel_count']==0
    assert r.manifest['metadata_changes']['transform_before']!=r.manifest['metadata_changes']['transform_after']
    assert preview(r,tmp_path/'metadata_preview.png').exists()


def test_real_eurosat_demo_if_present():
    p=Path('/mnt/data/AnnualCrop_2.tif')
    if not p.exists(): pytest.skip('No user EuroSAT sample mounted in current environment')
    r=run(p,attack='cloud_injection',profile='eurosat',coverage='regional')
    assert r.changed_mask.any() and r.scene.pixels.shape[0]==13
    assert r.manifest['requested_attack']==r.attack
