from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/'specs/screen_map.json').read_text())
labels=['能力目录','能力详情','输入与目标','分析与方案','目标生成包','制作与核验','恢复与对账','成果目录','产物与改稿','版本评审','交付预检','反馈与候选','教学需求','连接与诊断','界面状态','组件规范']
cards=[]
for i,(s,name) in enumerate(zip(data,labels)):
 full=f'<a href="{s["full_page"]}">完整长图</a>' if s.get('full_page') else ''
 cards.append(f'<article><a href="{s["retina"]}"><img src="{s["desktop"]}" alt="{name}"></a><div><strong>{i+1:02d}　{name}</strong><span><a href="prototype/index.html#{s["route"]}">可编辑参考</a>　<a href="{s["retina"]}">4K</a>　{full}</span></div></article>')
css='''@font-face{font-family:CJK;src:url(assets/fonts/DroidSansFallback.ttf)}*{box-sizing:border-box}body{margin:0;background:#080e16;color:#edf5fc;font-family:Segoe UI,CJK,sans-serif}header{padding:35px 40px 28px;border-bottom:1px solid #283a4d}h1{font-size:28px;margin:8px 0 12px}p{color:#9fb1c3;margin:0}a{color:#87dcff;text-decoration:none}main{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;padding:30px 40px}article{background:#101a26;border:1px solid #283a4d;border-radius:10px;overflow:hidden}img{width:100%;display:block}article div{padding:13px 16px;font-size:14px;display:flex;justify-content:space-between;gap:15px}span{font-size:11px;color:#9fb1c3}footer{padding:20px 40px 35px;color:#9fb1c3;font-size:12px}.more{display:flex;gap:24px;padding:20px 40px}@media(max-width:950px){main{grid-template-columns:1fr;padding:20px}header{padding:25px 20px}article div{display:block}span{display:block;margin-top:6px}}'''
header='<header><p>DESIGN-LAB / UI-20261009-r1</p><h1>专业能力资产与设计自动化 · UI 前端参考</h1><p>16 个桌面页面 / 深浅主题 / 窄屏适配 / 独立媒体素材　·　当前为演示界面，真实集成待执行。</p></header>'
base='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>DESIGN-LAB UI 总览</title><style>'+css+'</style>'
(ROOT/'gallery.html').write_text(base+header+'<main>'+''.join(cards)+'</main><div class="more"><a href="screens/4k/17_catalog_light_3840x2160.png">17 浅色能力目录</a><a href="screens/mobile/18_catalog_full.png">18 窄屏目录</a><a href="screens/mobile/19_input_full.png">19 窄屏输入</a><a href="screens/mobile/20_result_full.png">20 窄屏产物</a><a href="screens/mobile/21_feedback_full.png">21 窄屏反馈</a></div><footer>首屏与完整长图分别提供；优先使用独立 SVG / PNG 和原生组件，截图不等于业务或宿主验证。</footer></html>',encoding='utf-8')
overview=base.replace('</style>','main{grid-template-columns:repeat(4,1fr);gap:18px;padding:26px 40px}header{padding:27px 40px}article div{font-size:18px;padding:10px 14px}article span{display:none}h1{font-size:36px}p{font-size:20px}</style>')
(ROOT/'overview.html').write_text(overview+header+'<main>'+''.join(cards)+'</main></html>',encoding='utf-8')
print('Built gallery and overview')
