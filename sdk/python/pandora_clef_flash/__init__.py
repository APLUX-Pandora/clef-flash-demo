"""Jev/SystemOne model interface over the Clef native SDK; standard library only."""
import ctypes
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import threading

from . import _native
from ._runtime import CpuOptions, QnnOptions, Runtime, RuntimeNativeError
from ._version import __version__ as __version__

__all__ = ["DecisionModel", "ClefFlash", "ClefError", "InputError", "UnsupportedFeatureError",
           "ClosedError", "InferenceError", "Runtime", "QnnOptions", "CpuOptions", "RuntimeNativeError", "JevCapabilities", "resolve_models"]

def resolve_models(path=None, *, default_root=None):
    """Resolve explicit/environment roots or one application-supplied model directory."""
    def configured(root):
        return (root / "models.json").is_file() or (root / "manifest.json").is_file()
    selected = path if path is not None else os.environ.get("CLEF_MODELS")
    if selected is not None:
        if not str(selected).strip():
            raise ValueError("The explicit model directory is empty")
        package = Path(selected).expanduser().resolve()
        if not configured(package):
            raise FileNotFoundError(f"No models.json or legacy manifest.json in explicit model directory: {package}")
        return package
    if default_root is None:
        raise FileNotFoundError("Pass model_dir or set CLEF_MODELS; an installed SDK has no application model directory")
    root = Path(default_root).expanduser().resolve()
    if configured(root):
        return root
    children = sorted(p for p in root.iterdir() if p.is_dir() and configured(p)) if root.is_dir() else []
    if len(children) == 1:
        return children[0]
    if children:
        raise ValueError("Multiple model packages found; pass its directory as model_dir or set CLEF_MODELS: " + ", ".join(str(p) for p in children))
    raise FileNotFoundError(f"No model package under {root}; follow docs/MODEL_SETUP.md")

_IMAGE_ENCODED, _IMAGE_RGB = 0, 1


class _Image(ctypes.Structure):
    _fields_ = [("kind", ctypes.c_int), ("data", ctypes.c_void_p), ("size", ctypes.c_size_t),
                ("width", ctypes.c_int), ("height", ctypes.c_int)]


class ClefError(RuntimeError):
    def __init__(self, message, *, native_code=None, operation=None):
        super().__init__(message)
        self.native_code = self.code = native_code
        self.operation = operation


class InputError(ClefError, ValueError):
    pass


class UnsupportedFeatureError(ClefError):
    pass


class ClosedError(ClefError):
    pass


class InferenceError(ClefError):
    pass


@dataclass(frozen=True)
class JevCapabilities:
    input_types: tuple = ("text", "image")
    question_types: tuple = ("noul", "choice", "score")
    context_tokens: int = 8192
    diagnostics: tuple = ("logits", "timing_ms")


def _finite_float(text):
    value = float(text)
    if not math.isfinite(value):
        raise ValueError("nonfinite native value")
    return value


def _input(message):
    raise InputError(message, operation="validate")


def _json_value(value, path="state", seen=None):
    """Copy JSON values without coercing keys, objects, NaNs or cyclic inputs."""
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int):
        if not -(1 << 63) <= value < (1 << 64):
            _input(f"{path}: integer exceeds the native JSON 64-bit range")
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            _input(f"{path}: expected a finite JSON number")
        return value
    if not isinstance(value, (dict, list)):
        _input(f"{path}: expected a JSON value")
    seen = set() if seen is None else seen
    if id(value) in seen:
        _input(f"{path}: cyclic JSON values are unsupported")
    seen.add(id(value))
    try:
        if isinstance(value, list):
            return [_json_value(v, f"{path}[{i}]", seen) for i, v in enumerate(value)]
        result = {}
        for key, item in value.items():
            if not isinstance(key, str):
                _input(f"{path}: JSON object keys must be strings")
            result[key] = _json_value(item, f"{path}.{key}", seen)
        return result
    finally:
        seen.remove(id(value))


