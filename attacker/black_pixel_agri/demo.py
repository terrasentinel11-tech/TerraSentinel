"""Synthetic toy farm, NEVER a genuine satellite acquisition."""
from pathlib import Path
import numpy as np
import rasterio
from rasterio.transform import from_origin
from .raster import SEN12MS13


def create(output:Path,seed:int=5):
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    rng=np.random.default_rng(seed)
    h=w=256
    arr=np.zeros((13,h,w),dtype=np.uint16)
    xx,yy=np.meshgrid(np.arange(w),np.arange(h))
    # Blocks emulate a patchwork of agricultural fields (not physical imagery).
    palette=[(1000,1800,2400,1100,3100,4000,4900,7200,6900,800,1400,2700,2300),
             (2500,2900,3100,2600,3800,3900,4200,3900,3300,1000,1900,4000,3500),
             (1000,1800,2300,800,4300,4900,5400,8300,7600,700,1700,2000,1600),
             (3200,3200,3000,2400,2800,3000,3100,2700,2800,1200,2000,4200,4400)]
    for y in range(0,h,32):
        for x in range(0,w,40):
            c=np.array(palette[int(rng.integers(len(palette)))],dtype=np.float32)
            tex=(np.sin((xx[y:y+32,x:x+40]+yy[y:y+32,x:x+40])*.9)*50+
                 rng.normal(0,65,size=(min(32,h-y),min(40,w-x))))
            for band in range(13):
                arr[band,y:y+32,x:x+40]=np.clip(c[band]+tex,0,10000).astype(np.uint16)
    with rasterio.open(output,'w',driver='GTiff',height=h,width=w,count=13,dtype='uint16',
                       crs='EPSG:32632',transform=from_origin(500000,5000000,10,10),nodata=0) as ds:
        ds.write(arr)
        for i,b in enumerate(SEN12MS13,1):ds.set_band_description(i,b)
        ds.update_tags(REFLECTANCE_SCALE='10000', SOURCE='SYNTHETIC TEST IMAGE, NOT A REAL ACQUISITION')
    return output
