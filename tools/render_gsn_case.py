"""Render a formal receipt through an explicitly installed native gsn2x."""
import argparse
import json
from pathlib import Path
import sys
import webbrowser

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.gsn_case import export, review


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('receipt')
    parser.add_argument('output')
    parser.add_argument('--gsn2x', required=True)
    args = parser.parse_args()
    root = Path(args.output).resolve()
    result = export(Path(args.receipt).resolve(), root, args.gsn2x)
    page = root / 'review.html'
    box = result['svg_viewbox']
    page.write_text(review(box[3] / box[2]), encoding='utf-8')
    webbrowser.open(page.as_uri())
    print(json.dumps({'review': str(page), 'nodes': result['nodes'], 'exit_code': result['exit_code']}))


if __name__ == '__main__':
    main()
