"""Reproduce the accepted single-image SAM1 tiled draft in an isolated output folder."""
from pathlib import Path
import os,sys,argparse,json,time,hashlib,math,shutil,zipfile
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/experiments/full_image_reproduction_output'
CACHE=ROOT/'docs/experiments/full_image_cache'
ASSETS=ROOT/'docs/assets/full_image_reproduction'
sys.path.insert(0,str(ROOT/'wall2cad_mvp'))
import numpy as np,cv2
from PIL import Image,ImageDraw,ImageFont

SETTINGS={'version':1,'tile_width':2048,'overlap':512,'roi_padding':64,'white_threshold':245,
 'points_per_side':32,'pred_iou_thresh':.88,'stability_score_thresh':.95,
 'crop_n_layers':0,'min_mask_region_area':100,'min_contour_area_px':500,
 'max_contour_fraction_of_tile':.35,'max_white_fraction':.1,
 'internal_tile_edge_margin_px':2,'duplicate_iou':.6,'duplicate_containment':.9,
 'duplicate_min_area_ratio':.6,'review_polygon_overlap_fraction':.05,'dp_perimeter_factor':.012}
IMAGE=ROOT.parent/'inputoutput/building_001_input.jpeg'
CHECKPOINT=Path('/private/tmp/wall2cad-sam_vit_b_01ec64.pth')

def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2))

def plan(image):
    h,w=image.shape[:2];ys,xs=np.where(image[::4,::4].min(2)<SETTINGS['white_threshold'])
    p=SETTINGS['roi_padding'];x0=max(0,int(xs.min()*4)-p);y0=max(0,int(ys.min()*4)-p)
    x1=min(w,int((xs.max()+1)*4)+p);y1=min(h,int((ys.max()+1)*4)+p)
    tw=SETTINGS['tile_width'];step=tw-SETTINGS['overlap'];starts=list(range(x0,max(x0+1,x1-tw+1),step))
    if starts[-1]+tw<x1:starts.append(max(x0,x1-tw))
    tiles=[{'id':f'T{i+1:02d}','xyxy':[x,y0,min(x+tw,x1),y1]} for i,x in enumerate(starts)]
    return {'image_shape':list(image.shape),'roi_xyxy':[x0,y0,x1,y1],'settings':SETTINGS,
      'image_sha256':hashlib.sha256(IMAGE.read_bytes()).hexdigest(),'checkpoint_sha256':hashlib.sha256(CHECKPOINT.read_bytes()).hexdigest(),'tiles':tiles}

def infer(image,run):
    import torch
    from segment_anything import sam_model_registry,SamAutomaticMaskGenerator
    torch.set_num_threads(4);t=time.perf_counter()
    model=sam_model_registry['vit_b'](checkpoint=str(CHECKPOINT)).to('cpu').eval()
    generator=SamAutomaticMaskGenerator(model,points_per_side=32,pred_iou_thresh=.88,
      stability_score_thresh=.95,crop_n_layers=0,box_nms_thresh=.7,min_mask_region_area=100,output_mode='binary_mask')
    load_seconds=time.perf_counter()-t;completed=[]
    cache=CACHE/'tiles';cache.mkdir(exist_ok=True)
    for tile in run['tiles']:
        meta_path=cache/(tile['id']+'.json');mask_path=cache/(tile['id']+'.npz')
        if meta_path.exists() and mask_path.exists():
            m=json.loads(meta_path.read_text())
            if m.get('run_fingerprint')==run['fingerprint']:
                completed.append(m);print('cached',tile['id'],flush=True);continue
        x0,y0,x1,y1=tile['xyxy'];t=time.perf_counter()
        with torch.inference_mode():masks=generator.generate(image[y0:y1,x0:x1])
        elapsed=time.perf_counter()-t
        metadata=[]
        for m in masks:
            metadata.append({k:(v.item() if isinstance(v,np.generic) else v) for k,v in m.items() if k!='segmentation'})
        stack=np.stack([m['segmentation'] for m in masks]) if masks else np.zeros((0,y1-y0,x1-x0),bool)
        np.savez_compressed(mask_path,masks=stack)
        m={'tile':tile,'run_fingerprint':run['fingerprint'],'inference_seconds':elapsed,'masks':metadata}
        save(meta_path,m);completed.append(m)
        save(OUT/'progress.json',{'completed_tiles':len(completed),'total_tiles':len(run['tiles']),
            'last_tile':tile['id'],'raw_masks_so_far':sum(len(c['masks']) for c in completed),
            'inference_seconds_so_far':sum(c['inference_seconds'] for c in completed)})
        print(json.dumps({'tile':tile['id'],'seconds':round(elapsed,2),'masks':len(masks),'completed':len(completed),'total':len(run['tiles'])}),flush=True)
        del masks,stack
    save(OUT/'inference.json',{'model':'SAM 1 ViT-B','device':'cpu','torch_threads':4,'load_seconds_this_run':load_seconds,
       'torch':torch.__version__,'python':sys.version,'total_stored_inference_seconds':sum(m['inference_seconds'] for m in completed),
       'raw_masks':sum(len(m['masks']) for m in completed),'tiles':len(completed)})

