# Clef-Flash

<p align="center">
  <a href="https://huggingface.co/APLUX-Pandora/clef-flash"><img src="https://img.shields.io/badge/Hugging%20Face-CLEF--FLASH-E3B800?style=for-the-badge&amp;logo=huggingface&amp;logoColor=FFD21E&amp;labelColor=555555" alt="Hugging Face: Clef-Flash"></a>
  <a href="https://github.com/APLUX-Pandora/clef-flash-demo"><img src="https://img.shields.io/badge/GitHub-CLEF--FLASH-000000?style=for-the-badge&amp;logo=github&amp;logoColor=white&amp;labelColor=555555" alt="GitHub: Clef-Flash"></a>
</p>

Clef-Flash answers choice, yes/no probability and ordinal-score questions from text and images on an on-device NPU.

Based on [Clef-Flash](https://huggingface.co/Cloudflare/clef-flash).

**Demo recording:** reserved for a post-release recording.

## 1. Install

The example images use Git LFS. On Ubuntu, install and initialize Git LFS before cloning:

```bash
sudo apt install git-lfs
git lfs install
```

Clone the Demo and enter its root directory:

```bash
git clone https://github.com/APLUX-Pandora/clef-flash-demo.git
cd clef-flash-demo
```

If you already cloned the Demo before installing Git LFS, run this from the existing checkout after initialization:

```bash
git lfs pull
```

### Prepare the device

Use a compatible Linux device with Aidlux LMS and the required drivers, DSP firmware and BSP/FastRPC support. The SDK includes its QNN runtime libraries; no separate QNN installation or path configuration is required.

Check the activation:

```bash
sudo lms check
```

Continue only when it returns true.

Install the system packages the Demo needs:

```bash
sudo apt install python3-venv
```

### Install the Demo and SDK

Use Python 3.10–3.12. Create and activate the Demo environment, then install:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

This installs the SDK, the Web Demo and the Hugging Face CLI. To use only the SDK in your own application, see the [SDK installation](sdk/README.md#install).

## 2. Get the model

Download the shared files and one device target. The commands below use QCS8550; for another device, use the folder in the [targets table](docs/MODEL_SETUP.md#targets).

For a private model, run `hf auth login` first.

```bash
hf download APLUX-Pandora/clef-flash --local-dir models --exclude "targets/*" --exclude "media/*" --exclude README.md --exclude .gitattributes
hf download APLUX-Pandora/clef-flash --local-dir models --include "targets/qcs8550_qnn248/*"
```

## 3. Run the Web Demo

```bash
bash demo/run.sh --port 8765
```

Open `http://<device-ip>:8765/` and enter some context, add an image if needed, and run your questions. Stop it with `Ctrl+C`. See the [Web Demo guide](demo/README.md).

## 4. Python Usage

The SDK is installed as `pandora-clef-flash`. In the same environment, from the Demo root:

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

More in the [Python API](sdk/PYTHON_API.md) and [examples](examples/README.md).

## Documentation

- [Model setup](docs/MODEL_SETUP.md): device requirements, targets, download and folder layout
- [Python API](sdk/PYTHON_API.md): every public class, method and parameter
- [Runtime API](sdk/RUNTIME_API.md): CPU placement and model runtime options
- [C ABI](docs/C_ABI.md): native integration
- [Examples](examples/README.md): runnable Python and C examples

## License

See [LICENSING.md](LICENSING.md), [NOTICE](NOTICE) and [LICENSES](LICENSES/).
