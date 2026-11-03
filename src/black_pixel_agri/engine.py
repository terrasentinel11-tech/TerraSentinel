"""Attack orchestration: manual attack is never silently substituted."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import numpy as np
from .raster import Scene, read_scene, sha256
from .analysis import analyze, SceneFeatures
from .attacks import ATTACKS, SEVERITIES, feasible, normalize_coverage, synthesize

@dataclass
class Result:
    scene:Scene
    output:np.ndarray
    selected_mask:np.ndarray
    changed_mask:np.ndarray
    attack:str
    coverage:str
    level:str
    features:SceneFeatures
    manifest:dict
    geo_transform:object|None=None


def compatible_attacks(scene:Scene, *, allow:list[str]|None=None):
    features=analyze(scene)
    valid=scene.valid
    vegetation=float((features.vegetation&valid).sum()/max(1,valid.sum()))
    stressed=float((features.stressed&valid).sum()/max(1,valid.sum()))
    candidates=[]
    for name,info in ATTACKS.items():
        if allow is not None and name not in allow:continue
        ok,reason=feasible(scene,info)
        if not ok:continue
        if name=='georeference_shift' and not scene.profile.get('crs'):
            continue
        if info.family in ('spatial','agronomic') and not features.candidate_masks and min(scene.hw)<64:
            continue
        if info.purpose in ('drought','harvest') and vegetation<.04:continue
        if info.purpose=='recovery' and stressed<.03:continue
        score=.45
        if info.family=='spatial':score+=.10+min(.22,len(features.candidate_masks)/100)
        if info.family=='agronomic':score+=.11+min(.16,vegetation if info.purpose!='recovery' else stressed)
        if info.family=='atmospheric':score+=.12
        if info.family=='spectral':score+=.08
        if name=='field_patch_replacement':score+=.05
        candidates.append({'attack':name,'family':info.family,'score':round(min(.99,score),3),
                           'reason':f'{reason}; {len(features.candidate_masks)} unverified regions; vegetation fraction {vegetation:.1%}'})
    return sorted(candidates,key=lambda x:(-x['score'],x['attack']))


def run(path:str|Path, *, attack:str='auto', coverage:str='auto', level:str='balanced',
        seed:int=42, profile:str='auto', assume_scale:float|None=None, allowed:list[str]|None=None,
        selected_auto_policy:str='best')->Result:
    scene=read_scene(path,source_profile=profile,assume_scale=assume_scale)
    if attack!='auto' and attack not in ATTACKS:raise ValueError(f'Unknown attack {attack}')
    if level not in SEVERITIES:raise ValueError('Unknown level '+level)
    ranked=compatible_attacks(scene,allow=allowed)
    if attack=='auto':
        if not ranked: raise ValueError('No compatible attack candidates for scene')
        # Reproducible alternative choices across datasets while still based on scene feasibility.
        top=ranked[:min(3,len(ranked))]
        import hashlib
        digest=int(hashlib.sha256((str(seed)+sha256(path)[:16]).encode()).hexdigest()[:8],16)
        attack=top[digest%len(top)]['attack'] if selected_auto_policy=='diverse' else top[0]['attack']
    elif allowed is not None and attack not in allowed:
        raise ValueError('Selected attack is not in allowed list')
    info=ATTACKS[attack]
    c=normalize_coverage(info,coverage)
    features=analyze(scene,seed)
    output,intended,aux=synthesize(scene,features,attack,c,level,seed)
    changed=np.any(output!=scene.pixels,axis=0)&scene.valid
    meta_change={}
    geo=None
    if attack=='georeference_shift':
        from affine import Affine
        source_transform=scene.profile.get('transform')
        if source_transform is None or not scene.profile.get('crs'):
            raise ValueError('Georeference shift requires a real CRS and affine transform')
        # Simulate footprint offset by 2 columns and 1 row without editing raster samples.
        geo=source_transform*Affine.translation(2,1)
        meta_change={'transform_before':list(source_transform)[:6], 'transform_after':list(geo)[:6]}
    elif not changed.any():
        raise ValueError('Selected attack made no measurable pixel changes on this input')
    frac=float(changed.sum()/max(1,scene.valid.sum()))
    if attack!='georeference_shift' and frac<.00002:
        raise ValueError(f'Changed pixel fraction {frac:.6f} is too small')
    manifest={
        'schema_version':'3.0a1', 'research_only':True,
        'source_name':scene.path.name,'source_sha256':sha256(scene.path),
        'requested_attack':attack, 'executed_attack':attack,'family':info.family,
        'coverage':c,'severity':level,'seed':int(seed),
        'selected_pixels':int(intended.sum()),'edited_pixel_count':int(changed.sum()),
        'edited_fraction':frac,
        'bands':list(scene.bands),'dtype':str(scene.pixels.dtype),
        'source_profile':profile,'assumed_dn_denominator':scene.scale,
        'radiometric_warning':('DN denominator is an assumption, not proof of physical calibration' if assume_scale is not None else None),
        'target_mask_kind':'selected region; not necessarily changed pixels',
        'changed_mask_kind':'actual raster sample changes only',
        'metadata_changes':meta_change,
        'attack_info':aux,'scene_notes':features.notes,
    }
    if features.ndvi is not None and attack!='georeference_shift':
        ix=scene.names
        old=features.ndvi
        red=output[ix['B04']].astype(np.float32);nir=output[ix['B08']].astype(np.float32)
        new=(nir-red)/(nir+red+1e-6)
        relevant=intended&scene.valid
        if relevant.any():manifest['mean_target_ndvi_delta']=round(float(np.mean(new[relevant]-old[relevant])),5)
    return Result(scene,output,intended,changed,attack,c,level,features,manifest,geo)
