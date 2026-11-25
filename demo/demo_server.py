#!/usr/bin/env python3
"""Single-device decision playground backed by the native Clef SDK."""
import argparse
import base64
import binascii
from contextlib import contextmanager
import json
import mimetypes
import os
from pathlib import Path
import signal
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

from pandora_clef_flash import ClefError, InputError, DecisionModel, resolve_models

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

MAX_BODY = 12 * 1024 * 1024
MAX_IMAGE = 8 * 1024 * 1024
PUBLIC_MODEL = 'clef-flash'


@contextmanager
def defer_stop_signals():
    """Finish native resource acquisition/release before handling stop signals."""
    previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT})
    try:
        yield
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous)


def close_model(state):
    if state.engine is not None:
        state.engine.close()
        state.engine = None


class State:
    def __init__(self, models):
        self.presets = json.loads((HERE / 'presets.json').read_text())
        for preset in self.presets:
            preset['request']['model'] = PUBLIC_MODEL
        self.by_id = {p['id']: p for p in self.presets}
        self.lock = threading.Lock()
        self.models = resolve_models(models, default_root=ROOT / "models")
        self.engine = DecisionModel.from_pretrained(self.models)
        self.busy = False
        self.phase = 'ready'
        self.version = self.engine.version

    def info(self):
        return {'ready': self.phase == 'ready', 'busy': self.busy,
                'state': self.phase, 'version': self.version,
                'reload_required': self.phase == 'failed', 'max_image_bytes': MAX_IMAGE}

    def reload(self):
        if not self.lock.acquire(blocking=False):
            return 409, {'error': 'The device is busy. Wait before reloading.'}
        self.busy = True
        self.phase = 'loading'
        try:
            with defer_stop_signals():
                close_model(self)
                self.engine = DecisionModel.from_pretrained(self.models)
            self.version = self.engine.version
            self.phase = 'ready'
            return 200, self.info()
        except Exception as exc:
            self.phase = 'failed'
            print(f'Model reload failed: {exc}', file=sys.stderr, flush=True)
            return 503, {'error': 'Model reload failed. Check the device service log.', 'reload_required': True}
        finally:
            self.busy = False
            self.lock.release()