def _fields(value, allowed, path):
    if not isinstance(value, dict):
        _input(f"{path}: expected a dictionary")
    for key in value:
        if key not in allowed:
            _input(f"{path}.{key}: unknown field; allowed fields: {', '.join(sorted(allowed))}")


def _text(value, path):
    if not isinstance(value, str) or not value.strip():
        _input(f"{path}: expected a nonempty string")
    return value


def _request(request):
    if not isinstance(request, dict):
        _input("request: expected a dictionary, not a serialized JSON string")
    if "images" in request:
        _input("request.images: use the separate images keyword argument")
    if "videos" in request or "media_kwargs" in request:
        raise UnsupportedFeatureError("Video/processor arguments are unsupported by this adapter", operation="validate")
    _fields(request, {"model", "state", "questions"}, "request")
    model_name = request.get("model", "clef-flash")
    if not isinstance(model_name, str) or model_name != "clef-flash":
        _input("request.model: does not match the loaded clef-flash model")
    if "state" not in request:
        _input("request.state: required field")
    questions = request.get("questions")
    if not isinstance(questions, dict) or not questions:
        _input("request.questions: expected a nonempty dictionary")
    copied = {}
    for qid, question in questions.items():
        _text(qid, "questions key")
        path = f"questions.{qid}"
        _fields(question, {"type", "instructions", "criteria"}, path)
        kind = question.get("type")
        if not isinstance(kind, str) or kind not in ("noul", "choice", "score"):
            _input(f"{path}.type: expected noul, choice or score")
        instruction = question.get("instructions")
        if instruction is None or (isinstance(instruction, str) and instruction == ""):
            instruction = qid
        elif not isinstance(instruction, str):
            _input(f"{path}.instructions: expected a string")
        item = {"type": kind, "instructions": instruction}
        criteria = question.get("criteria")
        if kind == "noul":
            if criteria is not None:
                _fields(criteria, {"true", "false"}, path + ".criteria")
                item["criteria"] = {key: _text(value, path + ".criteria." + key)
                                    for key, value in criteria.items()}
        elif kind == "choice":
            if not isinstance(criteria, dict) or not criteria:
                _input(f"{path}.criteria: expected a nonempty options dictionary")
            item["criteria"] = {_text(key, path + ".criteria key"): _text(value, path + ".criteria." + str(key))
                                for key, value in criteria.items()}
        else:
            if not isinstance(criteria, list) or not criteria:
                _input(f"{path}.criteria: expected a nonempty ordered list")
            item["criteria"] = [_text(value, f"{path}.criteria[{i}]") for i, value in enumerate(criteria)]
        copied[qid] = item
    try:
        return {"model": "clef-flash", "state": _json_value(request["state"]), "questions": copied}
    except RecursionError as exc:
        raise InputError("state: JSON nesting is too deep", operation="validate") from exc


