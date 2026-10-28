"""Offline test tools using inspected dependencies or public-only installed runtimes."""
from __future__ import annotations

import json
import inspect
import pathlib
import re
import subprocess
import uuid

from lib.verification import junit_outcome
from .adapter import sha
from .workspace import sandbox_command, verify_workspace
from .fsmodel import restore_source, through_link, python_source_paths, project_origin, copy_installed_source
from .build_artifacts import validate_artifacts, inventory_build_artifacts, restore_build_artifacts

PROJECT_MODULES = {'psf/requests': 'requests', 'sphinx-doc/sphinx': 'sphinx', 'pallets/flask': 'flask',
                   'django/django': 'django', 'matplotlib/matplotlib': 'matplotlib', 'pytest-dev/pytest': 'pytest',
                   'astropy/astropy': 'astropy', 'pylint-dev/pylint': 'pylint', 'scikit-learn/scikit-learn': 'sklearn',
                   'mwaskom/seaborn': 'seaborn', 'sympy/sympy': 'sympy', 'pydata/xarray': 'xarray'}

PYTHON = '/opt/miniconda3/envs/testbed/bin/python'
PROBE = '''import json,os,sys,pytest
assert os.path.isdir('/testbed') and not os.listdir('/testbed'), 'image contains task source'
assert not os.path.exists('/root/setup_repo.sh'), 'task setup script present'
print(json.dumps({'empty_testbed':True,'python':sys.version.split()[0],'pytest':pytest.__version__,'filesystem_encoding':sys.getfilesystemencoding()}))
'''

PUBLIC_PROBE = (inspect.getsource(validate_artifacts) + '\n' + inspect.getsource(inventory_build_artifacts) + '\n') + '''import hashlib,json,os,pathlib,sys,pytest
snapshot=json.load(sys.stdin)
root=pathlib.Path('/opt/athena-public-base')
assert pathlib.Path('/testbed').resolve()==root, 'unexpected editable source location'
assert not pathlib.Path('/root/setup_repo.sh').exists(), 'task setup script present'
for item in snapshot['files']:
    path=root/item['path']
    if item.get('kind')=='symlink':
        assert path.is_symlink() and os.readlink(str(path))==item['target'], 'public link differs'
    else:
        assert path.is_file() and not path.is_symlink(), 'public source missing'
        assert hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256'], 'public source differs'
for folder,dirs,files in os.walk('/',followlinks=False):
    if folder=='/': dirs[:]=[name for name in dirs if name not in ('proc','sys','dev')]
    assert not any(name.lower()=='.git' for name in dirs+files), 'Git history present'
assert not pathlib.Path('/bench/sealed').exists(), 'evaluator data present'
print(json.dumps({'public_source_verified':True,'history_free':True,'task_setup_present':False,
                  'build_artifacts':inventory_build_artifacts(snapshot,root),
                  'filesystem_encoding':sys.getfilesystemencoding(),
                  'python':sys.version.split()[0],'pytest':pytest.__version__}))
'''


def _runtime_kind(image: str) -> str:
    if re.fullmatch(r'sweb\.env\.x86_64\.[a-f0-9]{16,64}:latest', image):
        return 'environment-only'
    if re.fullmatch(r'athena\.public-runtime:[a-z0-9][a-z0-9_.-]{0,127}', image):
        return 'public-installed'
    raise ValueError('only environment-only or inspected public-installed images are allowed')