def simple_polygon(p):
    def cross(a,b,c):
        u,v=b-a,c-a;return float(u[0]*v[1]-u[1]*v[0])
    def on(a,b,p):return abs(cross(a,b,p))<1e-6 and np.all(p>=np.minimum(a,b)-1e-6) and np.all(p<=np.maximum(a,b)+1e-6)
    for i in range(len(p)):
        a,b=p[i],p[(i+1)%len(p)]
        for j in range(i+1,len(p)):
            if j==i+1 or (i==0 and j==len(p)-1):continue
            c,d=p[j],p[(j+1)%len(p)]
            if cross(a,b,c)*cross(a,b,d)<0 and cross(c,d,a)*cross(c,d,b)<0:return False
            if on(a,b,c) or on(a,b,d) or on(c,d,a) or on(c,d,b):return False
    return True

def intersection(a,b,key='mask'):
    x0=max(a['bbox'][0],b['bbox'][0]);y0=max(a['bbox'][1],b['bbox'][1])
    x1=min(a['bbox'][2],b['bbox'][2]);y1=min(a['bbox'][3],b['bbox'][3])
    if x1<=x0 or y1<=y0:return 0
    aa=a[key][y0-a['bbox'][1]:y1-a['bbox'][1],x0-a['bbox'][0]:x1-a['bbox'][0]]
    bb=b[key][y0-b['bbox'][1]:y1-b['bbox'][1],x0-b['bbox'][0]:x1-b['bbox'][0]]
    return int(np.logical_and(aa,bb).sum())

