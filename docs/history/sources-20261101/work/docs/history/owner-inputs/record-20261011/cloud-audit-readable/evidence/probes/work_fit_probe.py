import json,pathlib
from playwright.sync_api import sync_playwright
out=pathlib.Path('/tmp/tri-audit/evidence');r={}
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);page=b.new_page(viewport={'width':1800,'height':1200});page.goto('http://127.0.0.1:33691/?view=workflow-editor&api=http://127.0.0.1:33691/api/v1/snapshot');page.wait_for_timeout(300)
 for i in range(4):page.get_by_role('button',name='缩小',exact=True).click()
 canvas=page.locator('.canvas');c=canvas.bounding_box();layer=canvas.locator(':scope > div').first;x=c['x']+c['width']*.85;y=min(c['y']+c['height']*.8,1100)
 r['hit']=page.evaluate('([x,y])=>document.elementFromPoint(x,y)?.className',[x,y]);r['before']=layer.get_attribute('style');page.mouse.move(x,y);page.mouse.down();page.mouse.move(x-80,y-50,steps=10);page.mouse.up();r['panned']=layer.get_attribute('style');page.get_by_role('button',name='适应画布',exact=True).click();r['afterFit']=layer.get_attribute('style');page.screenshot(path=str(out/'work-ui-fit.png'));b.close()
(out/'work-ui-fit.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(r)