class Handler(BaseHTTPRequestHandler):
    server_version = 'ClefFlash/1'
    timeout = 30  # Bound incomplete HTTP reads while shutdown joins handlers.

    def reply(self, status, obj):
        data = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def serve_file(self, path):
        try:
            data = path.read_bytes()
        except OSError:
            self.reply(404, {'error': 'File not found'})
            return
        self.send_response(200)
        self.send_header('Content-Type', mimetypes.guess_type(str(path))[0] or 'application/octet-stream')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = unquote(urlsplit(self.path).path)
        state = self.server.state
        if path == '/api/info':
            self.reply(200, state.info())
        elif path == '/api/presets':
            self.reply(200, state.presets)
        elif path == '/':
            self.serve_file(HERE / 'static/index.html')
        elif path.startswith(('/static/', '/media/')):
            base = HERE / path.split('/')[1]
            candidate = (HERE / path.lstrip('/')).resolve()
            if candidate.is_relative_to(base.resolve()) and candidate.is_file():
                self.serve_file(candidate)
            else:
                self.reply(404, {'error': 'File not found'})
        else:
            self.reply(404, {'error': 'Unknown endpoint'})

    def do_POST(self):
        if urlsplit(self.path).path not in ('/api/run', '/api/reload'):
            self.reply(404, {'error': 'Unknown endpoint'})
            return
        origin = self.headers.get('Origin')
        if origin and urlsplit(origin).netloc != self.headers.get('Host'):
            self.reply(403, {'error': 'Cross-origin requests are not allowed'})
            return
        if urlsplit(self.path).path == '/api/reload':
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 <= size <= 1024:
                    raise ValueError('Reload body is too large')
                body = json.loads(self.rfile.read(size)) if size else {}
                if body != {}:
                    raise ValueError('Reload expects an empty JSON object')
            except (ValueError, TypeError):
                self.reply(400, {'error': 'Reload expects an empty JSON object'})
                return
            status, body = self.server.state.reload()
            try:
                self.reply(status, body)
            except (BrokenPipeError, ConnectionResetError, TimeoutError):
                pass
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= MAX_BODY:
                self.reply(413, {'error': 'Request must be nonempty and at most 12 MiB'})
                return
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError('Request body must be an object')
            req = body.get('request')
            if not isinstance(req, dict) or 'state' not in req:
                raise ValueError('A request object with state is required')
            questions = req.get('questions')
            if not isinstance(questions, dict) or not 1 <= len(questions) <= 12:
                raise ValueError('Provide between 1 and 12 questions')
            for q in questions.values():
                if not isinstance(q, dict) or q.get('type') not in ('choice', 'noul', 'score'):
                    raise ValueError('Question type must be choice, noul, or score')
                if not isinstance(q.get('instructions'), str) or not q['instructions'].strip():
                    raise ValueError('Every question needs instructions')
                if q['type'] == 'choice':
                    c = q.get('criteria')
                    if not isinstance(c, dict) or not 2 <= len(c) <= 12 or not all(isinstance(v, str) and v.strip() for v in c.values()):
                        raise ValueError('Choice questions need 2–12 nonempty options')
                if q['type'] == 'score':
                    c = q.get('criteria')
                    if not isinstance(c, list) or not 2 <= len(c) <= 12 or not all(isinstance(v, str) and v.strip() for v in c):
                        raise ValueError('Score questions need 2–12 ordered levels')
            if req.get('images') or req.get('videos'):
                raise ValueError('Use the image upload field, not request image/video paths')
            req = {'model': PUBLIC_MODEL, 'state': req['state'], 'questions': questions}
            preset_id = body.get('preset_id')
            if preset_id is not None and not isinstance(preset_id, str):
                raise ValueError('preset_id must be a string')
            preset = self.server.state.by_id.get(preset_id)
            if body.get('preset_id') is not None and preset is None:
                raise ValueError('Unknown built-in example')
            upload = body.get('image_base64')
            images = []
            if upload is not None:
                if not isinstance(upload, str):
                    raise ValueError('image_base64 must be a string')
                data = base64.b64decode(upload, validate=True)
                if not data or len(data) > MAX_IMAGE:
                    raise ValueError('Image must be nonempty and at most 8 MiB')
                if not (data.startswith(b'\xff\xd8\xff') or data.startswith(b'\x89PNG\r\n\x1a\n')):
                    raise ValueError('Only JPEG and PNG images are supported')
                images = [data]
            elif preset and preset.get('file'):
                images = [(HERE / 'media' / preset['file']).read_bytes()]
            state = self.server.state
            if not state.lock.acquire(blocking=False):
                self.reply(409, {'error': 'The device is busy with another request. Try again shortly.'})
                return
            try:
                state.busy = True
                if state.phase != 'ready' or state.engine is None:
                    self.reply(503, {'error': 'The model needs reloading before another request.', 'reload_required': True})
                    return
                started = time.monotonic()
                try:
                    response = state.engine.systemone(req, images=images, return_diagnostics=True)
                except InputError:
                    raise
                except ClefError:
                    state.phase = 'failed'
                    raise
                response['model'] = PUBLIC_MODEL
                details = response.pop('diagnostics')
                response['decision'] = {'logits': details['logits'],
                                        'timing': {**details['timing_ms'], 'tokens': response['usage']['input_tokens']}}
                reference = preset['reference'] if preset and upload is None and req == preset['request'] else None
                self.reply(200, {'response': response, 'reference': reference,
                                 'request_ms': (time.monotonic() - started) * 1000})
            finally:
                state.busy = False
                state.lock.release()
        except (ValueError, TypeError, binascii.Error) as exc:
            self.reply(400, {'error': str(exc)})
        except ClefError as exc:
            print(f'SDK request error: {exc}', file=sys.stderr, flush=True)
            message = ('Could not process the input. Check the image and question configuration.'
                       if isinstance(exc, InputError) else 'The inference engine failed. Check the device service log.')
            self.reply(400 if isinstance(exc, InputError) else 500, {'error': message, 'code': exc.code, 'reload_required': not isinstance(exc, InputError)})
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass
        except Exception as exc:
            print(f'Inference request failed: {exc}', file=sys.stderr, flush=True)
            self.reply(500, {'error': 'The inference request failed; see the server log.'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default=os.environ.get('CLEF_HOST', '0.0.0.0'))
    parser.add_argument('--port', type=int, default=int(os.environ.get('CLEF_PORT', '8765')))
    parser.add_argument('--models', default=None, help='Package directory containing models.json (legacy manifest.json also accepted; otherwise discover under models/)')
    args = parser.parse_args()
    state = server = shutdown_thread = None
    stopping = threading.Event()
    serving = threading.Event()
    shutdown_lock = threading.RLock()

    def stop(*_):
        nonlocal shutdown_thread
        stopping.set()
        with shutdown_lock:
            if server is not None and serving.is_set() and shutdown_thread is None:
                shutdown_thread = threading.Thread(target=server.shutdown, daemon=True)
                shutdown_thread.start()

    previous_handlers = {sig: signal.signal(sig, stop) for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        print('Loading the native SDK and model package...', flush=True)
        with defer_stop_signals():
            state = State(args.models)
        if stopping.is_set():
            return
        server = ThreadingHTTPServer((args.host, args.port), Handler)
        # ThreadingHTTPServer defaults to daemon handlers. Native ownership must
        # outlive every request/reload, so server_close must join those handlers.
        server.daemon_threads = False
        server.block_on_close = True
        server.state = state
        if stopping.is_set():
            return
        serving.set()
        if stopping.is_set():
            stop()
        print(f'CLEF_WEB_READY http://{args.host}:{args.port}', flush=True)
        server.serve_forever()
    finally:
        try:
            if server is not None:
                server.server_close()
        finally:
            try:
                if state is not None:
                    # The synchronous SDK has no cancel API. Wait for the current
                    # native call to finish before releasing its context.
                    with state.lock, defer_stop_signals():
                        close_model(state)
                    print(json.dumps({'model_closed': True}), flush=True)
            finally:
                if shutdown_thread is not None:
                    shutdown_thread.join(timeout=1)
                for sig, handler in previous_handlers.items():
                    signal.signal(sig, handler)


if __name__ == '__main__':
    main()