def prepare_runtime(directory: str, image: str, destination: str, *, runner=subprocess.run) -> dict:
    """Trusted provisioning: bind an inspected dependency image to one public snapshot."""
    snapshot = verify_workspace(directory)
    kind = _runtime_kind(image)
    out, root = pathlib.Path(destination).resolve(), pathlib.Path(directory).resolve()
    if out.is_relative_to(root) or out.exists():
        raise ValueError('runtime receipt must be new and outside the public workspace')
    inspected = runner(['docker', 'image', 'inspect', image, '--format', '{{.Id}}'],
                       capture_output=True, text=True, timeout=30, check=True)
    image_id = inspected.stdout.strip()
    if not re.fullmatch(r'sha256:[a-f0-9]{64}', image_id):
        raise ValueError('image inspect did not return an immutable id')
    snapshot_hash = sha((root / 'snapshot.json').read_bytes())
    if kind == 'public-installed':
        labels = json.loads(runner(['docker', 'image', 'inspect', image_id,
                                   '--format', '{{json .Config.Labels}}'],
                                  capture_output=True, text=True, timeout=30, check=True).stdout)
        if not isinstance(labels, dict) or labels.get('athena.public.instance') != snapshot['instance_id'] or labels.get('athena.public.snapshot') != snapshot_hash:
            raise ValueError('public runtime labels do not match the public snapshot')
    cmd = ['docker', 'run', '--rm', '--network', 'none', '--read-only',
           '--env', 'LANG=C.UTF-8', '--env', 'LC_ALL=C.UTF-8', '--entrypoint', PYTHON,
           image_id, '-c', PUBLIC_PROBE if kind == 'public-installed' else PROBE]
    options = {'input': json.dumps(snapshot)} if kind == 'public-installed' else {}
    if kind == 'public-installed':
        cmd.insert(3, '--interactive')
    probe = runner(cmd, capture_output=True, text=True, timeout=120, check=True, **options)
    info = json.loads(probe.stdout)
    if info.get('filesystem_encoding', '').lower().replace('-', '') != 'utf8':
        raise ValueError('runtime does not provide UTF-8 filesystem encoding')
    if kind == 'environment-only' and info.get('empty_testbed') is not True:
        raise ValueError('runtime contains task source')
    if kind == 'public-installed' and (info.get('public_source_verified') is not True or
            info.get('history_free') is not True or info.get('task_setup_present') is not False):
        raise ValueError('public runtime inspection is incomplete')
    artifacts = validate_artifacts(snapshot, info.get('build_artifacts', []))
    result = {'schema': 'athena.public_runtime/1' if kind == 'environment-only' else 'athena.public_runtime/2',
              'instance_id': snapshot['instance_id'], 'image_kind': kind,
              'snapshot_sha256': snapshot_hash,
              'image_tag': image, 'image_id': image_id, 'probe': info, 'python': PYTHON,
              'expected_module': PROJECT_MODULES.get(snapshot['repo'])}
    if kind == 'public-installed':
        result['build_artifacts'] = artifacts
        result['build_artifacts_sha256'] = sha(json.dumps(artifacts, sort_keys=True).encode())
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    return result


def load_runtime(directory: str, receipt: str) -> dict:
    snapshot = verify_workspace(directory)
    runtime = json.loads(pathlib.Path(receipt).read_text(encoding='utf-8'))
    kind = _runtime_kind(runtime.get('image_tag', ''))
    schema = 'athena.public_runtime/1' if kind == 'environment-only' else 'athena.public_runtime/2'
    inspected = (runtime.get('probe', {}).get('empty_testbed') is True if kind == 'environment-only' else
                 runtime.get('probe', {}).get('public_source_verified') is True and
                 runtime.get('probe', {}).get('history_free') is True and
                 runtime.get('probe', {}).get('task_setup_present') is False)
    if (runtime.get('schema') != schema
            or runtime.get('image_kind', 'environment-only') != kind
            or runtime.get('instance_id') != snapshot['instance_id']
            or runtime.get('snapshot_sha256') != sha((pathlib.Path(directory) / 'snapshot.json').read_bytes())
            or not re.fullmatch(r'sha256:[a-f0-9]{64}', runtime.get('image_id', ''))
            or not inspected or runtime.get('python') != PYTHON):
        raise ValueError('runtime receipt does not match the public snapshot')
    expected = PROJECT_MODULES.get(snapshot['repo'])
    encoding = runtime.get('probe', {}).get('filesystem_encoding')
    if encoding is not None and encoding.lower().replace('-', '') != 'utf8':
        raise ValueError('runtime does not provide UTF-8 filesystem encoding')
    if runtime.get('expected_module', expected) != expected:
        raise ValueError('runtime module identity differs from public repository')
    artifacts = validate_artifacts(snapshot, runtime.get('build_artifacts', []))
    if ('build_artifacts' in runtime or 'build_artifacts_sha256' in runtime) and (
            kind != 'public-installed' or
            runtime.get('build_artifacts_sha256') != sha(json.dumps(artifacts, sort_keys=True).encode())):
        raise ValueError('runtime build artifacts fingerprint differs')
    return {**runtime, 'expected_module': expected}


def _test_path(name: str) -> pathlib.PurePosixPath:
    if not isinstance(name, str) or not name or any(c in name for c in '\\:<>|"*?'):
        raise ValueError('invalid test file path')
    p = pathlib.PurePosixPath(name)
    if (p.is_absolute() or any(x in ('.', '..', '') or x.lower() == '.git' for x in name.split('/'))
            or not name.endswith('.py') or p.name in ('conftest.py', '__init__.py', 'setup.py')
            or not ('tests' in p.parts or p.name.startswith(('test_', 'unittest_')) or p.name.endswith('_test.py'))):
        raise ValueError('candidate overlays may contain only test files')
    return p


