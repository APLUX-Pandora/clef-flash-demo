# Model setup

## Device requirements

- A compatible Linux device with Aidlux LMS (`sudo lms check` returns true), drivers, DSP firmware and BSP/FastRPC support.
- Python 3.10–3.12 in the Demo environment (see [Install](../README.md#1-install)).
- The SDK includes its QNN runtime libraries. Do not install QNN separately or set QNN paths.

## Targets

Pick the folder for your device's SoC:

| SoC | Target folder | `soc_id` |
| --- | --- | --- |
| QCS8550 | `targets/qcs8550_qnn248` | 603 |
| QCS8625 | `targets/qcs8625_qnn248` | 702 |
| QCS8275 (IQ8) | `targets/qcs8275_qnn248` | 675 |
| QCS9075 (IQ9) | `targets/qcs9075_qnn248` | 676 |

Read `/sys/devices/soc0/soc_id` on your device and use the corresponding target folder. QCS8275 also accepts the QCS8625 target when the QCS8275 folder is absent.

## Download

For a model folder dedicated to one device, follow the single-target workflow below.

From the Demo root, in the activated environment, download the shared resources once and then one target:

```bash
hf download APLUX-Pandora/clef-flash --local-dir models --exclude "targets/*" --exclude "media/*" --exclude README.md --exclude .gitattributes
hf download APLUX-Pandora/clef-flash --local-dir models --include "targets/<target-folder>/*"
```

Run `hf auth login` first if the repository is private. Keep one target per model folder: to switch devices, move the old `targets/` folder out or download into a new folder.

Replace `<target-folder>` with the folder name from the table above, such as `qcs8550_qnn248`. For a shared model folder, keep the downloaded targets in place and repeat the second command for each additional SoC.

## Folder layout

After the download, `models/` looks like this:

```text
models/
├── models.json
├── SHA256SUMS
├── NOTICE
├── LICENSES/
│   └── Apache-2.0.txt
├── tokenizer.json
├── embedding_u16.bin
├── decision_head.json
├── decision_head.bin
├── lm_head_bf16.bin
├── vit_rope_cos.f32
├── vit_rope_sin.f32
└── targets/
    └── qcs8550_qnn248/
        ├── clef-flash_qnn248_qcs8550_cl8192_1_of_4.serialized.bin.aidem
        ├── clef-flash_qnn248_qcs8550_cl8192_2_of_4.serialized.bin.aidem
        ├── clef-flash_qnn248_qcs8550_cl8192_3_of_4.serialized.bin.aidem
        ├── clef-flash_qnn248_qcs8550_cl8192_4_of_4.serialized.bin.aidem
        ├── vision.aidem
        └── htp_config.json
```

Genie generates the language position encodings. A download can also contain `rope_cos_sin.f32` for
older SDKs. The current SDK uses the two vision position files shown above.

The SDK reads `models.json`, checks that the shared resources and one complete target are present, and reports what is missing. `hf download` verifies each large file's checksum.

The SDK selects the target for the detected SoC and checks for missing or empty files in that target and the shared resources.

Verify the downloaded target after both downloads, from the Demo root:

```bash
(
  set -o pipefail
  cd models || exit 1
  awk -v target="targets/qcs8550_qnn248/" '
    # Skip the 64-character digest and its two-character separator.
    { path = substr($0, 67) }
    index(path, target) == 1 { found = 1; print; next }
    path !~ /^(targets|media)\// && path != "README.md" && path != ".gitattributes"
    END {
      if (!found) {
        print "No checksum entries for " target > "/dev/stderr"
        exit 1
      }
    }
  ' SHA256SUMS | sha256sum --check --strict
)
```

If you downloaded a different target, replace `qcs8550_qnn248` in the check with its folder name.

## Troubleshooting

| Message or symptom | What to do |
| --- | --- |
| Resource missing | Repeat the shared download and the command for your SoC. |
| No model target for the detected SoC | Compare the reported device and available targets, then download the matching target. |
| Authorization fails | Check that Aidlux LMS is installed and reports an active license. |
| Vision or language context fails to load | Confirm that the downloaded target and the SDK release match your device. |
