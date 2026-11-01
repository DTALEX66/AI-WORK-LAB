import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);const {chromium}=require('playwright');
import fs from 'node:fs';import path from 'node:path';import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const routes=['catalog','capability','input','analysis','plan','running','recovery','results','result','jury','delivery','feedback','teaching','connections','states','components'];
for(const dir of ['screens/desktop','screens/4k','screens/mobile'])for(const file of fs.readdirSync(`${root}/${dir}`))if(file.endsWith('.png'))fs.unlinkSync(`${root}/${dir}/${file}`);
const browser=await chromium.launch({headless:true,executablePath:process.env.UI_CHROMIUM_PATH||undefined,args:['--no-sandbox','--allow-file-access-from-files','--disable-gpu']});
const ctx=await browser.newContext({viewport:{width:1920,height:1080},deviceScaleFactor:1});const page=await ctx.newPage();
const errors=[];page.on('pageerror',e=>errors.push(e.message));
const measurements=[];const screenshots=[];
for(let i=0;i<routes.length;i++){
 const route=routes[i],prefix=String(i+1).padStart(2,'0')+'_'+route;
 await page.goto(`file://${root}/prototype/index.html#${route}`);await page.evaluate(()=>document.fonts.ready);await page.waitForFunction(()=>window.previewReady);
 await page.screenshot({path:`${root}/screens/desktop/${prefix}_1920x1080.png`});
 const m=await page.evaluate(()=>({page:document.querySelector('[data-page]').dataset.page,scrollWidth:document.documentElement.scrollWidth,scrollHeight:document.documentElement.scrollHeight,viewport:[innerWidth,innerHeight],images:[...document.images].map(i=>({src:i.getAttribute('src'),ok:i.complete&&i.naturalWidth>0})),regions:[...document.querySelectorAll('[data-component]')].map(e=>{const r=e.getBoundingClientRect();return {name:e.dataset.component,x:r.x,y:r.y,width:r.width,height:r.height};})}));
 if(m.scrollHeight>1080) await page.screenshot({path:`${root}/screens/desktop/${prefix}_full.png`,fullPage:true});
 measurements.push(m);screenshots.push({id:prefix,route,desktop:`screens/desktop/${prefix}_1920x1080.png`,retina:`screens/4k/${prefix}_3840x2160.png`,viewport:[1920,1080],scale:2,full_height:m.scrollHeight,full_page:m.scrollHeight>1080?`screens/4k/${prefix}_full.png`:null});
 console.log(prefix,m.scrollWidth,m.scrollHeight);
}
await ctx.close();const retina=await browser.newContext({viewport:{width:1920,height:1080},deviceScaleFactor:2});const p2=await retina.newPage();
for(let i=0;i<routes.length;i++){const prefix=String(i+1).padStart(2,'0')+'_'+routes[i];await p2.goto(`file://${root}/prototype/index.html#${routes[i]}`);await p2.evaluate(()=>document.fonts.ready);await p2.screenshot({path:`${root}/screens/4k/${prefix}_3840x2160.png`});if(measurements[i].scrollHeight>1080)await p2.screenshot({path:`${root}/screens/4k/${prefix}_full.png`,fullPage:true});}
await p2.goto(`file://${root}/prototype/index.html?theme=light#catalog`);await p2.evaluate(()=>document.fonts.ready);await p2.screenshot({path:`${root}/screens/4k/17_catalog_light_3840x2160.png`});screenshots.push({id:'17_catalog_light',route:'catalog',theme:'light',retina:'screens/4k/17_catalog_light_3840x2160.png',viewport:[1920,1080],scale:2});await retina.close();
await page.close().catch(()=>{});
const mobile=await browser.newContext({viewport:{width:390,height:844},deviceScaleFactor:2,isMobile:true,hasTouch:true});const pm=await mobile.newPage();
for(const [i,route] of ['catalog','input','result','feedback'].entries()){await pm.goto(`file://${root}/prototype/index.html#${route}`);await pm.evaluate(()=>document.fonts.ready);await pm.screenshot({path:`${root}/screens/mobile/${18+i}_${route}_780x1688.png`});await pm.screenshot({path:`${root}/screens/mobile/${18+i}_${route}_full.png`,fullPage:true});measurements.push(await pm.evaluate(()=>({page:document.querySelector('[data-page]').dataset.page,mobile:true,scrollWidth:document.documentElement.scrollWidth,scrollHeight:document.documentElement.scrollHeight,viewport:[innerWidth,innerHeight]})));screenshots.push({id:`${18+i}_${route}_mobile`,route,mobile:true,retina:`screens/mobile/${18+i}_${route}_780x1688.png`,full_page:`screens/mobile/${18+i}_${route}_full.png`,viewport:[390,844],scale:2});}
await mobile.close();
const assets=await browser.newContext({viewport:{width:3840,height:2400},deviceScaleFactor:1});const pa=await assets.newPage();
for(const file of fs.readdirSync(`${root}/assets/art`).filter(x=>x.endsWith('.svg'))){await pa.goto(`file://${root}/assets/art/${file}`);await pa.evaluate(()=>{document.documentElement.style.width='100%';document.documentElement.style.height='100%';});await pa.screenshot({path:`${root}/assets/art/${file.replace('.svg','_4k.png')}`,omitBackground:true});}
fs.writeFileSync(`${root}/specs/screen_map.json`,JSON.stringify(screenshots,null,2));fs.writeFileSync(`${root}/specs/slice_map.json`,JSON.stringify({note:'CSS坐标基于1920x1080；4K裁切乘2。优先复用源码，截图仅核对；面板不是部署素材。',pages:measurements},null,2));fs.writeFileSync(`${root}/evidence/render_report.json`,JSON.stringify({date:'2026-10-09',errors,measurements,scope:'LOCAL_UI_REFERENCE_ONLY'},null,2));await browser.close();if(errors.length)throw Error(errors.join('\n'));
