"""Render local research charts in an isolated headless Chrome, then close it.

Fallback QA: the session has no in-app-browser/Node execution tools.
Only a newly created temporary browser profile and local project files are used.
"""
import argparse
import asyncio
import base64
import json
import hashlib
from pathlib import Path
import subprocess
import tempfile
import time
from urllib.request import urlopen
import websockets

CHROME='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'


async def inspect(port,out):
    targets=json.load(urlopen(f'http://127.0.0.1:{port}/json/list'))
    page=next(t for t in targets if t['type']=='page')
    async with websockets.connect(page['webSocketDebuggerUrl'],max_size=30_000_000) as ws:
        seq=0;events=[]
        async def call(method,params=None):
            nonlocal seq
            seq+=1;target=seq;await ws.send(json.dumps({'id':target,'method':method,'params':params or {}}))
            while True:
                r=json.loads(await asyncio.wait_for(ws.recv(),20))
                if r.get('id')==target:
                    if 'error' in r:raise RuntimeError(r)
                    return r.get('result',{})
                events.append(r)
        async def evaluate(expression):
            r=await call('Runtime.evaluate',{'expression':expression,'returnByValue':True,'awaitPromise':True})
            if 'exceptionDetails' in r:raise RuntimeError(r['exceptionDetails'])
            return r['result'].get('value')
        await call('Page.enable');await call('Runtime.enable')
        report=[]
        for width in [736,320]:
            await call('Emulation.setDeviceMetricsOverride',{'width':width,'height':1200,'deviceScaleFactor':1,'mobile':False})
            await call('Page.navigate',{'url':(out/'atlas-qa.html').resolve().as_uri()})
            for _ in range(100):
                ready=await evaluate("document.getElementById('combo-research-atlas')?.dataset.ready==='true'")
                if ready:break
                await asyncio.sleep(.05)
            assert ready,'charts did not become ready'
            await asyncio.sleep(.2)
            checked=await evaluate("""(() => {
                const root=document.getElementById('combo-research-atlas');
                const charts=[...root.querySelectorAll('svg')];
                return {charts:charts.length,declared:Number(root.dataset.chartCount),
                    overflow:document.documentElement.scrollWidth>innerWidth,
                    invalidPaths:charts.flatMap(s=>[...s.querySelectorAll('path')]).filter(p=>/NaN|undefined|Infinity/.test(p.getAttribute('d'))).length,
                    emptyCharts:charts.filter(s=>!s.querySelector('circle,rect')).length,
                    sectionCounts:[...root.querySelectorAll('section')].map(s=>({id:s.id,charts:s.querySelectorAll('svg').length})),
                    details:root.querySelectorAll('details').length};
            })()""")
            assert checked['charts']==20 and checked['declared']==20
            assert not checked['overflow'] and checked['invalidPaths']==0 and checked['emptyCharts']==0
            # Native disclosure is the primary interaction: it must expose actual values.
            interaction=await evaluate("""(() => {const d=document.querySelector('details');d.querySelector('summary').click();const ok=d.open&&d.querySelectorAll('tr').length>1;d.querySelector('summary').click();return ok&&!d.open;})()""")
            assert interaction
            checked.update(width=width,details_interaction=interaction);report.append(checked)
            for section in ['marks','volume','clock','hedge','inventory','samegame']:
                await evaluate(f"document.getElementById('atlas-{section}').scrollIntoView()")
                await asyncio.sleep(.05)
                shot=await call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False})
                (out/f'qa_{width}_{section}.png').write_bytes(base64.b64decode(shot['data']))
        exceptions=[e for e in events if e.get('method')=='Runtime.exceptionThrown']
        assert not exceptions,exceptions
        # Test the actual delivered standalone wrapper, not only the flat QA page.
        final=out.parents[1]/'visualizations/07-research-program/index.html'
        await call('Page.navigate',{'url':final.resolve().as_uri()});await asyncio.sleep(.5)
        # Same-origin outer page can inspect iframe presence; sandbox content has
        # an opaque origin, so screenshot verifies that wrapper visually.
        assert await evaluate("document.querySelectorAll('iframe').length===1")
        shot=await call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False})
        (out/'qa_standalone.png').write_bytes(base64.b64decode(shot['data']))
        (out/'visual_qa.json').write_text(json.dumps({'viewports':report,'runtime_exceptions':0,'standalone_iframe_present':True,
            'fragment_sha256':hashlib.sha256((out/'research-atlas.html').read_bytes()).hexdigest(),
            'standalone_sha256':hashlib.sha256(final.read_bytes()).hexdigest()},indent=2)+'\n')
        await call('Browser.close')


def run(out):
    with tempfile.TemporaryDirectory(prefix='combo-atlas-qa-') as profile:
        browser=subprocess.Popen([CHROME,'--headless','--disable-gpu','--no-first-run','--no-default-browser-check',
            '--disable-background-networking','--disable-component-update','--disable-sync','--disable-extensions',
            '--no-service-autorun','--disable-background-mode','--remote-debugging-port=0',f'--user-data-dir={profile}','about:blank'],
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            marker=Path(profile)/'DevToolsActivePort'
            for _ in range(200):
                if marker.exists():break
                if browser.poll() is not None:raise RuntimeError('headless Chrome exited')
                time.sleep(.05)
            port=int(marker.read_text().splitlines()[0]);asyncio.run(inspect(port,out))
        finally:
            if browser.poll() is None:
                browser.terminate()
                try:browser.wait(timeout=10)
                except subprocess.TimeoutExpired:browser.kill();browser.wait(timeout=10)
    print((out/'visual_qa.json').read_text())


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);run(p.parse_args().out)