def _images(images):
    if images is None:
        images = []
    if not isinstance(images, list):
        _input("images: expected a list or None")
    keep, array = [], (_Image * max(1, len(images)))()
    for i, image in enumerate(images):
        path = f"images[{i}]"
        if isinstance(image, (str, os.PathLike)):
            if isinstance(image, str) and "://" in image:
                _input(f"{path}: use a local JPEG/PNG file, not a URL")
            try:
                image = Path(image).expanduser().read_bytes()
            except OSError as exc:
                raise InputError(f"{path}: cannot read image: {exc}", operation="validate") from exc
        if isinstance(image, (bytes, bytearray)):
            data = bytes(image)
            if not (data.startswith(b"\xff\xd8\xff") or data.startswith(b"\x89PNG\r\n\x1a\n")):
                _input(f"{path}: expected encoded JPEG or PNG bytes")
            kind, width, height = _IMAGE_ENCODED, 0, 0
        elif isinstance(image, tuple) and len(image) == 3:
            data, width, height = image
            if not isinstance(data, (bytes, bytearray, memoryview)):
                _input(f"{path}: RGB data must be bytes-like")
            data, kind = bytes(data), _IMAGE_RGB
        elif hasattr(image, "shape") and hasattr(image, "tobytes") and hasattr(image, "dtype"):
            if len(image.shape) != 3 or image.shape[2] != 3 or str(image.dtype) != "uint8":
                _input(f"{path}: expected a uint8 (H,W,3) RGB array")
            height, width, _ = image.shape
            data, kind = image.tobytes(), _IMAGE_RGB
        else:
            _input(f"{path}: unsupported image type")
        if kind == _IMAGE_RGB:
            if (type(width) is not int or type(height) is not int or width <= 0 or height <= 0 or
                    width > 32768 or height > 32768 or width * height > 32 * 1024 * 1024):
                _input(f"{path}: invalid RGB dimensions (maximum 32 Mi pixels and 32768 per side)")
            if len(data) != width * height * 3:
                _input(f"{path}: RGB byte count must equal width*height*3")
        buffer = ctypes.create_string_buffer(data, len(data))
        array[i] = _Image(kind, ctypes.cast(buffer, ctypes.c_void_p), len(data), width, height)
        keep.append(buffer)
    return keep, array, len(images)


def _load():
    lib = _native.library()
    lib.clef_create_with_runtime.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    lib.clef_create_with_runtime.restype = ctypes.c_int
    lib.clef_destroy_owned.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
    lib.clef_destroy_owned.restype = ctypes.c_int
    lib.clef_systemone.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.POINTER(_Image), ctypes.c_int,
                                   ctypes.POINTER(ctypes.c_void_p)]
    lib.clef_systemone.restype = ctypes.c_int
    lib.clef_free_string.argtypes = [ctypes.c_void_p]
    lib.clef_free_string.restype = None
    lib.clef_last_error.argtypes = [ctypes.c_void_p]
    lib.clef_last_error.restype = ctypes.c_char_p
    lib.clef_version.restype = ctypes.c_char_p
    return lib


