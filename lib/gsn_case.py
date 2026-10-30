"""Export an archived formal receipt as a bounded GSN argument, not a verdict."""
from __future__ import annotations

import json
import math
from pathlib import Path
import subprocess
import shutil
import xml.etree.ElementTree as ET

from lib.assurance import sha
from lib.formal_evidence import SCHEMA


def build(report: dict, receipt_sha256: str) -> dict:
    if not isinstance(report, dict) or report.get('schema') != SCHEMA or not isinstance(report.get('results'), list) or not report['results']:
        raise ValueError('a nonempty formal receipt is required')
    graph = {
        'G1': {'text': 'Соответствие Athena замыслу пользователя. ОБЩИЙ ВЫВОД НЕ ПОДТВЕРЖДЁН.', 'supportedBy': ['S1'], 'inContextOf': ['C1', 'A1'], 'classes': ['open']},
        'S1': {'text': 'Для общего вывода нужны все ветви: результаты проверок, верность формализации и полнота охвата.', 'supportedBy': ['G2', 'G3', 'G4']},
        'C1': {'text': 'Архивный прогон выбранных функций. Это карта аргументов, не автоматическая оценка текущего кода.'},
        'A1': {'text': 'Доверяем установленным инструментам и объявленному составу входов. Полнота зависимостей отдельно не доказана.'},
        'G2': {'text': 'Наблюдения инструментов зафиксированы и доступны. Их смысл ограничен указанной областью.', 'supportedBy': ['S2'], 'inContextOf': ['C2']},
        'S2': {'text': 'Рассмотреть каждый результат отдельно; поиск без контрпримера не считать доказательством.', 'supportedBy': []},
        'G3': {'text': 'Формальные свойства верно выражают замысел пользователя. НЕ ПРОВЕРЕНО.', 'undeveloped': True, 'classes': ['open']},
        'G4': {'text': 'Остальные требования и код охвачены достаточными проверками. НЕ ПРОВЕРЕНО.', 'undeveloped': True, 'classes': ['open']},
        'C2': {'text': 'SHA-256 исходной записи: ' + receipt_sha256, 'url': 'receipt.json'},
    }
    known = {'NO_COUNTEREXAMPLE', 'COUNTEREXAMPLE', 'UNKNOWN', 'UNPROVEN', 'VERIFIED_RELATIVE_TO_SPEC'}
    for index, row in enumerate(report['results'], 1):
        if not isinstance(row, dict) or row.get('state') not in known or not all(isinstance(row.get(k), str) for k in ('id', 'engine', 'scope')):
            raise ValueError('invalid formal observation')
        goal, solution, context = f'Gcase{index}', f'Sncase{index}', f'Ccase{index}'
        graph['S2']['supportedBy'].append(goal)
        graph[goal] = {'text': f"В записи {row['id']} инструмент {row['engine']} сообщил {row['state']}.",
                       'supportedBy': [solution], 'inContextOf': [context],
                       'classes': ['observed' if row['state'] != 'UNKNOWN' else 'open']}
        graph[context] = {'text': 'Субъект: ' + str(row.get('subject_kind', 'не указан')) + '. Область: ' + row['scope']}
        assumptions = row.get('assumptions', [])
        if not isinstance(assumptions, list) or not all(isinstance(a, str) for a in assumptions):
            raise ValueError('invalid observation assumptions')
        for ai, assumption in enumerate(assumptions, 1):
            key = f'Acase{index}_{ai}'
            graph[key] = {'text': assumption}
            graph[goal]['inContextOf'].append(key)
        graph[solution] = {'text': 'Свидетельство: исходный результат ' + row['id'],
                           'url': f'evidence/result-{index}.json'}
    return graph


