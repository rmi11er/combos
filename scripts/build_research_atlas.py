"""Build the existing project's self-contained research charts from results."""
import argparse
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def run(out):
    template=ROOT/'visualizations/07-research-program/research-atlas.template.html'
    data=json.loads((out/'final_analysis.json').read_text())
    content=template.read_text().replace('__ATLAS_DATA__',json.dumps(data,separators=(',',':'),allow_nan=False).replace('</','<\\/'))
    fragment=out/'research-atlas.html';fragment.write_text(content)
    skill=Path('~/.codex/plugins/cache/openai-bundled/visualize/1.0.11/skills/visualize')
    spec=importlib.util.spec_from_file_location('visualize_render',skill/'scripts/render.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    standalone=ROOT/'visualizations/07-research-program/index.html'
    standalone.write_text(module.render(fragment,title='Combo research: volume, markouts and inventory'))
    assert len(content.encode())<2_000_000
    # Flat same-origin QA page uses the same fragment and bundled theme. The
    # deliverable above retains the skill's sandboxed standalone wrapper.
    css=(skill/'assets/visualize.css').read_text()
    (out/'atlas-qa.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Research chart QA</title><style>'+css+'</style><body>'+content+'</body></html>')
    print(standalone)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);run(p.parse_args().out)
