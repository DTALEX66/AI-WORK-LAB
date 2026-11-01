import json,pathlib
from playwright.sync_api import sync_playwright
out=pathlib.Path('/tmp/tri-audit/evidence'); results=[]
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
 page=b.new_page(viewport={'width':1440,'height':1200}); errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 url='http://127.0.0.1:33691/?api=http://127.0.0.1:33691/api/v1/snapshot'
 page.goto(url+'&view=workflow-editor');page.wait_for_timeout(700)
 results.append({'phase':'editor','text':page.locator('body').inner_text()[:3000]})
 def model():return json.loads(page.evaluate("localStorage.getItem('work-lab/editor/model')"))
 before=model();handle=page.get_by_title('拖出连线').first;target=page.locator('[data-node-id="n4"]');s=handle.bounding_box();t=target.bounding_box()
 page.mouse.move(s['x']+s['width']/2,s['y']+s['height']/2);page.mouse.down();page.mouse.move(t['x']+40,t['y']+30,steps=15);page.mouse.up();page.wait_for_timeout(100)
 after=model();results.append({'phase':'drag-line','beforeEdges':len(before['edges']),'afterEdges':len(after['edges']),'errors':errors.copy()})
 handle.click();page.wait_for_timeout(100);results.append({'phase':'click-line','errors':errors.copy()})
 canvas=page.locator('.canvas');box=canvas.bounding_box();layer=canvas.locator(':scope > div').first
 beforePan=layer.get_attribute('style');x=box['x']+50;y=min(box['y']+box['height']-40,1100)
 hit=page.evaluate('([x,y])=>document.elementFromPoint(x,y)?.outerHTML.slice(0,200)',[x,y])
 page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+100,y-50,steps=10);page.mouse.up();results.append({'phase':'pan','hit':hit,'before':beforePan,'after':layer.get_attribute('style')})
 page.screenshot(path=str(out/'work-ui-editor.png'))
 page.goto(url+'&view=monitoring');page.wait_for_timeout(300);results.append({'phase':'monitoring-real-offline','text':page.locator('body').inner_text()[:4000]})
 page.screenshot(path=str(out/'work-ui-monitoring.png'))
 page.set_viewport_size({'width':900,'height':600});page.screenshot(path=str(out/'work-ui-floor.png'))
 page.goto('http://127.0.0.1:44537/?api=http://127.0.0.1:44537/api/v1/snapshot');page.wait_for_timeout(300);page.screenshot(path=str(out/'work-active-home.png'));results.append({'phase':'active-home','text':page.locator('body').inner_text()[:3000]})
 page.goto('http://127.0.0.1:39701');page.wait_for_timeout(400);page.screenshot(path=str(out/'aaos-browser-no-core.png'));results.append({'phase':'aaos-no-core','text':page.locator('body').inner_text()[:4000]})
 b.close()
(out/'work-browser.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
