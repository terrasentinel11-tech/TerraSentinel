"""Resumable Option-A original/attacked/preview dataset builder."""
from __future__ import annotations
import csv, json, shutil
from pathlib import Path
from collections import Counter
import numpy as np
from PIL import Image
from .engine import run, ATTACKS, compatible_attacks
from .raster import read_scene
from .raster import export_tiff, sha256
from .visuals import preview

COLUMNS=['pair_id','source','source_sha256','attack','family','coverage','level','original_path','attacked_path','preview_path','changed_pixels','changed_fraction','status']


def discover(inputs):
    files=[]
    for raw in inputs:
        p=Path(raw)
        if p.is_file() and p.suffix.lower() in ('.tif','.tiff'):files.append(p)
        elif p.is_dir():files.extend(f for f in p.rglob('*') if f.is_file() and f.suffix.lower() in ('.tif','.tiff'))
        else:raise FileNotFoundError(str(p))
    return sorted(set(p.resolve() for p in files))


def _read_csv(path):
    with path.open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))


def build(inputs, output, *, total:int=20, attacks:list[str]|None=None,
          selection:str='auto', coverage='auto', level='balanced',
          profile='auto', assume_scale=None, seed:int=42,
          max_sources:int|None=None, on_progress=None, quotas:dict|None=None):
    if total<=0:raise ValueError('total must be positive')
    if selection not in ('auto','manual'):raise ValueError('selection must be auto or manual')
    allowed=attacks or list(ATTACKS)
    unknown=[name for name in allowed if name not in ATTACKS]
    if unknown:raise ValueError('Unknown attacks: '+','.join(unknown))
    if selection=='manual' and len(allowed)!=1:
        raise ValueError('Manual dataset mode requires one attack; use auto to distribute a selection')
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    summary=out/'dataset_summary.csv'; skipped=out/'skipped.csv'
    settings={'sources':[str(Path(a).resolve()) for a in inputs], 'attacks':allowed,
              'selection':selection,'coverage':coverage,'level':level,'profile':profile,
              'assumed_scale':assume_scale,'seed':seed,'quotas':quotas}
    settings_file=out/'campaign_config.json'
    if settings_file.exists():
        old=json.loads(settings_file.read_text(encoding='utf-8'))
        if old!=settings:
            raise ValueError('Existing campaign uses different settings. Choose a new output folder or restore the original settings.')
    else:
        settings_file.write_text(json.dumps(settings,indent=2),encoding='utf-8')
    rows=_read_csv(summary) if summary.exists() else []
    skip_rows=_read_csv(skipped) if skipped.exists() else []
    completed_sources=set(row['source'] for row in rows)
    completed_sources.update(row['source'] for row in skip_rows)
    counters=Counter(r['attack'] for r in rows)
    files=discover(inputs)
    if max_sources:files=files[:max_sources]
    for index,source in enumerate(files):
        if len(rows)>=total:break
        if str(source) in completed_sources:continue
        if selection=='manual':method=allowed[0]
        else:
            method='auto'
            if quotas:
                allowed_now=[name for name in allowed if counters[name]<int(quotas.get(name,total))]
                if not allowed_now:break
            else:allowed_now=allowed
        pair_id=f'pair_{len(rows)+1:06d}'
        try:
            if selection=='manual':
                result=run(source,attack=method,coverage=coverage,level=level,seed=seed+index,
                           profile=profile, assume_scale=assume_scale,allowed=allowed)
            else:
                scene=read_scene(source,source_profile=profile,assume_scale=assume_scale)
                candidates=compatible_attacks(scene,allow=allowed_now)
                if not candidates:raise ValueError('No suitable selected attack for this image')
                candidates.sort(key=lambda c:(counters[c['attack']] / max(1,int(quotas.get(c['attack'],total))) if quotas else counters[c['attack']],
                                              -c['score']))
                errors=[]
                result=None
                for candidate in candidates:
                    try:
                        result=run(source,attack=candidate['attack'],coverage=coverage,level=level,
                                   seed=seed+index,profile=profile,assume_scale=assume_scale,allowed=allowed_now)
                        break
                    except ValueError as e:errors.append(f"{candidate['attack']}: {e}")
                if result is None:raise ValueError('No feasible attack on this image; '+'; '.join(errors[:3]))
            folder=out/result.attack
            folder.mkdir(exist_ok=True)
            rel_o=f'{result.attack}/{pair_id}_original.tif'
            rel_a=f'{result.attack}/{pair_id}_attacked.tif'
            rel_p=f'{result.attack}/{pair_id}_preview.png'
            o=out/rel_o;a=out/rel_a;p=out/rel_p
            if any(f.exists() for f in (o,a,p)):
                raise ValueError('Output collision; do not overwrite existing pair')
            maskdir=out/'private_ground_truth';maskdir.mkdir(exist_ok=True)
            try:
                shutil.copy2(source,o)
                export_tiff(result.scene,a,result.output,transform=result.geo_transform)
                preview(result,p)
                if not all(f.is_file() and f.stat().st_size>0 for f in (o,a,p)):
                    raise IOError('Incomplete outputs')
                if sha256(source)!=sha256(o):raise IOError('Original image copy changed')
                np.savez_compressed(maskdir/f'{pair_id}_masks.npz',
                                    actual=result.changed_mask,selected=result.selected_mask)
                (maskdir/f'{pair_id}_manifest.json').write_text(json.dumps(result.manifest,indent=2),encoding='utf-8')
            except Exception:
                for f in [o,a,p,maskdir/f'{pair_id}_masks.npz',maskdir/f'{pair_id}_manifest.json']:
                    f.unlink(missing_ok=True)
                raise
            rows.append(dict(pair_id=pair_id, source=str(source),source_sha256=result.manifest['source_sha256'],
                             attack=result.attack,family=result.manifest['family'],coverage=result.coverage,
                             level=result.level,original_path=rel_o,attacked_path=rel_a,preview_path=rel_p,
                             changed_pixels=result.manifest['edited_pixel_count'],
                             changed_fraction=result.manifest['edited_fraction'],status='complete'))
            counters[result.attack]+=1
            completed_sources.add(str(source))
            _save_rows(summary,COLUMNS,rows)
        except Exception as exc:
            skip_rows.append(dict(source=str(source),reason=str(exc)))
            completed_sources.add(str(source))
            _save_rows(skipped,['source','reason'],skip_rows)
        if on_progress:on_progress(len(rows),total,index+1,len(files))
    report={'requested_pairs':total,'completed_pairs':len(rows),
            'shortfall':max(0,total-len(rows)),'skipped_sources':len(skip_rows),
            'counts_by_attack':dict(counters),
            'output_structure':'attack_folder/pair_ID_original.tif, pair_ID_attacked.tif, pair_ID_preview.png',
            'calibration_assumption':assume_scale,
            'dataset_source_count':len(files)}
    (out/'dataset_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


def _save_rows(path, columns, rows):
    tmp=path.with_suffix('.tmp')
    with tmp.open('w',newline='',encoding='utf-8') as f:
        wr=csv.DictWriter(f,fieldnames=columns)
        wr.writeheader();wr.writerows(rows)
    tmp.replace(path)
