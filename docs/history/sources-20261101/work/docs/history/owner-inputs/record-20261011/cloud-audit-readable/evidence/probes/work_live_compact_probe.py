import json,pathlib,urllib.request
from playwright.sync_api import sync_playwright
out=pathlib.Path('/tmp/tri-audit/evidence');snap=json.load(urllib.request.urlopen('http://127.0.0.1:33691/api/v1/snapshot'));snap['transport']['transportState']='LIVE';snap['transport']['freshnessState']='FRESH';snap['transport']['eventsUrl']='http://127.0.0.1:33691/api/v1/events';result={}
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);context=b.new_context(viewport={'width':1440,'height':1000});page=context.new_page()
 page.route('**/api/v1/snapshot',lambda route:route.fulfill(json=snap))
 page.goto('http://127.0.0.1:33691/?api=http://127.0.0.1:33691/api/v1/snapshot&view=monitoring');page.wait_for_timeout(500);result['before']=page.locator('body').inner_text()
 page.unroute('**/api/v1/snapshot');context.set_offline(True);page.wait_for_timeout(6500);result['after']=page.locator('body').inner_text();result['topbar']=page.locator('.topbar').inner_text();page.screenshot(path=str(out/'work-ui-stale-live.png'))
 result['greenNodes']=page.locator('.topbar').evaluate('(e)=>[...e.querySelectorAll("*")].filter(n=>n.textContent==="LIVE").map(n=>({text:n.textContent,color:getComputedStyle(n).color,html:n.outerHTML}))')
 page.get_by_role('button',name='切换到紧凑布局',exact=True).click();page.wait_for_timeout(200);result['compactAfter']=page.locator('body').inner_text();page.screenshot(path=str(out/'work-ui-stale-compact.png'));b.close()
(out/'work-ui-stale-compact.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(result['topbar']);print(result['after'][-2200:])
