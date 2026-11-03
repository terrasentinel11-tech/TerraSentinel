"""Synthetic attacks on authorized offline imagery, no operational exploitation."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from scipy import ndimage as ndi
from .analysis import SceneFeatures, select_target
from .raster import Scene

SEVERITIES={'subtle':.17,'balanced':.34,'strong':.55,'extreme':.78,'expert':.44,'auto':.34}

@dataclass(frozen=True)
class AttackInfo:
    name:str
    family:str
    purpose:str
    band_requirement:tuple[str,...]=()
    needs_calibration:bool=False
    coverages:tuple[str,...]=('local','regional')
    description:str=''

ATTACKS={x.name:x for x in [
    AttackInfo('field_patch_replacement','spatial','clone',description='Replace image content from another region'),
    AttackInfo('copy_move_clone','spatial','clone',description='Duplicate source texture onto another region'),
    AttackInfo('fake_drought_proxy','agronomic','drought',('B04','B08'),True,description='Simulated stress-like spectral signature'),
    AttackInfo('vegetation_recovery_proxy','agronomic','recovery',('B04','B08'),True,description='Simulated improved vegetation signature'),
    AttackInfo('fake_harvest_proxy','agronomic','harvest',('B04','B08'),True,description='Blend vegetated region toward soil-like spectral signature'),
    AttackInfo('cloud_injection','atmospheric','cloud',coverages=('local','regional','global'),description='Procedural optical cloud obscuration proxy'),
    AttackInfo('cloud_shadow_combined','atmospheric','cloud',coverages=('local','regional','global'),description='Cloud proxy and shifted shadow'),
    AttackInfo('atmospheric_haze','atmospheric','haze',coverages=('local','regional','global'),description='Optical haze proxy'),
    AttackInfo('scanline_stripes','sensor','sensor',coverages=('local','regional','global'),description='Sensor-like stripes'),
    AttackInfo('single_band_ndvi','spectral','drought',('B04','B08'),True,coverages=('local','regional','global'),description='Single-band NIR perturbation baseline'),
    AttackInfo('band_misregistration','geometry','sensor',('B08',),False,coverages=('local','regional','global'),description='Shift NIR band by one or more pixels'),
    AttackInfo('calibration_gain','radiometry','sensor',('B04',),False,coverages=('local','regional','global'),description='Change per-band gain on a research copy'),
    AttackInfo('georeference_shift','metadata','sensor',coverages=('global',),description='GeoTIFF transform shifted while pixels stay identical'),
]}


def feasible(scene:Scene, info:AttackInfo)->tuple[bool,str]:
    missing=[k for k in info.band_requirement if k not in scene.names]
    if missing:return False,'Required bands missing: '+', '.join(missing)
    if info.needs_calibration and not scene.calibrated:
        return False,'Requires documented/explicitly confirmed scale for B04 and B08'
    if scene.valid.sum()<64:return False,'Not enough valid pixels'
    if scene.hw[0]<16 or scene.hw[1]<16:return False,'Image dimensions are too small'
    return True,'Compatible inputs (target selection still must succeed)'


def normalize_coverage(info:AttackInfo, requested:str)->str:
    if requested=='auto': return ('global' if info.name in ('atmospheric_haze','calibration_gain','georeference_shift') else 'regional' if info.family=='atmospheric' else 'local')
    if requested not in info.coverages: raise ValueError(f'{info.name} does not support {requested} coverage')
    return requested


def clamp_dtype(x:np.ndarray, dtype:np.dtype)->np.ndarray:
    if np.issubdtype(dtype,np.integer):
        lim=np.iinfo(dtype)
        return np.rint(np.clip(x,lim.min,lim.max)).astype(dtype)
    return x.astype(dtype)


def mixing_mask(mask:np.ndarray, feather:float=2.0)->np.ndarray:
    if feather<=0:return mask.astype(np.float32)
    distance=ndi.distance_transform_edt(mask)
    return np.clip(distance/feather,0,1).astype(np.float32)


def smooth_noise(h:int,w:int,rng, detail=18):
    arr=rng.normal(size=(h,w)).astype(np.float32)
    big=ndi.gaussian_filter(arr,sigma=max(2,min(h,w)/detail))
    small=ndi.gaussian_filter(arr,sigma=max(1,min(h,w)/(detail*2)))
    noise=big*.75+small*.25
    return (noise-noise.min())/(np.ptp(noise)+1e-6)


def cloud_mask(scene:Scene, coverage:str, rng, amount:float):
    h,w=scene.hw
    field=smooth_noise(h,w,rng,detail=9)
    fraction={'local':.08,'regional':.32,'global':.76}[coverage]
    cutoff=np.quantile(field[scene.valid], max(0.,1-fraction))
    mask=(field>=cutoff)&scene.valid
    if not mask.any():raise ValueError('Failed to create cloud candidate')
    return mask,field


def donor_replacement(scene:Scene, features:SceneFeatures, target:np.ndarray, seed:int, *, clone:bool=False):
    h,w=scene.hw
    yy,xx=np.where(target)
    if len(yy)<12:raise ValueError('Region is too small for patch transfer')
    y0,y1=yy.min(),yy.max()+1
    x0,x1=xx.min(),xx.max()+1
    th,tw=y1-y0,x1-x0
    rgb=features.rgb.astype(np.float32)/255
    original_mean=rgb[target].mean(axis=0)
    original_std=rgb[target].std(axis=0)
    rng=np.random.default_rng(seed+119)
    best=[]
    for _ in range(120):
        sy=int(rng.integers(0,max(1,h-th+1)))
        sx=int(rng.integers(0,max(1,w-tw+1)))
        if abs(sx-x0)<tw*.7 and abs(sy-y0)<th*.7:continue
        source_ok=scene.valid[sy:sy+th,sx:sx+tw]
        tm=target[y0:y1,x0:x1]
        if source_ok.shape!=tm.shape or np.mean(source_ok[tm])<.96:continue
        patch=rgb[sy:sy+th,sx:sx+tw]
        donor_mean=patch[tm].mean(axis=0)
        donor_std=patch[tm].std(axis=0)
        delta=float(np.mean(np.abs(original_mean-donor_mean)))
        rough=float(np.mean(np.abs(original_std-donor_std)))
        # Replacement seeks more visible difference; cloning seeks compatible texture.
        ideal=.095 if clone else .17
        score=-(abs(delta-ideal)*1.7+rough*(.65 if clone else .30))
        if delta > .045:best.append((score,sy,sx,delta))
    if not best:raise ValueError('No compatible visually distinct donor region found')
    best.sort(reverse=True)
    _,sy,sx,delta=best[0]
    donor=scene.pixels[:,sy:sy+th,sx:sx+tw].copy()
    return (y0,y1,x0,x1),donor,{'donor_bbox_yxyx':[int(sy),int(sy+th),int(sx),int(sx+tw)],'donor_rgb_delta':round(delta,4)}


def synthesize(scene:Scene, features:SceneFeatures, attack:str,coverage:str,severity:str,seed:int):
    """Return output pixels, intended mask, semantic notes. In-memory only."""
    info=ATTACKS[attack]
    coverage=normalize_coverage(info,coverage)
    ok,reason=feasible(scene,info)
    if not ok: raise ValueError(reason)
    strength=SEVERITIES[severity]
    rng=np.random.default_rng(seed)
    original=scene.pixels.astype(np.float32)
    output=original.copy()
    aux={'method':attack,'coverage':coverage,'level':severity,'severity_scalar':strength}
    if attack=='georeference_shift':
        return scene.pixels.copy(),np.zeros(scene.hw,dtype=bool),{'georef_shift_px':[2,1],**aux}
    if attack in ('cloud_injection','cloud_shadow_combined'):
        mask,field=cloud_mask(scene,coverage,rng,strength)
        alpha=np.clip((field-np.quantile(field[mask],.12))*4,0.15,.92)*mask
        alpha*=.53+.43*strength
        # Physical realism not claimed; upper image percentiles approximate bright cloud response.
        for b in range(original.shape[0]):
            high=np.percentile(original[b,scene.valid],98)
            ceiling=max(high, np.percentile(original[b,scene.valid],75)*1.55)
            output[b]=original[b]*(1-alpha)+ceiling*alpha
        intended=mask.copy()
        if attack=='cloud_shadow_combined':
            shadow=ndi.shift(mask.astype(float),shift=(max(2,int(scene.hw[0]*.035)),max(2,int(scene.hw[1]*.025))),order=0,mode='constant')>.5
            shadow=shadow&scene.valid&(~mask)
            output[:,shadow]*=(1-(.30+.28*strength))
            intended|=shadow
        aux.update({'cloud_fraction':round(float(mask.sum()/scene.valid.sum()),4)})
    elif attack=='atmospheric_haze':
        target=select_target(scene,features,'haze',coverage,seed)
        if coverage=='global':target=scene.valid
        strengthfield=(.10+.25*strength)*mixing_mask(target,5)
        for b in range(original.shape[0]):
            bright=np.percentile(original[b,scene.valid],95)
            output[b]=original[b]*(1-strengthfield)+bright*strengthfield
        intended=target
    elif attack in ('field_patch_replacement','copy_move_clone'):
        target=select_target(scene,features,'clone',coverage,seed)
        bbox,donor,dinfo=donor_replacement(scene,features,target,seed,clone=(attack=='copy_move_clone'))
        y0,y1,x0,x1=bbox
        alpha=mixing_mask(target[y0:y1,x0:x1],2.3)*(0.45+strength*.62)
        alpha=np.clip(alpha,0,1)
        output[:,y0:y1,x0:x1]=original[:,y0:y1,x0:x1]*(1-alpha)+donor*alpha
        intended=target
        aux.update(dinfo)
    elif attack in ('fake_drought_proxy','vegetation_recovery_proxy','fake_harvest_proxy','single_band_ndvi'):
        purpose='recovery' if attack=='vegetation_recovery_proxy' else 'harvest' if attack=='fake_harvest_proxy' else 'drought'
        target=select_target(scene,features,purpose,coverage,seed)
        alpha=mixing_mask(target,3.0)*(.30+.54*strength)
        n=scene.names
        red=original[n['B04']]; nir=original[n['B08']]
        if attack=='single_band_ndvi':output[n['B08']]=nir*(1-alpha*.47)
        elif attack=='vegetation_recovery_proxy':
            output[n['B08']]=nir*(1+alpha*.50)
            output[n['B04']]=red*(1-alpha*.23)
        elif attack=='fake_drought_proxy':
            output[n['B08']]=nir*(1-alpha*.48)
            output[n['B04']]=red*(1+alpha*.32)
            for b in ('B05','B06','B07','B11','B12'):
                if b in n:output[n[b]]=original[n[b]]*(1+alpha*(.12 if b.startswith('B1') else -.16))
        else:
            soil=features.soil
            if np.count_nonzero(soil)<20:raise ValueError('Harvest proxy requires reference bare-soil candidates')
            for b in range(original.shape[0]):
                mean=float(np.median(original[b,soil]))
                output[b]=original[b]*(1-alpha)+mean*alpha
        intended=target
    elif attack=='calibration_gain':
        target=select_target(scene,features,'sensor',coverage,seed)
        if coverage=='global':target=scene.valid
        scale=mixing_mask(target,3.)
        idx=scene.names['B04']
        output[idx]*=(1-(.08+.27*strength)*scale)
        intended=target
    elif attack=='band_misregistration':
        target=select_target(scene,features,'sensor',coverage,seed)
        if coverage=='global':target=scene.valid
        index=scene.names['B08']
        shifted=ndi.shift(original[index],shift=(max(1,round(strength*3)),1),order=1,mode='nearest')
        output[index,target]=shifted[target]
        intended=target
    elif attack=='scanline_stripes':
        target=select_target(scene,features,'sensor',coverage,seed)
        if coverage=='global':target=scene.valid
        y=np.arange(scene.hw[0]); signal=(np.sin(y*.40)+np.sin(y*.13))*.5
        stripe=(1+signal*(.08+.22*strength))[:,None]
        for i in range(output.shape[0]):
            out=original[i]*stripe
            output[i,target]=out[target]
        intended=target
    else:
        raise ValueError('Unimplemented attack '+attack)
    cast=clamp_dtype(output,scene.pixels.dtype)
    return cast,intended,aux
