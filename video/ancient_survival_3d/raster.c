/* Minimal software 3D rasteriser for the Ancient Survival 3D reel.
 *
 * Renders procedural triangle meshes with:
 *   - perspective camera, near clipping
 *   - z-buffer
 *   - directional sun with a real shadow map (3x3 PCF)
 *   - hemispheric sky ambient + rim light
 *   - emissive geometry (fire)
 *   - exponential-squared fog, procedural sky, stars, sun/moon disc
 *   - vignette + film grain post
 *
 * Built with: gcc -O2 -march=native -shared -fPIC -o libraster.so raster.c -lm
 * Called from Python through ctypes. No image assets are read: every pixel is
 * produced from geometry and lighting computed per frame.
 */
#include <math.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>

#define SMP 1024

typedef struct {
    const float *v;      /* V x 3 world positions      */
    const float *n;      /* V x 3 world normals        */
    const float *c;      /* V x 3 albedo (linear)      */
    const float *e;      /* V x 3 emission             */
    const int32_t *t;    /* T x 3 vertex indices       */
    int nv, nt;
} Mesh;

typedef struct {
    float pos[3], target[3], up[3];
    float fov;      /* vertical, radians */
    float nearz, farz;
    int w, h;
} Camera;

typedef struct {
    float dir[3];      /* direction *towards* the sun */
    float colour[3];
    float ambient[3];
    float ground[3];
    float fog[3];
    float fog_density;
    float exposure;
    int night;          /* 0..1 blend for star field */
    float moon[3];      /* screen-space-ish sky anchor: x,y in [-1,1], z=radius */
    float shadow_strength;
} Env;

static inline void vsub(const float *a, const float *b, float *o) {
    o[0] = a[0] - b[0]; o[1] = a[1] - b[1]; o[2] = a[2] - b[2];
}
static inline void vcross(const float *a, const float *b, float *o) {
    o[0] = a[1] * b[2] - a[2] * b[1];
    o[1] = a[2] * b[0] - a[0] * b[2];
    o[2] = a[0] * b[1] - a[1] * b[0];
}
static inline float vdot(const float *a, const float *b) {
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}
static inline void vnorm(float *a) {
    float l = sqrtf(vdot(a, a));
    if (l > 1e-8f) { a[0] /= l; a[1] /= l; a[2] /= l; }
}

/* ------------------------------------------------------------------ camera */
static void camera_basis(const Camera *cam, float *right, float *up, float *fwd) {
    vsub(cam->target, cam->pos, fwd);
    vnorm(fwd);
    vcross(fwd, cam->up, right);
    vnorm(right);
    vcross(right, fwd, up);
    vnorm(up);
}

/* --------------------------------------------------------------- shadow map */
static float *g_shadow = NULL;
static float g_lr[3], g_lu[3], g_ld[3];
static float g_lcenter[3];
static float g_lradius = 26.0f;
static float g_ldepth_scale = 1.0f;

static void light_basis(const Env *env) {
    float d[3] = {env->dir[0], env->dir[1], env->dir[2]};
    vnorm(d);
    g_ld[0] = -d[0]; g_ld[1] = -d[1]; g_ld[2] = -d[2];  /* points down the light */
    float helper[3] = {0, 1, 0};
    if (fabsf(g_ld[1]) > 0.95f) { helper[0] = 1; helper[1] = 0; }
    vcross(g_ld, helper, g_lr); vnorm(g_lr);
    vcross(g_lr, g_ld, g_lu); vnorm(g_lu);
    g_lcenter[0] = 0; g_lcenter[1] = 0; g_lcenter[2] = 0;
}

static void light_project(const float *p, float *sx, float *sy, float *depth) {
    float d[3];
    vsub(p, g_lcenter, d);
    float x = vdot(d, g_lr), y = vdot(d, g_lu), z = vdot(d, g_ld);
    *sx = (x / g_lradius) * 0.5f + 0.5f;
    *sy = 0.5f - (y / g_lradius) * 0.5f;
    *depth = (z + g_lradius) / (2 * g_lradius);
}

