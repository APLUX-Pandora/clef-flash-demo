/* Clef-Flash: architecture-neutral C API of libclef.so.
 *
 * One call answers a Jev/SystemOne /v1/systemone request body, like the release's systemone():
 *   request  {"model": str, "state": any, "questions": {id: {"type": "noul"|"choice"|"score", "instructions", "criteria"}},
 *             "images": [file path, ...] (optional; images can also be passed as buffers)}
 *   response {"model", "answers": {id: answer}, "usage": {"input_tokens", "output_tokens": 0},
 *             "clef": {"logits": {id: {"options": [...], "logits": [...]}}, "timing": {...}}}
 * The answers are systemone_answer() of the release (probabilities = softmax of the option logits, rounded to 4
 * decimals). Records longer than the 8192-token context fail by default. Optional boolean request.truncation=true permits
 * state-tail truncation; response.truncated reports whether it occurred. Questions/options/images are retained.
 * Call sequence: create -> systemone (repeat) -> destroy. Each request resets model state.
 * Calls on one context are serialized internally; destroy must not overlap any other call.
 * Error text is valid until the next call on the context (or next create on this thread).
 * Inference is synchronous and deterministic for a fixed package, runtime and build.
 * The library loads and executes each model on a dedicated Runtime worker.
 */
#ifndef CLEF_API_H
#define CLEF_API_H

#include <stddef.h>
#include <stdint.h>
#include "pandora_runtime.h"

#define CLEF_VERSION "1.0.0"
#if defined(__GNUC__)
#define CLEF_API __attribute__((visibility("default")))
#else
#define CLEF_API
#endif

#ifdef __cplusplus
extern "C" {
#endif

#define CLEF_OK 0
#define CLEF_ERR_ARG (-1)      /* bad request / image */
#define CLEF_ERR_MODEL (-2)    /* package files missing or inconsistent */
#define CLEF_ERR_NPU (-3)
#define CLEF_ERR_IO (-4)
#define CLEF_ERR_INTERNAL (-5)
#define CLEF_ERR_STATE (-6)
#define CLEF_ERR_UNSUPPORTED (-7)

typedef struct clef_ctx clef_ctx;

enum clef_image_kind {
    CLEF_IMAGE_ENCODED = 0,   /* JPEG or PNG file contents: data, size */
    CLEF_IMAGE_RGB = 1        /* packed 8-bit RGB: data, width, height (size = width * height * 3) */
};

typedef struct {
    int kind;                 /* clef_image_kind */
    const uint8_t *data;
    size_t size;
    int width, height;        /* CLEF_IMAGE_RGB only */
} clef_image;

/* pkg_dir: model package root; head_threads: 0 = one per selected Runtime CPU.
 */
CLEF_API int clef_create(const char *pkg_dir, int head_threads, clef_ctx **ctx);
CLEF_API void clef_destroy(clef_ctx *ctx);
/* Output slots must start NULL. Success transfers ownership to the slot.
 * destroy_owned clears it before destruction; repeat calls are safe.
 * The model retains its Runtime; a null Runtime uses the defaults.
 * Same model calls serialize; destroy must not overlap any call. */
CLEF_API int clef_create_with_runtime(const char *, int, pandora_runtime_t *, clef_ctx **);
CLEF_API int clef_destroy_owned(clef_ctx **);

/* images (may be NULL / 0) come after the request's own "images" paths, in order. *response is a NUL-terminated JSON
 * string to free with clef_free_string. */
CLEF_API int clef_systemone(clef_ctx *ctx, const char *request_json, const clef_image *images, int n_images, char **response);
CLEF_API void clef_free_string(char *s);

/* message of the last failed call on ctx (or of the last failed clef_create when ctx is NULL) */
CLEF_API const char *clef_last_error(const clef_ctx *ctx);
CLEF_API const char *clef_version(void);

#ifdef __cplusplus
}
#endif

#endif /* CLEF_API_H */
