# Python API

`pandora_clef_flash` · Load Clef-Flash and return structured decisions for one or more questions.

## Quick start

```python
from pandora_clef_flash import DecisionModel

with DecisionModel.from_pretrained("models") as model:
    result = model.systemone({
        "state": "My card was charged twice for the same order.",
        "questions": {
            "team": {
                "type": "choice",
                "instructions": "Which team should handle this request?",
                "criteria": {"Billing": "Payments and refunds", "Support": "Technical problems"},
            },
        },
    })
    print(result["answers"]["team"]["choice"])
```

## API overview

| Name | Signature | Returns | Purpose |
| --- | --- | --- | --- |
| `DecisionModel.from_pretrained` | `(model_dir=None, *, runtime=None)` | `DecisionModel` | Load a model folder |
| `DecisionModel.systemone` | `(request, *, images=None, truncation=False, return_diagnostics=False)` | `dict` | Answer an ordered set of questions |
| `DecisionModel.capabilities` | Read-only property | `JevCapabilities` | Discover supported inputs and question types |
| `DecisionModel.version` | Read-only property | `str` | Read the native SDK version |
| `close` | `()` | `None` | Release the model; safe to call twice |
| `resolve_models` | `(path=None, *, default_root=None)` | `Path` | Resolve an explicitly named, configured or unique local model folder |

`DecisionModel(...)` accepts the same arguments as `from_pretrained`. `ClefFlash` is its compatibility alias.
The model path defaults to `CLEF_MODELS` when omitted.
See [Runtime](RUNTIME_API.md) for `runtime`.

## Parameters

### `systemone`

| Parameter | Type | Default | Meaning |
| --- | --- | --- | --- |
| `request` | `dict` | Required | Supply JSON-compatible `state`, a nonempty ordered `questions` mapping and optional `model="clef-flash"`. |
| `images` | `list` | `None` | A list of local JPEG/PNG paths, encoded JPEG/PNG bytes, `(rgb_bytes, width, height)` tuples, or `uint8` RGB arrays of shape `(height, width, 3)`. |
| `truncation` | `bool` | `False` | Permit state-tail truncation when the request exceeds the context. Questions, choices and image positions are kept. |
| `return_diagnostics` | `bool` | `False` | Return option logits and durations in milliseconds. |

Each question has a `type` of `noul`, `choice` or `score`. Its `instructions` default to the question ID.
A yes/no question accepts optional descriptions for `true` and `false`. A choice question requires a mapping
from option keys to descriptions. A score question requires a list of descriptions ordered from lowest to highest.

## Results and cleanup

### `dict`

| Field | Type | Meaning |
| --- | --- | --- |
| `model` | `str` | Loaded model ID |
| `answers` | `dict` | Per-question result. Yes/no returns `noul`, the probability of true. Choice returns `choice`, `confidence` and `probabilities`. Score returns `score`, `confidence`, `legend` and `probabilities`. |
| `usage` | `dict` | `input_tokens` and `output_tokens`; output tokens are always zero. |
| `truncated` | `bool` | Whether optional state-tail truncation was used |
| `diagnostics` | `dict` | Optional `logits` and `timing_ms` |

The score is the probability-weighted mean of the zero-based option indices.

### Errors

| Exception | When |
| --- | --- |
| `InputError` | Invalid request, image or argument |
| `UnsupportedFeatureError` | An unsupported feature or incompatible native library is requested |
| `FileNotFoundError` | The supplied model directory has no manifest |
| `InferenceError` | Model loading or an inference call failed |
| `ClosedError` | The model is closed or was inherited from another process |
| `RuntimeNativeError` | Native Runtime creation or status processing failed |

`ClefError` is the common base for the SDK's input, feature, inference and closed error types.

### Lifecycle

Use the model as a context manager. The returned dictionaries are owned by the caller and can outlive the model.
Each request is synchronous and starts with fresh model state. Calls and close on one instance are serialized.
After a native inference failure, close the model and load it again. The model retains its Runtime until the model closes.

## Advanced

See the [examples](../examples/README.md) for image input and [Runtime](RUNTIME_API.md) for hardware settings.
