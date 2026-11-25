# Examples

## Overview

| Example | What it shows |
| --- | --- |
| [python/systemone.py](python/systemone.py) | Answer a question about the included skiing image. |
| [c/systemone.c](c/systemone.c) | Run the same request through the C ABI. |

## Before you run

Complete [Install](../README.md#1-install) and [Get the model](../README.md#2-get-the-model). Run every command from the Demo root in the activated environment. Stop the Web Demo first; examples and the Web Demo share the NPU.

## Python examples

### systemone.py

The default request and JPEG are in `examples/inputs/`. Pass `--request` for a custom JSON request and repeat
`--image` to attach image files. Use `--truncation` to permit state-tail truncation or `--diagnostics` for logits and timings.

```bash
python examples/python/systemone.py
```

Example output excerpt:

```json
{"answers":{"answer":{"type":"choice","choice":"D","confidence":0.9752,"probabilities":{"A":0.0102,"B":0.0076,"C":0.007,"D":0.9752}}}}
```

## C example

### systemone.c

Build against the headers and prebuilt library in `sdk/`:

```bash
runtime_dir=$(python -c "import pathlib,pandora_runtime; print(pathlib.Path(pandora_runtime.__file__).parent)")
cc -std=c99 -Wall -Wextra -Werror -I sdk/include examples/c/systemone.c -L sdk/lib -L"$runtime_dir" -Wl,--no-as-needed -l:libpandora_runtime.so.5 -Wl,--as-needed -Wl,-rpath,"$runtime_dir" -lclef -Wl,-rpath,'$ORIGIN/../../sdk/lib' -o examples/c/systemone
examples/c/systemone models examples/inputs/request.json examples/inputs/skiing.jpeg
```

Example output excerpt:

```json
{"answers":{"answer":{"type":"choice","choice":"D","confidence":0.9752,"probabilities":{"A":0.0102,"B":0.0076,"C":0.007,"D":0.9752}}}}
```

See [C ABI](../docs/C_ABI.md) for ownership and error handling.
