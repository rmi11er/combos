import gzip
import hashlib
import os
from pathlib import Path
import subprocess
import sys

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import replay_artifact_io as artifacts


@pytest.mark.parametrize('suffix', ['gz', 'zst'])
def test_text_roundtrip_unicode_line_endings_large_writes(tmp_path, suffix):
    content = ('{"team":"São Paulo ⚾", "x": 1.00}\r\n' * 50000) + '\nlast\r'
    path = tmp_path / ('rows.jsonl.' + suffix)
    with artifacts.text_writer(path) as handle:
        handle.write(content)
        assert not path.exists()  # No partial artifact is published.
    with artifacts.text_reader(path) as handle:
        assert handle.read() == content
    assert list(tmp_path.glob('*.partial')) == []


def test_export_preserves_arbitrary_bytes_without_json_or_utf8_decode(tmp_path):
    content = b' {"a": 1.00}\r\n\xff\x00 no JSON\n'
    source = tmp_path / 'source.jsonl.zst'
    with artifacts._binary_writer(source) as handle:
        handle.write(content)
    output = tmp_path / 'output.jsonl.gz'
    report = artifacts.export_gzip(source, output)
    assert gzip.decompress(output.read_bytes()) == content
    assert report['decoded_sha256'] == hashlib.sha256(content).hexdigest()
    assert report['decoded_bytes'] == len(content)
    with pytest.raises(FileExistsError):
        artifacts.export_gzip(source, output)
    assert gzip.decompress(output.read_bytes()) == content


@pytest.mark.parametrize('suffix', ['gz', 'zst'])
def test_truncated_tail_detected_even_when_only_prefix_read(tmp_path, suffix):
    path = tmp_path / ('rows.jsonl.' + suffix)
    with artifacts.text_writer(path) as handle:
        handle.write('hello\n' * 10000)
    path.write_bytes(path.read_bytes()[:-5])
    with pytest.raises((artifacts.ArtifactCodecError, EOFError, gzip.BadGzipFile)):
        with artifacts.text_reader(path) as handle:
            handle.read(1)


def test_corrupt_export_never_publishes(tmp_path):
    source = tmp_path / 'broken.jsonl.zst'
    source.write_bytes(b'not a zstd file')
    destination = tmp_path / 'output.jsonl.gz'
    with pytest.raises(artifacts.ArtifactCodecError):
        artifacts.export_gzip(source, destination)
    assert not destination.exists()
    assert list(tmp_path.glob('*.partial')) == []


def fake_codec(tmp_path, body):
    path = tmp_path / 'fake_codec'
    path.write_text('#!' + sys.executable + '\n' + body)
    path.chmod(0o700)
    return path


def test_compressor_error_large_stderr_does_not_deadlock_or_publish(tmp_path):
    fake = fake_codec(tmp_path, 'import sys\nsys.stdin.buffer.read()\nsys.stderr.write("failure"*50000)\nsys.exit(7)\n')
    path = tmp_path / 'error.jsonl.zst'
    with pytest.raises(artifacts.ArtifactCodecError, match='exited 7'):
        with artifacts.text_writer(path, executable=fake) as handle:
            handle.write('hello\n')
    assert not path.exists()
    assert list(tmp_path.glob('*.partial')) == []


@pytest.mark.parametrize('direction', ['reader', 'writer'])
def test_consumer_exception_reaps_child_and_preserves_original_error(tmp_path, monkeypatch, direction):
    fake = fake_codec(tmp_path, 'import time\ntime.sleep(60)\n')
    children = []
    original = subprocess.Popen
    def tracked(*args, **kwargs):
        child = original(*args, **kwargs)
        children.append(child)
        return child
    monkeypatch.setattr(artifacts.subprocess, 'Popen', tracked)
    path = tmp_path / 'rows.jsonl.zst'
    manager = artifacts.text_reader if direction == 'reader' else artifacts.text_writer
    with pytest.raises(ValueError, match='consumer failed'):
        with manager(path, executable=fake) as handle:
            if direction == 'writer':
                handle.write('buffered Unicode ⚾')
            raise ValueError('consumer failed')
    assert children and all(child.poll() is not None for child in children)
    assert not path.exists()
    assert list(tmp_path.glob('*.partial')) == []


def test_atomic_publication_refuses_competing_output(tmp_path):
    path = tmp_path / 'raced.jsonl.gz'
    with pytest.raises(FileExistsError):
        with artifacts.text_writer(path) as handle:
            handle.write('ours')
            path.write_bytes(b'theirs')
    assert path.read_bytes() == b'theirs'
    assert list(tmp_path.glob('*.partial')) == []


def test_existing_writer_target_and_unknown_codec_rejected(tmp_path):
    path = tmp_path / 'old.jsonl.zst'
    path.write_bytes(b'original')
    with pytest.raises(FileExistsError):
        with artifacts.text_writer(path):
            pass
    assert path.read_bytes() == b'original'
    with pytest.raises(ValueError, match='Expected'):
        with artifacts.text_writer(tmp_path / 'wrong.gz'):
            pass


def test_cli_identity_pins_binary_and_version():
    identity = artifacts.zstd_identity()
    assert 'Zstandard CLI' in identity['version']
    assert len(identity['sha256']) == 64
    assert identity['sha256'] == artifacts._hash_file(identity['executable'])
    assert identity['compression_arguments'] == ['-q', '-6', '-c']


def test_early_compressor_exit_converts_broken_pipe(tmp_path):
    fake = fake_codec(tmp_path, 'import sys\nsys.exit(9)\n')
    path = tmp_path / 'early.jsonl.zst'
    with pytest.raises(artifacts.ArtifactCodecError):
        with artifacts.text_writer(path, executable=fake) as handle:
            handle.write('x' * 1000000)
    assert not path.exists()
    assert list(tmp_path.glob('*.partial')) == []


def test_missing_codec_removes_temporary_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        with artifacts.text_writer(tmp_path / 'missing.jsonl.zst', executable=tmp_path / 'absent'):
            pass
    assert list(tmp_path.iterdir()) == []


def test_uncooperative_decoder_is_killed_and_reaped(tmp_path, monkeypatch):
    fake = fake_codec(tmp_path, 'import signal,sys,time\nsignal.signal(signal.SIGTERM,signal.SIG_IGN)\nsys.stdout.write("ready\\n");sys.stdout.flush()\ntime.sleep(60)\n')
    children = []
    original = subprocess.Popen
    def tracked(*args, **kwargs):
        child = original(*args, **kwargs)
        children.append(child)
        return child
    monkeypatch.setattr(artifacts.subprocess, 'Popen', tracked)
    with pytest.raises(ValueError, match='original'):
        with artifacts.text_reader(tmp_path / 'unused.jsonl.zst', executable=fake) as handle:
            assert handle.readline() == 'ready\n'
            raise ValueError('original')
    assert children[0].returncode == -9
