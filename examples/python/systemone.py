"""Answer one structured request, optionally with image files, using the SDK."""
import argparse
import json
from pathlib import Path
import signal

from pandora_clef_flash import DecisionModel, resolve_models

ROOT = Path(__file__).resolve().parents[2]



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", default=None, help="Package directory containing models.json")
    parser.add_argument("--request")
    parser.add_argument("--image", action="append", default=[])
    parser.add_argument("--truncation", action="store_true", help="Allow state-tail truncation only")
    parser.add_argument("--diagnostics", action="store_true", help="Include option logits and timing")
    args = parser.parse_args()
    example_inputs = ROOT / "examples/inputs"
    request_path = Path(args.request) if args.request else example_inputs / "request.json"
    images = args.image
    if args.request is None and not images:
        images = [example_inputs / "skiing.jpeg"]
    request = json.loads(request_path.read_text())
    stop_signals = {signal.SIGINT, signal.SIGTERM}
    # Native threads inherit this mask when the model creates them.
    previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, stop_signals)
    try:
        with DecisionModel.from_pretrained(resolve_models(args.models, default_root=ROOT / "models")) as engine:
            if signal.sigpending() & (stop_signals - previous_mask):
                return
            result = engine.systemone(request, images=images, truncation=args.truncation,
                                      return_diagnostics=args.diagnostics)
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
