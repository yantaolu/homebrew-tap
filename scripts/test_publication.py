import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


guard = module('publication-guard')
upload = module('upload-bottles')
HEAD = 'a' * 40


def pr():
    return {'state': 'open', 'draft': False, 'number': 2, 'changed_files': 1,
            'head': {'repo': {'full_name': guard.REPO}, 'ref': 'release/codex-switch-v1.0.1', 'sha': HEAD},
            'base': {'ref': 'main'}}


def run():
    return {'id': 20, 'conclusion': 'success', 'event': 'pull_request', 'head_sha': HEAD,
            'head_repository': {'full_name': guard.REPO}, 'path': '.github/workflows/tests.yml'}


class GuardTests(unittest.TestCase):
    def test_auto_selects_only_current_managed_head(self):
        self.assertEqual(guard.select({'workflow_run': run()}, lambda _: [pr()]), (2, HEAD, 20))
        changed = pr()
        changed['head']['sha'] = 'b' * 40
        self.assertIsNone(guard.select({'workflow_run': run()}, lambda _: [changed]))

    def test_failed_main_push_and_fork_never_publish(self):
        for key, value in [('conclusion', 'failure'), ('event', 'push'),
                           ('head_repository', {'full_name': 'other/fork'})]:
            event = run()
            event[key] = value
            def forbidden(_): raise AssertionError('Must not query PR or publish')
            self.assertIsNone(guard.select({'workflow_run': event}, forbidden))

    def test_manual_branch_not_selected_automatically(self):
        p = pr()
        p['head']['ref'] = 'manual-test'
        self.assertIsNone(guard.select({'workflow_run': run()}, lambda _: [p]))

    def test_exact_two_native_jobs_and_artifacts_required(self):
        def request(path):
            if '/workflows/tests.yml/runs?' in path: return {'workflow_runs': [run()]}
            if path.endswith('/20'): return run()
            if '/jobs?' in path: return {'jobs': [{'name': name, 'conclusion': 'success'} for name in guard.JOBS]}
            if '/artifacts?' in path: return {'artifacts': [{'name': name, 'expired': False, 'size_in_bytes': 10} for name in ('bottles_macos-15', 'bottles_macos-15-intel')]}
            raise AssertionError(path)
        self.assertEqual(guard.test_run(pr(), 20, request), 20)
        def skipped(path):
            value = request(path)
            if '/jobs?' in path: value['jobs'][0]['conclusion'] = 'skipped'
            return value
        with self.assertRaisesRegex(ValueError, 'Both native'):
            guard.test_run(pr(), 20, skipped)
        def expired(path):
            value = request(path)
            if '/artifacts?' in path: value['artifacts'][0]['expired'] = True
            return value
        with self.assertRaisesRegex(ValueError, 'expired'):
            guard.test_run(pr(), 20, expired)

    def test_test_run_head_mismatch_blocked(self):
        r = run()
        r['head_sha'] = 'b' * 40
        def request(path):
            return {'workflow_runs': [r]} if '/workflows/tests.yml/runs?' in path else r
        with self.assertRaisesRegex(ValueError, 'reviewed PR head'):
            guard.test_run(pr(), 20, request)

    def test_newer_pending_run_blocks_older_success(self):
        with self.assertRaisesRegex(ValueError, 'newer test run'):
            guard.test_run(pr(), 20, lambda _: {'workflow_runs': [{'id': 21}]})

    def test_changed_pr_head_and_extra_files_blocked(self):
        changed = pr()
        changed['head']['sha'] = 'b' * 40
        with self.assertRaisesRegex(ValueError, 'head changed'):
            guard.guard(2, HEAD, request=lambda _: changed)
        changed = pr()
        changed['changed_files'] = 2
        def request(path):
            return [{'filename': guard.FORMULA}, {'filename': 'scripts/untrusted.py'}] if '/files?' in path else changed
        with self.assertRaisesRegex(ValueError, 'only the formula'):
            guard.guard(2, HEAD, request=request)


class UploadTests(unittest.TestCase):
    def fixture(self, directory):
        tags = {}
        for tag in ('arm64_sequoia', 'sequoia'):
            name = f'codex-switch-1.0.1.{tag}.bottle.tar.gz'
            local = name.replace('switch-', 'switch--')
            (directory / local).write_bytes(tag.encode())
            tags[tag] = {'filename': name, 'local_filename': local,
                         'sha256': hashlib.sha256(tag.encode()).hexdigest()}
        bottle = {'root_url': f'https://github.com/{upload.REPO}/releases/download/codex-switch-1.0.1', 'tags': tags}
        (directory / 'merged.bottle.json').write_text(json.dumps({'yantaolu/tap/codex-switch': {
            'formula': {'pkg_version': '1.0.1'}, 'bottle': bottle}}))
        return bottle

    def test_partial_upload_retries_only_missing_asset_with_correct_name(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            bottle = self.fixture(directory)
            arm = bottle['tags']['arm64_sequoia']['filename']
            calls = []
            def gh(*args):
                calls.append(args)
                if 'matching-refs' in str(args): return json.dumps([{'ref': 'refs/tags/codex-switch-1.0.1'}])
                if 'releases/tags' in str(args): return json.dumps({'draft': False, 'prerelease': False, 'assets': [{'name': arm, 'browser_download_url': bottle['root_url'] + '/' + arm}]})
                return ''
            with patch.object(upload, 'gh', gh), patch.object(upload.urllib.request, 'urlopen', return_value=io.BytesIO(b'arm64_sequoia')):
                upload.publish(directory)
            uploads = [call for call in calls if call[:2] == ('release', 'upload')]
            self.assertEqual(len(uploads), 1)
            self.assertEqual(Path(uploads[0][3]).name, bottle['tags']['sequoia']['filename'])
            self.assertNotIn('--clobber', uploads[0])

    def test_conflicting_existing_bottle_never_uploads(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            bottle = self.fixture(directory)
            name = bottle['tags']['arm64_sequoia']['filename']
            def gh(*args):
                if 'matching-refs' in str(args): return json.dumps([{'ref': 'refs/tags/codex-switch-1.0.1'}])
                if 'releases/tags' in str(args): return json.dumps({'draft': False, 'prerelease': False, 'assets': [{'name': name, 'browser_download_url': bottle['root_url'] + '/' + name}]})
                raise AssertionError('Must not upload or overwrite a conflicting bottle')
            with patch.object(upload, 'gh', gh), patch.object(upload.urllib.request, 'urlopen', return_value=io.BytesIO(b'wrong')):
                with self.assertRaisesRegex(ValueError, 'refusing replacement'):
                    upload.publish(directory)

    def test_local_corruption_blocks_all_api_mutations(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            bottle = self.fixture(directory)
            (directory / bottle['tags']['sequoia']['local_filename']).write_bytes(b'bad')
            with patch.object(upload, 'gh', side_effect=AssertionError('No API mutation allowed')):
                with self.assertRaisesRegex(ValueError, 'Local bottle checksum'):
                    upload.publish(directory)


if __name__ == '__main__':
    unittest.main()