static void build_shadow(const Mesh *m, int nmesh) {
    memset(g_shadow, 0x7f, sizeof(float) * SMP * SMP);  /* ~large default depth */
    for (int mi = 0; mi < nmesh; ++mi) {
        const Mesh *mesh = &m[mi];
        for (int ti = 0; ti < mesh->nt; ++ti) {
            const int32_t *idx = &mesh->t[ti * 3];
            float px[3], py[3], pz[3];
            for (int k = 0; k < 3; ++k) {
                const float *p = &mesh->v[idx[k] * 3];
                light_project(p, &px[k], &py[k], &pz[k]);
                px[k] *= SMP; py[k] *= SMP;
            }
            float minx = fminf(px[0], fminf(px[1], px[2]));
            float maxx = fmaxf(px[0], fmaxf(px[1], px[2]));
            float miny = fminf(py[0], fminf(py[1], py[2]));
            float maxy = fmaxf(py[0], fmaxf(py[1], py[2]));
            int x0 = (int)fmaxf(0, minx), x1 = (int)fminf(SMP - 1, maxx + 1);
            int y0 = (int)fmaxf(0, miny), y1 = (int)fminf(SMP - 1, maxy + 1);
            if (x0 > x1 || y0 > y1) continue;
            float area = (px[1] - px[0]) * (py[2] - py[0]) - (px[2] - px[0]) * (py[1] - py[0]);
            if (fabsf(area) < 1e-6f) continue;
            float inv = 1.0f / area;
            for (int y = y0; y <= y1; ++y) {
                for (int x = x0; x <= x1; ++x) {
                    float cx = x + 0.5f, cy = y + 0.5f;
                    float w0 = ((px[1] - cx) * (py[2] - cy) - (px[2] - cx) * (py[1] - cy)) * inv;
                    float w1 = ((px[2] - cx) * (py[0] - cy) - (px[0] - cx) * (py[2] - cy)) * inv;
                    float w2 = 1.0f - w0 - w1;
                    if (w0 < 0 || w1 < 0 || w2 < 0) continue;
                    float z = w0 * pz[0] + w1 * pz[1] + w2 * pz[2];
                    float *cell = &g_shadow[y * SMP + x];
                    if (z < *cell) *cell = z;
                }
            }
        }
    }
}

static float shadow_factor(const float *p, float bias) {
    float sx, sy, depth;
    light_project(p, &sx, &sy, &depth);
    if (sx < 0 || sx > 1 || sy < 0 || sy > 1) return 1.0f;
    int cx = (int)(sx * SMP), cy = (int)(sy * SMP);
    float sum = 0.0f;
    int count = 0;
    for (int dy = -1; dy <= 1; ++dy) {
        for (int dx = -1; dx <= 1; ++dx) {
            int x = cx + dx, y = cy + dy;
            if (x < 0 || y < 0 || x >= SMP || y >= SMP) { sum += 1.0f; count++; continue; }
            float ref = g_shadow[y * SMP + x];
            sum += (depth - bias > ref) ? 0.0f : 1.0f;
            count++;
        }
    }
    return sum / (float)count;
}

/* --------------------------------------------------------------- utilities */
static inline uint32_t hash32(uint32_t x) {
    x ^= x >> 16; x *= 0x7feb352dU; x ^= x >> 15; x *= 0x846ca68bU; x ^= x >> 16;
    return x;
}

/* MeshBuffer is assembled on the Python side; here we only read it. */

