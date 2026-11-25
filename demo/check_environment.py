"""Check the interpreter and native runtime before initializing the device model."""
import sys


def main():
    if sys.prefix == sys.base_prefix:
        print("Use the project .venv interpreter. See README Install.", file=sys.stderr)
        return 1

    try:
        from pandora_clef_flash._native import library

        library()
    except (ImportError, OSError) as error:
        print(f"Cannot load the native SDK: {error}", file=sys.stderr)
        print("Follow the installation steps in README Install.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
