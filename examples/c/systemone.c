#include <stdio.h>
#include <stdlib.h>
#include "clef_api.h"

static char *read_file(const char *path, size_t *size)
{
    FILE *file = fopen(path, "rb");
    if (!file)
        return NULL;

    char *data = NULL;
    if (fseek(file, 0, SEEK_END) == 0) {
        long length = ftell(file);
        if (length > 0 && length <= 64L * 1024 * 1024 && fseek(file, 0, SEEK_SET) == 0) {
            *size = (size_t)length;
            data = malloc(*size + 1);
            if (data && fread(data, 1, *size, file) != *size) {
                free(data);
                data = NULL;
            }
            if (data)
                data[*size] = '\0';
        }
    }
    fclose(file);
    return data;
}

int main(int argc, char **argv)
{
    if (argc != 4) {
        fprintf(stderr, "usage: %s MODEL_DIR REQUEST.json IMAGE\n", argv[0]);
        return 2;
    }

    size_t request_size = 0;
    size_t image_size = 0;
    char *request = read_file(argv[2], &request_size);
    char *image = read_file(argv[3], &image_size);
    clef_ctx *model = NULL;
    char *response = NULL;
    int result = 1;

    if (!request || !image) {
        fputs("Could not read the request or image file.\n", stderr);
    } else if (clef_create(argv[1], 0, &model) != CLEF_OK) {
        fprintf(stderr, "%s\n", clef_last_error(NULL));
    } else {
        const clef_image input = {CLEF_IMAGE_ENCODED, (const uint8_t *)image, image_size, 0, 0};
        if (clef_systemone(model, request, &input, 1, &response) == CLEF_OK) {
            puts(response);
            result = 0;
        } else {
            fprintf(stderr, "%s\n", clef_last_error(model));
        }
    }

    if (response)
        clef_free_string(response);
    if (model && clef_destroy_owned(&model) != CLEF_OK)
        result = 1;
    free(image);
    free(request);
    return result;
}
