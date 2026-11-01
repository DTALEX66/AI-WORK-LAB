# SPDX-License-Identifier: MIT
"""Fill observed browser plan controls without Windows command-line size limits."""
import json
from pathlib import Path
import shutil
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / '.project-local/task-artifacts/real-poster-20260908/run-3bc50140e7f44caca5393c29002c43f9'
CLI = ROOT / '.project-local/task-runtime/playwright/npm-cache/_npx/31e32ef8478fbf80/node_modules/@playwright/cli/playwright-cli.js'


def main():
    rir = json.loads((SOURCE / 'source-rir.json').read_text(encoding='utf-8'))
    styles = json.loads((SOURCE / 'text-styles.json').read_text(encoding='utf-8'))
    code = "async (page) => {\n"
    for label, value in [('可修正的 RIR 对象计划', rir), ('文字样式 JSON', styles)]:
        code += 'await page.getByRole("textbox",{name:' + json.dumps(label) + ',exact:true}).fill(' + json.dumps(json.dumps(value, ensure_ascii=False)) + ');\n'
    code += '}\n'
    target = ROOT / '.project-local/task-runtime/playwright' / ('fill-plan-' + uuid.uuid4().hex + '.js')
    with target.open('x', encoding='utf-8') as stream:
        stream.write(code)
    result = subprocess.run([shutil.which('node'), str(CLI), '-s=design-r5', 'run-code', '--filename', str(target)], cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=60)
    if result.returncode or '### Error' in result.stdout:
        raise RuntimeError('BROWSER_PLAN_FILL_FAILED: ' + result.stdout[-500:])
    print('BROWSER_PLAN_FILLED source=' + str(SOURCE) + ' styles=' + str(len(styles)))


if __name__ == '__main__':
    main()
