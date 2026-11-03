"""Streamlit test UI. Run: python -m streamlit run app.py"""
from pathlib import Path
import tempfile,json
import numpy as np
import streamlit as st
from PIL import Image
from black_pixel_agri.engine import run,compatible_attacks,ATTACKS
from black_pixel_agri.raster import read_scene,export_tiff
from black_pixel_agri.visuals import preview,difference_map
from black_pixel_agri.dataset import build

st.set_page_config(page_title='BLACK PIXEL AGRI — Research Lab',layout='wide')
st.title('BLACK PIXEL AGRI')
st.caption('Offline research laboratory • synthetic manipulation ground truth • no operational satellite access')
lab,batch,catalog=st.tabs(['Attack Lab','Dataset Forge','Attack Catalog'])
with lab:
    upload=st.file_uploader('Upload GeoTIFF / TIFF',type=['tif','tiff'])
    one,two,three=st.columns(3)
    with one:src_profile=st.selectbox('Source profile',['auto','sen12ms-cr','eurosat','rgb'],key='p1')
    with two:scale_ok=st.checkbox('I explicitly confirm DN/10000 as an experimental assumption',key='c1')
    with three:scale=10000.0 if scale_ok else None
    if upload:
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/upload.name;src.write_bytes(upload.getbuffer())
            try:
                scene=read_scene(src,source_profile=src_profile,assume_scale=scale)
                st.caption(f'{scene.pixels.shape[2]}×{scene.pixels.shape[1]}, {scene.pixels.shape[0]} bands, {scene.pixels.dtype}, CRS: {scene.profile.get("crs")}')
                candidates=compatible_attacks(scene)
                st.subheader('Automatic attack selection')
                st.caption('The engine analyzes the image and picks a compatible attack automatically. No manual attack selection is required.')
                if candidates:
                    st.info(f"Top scene recommendation: {candidates[0]['attack']} (heuristic score {candidates[0]['score']:.2f}; not a success probability)")
                else:
                    st.warning('No compatible attacks found for this image; no attack will be executed.')
                selected='auto'
                c1,c2,c3=st.columns(3)
                with c1:coverage=st.selectbox('Coverage',['auto','local','regional','global'])
                with c2:level=st.selectbox('Intensity',['balanced','subtle','strong','extreme','expert','auto'])
                with c3:seed=st.number_input('Reproducibility seed',value=42,step=1)
                if st.button('Analyze and auto-generate attack',type='primary',disabled=not bool(candidates)):
                    try:
                        result=run(src,attack=selected,coverage=coverage,level=level,seed=int(seed),
                                   profile=src_profile,assume_scale=scale)
                        st.success(f'Generated: {result.attack} • {result.coverage} • {result.level}')
                        pp=preview(result,Path(d)/'preview.png')
                        st.image(str(pp),use_container_width=True)
                        cc1,cc2=st.columns(2)
                        with cc1:st.image(str(difference_map(result,Path(d)/'difference.png')),caption='Real pixel difference map',width=340)
                        with cc2:st.json(result.manifest)
                        out=Path(d)/'attacked.tif'
                        export_tiff(result.scene,out,result.output,transform=result.geo_transform)
                        st.download_button('Download attacked TIFF',out.read_bytes(),file_name='attacked.tif')
                        st.download_button('Download 3-panel preview PNG',pp.read_bytes(),file_name='preview.png')
                        import io
                        buf=io.BytesIO()
                        np.savez_compressed(buf,actual=result.changed_mask,selected=result.selected_mask)
                        st.download_button('Download ground truth masks NPZ',buf.getvalue(),file_name='masks.npz')
                    except Exception as e:st.error(f'Attack not executed: {e}')
            except Exception as e:st.error(f'Cannot inspect input: {e}')
with batch:
    st.subheader('Dataset Forge — Option A (Original TIFF + Attacked TIFF + Preview PNG)')
    source_paths=st.text_area('Source folder paths (one per line)',help='Extract archive first; do not enter .tar.gz as an input')
    target_folder=st.text_input('Output folder',value='BLACK_PIXEL_DATASET_10K')
    source_profile2=st.selectbox('Dataset source profile',['auto','sen12ms-cr','eurosat','rgb'],key='p2')
    scale_ok2=st.checkbox('Confirm experimental DN/10000 denominator',key='c2')
    selected_attacks=list(ATTACKS)
    st.caption(f'Automatic selection enabled: all {len(selected_attacks)} registered attacks are available. Each input receives only one compatible attack.')
    count=st.number_input('Target number of successful pairs',min_value=1,max_value=10000,value=20)
    quotas_text=st.text_input('Optional per-attack quotas (JSON)',value='',help='Example: {"cloud_injection":5000,"atmospheric_haze":5000}')
    batchmode='auto'
    st.caption('Selection: automatic (no manual attack choice).')
    if st.button('Generate or Resume Dataset',type='primary'):
        progress=st.progress(0)
        try:
            report=build([s.strip() for s in source_paths.splitlines() if s.strip()],target_folder,
                         total=int(count),attacks=selected_attacks,selection=batchmode,
                         profile=source_profile2,assume_scale=10000. if scale_ok2 else None,
                         quotas=json.loads(quotas_text) if quotas_text.strip() else None,
                         on_progress=lambda done,total,scanned,files:progress.progress(min(1,done/total)))
            st.json(report)
            if report['shortfall']:st.warning('Requested target not reached. Check skipped.csv and source compatibility.')
        except Exception as e:st.error(str(e))
with catalog:
    st.dataframe([{'Attack':info.name,'Family':info.family,'Coverage':', '.join(info.coverages),
                   'Bands':', '.join(info.band_requirement) or 'None','Description':info.description}
                  for info in ATTACKS.values()],hide_index=True,use_container_width=True)
    st.caption('Available methods are experimental. Large GAN/SAR/temporal models are not included in this milestone.')
