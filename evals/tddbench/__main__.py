"""Explicit preparation, execution and reporting for TDD-Bench-Verified."""
import argparse
import json
import pathlib
import subprocess

from .adapter import fetch_verified, harness_command, prepare, summarize


def main(argv=None):
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("fetch")
    fetch.add_argument("out")
    prep = sub.add_parser("prepare")
    prep.add_argument("--dataset", required=True)
    prep.add_argument("--membership", required=True)
    prep.add_argument("--archive", required=True)
    prep.add_argument("--out", required=True)
    prep.add_argument("--seed", type=int, default=20261024)
    snapshot = sub.add_parser('snapshot', help='export issue and base code without Git history')
    snapshot.add_argument('--public', required=True)
    snapshot.add_argument('--instance', required=True)
    snapshot.add_argument('--out', required=True)
    runtime = sub.add_parser('runtime', help='inspect and pin a dependency or public-installed image to public code')
    runtime.add_argument('--workspace', required=True)
    runtime.add_argument('--image', required=True)
    runtime.add_argument('--out', required=True)
    sandbox = sub.add_parser('sandbox', help='run a code tool with only a public workspace mounted')
    sandbox.add_argument('--workspace', required=True)
    sandbox.add_argument('--output', required=True)
    sandbox.add_argument('--execute', action='store_true')
    sandbox.add_argument('argv', nargs=argparse.REMAINDER)
    gen = sub.add_parser('generate', help='generate a direct-agent candidate from public code')
    gen.add_argument('--workspace', required=True)
    gen.add_argument('--out', required=True)
    gen.add_argument('--endpoint', required=True, help='chat-completions API base, e.g. http://localhost:8000/v1')
    gen.add_argument('--model', required=True)
    gen.add_argument('--mode', choices=('direct', 'athena', 'athena-trust'), default='direct')
    gen.add_argument('--api-key-env', default='ATHENA_BENCH_API_KEY')
    gen.add_argument('--max-calls', type=int, default=12)
    gen.add_argument('--max-output-tokens', type=int, default=4096)
    gen.add_argument('--max-context-chars', type=int, default=160000)
    gen.add_argument('--request-timeout', type=int, default=120)
    gen.add_argument('--runtime', default='')
    gen.add_argument('--max-test-runs', type=int, default=12)
    gen.add_argument('--test-timeout', type=int, default=60)
    gen.add_argument('--execute', action='store_true')
    review = sub.add_parser('review', help='review a frozen candidate in a fresh model context')
    review.add_argument('--workspace', required=True)
    review.add_argument('--generation', required=True)
    review.add_argument('--out', required=True)
    review.add_argument('--endpoint', required=True)
    review.add_argument('--model', required=True)
    review.add_argument('--api-key-env', default='ATHENA_BENCH_API_KEY')
    review.add_argument('--execute', action='store_true')
    trust = sub.add_parser('trust', help='run the native trust audit on a separately reviewed candidate')
    trust.add_argument('--workspace', required=True)
    trust.add_argument('--generation', required=True)
    trust.add_argument('--runtime', required=True)
    trust.add_argument('--review', required=True)
    trust.add_argument('--out', required=True)
    trust.add_argument('--execute', action='store_true')
    run = sub.add_parser("run")
    run.add_argument("directory")
    run.add_argument("--harness", required=True)
    run.add_argument("--run-id", required=True)
    run.add_argument("--git-authorized", action="store_true")
    run.add_argument("--execute", action="store_true")
    run.add_argument("--timeout", type=int, default=600)
    run.add_argument("--mode", choices=("calibration", "evaluation"), default="calibration")
    run.add_argument("--predictions", default="gold", help="gold or a JSON/JSONL path inside the benchmark directory")
    report = sub.add_parser("report")
    report.add_argument("directory")
    report.add_argument("--run-id", required=True)
    report.add_argument("--mode", choices=("calibration", "evaluation"), default="calibration")
    args = p.parse_args(argv)
    if args.command == "fetch":
        rows = fetch_verified(args.out)
        print(json.dumps({"downloaded": len(rows), "dataset": args.out}))
    elif args.command == "prepare":
        print(json.dumps(prepare(args.dataset, args.membership, args.archive, args.out, seed=args.seed), indent=2))
    elif args.command == "run":
        cmd = harness_command(args.directory, args.harness, git_authorized=args.git_authorized,
                              run_id=args.run_id, timeout=args.timeout, mode=args.mode,
                              predictions=args.predictions)
        if not args.execute:
            print(json.dumps({"command": cmd, "executed": False}, indent=2))
        else:
            return subprocess.call(cmd)
    elif args.command == 'snapshot':
        from .workspace import export_workspace
        result = export_workspace(args.public, args.instance, args.out)
        print(json.dumps({'instance_id': result['instance_id'], 'files': len(result['files']),
                          'archive_sha256': result['archive_sha256'], 'destination': args.out}))
    elif args.command == 'sandbox':
        from .workspace import sandbox_command
        argv = args.argv[1:] if args.argv[:1] == ['--'] else args.argv
        cmd = sandbox_command(args.workspace, args.output, argv)
        if args.execute:
            pathlib.Path(args.output).mkdir(parents=True, exist_ok=True)
            return subprocess.call(cmd)
        print(json.dumps({'command': cmd, 'executed': False}))
    elif args.command == 'runtime':
        from .execution import prepare_runtime
        result = prepare_runtime(args.workspace, args.image, args.out)
        print(json.dumps(result))
    elif args.command == 'generate':
        from dataclasses import asdict
        from .generator import Budget, HTTPModel, generate_direct
        from .workspace import verify_workspace
        budget = Budget(args.max_calls, args.max_output_tokens, args.max_context_chars, args.request_timeout,
                        args.max_test_runs, args.test_timeout)
        budget.validate()
        model = HTTPModel(args.endpoint, args.model, key_env=args.api_key_env)
        if not args.execute:
            snapshot = verify_workspace(args.workspace)
            if args.runtime:
                from .execution import load_runtime
                load_runtime(args.workspace, args.runtime)
            if args.mode != 'direct' and not args.runtime:
                raise ValueError('Athena generation requires an offline dependency runtime')
            print(json.dumps({'executed': False, 'mode': args.mode, 'instance_id': snapshot['instance_id'],
                              'endpoint': model.endpoint, 'model': model.model, 'budget': asdict(budget)}))
        else:
            receipt = generate_direct(args.workspace, args.out, model, budget=budget,
                                      runtime_receipt=args.runtime or None, mode=args.mode)
            print(json.dumps({k: receipt[k] for k in ('status', 'reason', 'calls', 'instance_id', 'mode')}))
            return 0 if receipt['status'] in ('GENERATED', 'AWAITING_REVIEW') else 1
    elif args.command in ('review', 'trust'):
        from .trust import load_candidate, create_review, audit_candidate
        receipt, _, _ = load_candidate(args.workspace, args.generation)
        if not args.execute:
            print(json.dumps({'executed': False, 'stage': args.command,
                              'candidate_sha256': receipt['candidate_sha256']}))
        elif args.command == 'review':
            from .generator import HTTPModel
            model = HTTPModel(args.endpoint, args.model, key_env=args.api_key_env)
            result = create_review(args.workspace, args.generation, args.out, model)
            print(json.dumps({k: result[k] for k in ('state', 'reason', 'calls')}))
            return 0 if result['state'] == 'READY' else 1
        else:
            result = audit_candidate(args.workspace, args.generation, args.runtime, args.review, args.out)
            print(json.dumps({k: result[k] for k in ('state', 'reason')}))
            return 0 if result['passed'] else 1
    else:
        result = summarize(args.directory, args.run_id, mode=args.mode)
        destination = pathlib.Path(args.directory) / (args.run_id + ".athena-report.json")
        destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
        return 0 if result["state"] == "PASS" else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
