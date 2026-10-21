"""Render the three review plots and check mobile/light/dark layout."""
from pathlib import Path
import importlib.util,json
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
FRAGMENTS=Path('~/.codex/visualizations/2026/09/09/01a0874f-8a56-7ad2-be80-ed5b30c3e6cd')
SKILL=Path('~/.codex/plugins/cache/openai-bundled/visualize/1.0.11/skills/visualize')
OUT=ROOT/'runs/shadow_exchange_fallback_20260909/post_session/visual_checks';OUT.mkdir(exist_ok=True)
spec=importlib.util.spec_from_file_location('visual_render',SKILL/'scripts/render.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
names=['corrected-rfq-coverage','fixture-headroom','edge-and-public-marks'];checks=[]
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True)
    for name in names:
        fragment=FRAGMENTS/(name+'.html');text=fragment.read_text()
        assert '\\"' not in text and '\\n' not in text and len(text)<2_000_000
        path=OUT/(name+'.html');path.write_text(module.render(fragment))
        for width in (320,736):
            for theme in ('light','dark'):
                page=browser.new_page(viewport={'width':width,'height':900},color_scheme=theme)
                errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto(path.as_uri());page.wait_for_timeout(150)
                frame=page.frames[1]
                metrics=frame.evaluate('''() => {
                    const root=document.querySelector('[role="img"]');
                    const nodes=[...root.querySelectorAll('.caption span,.key>span,.axis span')];
                    const bad=nodes.filter(n=>{let r=n.getBoundingClientRect();return r.left<0 || r.right>document.documentElement.clientWidth+1;});
                    return {viewport:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth,
                        overflowLabels:bad.map(n=>n.textContent),height:root.getBoundingClientRect().height};
                }''')
                assert not errors and not metrics['overflowLabels'] and metrics['scroll']<=metrics['viewport'],(name,width,theme,metrics,errors)
                page.screenshot(path=str(OUT/f'{name}-{width}-{theme}.png'),full_page=True)
                checks.append(dict(plot=name,width=width,theme=theme,passed=True,**metrics));page.close()
    browser.close()
(OUT/'checks.json').write_text(json.dumps(checks,indent=2)+'\n')
print(json.dumps(checks,indent=2))
