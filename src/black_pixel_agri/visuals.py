"""Single consistent RGB stretch for scientific before/after comparisons."""
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi
from .raster import rgb_for_preview


def preview(result, path:str|Path, *, min_panel_px:int=260):
    original,stretch=rgb_for_preview(result.scene)
    attacked,_=rgb_for_preview(result.scene,result.output,stretch=stretch)
    actual=result.changed_mask
    if result.attack=='georeference_shift':
        actual=np.zeros_like(actual)
    boundary=actual & ~ndi.binary_erosion(actual,iterations=1)
    center=original.copy()
    center[boundary]=np.array([255,225,0],dtype=np.uint8)
    panels=[original,center,attacked]
    h,w=original.shape[:2]
    factor=max(1,int(np.ceil(min_panel_px/max(h,w))))
    panel_w=w*factor;panel_h=h*factor
    margin=12;top=56;bottom=34
    width=3*panel_w+4*margin
    canvas=Image.new('RGB',(width,top+panel_h+bottom),(16,20,27))
    draw=ImageDraw.Draw(canvas)
    names=['ORIGINAL','ACTUAL ATTACK REGION','ATTACKED']
    for i,(p,name) in enumerate(zip(panels,names)):
        x=margin+i*(panel_w+margin)
        img=Image.fromarray(p).resize((panel_w,panel_h),Image.Resampling.NEAREST if factor>1 else Image.Resampling.BICUBIC)
        canvas.paste(img,(x,top))
        draw.text((x+3,17),name,fill=(240,246,248))
    if result.attack=='georeference_shift':
        draw.text((margin+panel_w+margin+5,top+8),'METADATA ONLY: pixels unchanged',fill=(255,229,90))
    draw.text((margin,top+panel_h+10),f'{result.attack}  |  {result.level}  |  {int(result.changed_mask.sum())} changed pixels',fill=(190,200,210))
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    canvas.save(path)
    return path


def difference_map(result,path:str|Path):
    before=result.scene.pixels.astype(np.float32)
    after=result.output.astype(np.float32)
    dif=np.max(np.abs(after-before),axis=0)
    if np.max(dif)>0:dif=np.clip(dif/(np.percentile(dif[result.changed_mask],97)+1e-6),0,1)
    vis=np.uint8(dif*255)
    rgb=np.stack([vis,(vis*.48).astype(np.uint8),np.zeros_like(vis)],axis=-1)
    out=Path(path);out.parent.mkdir(parents=True,exist_ok=True)
    Image.fromarray(rgb).save(out)
    return out
