# Decision Studio

Start on the device from the repository root:

```bash
bash demo/run.sh --port 8765
```

Open `http://<device-ip>:8765` from a browser on the same LAN. Model loading happens once at startup; the server
prints `CLEF_WEB_READY` after it is ready. Stop with Ctrl+C or SIGTERM. The service retains model memory while running.
The launcher uses the project .venv interpreter and checks native dependencies before model loading.
It uses Python's standard library and the native SDK; no frontend build, CDN, Node.js, or extra Python packages are needed.
This is a trusted-LAN demo without authentication; it is not an Internet-facing service.

## Controls

- The page starts with empty State text, an optional image upload, one empty Yes/no question and no selected template.
  Four template buttons load examples from `presets.json`: three image examples (skiing, sandwich and food web),
  plus an APLUX-authored text-only support ticket. Support ticket clears the image and asks which team should
  handle a duplicate-payment refund; the reference answer is Billing.
- Enlarge image opens the full image; Upload replaces it with a local JPEG or PNG up to 8 MiB. Uploads stay in memory.
  The SDK also limits decoded images to 32 Mi pixels and 32768 pixels per side. Run is unavailable while the
  browser reads an upload; reset, template selection or removal cancels its effect.
  Remove image keeps State text and questions. Reset inputs in the State panel clears all inputs and previous results.
- State is the text or background material used for the decision, not a system prompt. It can be used alone or with
  an image; text can be empty for image-only questions. The text field expands when no image is attached.
  The browser sends edited State as plain text; unchanged built-in templates preserve their original State values.
- The main view shows State, an optional image, a plain-text question, Run decision, and an answer. Answer format
  and option editing are grouped under each question, with the first question expanded by default. There is no Settings dialog.
- Question instructions are plain text. The native model API, not the web UI, defines the question type and candidate
  answers: Choice uses 2–12 named option descriptions; Yes/no uses true and false;
  Score uses 2–12 ordered descriptions with indices starting at 0. The returned score is the probability-weighted
  mean of those indices. This is candidate-based decision scoring, not open-ended text generation.
  Add question in the Question panel creates a Yes/no question; remove controls appear on each question when
  there is more than one (up to 12).
  All questions are encoded together in one SDK inference, not one inference per question. Additional questions
  increase the input length and may increase inference time.
- Run decision invokes the live SDK. Previous results are marked out of date after an edit. There is no result cache.
  Another simultaneous request receives HTTP 409 instead of queuing for the device.
- Results show the selected option key, Yes/no outcome or expected score. Softmax probabilities appear beside the
  existing question options, with the most likely option highlighted; full option text is not duplicated in Answer.
  Built-in reference labels remain available through the HTTP API when the input matches the template.
- The always-visible Performance strip at the bottom shows model inference time (excluding startup), tokens/slices,
  vision, prefill, decision head, and image/encoding time. Values describe the last completed run; editing inputs marks
  them as belonging to earlier inputs. Reset inputs clears them to placeholders.
- Model probabilities are not empirical accuracy. The SDK context window
  is 8192 tokens. If the request exceeds that limit, the page shows an input error. Shorten State or
  the questions and try again. Browser requests time out after three minutes; timing out does not
  cancel a synchronous inference already running on the device.
- Desktop panels fit the viewport and scroll when expanded options or multiple questions need more space.

## Configuration

| Argument / environment | Default | Purpose |
|---|---|---|
| `--host` / `CLEF_HOST` | `0.0.0.0` | Listen address |
| `--port` / `CLEF_PORT` | `8765` | HTTP port |
| `--models` / `CLEF_MODELS` | flat `models/` or its unique immediate package | Package containing `models.json` |

The page uses the APLUX / Pandora brand assets provided by the demo standard.
The example illustrations are licensed under Apache-2.0. See [NOTICE](../NOTICE) for attribution.

## HTTP API

| Endpoint | Body | Success |
| --- | --- | --- |
| `GET /api/info` | — | Device state and SDK version |
| `GET /api/presets` | — | Built-in examples with `clef-flash` as the model ID |
| `POST /api/run` | A `request` object with `state` and `questions`, plus optional `preset_id` or `image_base64` | `response`, `reference` and `request_ms` |
| `POST /api/reload` | Omit the body or send `{}` | Current device state after reopening the model |

For `/api/run`, supply an example ID such as `skiing` to use its image or send JPEG/PNG bytes
as base64 without the data-URL prefix. An upload takes precedence over a preset image. Omit both
for text-only input. The server uses `clef-flash` as the model ID and returns it in `response.model`.
The `response` also contains answers, usage and `decision` with option logits and timings.
`reference` is returned for an unchanged example and is null otherwise.

| Status | Meaning |
| --- | --- |
| 200 | Request succeeded |
| 400 | Invalid input or invalid reload body |
| 403 | Cross-origin POST |
| 404 | Unknown endpoint |
| 409 | The model is busy with another request or reload |
| 413 | Run body is empty or exceeds 12 MiB |
| 500 | Inference failed |
| 503 | Inference requires a model reload, or a reload failed. The error body includes `reload_required: true`. |

## Connection and model recovery

Retry connection checks the service state without re-running a decision and retains the current inputs. A native failure blocks further inference and exposes Reload model. Reload waits for request ownership, closes the old model and creates a new owner; validation errors do not trigger reload. Loading/failure/busy states are reported by /api/info. Stop during reload joins the handler before final model destruction. The SDK has no cancellation for an in-flight vendor call.

The HTTP server joins request threads before releasing the model, including a pending reload. Model shutdown checks ownership under the same lock as inference/reload. This retains the single-process SDK caller and prevents interpreter exit during native acquisition or release.

## CPU placement

See the [SDK Runtime API](../sdk/RUNTIME_API.md) for default CPU placement.