/* ------------------------------------------------------------------ render */
void render(const Mesh *meshes, int nmesh, const Camera *cam, const Env *env,
            uint8_t *out, float *depth_out, float *normal_out) {
    const int W = cam->w, H = cam->h;
    float right[3], up[3], fwd[3];
    camera_basis(cam, right, up, fwd);
    const float tan_half = tanf(cam->fov * 0.5f);
    const float aspect = (float)W / (float)H;

    if (!g_shadow) g_shadow = (float *)malloc(sizeof(float) * SMP * SMP);
    light_basis(env);
    build_shadow(meshes, nmesh);

    float *zbuf = (float *)malloc(sizeof(float) * W * H);
    float *r = (float *)malloc(sizeof(float) * W * H);
    float *g = (float *)malloc(sizeof(float) * W * H);
    float *b = (float *)malloc(sizeof(float) * W * H);
    for (int i = 0; i < W * H; ++i) {
        zbuf[i] = 1e30f; r[i] = g[i] = b[i] = 0.0f;
        if (normal_out) { normal_out[i*3] = normal_out[i*3+1] = normal_out[i*3+2] = 0.0f; }
    }

    for (int mi = 0; mi < nmesh; ++mi) {
        const Mesh *mesh = &meshes[mi];
        for (int ti = 0; ti < mesh->nt; ++ti) {
            const int32_t *idx = &mesh->t[ti * 3];
            float sx[3], sy[3], sz[3];
            int culled = 0;
            for (int k = 0; k < 3; ++k) {
                const float *p = &mesh->v[idx[k] * 3];
                float d[3];
                vsub(p, cam->pos, d);
                float z = vdot(d, fwd);
                if (z < cam->nearz) { culled = 1; break; }
                float x = vdot(d, right), y = vdot(d, up);
                sx[k] = ((x / (z * tan_half * aspect)) * 0.5f + 0.5f) * W;
                sy[k] = (0.5f - (y / (z * tan_half)) * 0.5f) * H;
                sz[k] = z;
            }
            if (culled) continue;
            float minx = fminf(sx[0], fminf(sx[1], sx[2]));
            float maxx = fmaxf(sx[0], fmaxf(sx[1], sx[2]));
            float miny = fminf(sy[0], fminf(sy[1], sy[2]));
            float maxy = fmaxf(sy[0], fmaxf(sy[1], sy[2]));
            if (maxx < 0 || minx > W - 1 || maxy < 0 || miny > H - 1) continue;
            int x0 = (int)fmaxf(0, minx), x1 = (int)fminf(W - 1, maxx + 1);
            int y0 = (int)fmaxf(0, miny), y1 = (int)fminf(H - 1, maxy + 1);
            if (x0 > x1 || y0 > y1) continue;
            float area = (sx[1] - sx[0]) * (sy[2] - sy[0]) - (sx[2] - sx[0]) * (sy[1] - sy[0]);
            if (fabsf(area) < 1e-6f) continue;
            float inv = 1.0f / area;
            /* back-face cull in screen space (counter-clockwise = front) */
            if (area >= 0.0f) continue;

            float invz[3] = {1.0f / sz[0], 1.0f / sz[1], 1.0f / sz[2]};
            for (int y = y0; y <= y1; ++y) {
                float cy = y + 0.5f;
                for (int x = x0; x <= x1; ++x) {
                    float cx = x + 0.5f;
                    float w0 = ((sx[1] - cx) * (sy[2] - cy) - (sx[2] - cx) * (sy[1] - cy)) * inv;
                    float w1 = ((sx[2] - cx) * (sy[0] - cy) - (sx[0] - cx) * (sy[2] - cy)) * inv;
                    float w2 = 1.0f - w0 - w1;
                    if (w0 < 0 || w1 < 0 || w2 < 0) continue;
                    float iz = w0 * invz[0] + w1 * invz[1] + w2 * invz[2];
                    float z = 1.0f / iz;
                    int pi = y * W + x;
                    if (z >= zbuf[pi]) continue;
                    zbuf[pi] = z;
                    float b0 = w0 * invz[0] * z, b1 = w1 * invz[1] * z, b2 = w2 * invz[2] * z;

                    const float *pa = &mesh->v[idx[0] * 3], *pb = &mesh->v[idx[1] * 3];
                    const float *pc = &mesh->v[idx[2] * 3];
                    float wp[3], na[3], col[3], emi[3];
                    for (int k = 0; k < 3; ++k) {
                        wp[k] = pa[k] * b0 + pb[k] * b1 + pc[k] * b2;
                        na[k] = mesh->n[idx[0] * 3 + k] * b0 + mesh->n[idx[1] * 3 + k] * b1 +
                                mesh->n[idx[2] * 3 + k] * b2;
                        col[k] = mesh->c[idx[0] * 3 + k] * b0 + mesh->c[idx[1] * 3 + k] * b1 +
                                 mesh->c[idx[2] * 3 + k] * b2;
                        emi[k] = mesh->e[idx[0] * 3 + k] * b0 + mesh->e[idx[1] * 3 + k] * b1 +
                                 mesh->e[idx[2] * 3 + k] * b2;
                    }
                    vnorm(na);

                    float ndl = vdot(na, env->dir);
                    float sh = 1.0f;
                    if (fabsf(emi[0]) + fabsf(emi[1]) + fabsf(emi[2]) < 1e-4f) {
                        sh = shadow_factor(wp, 0.0022f);
                        sh = 1.0f - env->shadow_strength * (1.0f - sh);
                    }
                    float diff = fmaxf(0.0f, ndl);
                    /* cel-shaded bands: 3 tonal steps with a soft transition band */
                    float band;
                    if (diff > 0.62f) band = 1.0f;
                    else if (diff > 0.24f) band = 0.70f;
                    else band = 0.44f;
                    diff = band;
                    float hemi = 0.5f + 0.5f * na[1];
                    float ambient = hemi;
                    float viewv[3];
                    vsub(cam->pos, wp, viewv); vnorm(viewv);
                    float rim = powf(1.0f - fmaxf(0.0f, vdot(na, viewv)), 3.0f);

                    if (normal_out) {
                        normal_out[pi * 3 + 0] = na[0];
                        normal_out[pi * 3 + 1] = na[1];
                        normal_out[pi * 3 + 2] = na[2];
                    }
                    for (int k = 0; k < 3; ++k) {
                        float lit = col[k] * (env->colour[k] * diff * 0.92f * sh +
                                              env->ambient[k] * ambient * 0.60f +
                                              env->ground[k] * (1.0f - hemi) * 0.34f +
                                              env->colour[k] * rim * 0.22f * sh);
                        lit += emi[k] * 2.2f;
                        float fog = 1.0f - expf(-env->fog_density * z * z);
                        lit = lit * (1.0f - fog) + env->fog[k] * fog;
                        float v = powf(fmaxf(0.0f, lit) * env->exposure, 1.0f / 2.2f);
                        if (k == 0) r[pi] = v; else if (k == 1) g[pi] = v; else b[pi] = v;
                    }
                }
            }
        }
    }

    /* ---- ink outline pass (cel look) ---- */
    {
        uint8_t *copy = (uint8_t *)malloc((size_t)W * H * 3);
        memcpy(copy, out, (size_t)W * H * 3);
        for (int y = 1; y < H - 1; ++y) {
            for (int x = 1; x < W - 1; ++x) {
                int i = y * W + x;
                float d0 = zbuf[i];
                int edge = 0;
                if (d0 < 1e29f) {
                    const float *n0 = &normal_out[i * 3];
                    int nb[2] = {i + 1, i + W};
                    for (int k = 0; k < 2; ++k) {
                        int j = nb[k];
                        float d1 = zbuf[j];
                        if (d1 > 1e28f) { edge = 1; break; }
                        float nd = n0[0] * normal_out[j * 3] + n0[1] * normal_out[j * 3 + 1] +
                                   n0[2] * normal_out[j * 3 + 2];
                        float dd = fabsf(d0 - d1) / d0;
                        if (nd < 0.90f || dd > 0.055f) { edge = 1; break; }
                    }
                }
                if (edge) {
                    for (int k = 0; k < 3; ++k) {
                        float v = copy[i * 3 + k] * 0.34f;
                        int iv = (int)v;
                        out[i * 3 + k] = (uint8_t)(iv < 0 ? 0 : iv);
                    }
                }
            }
        }
        free(copy);
    }

    /* sky + composite */
    for (int y = 0; y < H; ++y) {
        for (int x = 0; x < W; ++x) {
            int pi = y * W + x;
            float ndx = (x + 0.5f) / W * 2.0f - 1.0f;
            float ndy = 1.0f - (y + 0.5f) / H * 2.0f;
            /* sky gradient: horizon -> zenith */
            float t = fmaxf(0.0f, fminf(1.0f, (ndy + 0.35f) / 1.15f));
            float sky[3];
            float top[3] = {0.16f, 0.22f, 0.38f};
            float hor[3] = {0.86f, 0.70f, 0.55f};
            if (env->night > 0.5f) {
                top[0] = 0.05f; top[1] = 0.07f; top[2] = 0.16f;
                hor[0] = 0.30f; hor[1] = 0.26f; hor[2] = 0.34f;
            }
            for (int k = 0; k < 3; ++k) sky[k] = hor[k] * (1 - t) + top[k] * t;
            /* stars */
            if (env->night > 0.05f && ndy > 0.18f) {
                uint32_t h = hash32((uint32_t)(x * 7919 + y * 104729));
                float s = (h & 0xFFFF) / 65535.0f;
                if (s > 0.9975f) {
                    float br = ((h >> 16) & 0xFF) / 255.0f;
                    float k2 = env->night * (0.35f + 0.65f * br);
                    sky[0] += k2; sky[1] += k2; sky[2] += k2 * 1.05f;
                }
            }
            /* sun / moon disc */
            float dx = ndx - env->moon[0], dy = ndy - env->moon[1];
            float rad = env->moon[2];
            float dd = sqrtf(dx * dx + dy * dy);
            if (rad > 0 && dd < rad * 1.9f) {
                float core = fmaxf(0.0f, 1.0f - dd / rad);
                float halo = fmaxf(0.0f, 1.0f - dd / (rad * 1.9f));
                float glow = core * core * 1.4f + halo * halo * 0.25f;
                if (env->night > 0.5f) {
                    sky[0] += glow * 0.95f; sky[1] += glow * 0.95f; sky[2] += glow * 1.0f;
                } else {
                    sky[0] += glow * 1.15f; sky[1] += glow * 0.95f; sky[2] += glow * 0.65f;
                }
            }
            float sr = powf(fmaxf(0.0f, sky[0]) * env->exposure, 1 / 2.2f);
            float sg = powf(fmaxf(0.0f, sky[1]) * env->exposure, 1 / 2.2f);
            float sb = powf(fmaxf(0.0f, sky[2]) * env->exposure, 1 / 2.2f);

            float px[3];
            float d = zbuf[pi];
            if (d < 1e29f) {
                px[0] = r[pi]; px[1] = g[pi]; px[2] = b[pi];
            } else {
                px[0] = sr; px[1] = sg; px[2] = sb;
            }

            /* vignette */
            float vx = ndx * 0.82f, vy = ndy * 0.62f;
            float vig = 1.0f - 0.34f * (vx * vx + vy * vy);
            vig = fmaxf(0.35f, vig);

            /* grain */
            uint32_t h = hash32((uint32_t)(x * 1973 + y * 9277 + 17));
            float grain = (((h >> 8) & 0xFF) / 255.0f - 0.5f) * 0.020f;

            for (int k = 0; k < 3; ++k) {
                float v = px[k] * vig + grain;
                int iv = (int)(v * 255.0f + 0.5f);
                if (iv < 0) iv = 0;
                if (iv > 255) iv = 255;
                out[pi * 3 + k] = (uint8_t)iv;
            }
            if (depth_out) depth_out[pi] = d;
        }
    }
    free(zbuf); free(r); free(g); free(b);
}