def finalize(image,run):
    import ezdxf
    ASSETS.mkdir(parents=True,exist_ok=True);candidates=[];rejected=[]
    for tile in run['tiles']:
        tid=tile['id'];meta=json.loads((CACHE/'tiles'/(tid+'.json')).read_text())
        assert meta['run_fingerprint']==run['fingerprint']
        masks=np.load(CACHE/'tiles'/(tid+'.npz'))['masks'];tx,ty,tx1,ty1=tile['xyxy'];tw=tx1-tx;th=ty1-ty
        for index,mask in enumerate(masks):
            rid=f'{tid}_{index:03d}';reason=None
            contours=cv2.findContours(mask.astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)[0]
            if not contours:rejected.append({'source':rid,'reason':'empty'});continue
            contour=max(contours,key=cv2.contourArea);area=float(cv2.contourArea(contour));x,y,w,h=cv2.boundingRect(contour)
            raw=np.zeros((h,w),np.uint8);cv2.fillPoly(raw,[contour-np.array([[[x,y]]])],1);raw=raw.astype(bool)
            white=image[ty+y:ty+y+h,tx+x:tx+x+w].min(2)>=SETTINGS['white_threshold']
            white_fraction=float(white[raw].mean())
            if area<SETTINGS['min_contour_area_px']:reason='small_area'
            elif area>tw*th*SETTINGS['max_contour_fraction_of_tile']:reason='large_region'
            elif white_fraction>SETTINGS['max_white_fraction']:reason='white_background'
            elif (tx>run['roi_xyxy'][0] and x<=2) or (tx1<run['roi_xyxy'][2] and x+w>=tw-2):reason='internal_tile_edge'
            points=cv2.approxPolyDP(contour,cv2.arcLength(contour,True)*.012,True).reshape(-1,2)+[tx,ty]
            if not reason and (len(points)<3 or cv2.contourArea(points.astype(np.float32))<=0 or not simple_polygon(points.astype(float))):reason='invalid_polygon'
            info={'source':rid,'tile_id':tid,'mask_index':index,'bbox':[tx+x,ty+y,tx+x+w,ty+y+h],
              'raw_contour_area_px':area,'white_fraction':white_fraction,
              'stability_score_not_acceptance':float(meta['masks'][index]['stability_score']),
              'predicted_iou_not_accuracy':float(meta['masks'][index]['predicted_iou'])}
            if reason:rejected.append(dict(info,reason=reason));continue
            margin=min(x if tx>run['roi_xyxy'][0] else tw,tw-x-w if tx1<run['roi_xyxy'][2] else tw)
            poly=np.zeros((h,w),np.uint8);cv2.fillPoly(poly,[points-[tx+x,ty+y]],1)
            candidates.append(dict(info,points=points.tolist(),margin=margin,mask=raw,poly=poly.astype(bool),mask_area=int(raw.sum()),polygon_area=int(poly.sum())))
        del masks
    kept=[];duplicates=[]
    # Prefer candidates farther from internal tile edges; model scores break ties only.
    for c in sorted(candidates,key=lambda c:(-c['margin'],-c['stability_score_not_acceptance'],c['source'])):
        dup=None
        for k in kept:
            inter=intersection(c,k)
            if not inter:continue
            small=min(c['mask_area'],k['mask_area']);large=max(c['mask_area'],k['mask_area'])
            iou=inter/(c['mask_area']+k['mask_area']-inter)
            if iou>=.6 or (inter/small>=.9 and small/large>=.6):dup=k;break
        if dup:duplicates.append({'source':c['source'],'retained_source':dup['source']})
        else:kept.append(c)
    kept.sort(key=lambda c:((c['bbox'][0]+c['bbox'][2])/2,(c['bbox'][1]+c['bbox'][3])/2))
    for i,c in enumerate(kept,1):c['id']=f'S{i:03d}';c['overlap_with']=[]
    overlaps=[]
    for i,c in enumerate(kept):
        for k in kept[i+1:]:
            n=intersection(c,k,'poly')
            if n and n/min(c['polygon_area'],k['polygon_area'])>.05:
                c['overlap_with'].append(k['id']);k['overlap_with'].append(c['id'])
                overlaps.append({'a':c['id'],'b':k['id'],'intersection_pixels':n,'fraction_of_smaller':n/min(c['polygon_area'],k['polygon_area'])})
    for c in kept:c['layer']='REVIEW_OVERLAP' if c['overlap_with'] else 'STONE_CANDIDATE'
    serial=[{k:v for k,v in c.items() if k not in ['mask','poly']} for c in kept]
    save(OUT/'candidates.json',serial);save(OUT/'rejected.json',rejected);save(OUT/'duplicates.json',duplicates);save(OUT/'overlaps.json',overlaps)
    bundle=OUT/'cad_bundle';bundle.mkdir(exist_ok=True)
    shutil.copyfile(IMAGE,bundle/IMAGE.name)
    save(bundle/'candidates.json',serial)
    assert hashlib.sha256((bundle/IMAGE.name).read_bytes()).hexdigest()==run['image_sha256']
    h,w=image.shape[:2];dxfchecks={}
    for with_image in [False,True]:
        name='building_001_candidates'+('_with_image' if with_image else '')+'.dxf'
        doc=ezdxf.new('R2010');doc.units=0
        doc.layers.new('STONE_CANDIDATE',dxfattribs={'color':3});doc.layers.new('REVIEW_OVERLAP',dxfattribs={'color':1})
        msp=doc.modelspace()
        if with_image:
            doc.layers.new('SOURCE_IMAGE')
            image_def=doc.add_image_def(filename=IMAGE.name,size_in_pixel=(w,h))
            msp.add_image(image_def,insert=(0,0),size_in_units=(w,h),dxfattribs={'layer':'SOURCE_IMAGE'})
        for c in kept:
            p=np.array(c['points'],float);p[:,1]=h-p[:,1]
            e=msp.add_lwpolyline(p.tolist(),close=True,dxfattribs={'layer':c['layer']})
            if 'WALL2CAD_REVIEW' not in doc.appids:doc.appids.new('WALL2CAD_REVIEW')
            e.set_xdata('WALL2CAD_REVIEW',[(1000,c['id']),(1000,c['source'])])
        path=bundle/name;doc.saveas(path);check=ezdxf.readfile(path);audit=check.audit();entities=list(check.modelspace().query('LWPOLYLINE'))
        assert check.units==0 and len(entities)==len(kept) and all(e.closed for e in entities)
        assert not audit.errors and not audit.fixes
        for e,c in zip(entities,kept):
            p=np.array(e.get_points('xy'));p[:,1]=h-p[:,1]
            assert np.allclose(p,np.array(c['points']),rtol=0,atol=1e-7)
        if with_image:
            assert len(check.modelspace().query('IMAGE'))==1
            e=check.modelspace().query('IMAGE')[0];idef=check.entitydb[e.dxf.image_def_handle]
            assert idef.dxf.filename==IMAGE.name
            assert tuple(e.dxf.insert)[:2]==(0,0)
        dxfchecks[name]={'closed_polylines':len(entities),'audit_errors':0,'audit_fixes':0,'coordinate_roundtrip':True,'image_reference':with_image}
    note='''Wall2CAD 전체 사진 검토 초안 — 납품 도면 아님

building_001_candidates_with_image.dxf: 같은 폴더의 JPEG를 상대 경로로 참조합니다.
building_001_candidates.dxf: 윤곽만 있습니다.
AutoCAD에서 실제로 열어 본 것은 아닙니다. 이미지가 보이지 않으면 같은 폴더의 JPEG를 다시 연결하세요.

단위는 Unitless, 1 도면 단위 = 원본 사진 1 픽셀입니다. 실측 mm 좌표가 아닙니다.
이미지 왼쪽 아래 (0,0), 폭 13788, 높이 2574. 별도 실측 정합이 필요합니다.
STONE_CANDIDATE: 일반 검토 후보. 돌로 확정한 레이어가 아닙니다.
REVIEW_OVERLAP: 다른 후보와 많이 겹치는 검토 대상. 중복/합쳐진 돌/실제 가림 여부를 확인하세요.
사진에서 잘린 돌, 식생 뒤 돌, 앞면과 뒤쪽 경계, 누락/오검출을 사람이 검토해야 합니다.
후보 번호는 비교 이미지와 candidates.json 및 DXF 엔티티의 WALL2CAD_REVIEW 확장 데이터에 있습니다.
'''
    (bundle/'READ_ME.txt').write_text(note,encoding='utf-8')
    with zipfile.ZipFile(OUT/'building_001_review_bundle.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(bundle.iterdir()):z.write(p,arcname='building_001_review/'+p.name)
    # Pixel overlays retain the original image geometry; no generative editing.
    canvas=Image.fromarray(image);draw=ImageDraw.Draw(canvas)
    for c in kept:
        p=[tuple(v) for v in c['points']];color='#ff3b3b' if c['overlap_with'] else '#00e8b5'
        draw.line(p+[p[0]],fill=color,width=5,joint='curve')
    canvas.save(ASSETS/'full_overlay.jpg',quality=93)
    roi=run['roi_xyxy'];overview=canvas.crop(tuple(roi));overview.thumbnail((3200,1100));overview.save(ASSETS/'overview.jpg',quality=93)
    font=ImageFont.load_default()
    # Four pages, with horizontal overlap, provide legible IDs and original-photo comparison.
    pages=[];part=(roi[2]-roi[0])/4
    for i in range(4):
        x0=max(roi[0],int(roi[0]+i*part)-100);x1=min(roi[2],int(roi[0]+(i+1)*part)+100)
        bounds=(x0,roi[1],x1,roi[3]);labelled=canvas.crop(bounds);ld=ImageDraw.Draw(labelled)
        ids=[]
        for c in kept:
            pts=np.array(c['points']);cx,cy=pts.mean(0)
            if x0<=cx<x1:
                ids.append(c['id']);ld.text((cx-x0,cy-roi[1]),c['id'],font=font,fill='white',stroke_width=2,stroke_fill='black')
        labelled.thumbnail((1800,1100));labelled.save(ASSETS/f'section_{i+1:02d}_overlay.jpg',quality=94)
        photo=Image.fromarray(image).crop(bounds);photo.thumbnail((1800,1100));photo.save(ASSETS/f'section_{i+1:02d}_photo.jpg',quality=94)
        pages.append({'section':i+1,'bounds_original_xyxy':list(bounds),'candidate_ids':ids})
    save(OUT/'sections.json',pages)
    inference=json.loads((OUT/'inference.json').read_text())
    from collections import Counter
    summary={'run_fingerprint':run['fingerprint'],'raw_masks':inference['raw_masks'],'filtered_candidates_before_dedup':len(candidates),
      'rejected_counts':dict(Counter(r['reason'] for r in rejected)),'duplicate_candidates_removed':len(duplicates),
      'exported_candidates':len(kept),'overlap_review_candidates':sum(bool(c['overlap_with']) for c in kept),
      'overlap_pairs':len(overlaps),'tiles':len(run['tiles']),'total_inference_seconds':inference['total_stored_inference_seconds'],
      'dxf_checks':dxfchecks,'semantically_verified_stones':None,'human_review_time_minutes':None,
      'limitations':['No target DXF registration or accuracy score','Pixel units, not measured CAD units','No front-face or vegetation completion model','Overlap flags do not classify the cause','AutoCAD UI not tested']}
    save(OUT/'summary.json',summary);print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=['plan','infer','finalize','all'],default='all');parser.add_argument('--checkpoint',type=Path,default=CHECKPOINT);args=parser.parse_args()
    CHECKPOINT=args.checkpoint
    OUT.mkdir(parents=True,exist_ok=True);CACHE.mkdir(parents=True,exist_ok=True)
    image=np.array(Image.open(IMAGE).convert('RGB'));run=plan(image)
    run['fingerprint']=hashlib.sha256(json.dumps(run,sort_keys=True).encode()).hexdigest()
    save(OUT/'plan.json',run)
    print(json.dumps({'stage':args.stage,'roi':run['roi_xyxy'],'tiles':len(run['tiles'])}),flush=True)
    if args.stage in ['infer','all']:infer(image,run)
    if args.stage in ['finalize','all']:finalize(image,run)