class DecisionModel:
    """One local Jev model. Calls and close serialize on the same instance lock."""
    def __init__(self, model_dir=None, *, runtime=None):
        self._pid = os.getpid()
        self._lock = threading.Lock()
        self._runtime = None
        self._ctx = None
        self._failed = False
        if runtime is not None and not isinstance(runtime, Runtime):
            raise TypeError("runtime must be this SDK's Runtime")
        self._runtime = runtime
        model_dir = resolve_models(model_dir)
        self._lib = _load()
        self._version = self._lib.clef_version().decode()
        if self._version.split(".")[:2] != __version__.split(".")[:2]:
            raise UnsupportedFeatureError(
                f"This binding requires a native SDK matching {__version__} major and minor versions",
                operation="load",
            )
        self._capabilities = JevCapabilities()
        self._ctx = ctypes.c_void_p()
        try:
            path = os.fsencode(model_dir)
            output = ctypes.byref(self._ctx)
            if runtime is None:
                rc = self._lib.clef_create_with_runtime(path, 0, None, output)
            else:
                # Keep the handle valid until native code acquires its own reference.
                # Check the process before locking, since fork may inherit a held lock.
                runtime._native_handle()
                with runtime._lock:
                    rc = self._lib.clef_create_with_runtime(path, 0, runtime._native_handle(), output)
            if rc != 0:
                message = self._lib.clef_last_error(None).decode(errors="replace")
                error = UnsupportedFeatureError if rc == -7 else InferenceError
                raise error(message, native_code=rc, operation="load")
        except BaseException:
            # Native code owns the output slot before Python can deliver deferred signals.
            self.close()
            raise

    @classmethod
    def from_pretrained(cls, model_dir=None, *, runtime=None):
        return cls(model_dir, runtime=runtime)

    @property
    def capabilities(self):
        return self._capabilities

    @property
    def version(self):
        return self._version

    def _check_process(self):
        if os.getpid() != self._pid:
            raise ClosedError("Model inherited through fork; initialize after spawn/exec", operation="process")

    def systemone(self, request, *, images=None, truncation=False, return_diagnostics=False):
        self._check_process()
        with self._lock:
            if self._ctx is None or not self._ctx.value:
                raise ClosedError("model is closed", operation="systemone")
            if self._failed:
                raise InferenceError("A previous native failure requires close and reload", operation="state")
            if type(truncation) is not bool or type(return_diagnostics) is not bool:
                _input("truncation and return_diagnostics must be booleans")
            normalized = _request(request)
            normalized["truncation"] = truncation
            try:
                body = json.dumps(normalized, ensure_ascii=False, allow_nan=False).encode("utf-8")
            except (ValueError, UnicodeError) as exc:
                raise InputError(f"request: cannot encode JSON: {exc}", operation="validate") from exc
            keep, array, count = _images(images)
            output = ctypes.c_void_p()
            try:
                rc = self._lib.clef_systemone(self._ctx, body, array, count, ctypes.byref(output))
            except BaseException:
                self._failed = True  # Outcome may be unknown when a deferred exception arrives.
                if output.value:
                    self._lib.clef_free_string(output)
                raise
            if rc != 0:
                message = self._lib.clef_last_error(self._ctx).decode(errors="replace")
                self._failed = rc != -1
                error = InputError if rc == -1 else InferenceError
                raise error(message, native_code=rc, operation="systemone")
            if not output.value:
                self._failed = True
                raise InferenceError("Native success returned no response", operation="response")
            try:
                result = json.loads(ctypes.string_at(output.value).decode("utf-8"),
                                    parse_float=_finite_float, parse_constant=lambda x: (_ for _ in ()).throw(ValueError("nonfinite " + x)))
            except (ValueError, UnicodeError) as exc:
                self._failed = True
                raise InferenceError("Invalid native response", operation="response") from exc
            finally:
                self._lib.clef_free_string(output)
            answers = result.get("answers") if isinstance(result, dict) else None
            usage = result.get("usage") if isinstance(result, dict) else None
            if (not isinstance(result, dict) or result.get("model") != "clef-flash" or
                    type(result.get("truncated")) is not bool or not isinstance(answers, dict) or
                    set(answers) != set(normalized["questions"]) or not isinstance(usage, dict) or
                    type(usage.get("input_tokens")) is not int or usage["input_tokens"] < 0 or
                    type(usage.get("output_tokens")) is not int or usage["output_tokens"] != 0):
                self._failed = True
                raise InferenceError("Native response does not match the request contract", operation="response")
            details = result.pop("clef", None)
            if return_diagnostics:
                if (not isinstance(details, dict) or not isinstance(details.get("logits"), dict) or
                        not isinstance(details.get("timing"), dict)):
                    self._failed = True
                    raise InferenceError("Native diagnostics are missing", operation="response")
                result["diagnostics"] = {"logits": details["logits"],
                                         "timing_ms": {k: v for k, v in details["timing"].items() if k.endswith("_ms")}}
            return result

    def close(self):
        if not hasattr(self, "_pid"):
            return
        self._check_process()
        lock = getattr(self, "_lock", None)
        if lock is None:
            return
        with lock:
            if self._ctx is not None and self._ctx.value:
                rc = self._lib.clef_destroy_owned(ctypes.byref(self._ctx))
                if rc:
                    raise InferenceError(self._lib.clef_last_error(None).decode(errors="replace"), native_code=rc, operation="close")
            self._ctx = None
            self._runtime = None

    def __enter__(self):
        self._check_process()
        with self._lock:
            if self._ctx is None or not self._ctx.value:
                raise ClosedError("model is closed", operation="enter")
        return self

    def __exit__(self, *_):
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


# Historical import name uses the same model and the new request contract.
ClefFlash = DecisionModel
