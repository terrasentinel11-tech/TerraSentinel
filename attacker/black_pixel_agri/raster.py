"""Raster input: explicit band profiles and calibration assumptions, never source mutation."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import hashlib
import re
import numpy as np
import rasterio

EUROSAT13 = ('B01','B02','B03','B04','B05','B06','B07','B08','B09','B10','B11','B12','B8A')
SEN12MS13 = ('B01','B02','B03','B04','B05','B06','B07','B08','B8A','B09','B10','B11','B12')


def sha256(path: str|Path) -> str:
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024), b''): h.update(b)
    return h.hexdigest()

@dataclass
class Scene:
    path: Path
    pixels: np.ndarray               # bands x height x width original dtype
    valid: np.ndarray                # H x W, excludes NoData
    profile: dict
    bands: tuple[str,...]
    scale: float | None              # DN denominator; opt-in, NOT claimed calibration
    tags: dict
    band_descriptions: tuple

    @property
    def hw(self): return self.pixels.shape[1:]
    @property
    def names(self): return {b: i for i,b in enumerate(self.bands)}
    @property
    def calibrated(self): return self.scale is not None and 'B04' in self.names and 'B08' in self.names

    def image(self, band: str) -> np.ndarray:
        if band not in self.names: raise ValueError('Missing spectral band '+band)
        return self.pixels[self.names[band]].astype(np.float32)


def normalize_band_name(s):
    if not s: return ''
    key=re.sub(r'[^a-zA-Z0-9]','',str(s)).upper()
    alias={'RED':'B04','NIR':'B08','GREEN':'B03','BLUE':'B02', 'B8A':'B8A','B08A':'B8A',
           'R':'B04','G':'B03','B':'B02'}
    if key in alias:return alias[key]
    if re.fullmatch(r'B\d{1,2}',key):return 'B'+key[1:].zfill(2)
    return key


def read_scene(path: str|Path, *, source_profile: str='auto', assume_scale:float|None=None) -> Scene:
    p=Path(path)
    if assume_scale is not None and not (0 < float(assume_scale) < 1e10):
        raise ValueError('assume_scale must be positive; it is an unverified experimental assumption')
    with rasterio.open(p) as ds:
        arr=ds.read()
        valid=np.all(ds.read_masks()>0,axis=0)
        valid &= np.all(np.isfinite(arr),axis=0)
        labels=tuple(normalize_band_name(d) for d in ds.descriptions)
        tags=ds.tags().copy()
        profile=ds.profile.copy()
        descriptions=ds.descriptions
    if source_profile=='eurosat':
        if arr.shape[0]!=13: raise ValueError('EuroSAT preset requires 13 bands')
        labels=EUROSAT13
    elif source_profile=='sen12ms-cr':
        if arr.shape[0]!=13: raise ValueError('SEN12MS-CR preset requires 13 bands')
        labels=SEN12MS13
    elif source_profile not in ('auto','rgb'):
        raise ValueError('Unknown profile '+source_profile)
    elif source_profile=='rgb':
        if arr.shape[0]!=3: raise ValueError('RGB preset requires 3 bands')
        labels=('B04','B03','B02')
    elif arr.shape[0]==3 and not any(labels):
        labels=('B04','B03','B02')  # RGB display ONLY; cannot be spectrally calibrated without scale
    else:
        labels=tuple(labels)
    if assume_scale is None and tags.get('REFLECTANCE_SCALE'):
        try:
            # Metadata provenance may remain unverified; user should inspect dataset metadata.
            assume_scale=float(tags['REFLECTANCE_SCALE'])
        except ValueError: pass
    return Scene(p,arr,valid,profile,tuple(labels),assume_scale,tags,descriptions)


def rgb_for_preview(scene:Scene, pixels:np.ndarray|None=None, stretch:tuple|None=None):
    arr=scene.pixels if pixels is None else pixels
    n=scene.names
    if all(b in n for b in ('B04','B03','B02')):
        ind=(n['B04'],n['B03'],n['B02'])
    else:
        ind=tuple(range(min(3,len(arr))))
        if len(ind)<3:ind=(0,0,0)
    raw=arr[list(ind)].astype(np.float32)
    if stretch is None:
        vals=raw[:,scene.valid]
        if vals.size==0: stretch=(0.,1.)
        else:
            low=np.percentile(vals,2); high=np.percentile(vals,98)
            stretch=(float(low),float(max(high,low+1)))
    lo,hi=stretch
    return np.uint8(np.clip((raw-lo)/max(hi-lo,1e-6),0,1)*255).transpose(1,2,0),stretch


def export_tiff(scene:Scene, output:Path, pixels:np.ndarray, *, tags:dict|None=None, transform=None):
    output.parent.mkdir(parents=True,exist_ok=True)
    profile=scene.profile.copy()
    profile.update(driver='GTiff', count=pixels.shape[0], height=pixels.shape[1], width=pixels.shape[2],
                   dtype=scene.pixels.dtype)
    if transform is not None:profile['transform']=transform
    tmp=output.with_suffix('.writing.tif')
    try:
        with rasterio.open(tmp,'w',**profile) as ds:
            ds.write(pixels)
            for i,d in enumerate(scene.band_descriptions,start=1):
                if d:ds.set_band_description(i,d)
            ds.update_tags(**{k:str(v) for k,v in scene.tags.items()})
            if tags:ds.update_tags(**{k:str(v) for k,v in tags.items()})
        tmp.replace(output)
    finally:
        tmp.unlink(missing_ok=True)
