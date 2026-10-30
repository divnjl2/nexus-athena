import pytest

from lib.gsn_case import build


def receipt(state='NO_COUNTEREXAMPLE'):
    return {'schema': 'athena.formal_evidence/1', 'results': [
        {'id': 'production', 'engine': 'crosshair', 'scope': 'only combine(bool, bool)', 'state': state}]}


def test_gsn_leaves_global_intent_and_coverage_claims_open():
    """C-1.8 — bounded tool observations cannot close global assurance claims."""
    for state in ('NO_COUNTEREXAMPLE', 'COUNTEREXAMPLE', 'UNKNOWN', 'VERIFIED_RELATIVE_TO_SPEC'):
        graph = build(receipt(state), 'a' * 64)
        assert graph['G3']['undeveloped'] and graph['G4']['undeveloped']
        assert 'open' in graph['G1']['classes']
        assert state in graph['Gcase1']['text']
        assert graph['Sncase1']['url'] == 'evidence/result-1.json'
        for node in graph.values():
            for relation in ('supportedBy', 'inContextOf'):
                assert all(target in graph for target in node.get(relation, []))
            assert not (node.get('undeveloped') and node.get('supportedBy'))
        # GSN solutions cannot bear in-context-of edges; native gsn2x enforces this.
        assert not graph['Sncase1'].get('inContextOf')


def test_gsn_rejects_empty_and_unrecognized_observations():
    for invalid in ({}, {'schema': 'athena.formal_evidence/1', 'results': []}, receipt('PASS')):
        with pytest.raises(ValueError):
            build(invalid, 'a' * 64)


def test_gsn_preserves_model_subject_and_local_assumptions():
    report = receipt('VERIFIED_RELATIVE_TO_SPEC')
    report['results'][0].update(engine='dafny', subject_kind='model', assumptions=['Only x > 1000000000 is admitted'])
    graph = build(report, 'a' * 64)
    assert 'model' in graph['Ccase1']['text']
    assert graph['Acase1_1']['text'] == 'Only x > 1000000000 is admitted'
    assert 'Acase1_1' in graph['Gcase1']['inContextOf']


def test_failed_reexport_invalidates_old_success_journal(tmp_path, monkeypatch):
    import json
    from lib.assurance import sha
    from lib.gsn_case import export
    source = tmp_path / 'input.json'
    source.write_text(json.dumps(receipt()), encoding='utf-8')
    destination = tmp_path / 'render'
    destination.mkdir()
    (destination / 'render.json').write_text(json.dumps({'state': 'RENDERED', 'exit_code': 0, 'source_receipt_sha256': 'old'}))
    def missing(*a, **k):
        raise FileNotFoundError('renderer missing')
    monkeypatch.setattr('lib.gsn_case.subprocess.run', missing)
    with pytest.raises(FileNotFoundError):
        export(source, destination, 'nonexistent-renderer')
    journal = json.loads((destination / 'render.json').read_text(encoding='utf-8'))
    assert journal['state'] == 'RENDER_FAILED' and journal['exit_code'] is None
    assert journal['source_receipt_sha256'] == sha((destination / 'receipt.json').read_bytes())


def test_successful_renderer_cannot_reuse_a_previous_svg(tmp_path, monkeypatch):
    """A zero exit without fresh output must not credit an earlier diagram."""
    import json
    from types import SimpleNamespace
    from lib.gsn_case import export
    source = tmp_path / 'input.json'
    source.write_text(json.dumps(receipt()), encoding='utf-8')
    destination = tmp_path / 'render'
    destination.mkdir()
    svg = destination / 'argument.gsn.svg'
    svg.write_text('<svg viewBox="0 0 100 100"/>')
    monkeypatch.setattr('lib.gsn_case.subprocess.run', lambda *a, **k: SimpleNamespace(returncode=0, stdout='', stderr=''))
    with pytest.raises(FileNotFoundError):
        export(source, destination, 'nonexistent-renderer')
    assert not svg.exists()


@pytest.mark.parametrize('box', ['0 0 NaN 100', '0 0 100 inf', '0 0 -10 100', '0 0 0 100'])
def test_renderer_rejects_unusable_viewbox(tmp_path, monkeypatch, box):
    import json
    from types import SimpleNamespace
    from lib.gsn_case import export
    source = tmp_path / 'input.json'
    source.write_text(json.dumps(receipt()), encoding='utf-8')
    destination = tmp_path / 'render'
    def run(*args, **kwargs):
        (destination / 'argument.gsn.svg').write_text(f'<svg viewBox="{box}"/>')
        return SimpleNamespace(returncode=0, stdout='', stderr='')
    monkeypatch.setattr('lib.gsn_case.subprocess.run', run)
    with pytest.raises(ValueError, match='viewBox'):
        export(source, destination, 'nonexistent-renderer')
