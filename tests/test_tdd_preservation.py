"""Named tests survive model overlays and all prediction export paths."""
import difflib
import io
import json
import tarfile
import pytest
from evals.tddbench.workspace import export_workspace
from evals.tddbench.test_preservation import preserve_named_tests
from evals.tddbench.native import check_proposal, test_patch as export_test_patch
from evals.tddbench.patches import validate_patch
from evals.tddbench.execution import run_tests
from test_tdd_native import proposal

OLD = 'def test_old():\n    assert 1\n\nclass TestOld:\n    def test_method(self):\n        assert 2\n'
NEW = 'def test_new():\n    assert True\n'


@pytest.mark.parametrize('replacement', [NEW, OLD.replace('assert 1', 'assert True'),
    OLD.replace('assert 2', 'assert True'), OLD+'\ndef test_old():\n    assert True\n'])
def test_changed_removed_and_shadowed_named_tests_are_rejected(replacement):
    """C-5.9 - native, export and tool paths refuse destructive definitions before execution while allowing additions."""
    with pytest.raises(ValueError, match='existing named test'):
        preserve_named_tests(OLD, replacement, 'tests/test_old.py')


def test_additive_tests_and_comments_preserve_definitions():
    preserve_named_tests(OLD, '# comment\n'+OLD+'\n'+NEW, 'tests/test_old.py')
    preserve_named_tests('', NEW, 'tests/test_new.py')
    preserve_named_tests(OLD, OLD, 'tests/test_old.py')


def test_async_test_body_and_decorators_are_protected():
    old='@marker\nasync def test_async():\n    assert 1\n'
    for new in (old.replace('assert 1','assert True'),old.replace('@marker','@other')):
        with pytest.raises(ValueError,match='existing named test'):
            preserve_named_tests(old,new,'tests/test_async.py')


def test_unparseable_changed_existing_file_cannot_claim_preservation():
    old='print "legacy syntax"\n'
    preserve_named_tests(old,old,'tests/test_legacy.py')
    with pytest.raises(ValueError,match='cannot establish named-test preservation'):
        preserve_named_tests(old,NEW,'tests/test_legacy.py')


@pytest.fixture
def public(tmp_path):
    data=tmp_path/'public.json'
    data.write_text(json.dumps([{'instance_id':'psf__requests-1','repo':'psf/requests',
        'base_commit':'a'*40,'problem_statement':'Preserve behavior.'}]))
    stream=io.BytesIO()
    with tarfile.open(fileobj=stream,mode='w:gz') as archive:
        for name,text in {'api.py':'pass\n','tests/test_old.py':OLD}.items():
            value=text.encode(); item=tarfile.TarInfo('base/'+name);item.size=len(value)
            archive.addfile(item,io.BytesIO(value))
    root=tmp_path/'public'
    export_workspace(str(data),'psf__requests-1',str(root),opener=lambda *a,**k:io.BytesIO(stream.getvalue()))
    return root


def test_native_refuses_test_replacement_before_execution(public,tmp_path):
    candidate=proposal();candidate['files']={'tests/test_old.py':NEW}
    candidate['scenarios']=candidate['scenarios'].replace('tests/test_value.py','tests/test_old.py')
    def never(*a,**k):pytest.fail('destructive candidate reached execution')
    with pytest.raises(ValueError,match='existing named test'):
        check_proposal(str(public),str(tmp_path/'native'),candidate,never)
    assert not (tmp_path/'native').exists()


def test_patch_replacement_is_refused_and_addition_remains_valid(public):
    bad='diff --git a/tests/test_old.py b/tests/test_old.py\n'+''.join(difflib.unified_diff(
        OLD.splitlines(keepends=True),NEW.splitlines(keepends=True),fromfile='a/tests/test_old.py',tofile='b/tests/test_old.py'))
    with pytest.raises(ValueError,match='existing named test'):
        validate_patch(str(public),bad)
    patch=export_test_patch(str(public),{'tests/test_old.py':OLD+'\n'+NEW})
    assert validate_patch(str(public),patch)==patch and '+def test_new():' in patch


def test_test_tool_refuses_replacement_before_runtime_or_container(public,tmp_path):
    def never(*a,**k):pytest.fail('destructive overlay launched a subprocess')
    out=tmp_path/'tool'
    with pytest.raises(ValueError,match='existing named test'):
        run_tests(str(public),str(tmp_path/'missing-runtime.json'),str(out),
            {'action':'run','files':{'tests/test_old.py':NEW},'tests':['tests/test_old.py']},runner=never)
    assert not out.exists()