def validate_test_action(action: dict) -> dict:
    files, nodes = action.get('files'), action.get('tests')
    if not isinstance(files, dict) or not files or len(files) > 20:
        raise ValueError('run requires between one and twenty test files')
    if not isinstance(nodes, list) or not nodes or len(nodes) > 50:
        raise ValueError('run requires between one and fifty test nodes')
    for name, content in files.items():
        _test_path(name)
        if not isinstance(content, str):
            raise ValueError('test content must be text')
    if sum(len(v.encode('utf-8')) for v in files.values()) > 1024 * 1024:
        raise ValueError('candidate tests exceed one-megabyte tool limit')
    for node in nodes:
        if not isinstance(node, str) or len(node) > 1000:
            raise ValueError('invalid test node')
        name = node.split('::', 1)[0]
        _test_path(name)
        if name not in files:
            raise ValueError('select only submitted test files')
    return {'files': files, 'tests': nodes}


def validate_reference(directory: str, files: dict | list | None) -> dict:
    """A model proposal can replace known Python implementation, never test/config files."""
    if files is None:
        return {}
    snapshot = verify_workspace(directory)
    known = {item['path'] for item in snapshot['files']}
    links = {item['path'] for item in snapshot['files'] if item.get('kind') == 'symlink'}
    if isinstance(files, list):
        if not files or len(files) > 20:
            raise ValueError('reference edits require between one and twenty replacements')
        resolved = {}
        for edit in files:
            if not isinstance(edit, dict) or set(edit) != {'path', 'old', 'new'}:
                raise ValueError('reference edit requires path, old and new')
            name, old, new = edit['path'], edit['old'], edit['new']
            if (not isinstance(name, str) or name not in known or not isinstance(old, str)
                    or not old or not isinstance(new, str)):
                raise ValueError('reference edit must target known public source')
            source = resolved.get(name)
            if source is None:
                source = (pathlib.Path(directory) / 'source' / name).read_text(encoding='utf-8')
            if source.count(old) != 1:
                raise ValueError('reference edit anchor must occur exactly once')
            resolved[name] = source.replace(old, new, 1)
        files = resolved
    if not isinstance(files, dict) or len(files) > 20:
        raise ValueError('reference proposal must contain at most twenty implementation files')
    for name, content in files.items():
        if not isinstance(name, str) or name not in known or name in links or not isinstance(content, str):
            raise ValueError('reference proposal must use known public implementation files')
        p = pathlib.PurePosixPath(name)
        if (p.suffix != '.py' or any(x in ('tests', '.git') for x in p.parts)
                or p.name.startswith(('test_', 'unittest_')) or p.name.endswith('_test.py')
                or p.name in ('conftest.py', 'setup.py')):
            raise ValueError('reference proposal cannot replace tests or runtime configuration')
    if sum(len(v.encode('utf-8')) for v in files.values()) > 1024 * 1024:
        raise ValueError('reference proposal exceeds one-megabyte tool limit')
    return files


# This fixed runner executes inside the offline container. Test code is a separate
# process, its stdout/stderr go to a diagnostic file, and no model argv reaches the host.
ORIGIN_PROBE = 'import json,pathlib,sys\n' + inspect.getsource(project_origin) + "\nprint(json.dumps(project_origin(sys.argv[1],pathlib.Path(sys.argv[2]))))\n"
TEST_RUNNER = ('import json,os,pathlib,shutil,subprocess,sys,resource\n' + inspect.getsource(restore_source)
               + inspect.getsource(copy_installed_source)
               + inspect.getsource(python_source_paths) + inspect.getsource(validate_artifacts)
               + inspect.getsource(restore_build_artifacts) + '\nORIGIN_PROBE=' + repr(ORIGIN_PROBE) + '\n') + '''
payload=json.load(sys.stdin)
work=pathlib.Path('/tmp/work')
snapshot=json.loads(pathlib.Path('/input/snapshot.json').read_text())
if payload.get('source_mode')=='public-installed':
    copy_installed_source(snapshot,pathlib.Path('/opt/athena-public-base'),work)
else:
    shutil.copytree('/input/source',work)
restore_source(snapshot,work)
restore_build_artifacts(snapshot,payload.get('build_artifacts',[]),pathlib.Path('/opt/athena-public-base'),work)
for name,content in {**payload.get('implementation',{}),**payload['files']}.items():
    path=work/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(content,encoding='utf-8')
os.chdir(work)
resource.setrlimit(resource.RLIMIT_FSIZE,(8*1024*1024,8*1024*1024))
env=dict(os.environ,PYTHONPATH=os.pathsep.join(python_source_paths(work)),HOME='/tmp',PYTHONDONTWRITEBYTECODE='1')
with open('/output/test.log','w') as log:
    origin_ok=True
    if payload.get('expected_module'):
        probe=subprocess.run([sys.executable,'-c',ORIGIN_PROBE,payload['expected_module'],str(work)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True,env=env)
        try:
            origin=json.loads(probe.stdout)
        except ValueError:
            origin={'in_public_source':False,'reason':'origin probe returned no JSON'}
        pathlib.Path('/output/project-origin.json').write_text(json.dumps(origin))
        origin_ok=probe.returncode==0 and origin.get('in_public_source') is True
        if not origin_ok:
            log.write('project module is not the copied public source: '+json.dumps(origin)+chr(10)+probe.stderr)
    if origin_ok:
        result=subprocess.run([sys.executable,'-m','pytest','-q','--junitxml=/output/junit.xml',*payload['tests']],stdout=log,stderr=subprocess.STDOUT,env=env)
        process={'exit_code':result.returncode}
    else:
        process={'exit_code':2,'infrastructure_error':'project import origin is outside public source'}
pathlib.Path('/output/process.json').write_text(json.dumps(process))
'''


