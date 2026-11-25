# C ABI

`sdk/include/clef_api.h` · `sdk/lib/libclef.so` · Load Clef-Flash and return structured decisions for one or more questions.

## Build and link

From the Demo root, run `python -m pip install sdk/wheels/pandora_runtime-*.whl` in the activated Python environment to install the Runtime wheel.

From the Demo root, compile against the shipped header and library; the library carries its QNN runtime:

```bash
runtime_dir=$(python -c "import pathlib,pandora_runtime; print(pathlib.Path(pandora_runtime.__file__).parent)")
cc -std=c99 -I sdk/include your_app.c -L sdk/lib -L"$runtime_dir" -Wl,--no-as-needed -l:libpandora_runtime.so.5 -Wl,--as-needed -Wl,-rpath,"$runtime_dir" -lclef -Wl,-rpath,'$ORIGIN/sdk/lib' -o your_app
```

The Runtime library comes from the wheel installed with the SDK. For a native-only deployment, make the same library available to the system loader.

## Lifecycle

```text
clef_create → clef_systemone → clef_free_string → clef_destroy_owned
```

## Functions

| Function | Purpose | Returns |
| --- | --- | --- |
| `clef_create`, `clef_create_with_runtime` | Load the model using an owned or supplied Runtime. | Status and output context |
| `clef_systemone` | Submit UTF-8 request JSON and optional images. | Status and allocated UTF-8 response |
| `clef_free_string` | Release the response string. | Void |
| `clef_destroy`, `clef_destroy_owned` | Release the context. The owned form clears the caller's slot. | Void or status |
| `clef_last_error` | Inspect the last error for a context or the calling thread. | Borrowed string |
| `clef_version` | Read the SDK version. | Static string |
| `pandora_runtime_create`, `pandora_runtime_destroy` | Manage an explicit Runtime. | Status |
| `pandora_runtime_get_status` | Read the Runtime settings. | Status and output structure |
| `pandora_runtime_last_error` | Read the calling thread's Runtime error. | Borrowed string |

## Error codes

| Code | Meaning | What the caller should do |
| --- | --- | --- |
| `CLEF_OK` | Success | Use the result. |
| `CLEF_ERR_ARG` | Invalid argument, request or image | Correct the input and retry. |
| `CLEF_ERR_MODEL`, `CLEF_ERR_IO` | Model data missing, unreadable or inconsistent | Check the installed resources and selected target. |
| `CLEF_ERR_NPU`, `CLEF_ERR_INTERNAL` | Backend or processing failed | Read the error detail, then close and reload. |
| `CLEF_ERR_STATE`, `CLEF_ERR_UNSUPPORTED` | Invalid state or unsupported option | Correct the lifecycle or configuration. |

## Threads and ownership

Keep request and image buffers alive until the synchronous call returns. Pass encoded JPEG/PNG bytes or packed RGB.
Use `clef_free_string` exactly once per successful response. Copy an error string before the next SDK call.
Calls on one model are serialized; finish them before destroying the context. On create failure, read the error
with a null context. A model retains its Runtime even if the caller releases the Runtime handle first.

## Example

A complete program is in [examples/c/systemone.c](../examples/c/systemone.c).
