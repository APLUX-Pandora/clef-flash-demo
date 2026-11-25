# Clef-Flash SDK

Load Clef-Flash and return structured decisions for one or more questions.

## What's included

| Path | Content |
| --- | --- |
| `python/` | Python package (`from pandora_clef_flash import DecisionModel`) |
| `include/` | C header |
| `lib/` | Prebuilt native library with its QNN runtime |
| `SHA256SUMS` | Checksums of the shipped files |

The vendor build manifest (`manifest.json`) records the QNN inputs used to build the runtime and stays with the build inputs.
Use `lib/qnn248/inventory.json` to verify the bundled QNN libraries and `SHA256SUMS` to verify the SDK files.

## Install

In your application's activated Python 3.10–3.12 environment, from the Demo root:

```bash
python -m pip install sdk/wheels/pandora_runtime-*.whl
python -m pip install ./sdk
```

The device must pass `sudo lms check`. The SDK does not install LMS or drivers and does not download models; see [Get the model](../README.md#2-get-the-model).

## Usage

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

## Documentation

- [Python API](PYTHON_API.md)
- [Runtime API](RUNTIME_API.md)
- [C ABI](../docs/C_ABI.md)
- [Examples](../examples/README.md)
- [Licensing](../LICENSING.md)
