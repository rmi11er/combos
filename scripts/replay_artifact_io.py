"""Lossless, bounded-stream research artifact I/O; no replay integration.

Writers publish atomically into NEW paths. Normal reader exit validates the whole
stream, including unread tails. Exceptional exit reaps child processes without
masking the consumer's exception. No JSON parsing or serialization occurs here.
"""
from contextlib import contextmanager
import gzip
import hashlib
import io
import os
from pathlib import Path
import subprocess
import tempfile

ZSTD = Path('/opt/homebrew/bin/zstd')
CHUNK_BYTES = 1024 * 1024


class ArtifactCodecError(RuntimeError):
    """An external codec failed; its output must not be published."""


def _codec(path):
    name = str(path)
    for suffix, codec in (('.jsonl.gz', 'gzip'), ('.jsonl.zst', 'zstd')):
        if name.endswith(suffix):
            return codec
    raise ValueError('Expected .jsonl.gz or .jsonl.zst artifact')


def _hash_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for data in iter(lambda: handle.read(CHUNK_BYTES), b''):
            digest.update(data)
    return digest.hexdigest()


def zstd_identity(executable=ZSTD):
    """Record the actual installed executable, bytes and CLI version."""
    executable = Path(executable).resolve(strict=True)
    version = subprocess.run([str(executable), '--version'], check=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, timeout=10).stdout.strip()
    return {'executable': str(executable), 'sha256': _hash_file(executable),
            'bytes': executable.stat().st_size, 'version': version,
            'compression_arguments': ['-q', '-6', '-c'],
            'window_and_threads': 'CLI defaults; no --long or extra workers'}


@contextmanager
def _new_destination(path):
    """Atomic, no-clobber publication using a same-directory hard link."""
    path = Path(path)
    if path.exists() or path.is_symlink():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = tempfile.NamedTemporaryFile(mode='w+b', prefix='.' + path.name + '.',
                                      suffix='.partial', dir=path.parent, delete=False)
    temporary = Path(raw.name)
    try:
        yield raw
        raw.flush()
        os.fsync(raw.fileno())
        raw.close()
        # link() fails atomically if a competing writer published this name.
        os.link(temporary, path)
    finally:
        try:
            raw.close()
        finally:
            temporary.unlink(missing_ok=True)


def _abort(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    else:
        process.wait()


def _codec_error(process, diagnostics):
    diagnostics.seek(0)
    message = diagnostics.read(16384).decode('utf-8', errors='replace').strip()
    return ArtifactCodecError(f'zstd exited {process.returncode}: {message}')


@contextmanager
def _binary_writer(path, executable=ZSTD):
    codec = _codec(path)
    with _new_destination(path) as output:
        if codec == 'gzip':
            with gzip.GzipFile(filename='', fileobj=output, mode='wb', mtime=0) as stream:
                yield stream
            return
        # A temporary diagnostics file avoids stderr-pipe deadlock and unbounded RAM.
        with tempfile.TemporaryFile() as diagnostics:
            process = subprocess.Popen([str(executable), '-q', '-6', '-c'],
                                       stdin=subprocess.PIPE, stdout=output,
                                       stderr=diagnostics, bufsize=0)
            stream = io.BufferedWriter(process.stdin, buffer_size=65536)
            try:
                yield stream
                stream.close()
                if process.wait() != 0:
                    raise _codec_error(process, diagnostics)
            except BaseException as exc:
                _abort(process)
                if isinstance(exc, BrokenPipeError):
                    raise _codec_error(process, diagnostics) from exc
                raise
            finally:
                try:
                    stream.close()
                except BrokenPipeError:
                    pass


@contextmanager
def _binary_reader(path, executable=ZSTD):
    codec = _codec(path)
    if codec == 'gzip':
        with gzip.open(path, 'rb') as stream:
            yield stream
            # Also check CRC/trailer when a caller consumes only a prefix.
            while stream.read(CHUNK_BYTES):
                pass
        return
    with tempfile.TemporaryFile() as diagnostics:
        process = subprocess.Popen([str(executable), '-q', '-d', '-c', str(path)],
                                   stdout=subprocess.PIPE, stderr=diagnostics,
                                   bufsize=0)
        try:
            yield process.stdout
            while process.stdout.read(CHUNK_BYTES):
                pass
            if process.wait() != 0:
                raise _codec_error(process, diagnostics)
        except BaseException:
            _abort(process)
            raise
        finally:
            process.stdout.close()


@contextmanager
def text_writer(path, *, executable=ZSTD):
    """Write UTF-8 text without newline translation; refuse existing paths."""
    with _binary_writer(path, executable) as raw:
        text = io.TextIOWrapper(raw, encoding='utf-8', newline='')
        try:
            yield text
            text.flush()
            text.detach()
        except BaseException:
            # The binary context aborts/reaps a child before touching blocked pipes.
            # Its close also makes the text wrapper's eventual cleanup harmless.
            raise


@contextmanager
def text_reader(path, *, executable=ZSTD):
    """Read UTF-8 text, preserving line endings and verifying the unread tail."""
    with _binary_reader(path, executable) as raw:
        text = io.TextIOWrapper(raw, encoding='utf-8', newline='')
        try:
            yield text
            text.detach()
        except BaseException:
            raise


def export_gzip(source, destination, *, executable=ZSTD):
    """Stream exact Zstd-decoded BYTES into a new gzip file; never reserialize JSON."""
    if _codec(source) != 'zstd' or _codec(destination) != 'gzip':
        raise ValueError('Export requires .jsonl.zst source and .jsonl.gz destination')
    digest = hashlib.sha256()
    size = rows = 0
    # Validate the reader before allowing the writer to publish its destination.
    with _binary_writer(destination) as output:
        with _binary_reader(source, executable) as incoming:
            for data in iter(lambda: incoming.read(CHUNK_BYTES), b''):
                output.write(data)
                digest.update(data)
                size += len(data)
                rows += data.count(b'\n')
    return {'source': str(source), 'destination': str(destination),
            'decoded_sha256': digest.hexdigest(), 'decoded_bytes': size,
            'newline_count': rows}
