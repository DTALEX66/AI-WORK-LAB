from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import json,hashlib,re,html
ROOT=Path(__file__).resolve().parents[1]
def write(name,obj): (ROOT/'specs'/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
s=(ROOT/'prototype/r2.js').read_text()
registry=re.search(r'const DOMAIN_REGISTRY=(\[.*?\]);',s).group(1)
registry=json.loads(registry.replace("'",'"'))
write('navigation.json',{'version':'UI-20261009-r2','status':'UI_REFERENCE_CONFIG','id_rule':'UI alias only; map to existing canonical domain IDs; not a replacement domain registry','primary':[{'id':'assets','label':'能力资产','prototype_route':'catalog','secondary':'domains'},{'id':'make','label':'分析与制作','prototype_route':'input','secondary':['新建需求','制作记录与待继续','导入教学需求']},{'id':'outputs','label':'成果与反馈','prototype_route':'results','secondary':['全部成果','版本审阅','交付预检','反馈与候选']}],'domains':[{'ui_alias':i,'label':n} for i,n in registry],'asset_types':['全部资产','可调用能力','规范与方法','案例与参考','模板与配方'],'facets':['design domain','asset type','scene','style','method','software candidate','delivery type','actual qualification'],'auxiliary':'连接与设置','record_rule':'one identity with multiple domain associations; no per-domain duplicates','mobile':'bottom primary navigation plus in-page domain selector'})
tokens=json.loads((ROOT/'specs/R1_tokens_reference.json').read_text());tokens['version']='UI-20261009-r2';tokens['layout']={'sidebar':256,'compact_sidebar':216,'topbar':64,'mobile_topbar':60,'desktop_gutter':30,'compact_gutter':22,'mobile_gutter':16,'mobile_nav_height':72,'drawer_width':450,'breakpoints':[768,1200,1700],'grid_columns':{'mobile':1,'compact':2,'desktop':3,'wide':4},'activity_dock_min_height':54};tokens['typography']['size_css_px'].update(h1=27,h1_mobile=23);write('design_tokens.json',tokens)
work=[('W01','P0','壳层与上下文导航',['DL-FINAL-T06','DL-FINAL-T08'],'常驻3主入口；完整领域入口；手机领域选择；两个层级；保留品牌'),('W02','P0','能力目录与详情',['DL-FINAL-T06','DL-FINAL-T07','DL-FINAL-T08'],'分类轴映射；交叉去重；组合检索；抽屉关闭保留位置与条件；原生组件'),('W03','P0','制作上下文与草稿',['DL-FINAL-T08','DL-FINAL-T09'],'新建/恢复正确身份；多领域标签；多字段持久化；文件引用与知识版本'),('W04','P1','制作记录与真实状态',['DL-FINAL-T10','DL-FINAL-T11','DL-FINAL-T13','DL-FINAL-T15'],'读既有任务；当前任务条；真实暂停/取消；恢复先对账'),('W05','P1','成果检索、评审与交付',['DL-FINAL-T08','DL-FINAL-T12','DL-FINAL-T14'],'领域和输出组合检索；准确版本；资格未知不当成功；评审与交付回执'),('W06','P2','跨设备、素材与状态验收',['DL-FINAL-T08','DL-FINAL-T13','DL-FINAL-T14'],'390/768/1366/1920 px；焦点键盘；深浅主题；权限和网络状态；素材清单与来源')]
write('implementation_tasks.json',{'version':'UI-20261009-r2','kind':'FRONTEND_INCREMENTAL_WORK_MAPPING','ledger_rule':'Map work into existing single DL-FINAL ledger; W IDs are implementation notes, not new business tasks','source_mapping':'specs/r1/page_tasks.json; actual repository ledger wins','status':'REFERENCE_COMPLETED_PRODUCTION_IMPLEMENTATION_PENDING','work_items':[{'work_item':i,'priority':pr,'title':t,'parent_tasks':pt,'acceptance':a} for i,pr,t,pt,a in work]})
labels={'01_catalog_all':'能力资产 / 全领域','02_catalog_audio':'音频领域 / 多领域关联','03_audio_detail_drawer':'声音能力 / 侧边详情','04_execution_empty':'未验证执行 / 空结果','05_catalog_three':'3D 建模与渲染','06_facets':'领域＋软件组合筛选','07_catalog_brand':'品牌与 VI','08_catalog_list':'列表布局','09_cross_domain_input':'跨领域任务 / 输入与交付','09_cross_domain_input_full':'跨领域任务 / 完整长页','10_domain_multiselect':'任务领域 / 多选','11_records':'制作记录与待继续','12_results':'成果检索','13_global_search':'全局搜索 / 三类对象','14_catalog_light':'浅色主题','15_mobile_audio':'手机音频领域','16_mobile_input':'手机制作输入','16_mobile_input_full':'手机制作 / 完整长页','17_mobile_results':'手机成果','18_tablet_catalog':'平板能力目录','19_catalog_4k':'4K 目录首屏'}
route={'01':'catalog','02':'catalog?domain=audio','03':'catalog?domain=audio + detail(audio)','04':'catalog?domain=audio + execution filter','05':'catalog?domain=three','06':'catalog?domain=three + software Photoshop','07':'catalog?domain=brand','08':'catalog?domain=brand + list','09':'input','10':'input + domain dialog','11':'records','12':'results','13':'catalog + global search','14':'catalog?theme=light','15':'catalog?domain=audio','16':'input','17':'results','18':'catalog','19':'catalog'}
screens=[]
for p in sorted((ROOT/'screens').glob('*.png')):
 if p.stem=='00_overview': continue
 im=Image.open(p);factor=2 if p.stem=='19_catalog_4k' else 1
 vp=[1920,1080] if factor==2 else ([390,844] if p.stem.startswith(('15','16','17')) else [768,1024] if p.stem.startswith('18') else [1440,1000])
 screens.append({'file':'screens/'+p.name,'label':labels[p.stem],'prototype_state':route[p.stem[:2]],'pixels':list(im.size),'css_viewport':vp,'deviceScaleFactor':factor,'full_page':p.stem.endswith('_full'),'coordinate_rule':'image pixel = CSS coordinate * deviceScaleFactor; long page uses page coordinates'})
write('screen_map.json',{'version':'UI-20261009-r2','screens':screens})
assets=[]
for p in sorted((ROOT/'assets/art').glob('*')):
 size=[960,600] if p.suffix=='.svg' else list(Image.open(p).size)
 assets.append({'file':str(p.relative_to(ROOT)),'pixels_or_viewbox':size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'source':'R2 code-native illustration' if p.stem.split('_')[0] in ['three-study','video-study','audio-study','game-study'] else 'R1 inherited reference illustration','usage':'media illustration, not proof of executed native deliverable','edit':'SVG first; UI controls and text rebuilt as components','rights':'new study artwork for this UI task; do not infer license for user brand or third-party material'})
write('asset_manifest.json',{'version':'UI-20261009-r2','assets':assets,'brand':'Inherited user concept board unchanged; production reuses approved standalone logo','fonts':'Licenses retained in assets/fonts','new_art_prompts':{'three-study':'银蓝几何三维形体、深蓝网格与相机/材质示意，保持当前构图；不生成工程证明','video-study':'三格分镜、几何产品主体、底部双层时间轨道；无软件窗口或状态控件','audio-study':'旁白、音乐、音效三条波形与播放定位线；示意波形，不生成虚构音频文件','game-study':'等轴层级场景、几何建筑与互动焦点；不生成实际引擎或游戏界面'},'generation_rule':'Only replace a single content illustration if needed; use SVG for exact geometry and editable text; never generate a whole UI image as implementation'})
# Contact sheet from exact UI captures; no diagram facts invented.
chosen=['01_catalog_all','02_catalog_audio','03_audio_detail_drawer','09_cross_domain_input','12_results','15_mobile_audio']
canvas=Image.new('RGB',(1800,1290),'#eaf0f6');d=ImageDraw.Draw(canvas);fontpath=ROOT/'assets/fonts/DroidSansFallback.ttf';f=ImageFont.truetype(str(fontpath),25);small=ImageFont.truetype(str(fontpath),17)
d.text((40,24),'DESIGN-LAB UI R2 · 领域入口、制作上下文与交付检索',font=f,fill='#17344b')
for j,key in enumerate(chosen):
 x=40+(j%3)*580;y=85+(j//3)*570
 d.rounded_rectangle((x,y,x+550,y+535),radius=12,fill='white',outline='#cfdae5',width=2)
 d.text((x+16,y+13),labels[key],font=small,fill='#17344b')
 im=Image.open(ROOT/'screens'/f'{key}.png').convert('RGB');im.thumbnail((518,465))
 canvas.paste(im,(x+(550-im.width)//2,y+58))
d.text((40,1235),'参考 UI 已验证；真实服务与软件执行待接入。包内提供独立 SVG、4K PNG 和组件映射。',font=small,fill='#4f657b')
canvas.save(ROOT/'screens/00_overview.png')
# Browsable gallery.
items=''.join(f'<article><h2>{html.escape(x["label"])}</h2><p>{x["pixels"][0]} × {x["pixels"][1]} · CSS {x["css_viewport"]} · 倍率 {x["deviceScaleFactor"]}</p><a href="../{x["file"]}" target="_blank"><img src="../{x["file"]}" loading="lazy" alt="{html.escape(x["label"])}"></a></article>' for x in screens)
(ROOT/'prototype/gallery.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>DESIGN-LAB R2 效果图库</title><style>body{font:14px/1.7 system-ui;margin:30px;background:#eef3f7;color:#17344b}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:24px}article{background:white;padding:20px;border-radius:10px}h1{font-size:24px}h2{font-size:16px}img{width:100%;max-height:430px;object-fit:contain;object-position:top}a{color:#006c9e}</style><h1>DESIGN-LAB R2 效果图库</h1><p>点击图片查看原始尺寸。<a href="index.html">进入可点击原型</a>。这些是参考界面，不是真实运行数据。</p><main>'+items+'</main></html>')
print(json.dumps({'screens':len(screens),'media_files':len(assets),'overview':str(ROOT/'screens/00_overview.png')},ensure_ascii=False))
