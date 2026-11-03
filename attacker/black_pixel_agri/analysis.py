"""Transparent scene heuristics: segments are candidates, NOT verified field polygons."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from scipy import ndimage as ndi
from .raster import Scene, rgb_for_preview

@dataclass
class SceneFeatures:
    ndvi:np.ndarray|None
    vegetation:np.ndarray
    stressed:np.ndarray
    soil:np.ndarray
    candidate_masks:list[np.ndarray]
    rgb:np.ndarray
    notes:list[str]


def candidate_segments(rgb:np.ndarray, valid:np.ndarray, seed:int=42):
    h,w=valid.shape
    masks=[]
    if min(h,w)<16: return masks
    try:
        from skimage.segmentation import slic
        parts=slic(rgb.astype(float)/255., n_segments=max(18, min(220,(h*w)//180)),
                   compactness=11, sigma=.8, start_label=1, channel_axis=-1)
        for id_ in np.unique(parts):
            mask=(parts==id_)&valid
            count=int(mask.sum())
            if max(12,int(h*w*.002)) <= count <= int(h*w*.18): masks.append(mask)
    except ImportError:
        # Dependency-free alternative: color-coherent connected regions, not field boundaries.
        sm=ndi.gaussian_filter(rgb.astype(np.float32),sigma=(1.8,1.8,0))
        grad=np.sqrt(sum(ndi.sobel(sm[:,:,c],axis=ax)**2 for c in range(3) for ax in (0,1)))
        threshold=np.percentile(grad[valid],65) if valid.any() else 0
        interior=(grad<threshold)&valid
        interior=ndi.binary_opening(interior,iterations=1)
        lbl,n=ndi.label(interior)
        for j in range(1,n+1):
            m=(lbl==j)
            count=int(m.sum())
            if max(12,int(h*w*.003))<=count<=int(h*w*.18):
                masks.append(ndi.binary_fill_holes(m)&valid)
    return masks


def analyze(scene:Scene, seed:int=42)->SceneFeatures:
    rgb,_=rgb_for_preview(scene)
    valid=scene.valid
    ndvi=None
    notes=[]
    if scene.calibrated:
        nir=scene.image('B08')
        red=scene.image('B04')
        ndvi=(nir-red)/(nir+red+1e-6)
        veg=valid & (ndvi>.40) & (ndvi<1.01)
        stressed=valid & (ndvi>.12) & (ndvi<.36)
        soil=valid & (ndvi<.18) & (ndvi>-.25)
    else:
        # RGB approximate greenness is not NDVI, use only for content selection.
        r,g,b=np.moveaxis(rgb.astype(np.float32)/255.,-1,0)
        green=(g-r)*.7+(g-b)*.3
        veg=valid & (green > -.015)
        stressed=valid & (green < -.02)
        soil=valid & (green < -.035)
        notes.append('RGB heuristic only: vegetation and soil candidates are NOT agronomic labels')
    masks=candidate_segments(rgb,valid,seed)
    notes.append('Candidate segments are unverified image regions, not cadastral field boundaries')
    return SceneFeatures(ndvi,veg,stressed,soil,masks,rgb,notes)


def select_target(scene:Scene, features:SceneFeatures, purpose:str, coverage:str, seed:int)->np.ndarray:
    rng=np.random.default_rng(seed)
    valid=scene.valid
    h,w=valid.shape
    if coverage=='global': return valid.copy()
    wanted=features.vegetation if purpose in ('drought','harvest') else (
        features.stressed if purpose=='recovery' else valid)
    if wanted.sum() < max(8,int(valid.sum()*.002)):
        raise ValueError(f'No sufficiently large compatible {purpose} region detected')
    best=[]
    for seg in features.candidate_masks:
        cnt=seg.sum()
        if cnt < max(12,int(valid.sum()*.001)) :continue
        fraction=float((seg&wanted).sum()/cnt)
        if fraction >= (.55 if purpose in ('drought','harvest','recovery') else .4):
            score=fraction+.14*rng.random()+min(cnt/valid.size,.08)
            best.append((score,seg))
    if best:
        best.sort(key=lambda t:t[0],reverse=True)
        # Grow a connected set of adjacent superpixels to a meaningful area.
        # This is scene-derived segmentation, NOT verified parcel delineation.
        base=best[0][1].copy()
        target=base.copy()
        goal=int(valid.sum()*(.035 if coverage=='local' else .13))
        rgb=features.rgb.astype(np.float32)/255
        ref=rgb[base].mean(axis=0)
        unused=[m for _,m in best[1:]]
        while target.sum()<goal and unused:
            border=ndi.binary_dilation(target,iterations=2)
            scored=[]
            for i,m in enumerate(unused):
                if not np.any(border&m):continue
                color=float(np.mean(np.abs(rgb[m].mean(axis=0)-ref)))
                scored.append((color-.035*rng.random(),i))
            if not scored:break
            color,i=min(scored)
            if color>.30:break
            target |= unused.pop(i)
        target &= wanted
        if target.sum()>=max(8,int(valid.sum()*.007)):
            return target
    # Fallback: connected candidate from a contextual mask; never present as verified parcel.
    fill=ndi.binary_fill_holes(ndi.binary_closing(wanted,iterations=1))&valid
    labels,n=ndi.label(fill)
    objects=sorted(((np.sum(labels==i),i) for i in range(1,n+1)),reverse=True)
    for area,i in objects:
        if area>=max(12,int(valid.sum()*.004)):
            area_mask=(labels==i)&wanted
            # Region may span most of the image: choose a spatially coherent subset.
            if area_mask.sum() > valid.sum()*(.13 if coverage=='local' else .40):
                yy,xx=np.where(area_mask)
                index=int(rng.integers(len(yy)))
                cy,cx=int(yy[index]),int(xx[index])
                size=max(4,int(min(h,w)*(.12 if coverage=='local' else .25)))
                y0,y1=max(0,cy-size),min(h,cy+size)
                x0,x1=max(0,cx-size),min(w,cx+size)
                subset=np.zeros_like(valid);subset[y0:y1,x0:x1]=True
                area_mask &= subset
            if area_mask.sum()>=8:return area_mask
    raise ValueError('No coherent region large enough; try a larger/agricultural image')