def run_tests(directory: str, runtime_receipt: str, destination: str, action: dict, *,
              timeout: int = 60, runner=subprocess.run, implementation: dict | list | None = None) -> dict:
    if type(timeout) is not int or timeout <= 0:
        raise ValueError('test tool timeout must be a positive integer')
    payload = validate_test_action(action)
    snapshot = verify_workspace(directory)
    links = {item['path'] for item in snapshot['files'] if item.get('kind') == 'symlink'}
    if any(through_link(name, links) for name in payload['files']):
        raise ValueError('test overlays cannot replace source symlinks')
    from .test_preservation import preserve_named_tests
    for name, content in payload['files'].items():
        path = pathlib.Path(directory) / 'source' / name
        preserve_named_tests(path.read_text(encoding='utf-8') if path.is_file() else '', content, name)
    payload['implementation'] = validate_reference(directory, implementation)
    runtime = load_runtime(directory, runtime_receipt)
    payload['expected_module'] = runtime['expected_module']
    payload['build_artifacts'] = runtime.get('build_artifacts', [])
    payload['source_mode'] = runtime.get('image_kind', 'environment-only')
    out = pathlib.Path(destination).resolve()
    # Reuse the already tested isolation flags, replacing only the trusted runtime.
    cmd = sandbox_command(directory, str(out), [PYTHON, '-c', TEST_RUNNER])
    cmd[cmd.index('athena-tdd-controller:20261024')] = runtime['image_id']
    # Repository copies and installed scientific packages need more than a small script.
    cmd[cmd.index('--memory') + 1] = '2g'
    cmd[cmd.index('--tmpfs') + 1] = '/tmp:rw,exec,nosuid,nodev,size=1g'
    name = 'athena-generator-' + uuid.uuid4().hex
    cmd[2:2] = ['--interactive', '--name', name]
    out.mkdir(parents=True, exist_ok=False)
    request_json = json.dumps(payload)
    result = {'schema': 'athena.public_test_tool/1', 'status': 'TOOL_ERROR',
              'diagnostic_only': True, 'image_id': runtime['image_id'],
              'request_sha256': sha(request_json.encode('utf-8')), 'command': cmd}
    try:
        process = runner(cmd, input=request_json, capture_output=True, text=True, timeout=timeout)
        if process.returncode != 0 or not (out / 'process.json').exists():
            result['reason'] = 'container or test runner did not finish normally'
        else:
            process_info = json.loads((out / 'process.json').read_text())
            code = process_info['exit_code']
            xml = (out / 'junit.xml').read_text() if (out / 'junit.xml').exists() else ''
            observed = junit_outcome(code, xml)
            result.update(status=observed.status, test_exit_code=code, tests=observed.tests)
            if process_info.get('infrastructure_error'):
                result.update(status='TOOL_ERROR', reason=process_info['infrastructure_error'])
    except subprocess.TimeoutExpired:
        result.update(status='TIMEOUT', reason='test tool time budget exhausted', timed_out=True)
    except (OSError, ValueError, KeyError) as error:
        result['reason'] = 'test tool error: ' + type(error).__name__
    finally:
        # Kill only this invocation, including children, even if the Docker client timed out.
        try:
            cleanup = runner(['docker', 'rm', '-f', name], capture_output=True, text=True, timeout=30)
            if cleanup.returncode and 'No such container' not in getattr(cleanup, 'stderr', ''):
                result.update(status='TOOL_ERROR', reason='container cleanup could not be confirmed')
        except (OSError, subprocess.TimeoutExpired):
            result.update(status='TOOL_ERROR', reason='container cleanup could not be confirmed')
    (out / 'request.json').write_text(request_json, encoding='utf-8')
    if (out / 'project-origin.json').exists():
        result['project_origin'] = json.loads((out / 'project-origin.json').read_text(encoding='utf-8'))
    log = out / 'test.log'
    if log.exists():
        with log.open('rb') as stream:
            stream.seek(max(0, log.stat().st_size - 16000))
            result['tail'] = stream.read(16000).decode('utf-8', errors='replace')
    (out / 'tool.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result
