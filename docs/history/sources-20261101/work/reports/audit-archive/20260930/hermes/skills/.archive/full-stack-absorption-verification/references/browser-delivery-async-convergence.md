# Browser delivery async-convergence recipe

Use this pattern for a real UI test that submits an intake form and then operates a delivery control rendered elsewhere on the page.

```python
page.set_input_files("#intake-file", str(fixture))
page.get_by_role("button", name="导入文件").click()
page.locator("#intake-result").wait_for(state="visible")
page.wait_for_function(
    """() => document.querySelector('#intake-result')?.innerText !== '处理中…'"""
)
assert "处理完成" in page.locator("#intake-result").inner_text()
page.get_by_role("button", name="关闭").click()

page.goto(f"{base_url}#runtime", wait_until="networkidle")
delivery = page.locator("#delivery-center")
delivery.get_by_role("button", name="投递下一条").click()
page.wait_for_function(
    """() => document.querySelector('#delivery-center')?.innerText.includes('Receipt recorded：1')"""
)
assert "Outbox pending：0" in delivery.inner_text()
page.reload(wait_until="networkidle")
page.wait_for_function(
    """() => document.querySelector('#delivery-center')?.innerText.includes('Receipt recorded：1')"""
)
```

Run the server, database, uploads, browser cache, and logs through the project-data boundary wrapper. Keep HTTP, SQLite, Chromium, and desktop/Tauri results as separate evidence rows. This proves the on-demand browser path only; it does not prove a supervised worker or Tauri WebView click path.
