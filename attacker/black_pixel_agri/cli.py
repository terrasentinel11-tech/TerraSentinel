"""Windows-friendly command line for offline experimental runs and datasets."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
from .engine import run, compatible_attacks, ATTACKS
from .raster import read_scene, export_tiff
from .visuals import preview,difference_map
from .dataset import discover,build


def main(argv=None):
    p=argparse.ArgumentParser(description='BLACK PIXEL AGRI offline experimental laboratory')
    sub=p.add_subparsers(dest='command',required=True)
    scan=sub.add_parser('scan',help='Inspect dataset recursively')
    scan.add_argument('--input',nargs='+',required=True)
    scan.add_argument('--limit',type=int,default=10)
    one=sub.add_parser('run',help='Execute one attack on one image')
    one.add_argument('--input',required=True)
    one.add_argument('--output',required=True)
    one.add_argument('--attack',default='auto',choices=['auto',*ATTACKS])
    one.add_argument('--coverage',default='auto',choices=['auto','local','regional','global'])
    one.add_argument('--level',default='balanced',choices=['auto','subtle','balanced','strong','extreme','expert'])
    one.add_argument('--seed',type=int,default=42)
    batch=sub.add_parser('build',help='Generate original/attacked GeoTIFF pairs')
    batch.add_argument('--input',nargs='+',required=True)
    batch.add_argument('--output',required=True)
    batch.add_argument('--total',type=int,default=20)
    batch.add_argument('--attacks',default='cloud_injection,field_patch_replacement,atmospheric_haze')
    batch.add_argument('--selection',default='auto',choices=['auto','manual'])
    batch.add_argument('--coverage',default='auto',choices=['auto','local','regional','global'])
    batch.add_argument('--level',default='balanced',choices=['auto','subtle','balanced','strong','extreme','expert'])
    batch.add_argument('--seed',type=int,default=42)
    batch.add_argument('--max-sources',type=int,default=0)
    batch.add_argument('--quotas',default='',help='Optional JSON object e.g. {"cloud_injection":2500,"field_patch_replacement":2500}')
    for cmd in [one,batch]:
        cmd.add_argument('--profile',default='auto',choices=['auto','rgb','eurosat','sen12ms-cr'])
        cmd.add_argument('--assume-scale',type=float,default=None,help='Explicit unverified DN denominator; use only when documented')
    demo=sub.add_parser('make-demo',help='Create a labeled SYNTHETIC agricultural GeoTIFF')
    demo.add_argument('--output',default='examples/synthetic_farms.tif')
    args=p.parse_args(argv)
    if args.command=='scan':
        paths=discover(args.input)
        print('GeoTIFF/TIFF files:',len(paths))
        for f in paths[:args.limit]:
            try:
                scene=read_scene(f)
                print(str(f),scene.pixels.shape,scene.pixels.dtype,scene.bands,'CRS:',scene.profile.get('crs'))
            except Exception as e:print(str(f),'ERROR:',e)
    elif args.command=='make-demo':
        from .demo import create
        print(create(Path(args.output)))
    elif args.command=='run':
        result=run(args.input,attack=args.attack,coverage=args.coverage,level=args.level,
                   seed=args.seed,profile=args.profile,assume_scale=args.assume_scale)
        out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
        export_tiff(result.scene,out/'attacked.tif',result.output,transform=result.geo_transform)
        preview(result,out/'preview.png')
        difference_map(result,out/'difference.png')
        np.savez_compressed(out/'ground_truth.npz',actual=result.changed_mask,selected=result.selected_mask)
        (out/'manifest.json').write_text(json.dumps(result.manifest,indent=2),encoding='utf-8')
        print(json.dumps({'attack':result.attack,'edited_pixels':result.manifest['edited_pixel_count'],'output':str(out)},indent=2))
    elif args.command=='build':
        report=build(args.input,args.output,total=args.total,attacks=args.attacks.split(','),
                     selection=args.selection,coverage=args.coverage,level=args.level,
                     profile=args.profile,assume_scale=args.assume_scale,seed=args.seed,
                     max_sources=args.max_sources or None,quotas=json.loads(args.quotas) if args.quotas else None,
                     on_progress=lambda done,total,scanned,allfiles:print(f'\r{done}/{total} successful pairs, {scanned}/{allfiles} sources scanned',end='',flush=True))
        print('\n'+json.dumps(report,indent=2))

if __name__=='__main__':main()