def export(receipt: Path, destination: Path, executable: str) -> dict:
    raw = receipt.read_bytes()
    report = json.loads(raw)
    graph = build(report, sha(raw))
    destination.mkdir(parents=True, exist_ok=True)
    evidence = destination / 'evidence'
    evidence.mkdir(exist_ok=True)
    (destination / 'receipt.json').write_bytes(raw)
    for i, row in enumerate(report['results'], 1):
        (evidence / f'result-{i}.json').write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding='utf-8')
    # JSON is a YAML-compatible representation, verified by native gsn2x below.
    source = destination / 'argument.gsn.yaml'
    source.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding='utf-8')
    # A previous diagram must not masquerade as the output of this invocation.
    svg = destination / 'argument.gsn.svg'
    svg.unlink(missing_ok=True)
    journal = destination / 'render.json'
    result = {'schema': 'athena.gsn_render/1', 'source_receipt_sha256': sha(raw),
              'state': 'PREPARING', 'exit_code': None, 'nodes': len(graph),
              'open_claims': ['G1', 'G3', 'G4'],
              'limitations': ['Native rendering validates GSN structure, not truth or completeness of the argument.',
                              'Archived receipt integrity does not establish current source freshness.']}
    journal.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    (destination / 'style.css').write_text('''
.gsnelem text { font-family: Arial, sans-serif; }
.gsnelem.open rect,.gsnelem.open path { fill: #fff0d8; fill-opacity: 1; }
.gsnelem.observed rect,.gsnelem.observed path { fill: #e9f3ff; fill-opacity: 1; }
.gsnelem:target > rect,.gsnelem:target > path { fill: #ccebe4; }
''', encoding='utf-8')
    argv = [executable, source.name, '--no-full', '--no-arch', '--embed-css', '--stylesheet=style.css', '--wrap=36']
    result.update(state='RUNNING', argv=argv)
    journal.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    try:
        proc = subprocess.run(argv, cwd=destination, capture_output=True, text=True, errors='replace', timeout=30, shell=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        result.update(state='RENDER_FAILED', error=str(exc))
        journal.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        raise
    result.update(state='VALIDATING_OUTPUT' if proc.returncode == 0 else 'RENDER_FAILED',
                  exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)
    binary = shutil.which(executable)
    result['renderer'] = {'path': binary, 'sha256': sha(Path(binary).read_bytes()) if binary else None}
    (destination / 'render.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    if proc.returncode:
        raise ValueError('gsn2x failed: ' + proc.stdout + proc.stderr)
    tree = ET.parse(svg)
    if not tree.getroot().tag.endswith('svg'):
        raise ValueError('gsn2x did not produce an SVG')
    viewbox = [float(v) for v in tree.getroot().get('viewBox', '').split()]
    if len(viewbox) != 4 or not all(math.isfinite(v) for v in viewbox) or viewbox[2] <= 0 or viewbox[3] <= 0:
        raise ValueError('invalid SVG viewBox')
    result['rendered_svg_sha256'] = sha(svg.read_bytes())
    result['svg_viewbox'] = viewbox
    result['state'] = 'RENDERED'
    (destination / 'render.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


def review(aspect_ratio: float = 1) -> str:
    return '''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Athena × gsn2x — карта аргументов</title><style>
body{margin:0;background:#f5f7fb;color:#17283c;font:16px/1.6 system-ui}main{max-width:1500px;margin:auto;padding:24px}h1{margin:10px 0}.note{border-left:4px solid #de9e35;background:#fff1d7;padding:14px 18px}.controls{display:flex;gap:10px;flex-wrap:wrap;margin:16px 0}button,a{color:#175aaa}button{padding:8px 14px;background:white;border:1px solid #aabbce;border-radius:7px;cursor:pointer}.viewport{height:76vh;overflow:auto;background:white;border:1px solid #c6d1df;border-radius:12px}object{display:block;width:100%;height:100%}small{color:#53667d}
</style><main><small>ATHENA / НАТИВНЫЙ GSN2X / АРХИВНЫЕ СВИДЕТЕЛЬСТВА</small>
<h1>Почему мы можем — или пока не можем — верить выводу</h1>
<p>Прямоугольники — утверждения; параллелограммы — способ обоснования; круги — свидетельства. Узлы A — допущения, C — контекст. Ромб под утверждением обозначает незавершённую ветвь. Нажми свидетельство, чтобы открыть сохранённый результат.</p>
<div class="note"><b>Общий вывод остаётся неподтверждённым.</b> Здесь показаны реальные результаты ограниченного прогона. Верность формализации замыслу и полнота проверки проекта остаются открытыми. gsn2x проверяет структуру графа и рисует его; истинность аргументов он не удостоверяет.</div>
<div class="controls"><button id="out">− Уменьшить</button><button id="in">+ Увеличить</button><button id="fit">Вписать</button><a href="argument.gsn.svg" target="_blank">Открыть SVG</a><a href="argument.gsn.yaml">Исходный GSN</a><a href="receipt.json">Исходные результаты</a><a href="render.json">Протокол рендера</a></div>
<div class="viewport" id="viewport"><object id="graph" type="image/svg+xml" data="argument.gsn.svg"><a href="argument.gsn.svg">Открыть граф</a></object></div>
<p><small>Архивная запись не означает актуальность результата для изменившегося кода. Аргументы сформированы адаптером Athena; SVG построен настоящим gsn2x.</small></p></main>
<script>let zoom=1;const ratio=SVG_ASPECT;const graph=document.getElementById('graph'),view=document.getElementById('viewport');function resize(){graph.style.width=(view.clientWidth*zoom)+'px';graph.style.height=(view.clientWidth*zoom*ratio)+'px'}graph.addEventListener('load',resize);document.getElementById('in').onclick=()=>{zoom=Math.min(zoom*1.5,12);resize()};document.getElementById('out').onclick=()=>{zoom=Math.max(zoom/1.5,.25);resize()};document.getElementById('fit').onclick=()=>{zoom=1;resize()};window.addEventListener('resize',resize);resize();</script></html>'''.replace('SVG_ASPECT', json.dumps(float(aspect_ratio)))
