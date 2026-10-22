/* Software 3D rasteriser for the Ancient Survival reel — v2.
 *
 * Renders procedural triangle meshes with:
 *   - perspective camera + z-buffer
 *   - directional sun with a real shadow map (3x3 PCF)
 *   - hemispheric sky ambient, rim light, two point lights (camp fire, torch)
 *   - emissive geometry (flames, embers, stars)
 *   - screen-space ambient occlusion (contact darkening in creases)
 *   - bloom on bright/emissive pixels
 *   - ACES-style filmic tone mapping, exponential-squared fog
 *   - procedural sky: gradient, sun/moon disc with phase + halo, stars,
 *     milky way band and soft cloud banks
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
    /* --- v2 additions --- */
    float light[3];         /* primary point light (camp fire)   */
    float light_colour[3];
    float light_range;
    float light2[3];        /* secondary point light             */
    float light2_colour[3];
    float light2_range;
    float sky_hor[3];       /* horizon colour                    */
    float sky_top[3];       /* zenith colour                     */
    float cloud;            /* cloud amount (day skies)          */
    float milky;            /* milky way strength                */
    float ao_strength;      /* 0..1                              */
    float bloom;            /* 0..1                              */
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

static inline float hash2f(int x, int y) {
    uint32_t h = hash32((uint32_t)(x * 374761393 + y * 668265263));
    return (h & 0xFFFFFF) / 16777215.0f;
}

static inline float smoothstepf(float e0, float e1, float x) {
    float t = (x - e0) / (e1 - e0 + 1e-6f);
    t = t < 0 ? 0 : (t > 1 ? 1 : t);
    return t * t * (3 - 2 * t);
}

/* value noise + fbm, used for the milky way and cloud banks */
static float vnoise(float x, float y) {
    int xi = (int)floorf(x), yi = (int)floorf(y);
    float xf = x - xi, yf = y - yi;
    float u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
    float a = hash2f(xi, yi), b = hash2f(xi + 1, yi);
    float c = hash2f(xi, yi + 1), d = hash2f(xi + 1, yi + 1);
    return (a * (1 - u) + b * u) * (1 - v) + (c * (1 - u) + d * u) * v;
}

static float fbm(float x, float y, int oct) {
    float sum = 0.0f, amp = 0.5f, f = 1.0f;
    for (int i = 0; i < oct; ++i) {
        sum += amp * vnoise(x * f, y * f);
        f *= 2.07f;
        amp *= 0.5f;
    }
    return sum;
}

static inline float point_term(const float *wp, const float *na, const float *lp,
                               float range) {
    float d[3];
    vsub(lp, wp, d);
    float dist2 = vdot(d, d);
    if (dist2 > range * range) return 0.0f;
    float dist = sqrtf(dist2) + 1e-5f;
    float ndl = vdot(na, d) / dist;
    if (ndl <= 0.0f) return 0.0f;
    float f = 1.0f - dist / range;
    return f * f * ndl;
}

static inline float aces(float x) {
    const float a = 2.51f, b = 0.03f, c = 2.43f, d = 0.59f, e = 0.14f;
    float y = (x * (a * x + b)) / (x * (c * x + d) + e);
    return y < 0.0f ? 0.0f : (y > 1.0f ? 1.0f : y);
}

typedef struct {
    float p[3], n[3], c[3], e[3];
    float cx, cy, cz;
} Vtx;

static void raster_tri(const Vtx *A, const Vtx *B, const Vtx *C, const Camera *cam,
                       const Env *env, int W, int H, float tan_half, float aspect,
                       float *zbuf, float *lin, float *glow, float *normal_out,
                       const float *campos) {
    float sx[3], sy[3], sz[3];
    const Vtx *vv[3] = {A, B, C};
    for (int k = 0; k < 3; ++k) {
        float z = vv[k]->cz;
        if (z < cam->nearz) return;
        sx[k] = ((vv[k]->cx / (z * tan_half * aspect)) * 0.5f + 0.5f) * W;
        sy[k] = (0.5f - (vv[k]->cy / (z * tan_half)) * 0.5f) * H;
        sz[k] = z;
    }
    float minx = fminf(sx[0], fminf(sx[1], sx[2]));
    float maxx = fmaxf(sx[0], fmaxf(sx[1], sx[2]));
    float miny = fminf(sy[0], fminf(sy[1], sy[2]));
    float maxy = fmaxf(sy[0], fmaxf(sy[1], sy[2]));
    if (maxx < 0 || minx > W - 1 || maxy < 0 || miny > H - 1) return;
    int x0 = (int)fmaxf(0, minx), x1 = (int)fminf(W - 1, maxx + 1);
    int y0 = (int)fmaxf(0, miny), y1 = (int)fminf(H - 1, maxy + 1);
    if (x0 > x1 || y0 > y1) return;
    float area = (sx[1] - sx[0]) * (sy[2] - sy[0]) - (sx[2] - sx[0]) * (sy[1] - sy[0]);
    if (fabsf(area) < 1e-6f) return;
    if (area >= 0.0f) return;          /* back-face (CCW = front) */
    float inv = 1.0f / area;
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
            size_t pi = (size_t)y * W + x;
            if (z >= zbuf[pi]) continue;
            zbuf[pi] = z;
            float b0 = w0 * invz[0] * z, b1 = w1 * invz[1] * z, b2 = w2 * invz[2] * z;

            float wp[3], na[3], col[3], emi[3];
            for (int k = 0; k < 3; ++k) {
                wp[k] = A->p[k] * b0 + B->p[k] * b1 + C->p[k] * b2;
                na[k] = A->n[k] * b0 + B->n[k] * b1 + C->n[k] * b2;
                col[k] = A->c[k] * b0 + B->c[k] * b1 + C->c[k] * b2;
                emi[k] = A->e[k] * b0 + B->e[k] * b1 + C->e[k] * b2;
            }
            vnorm(na);

            float emissive = fabsf(emi[0]) + fabsf(emi[1]) + fabsf(emi[2]);
            float ndl = vdot(na, env->dir);
            float sh = 1.0f;
            if (emissive < 1e-4f) {
                sh = shadow_factor(wp, 0.0022f);
                sh = 1.0f - env->shadow_strength * (1.0f - sh);
            }
            float diff = fmaxf(0.0f, ndl);
            float band;
            if (diff > 0.55f) band = 1.0f;
            else if (diff > 0.20f) band = smoothstepf(0.20f, 0.55f, diff) * 0.30f + 0.70f;
            else band = 0.44f + smoothstepf(0.0f, 0.20f, diff) * 0.20f;
            float hemi = 0.5f + 0.5f * na[1];
            float viewv[3];
            vsub(campos, wp, viewv); vnorm(viewv);
            float fres = 1.0f - fmaxf(0.0f, vdot(na, viewv));
            float rim = powf(fres, 3.0f);

            float p1 = 0.0f, p2 = 0.0f;
            if (emissive < 1e-4f) {
                p1 = point_term(wp, na, env->light, env->light_range);
                p2 = point_term(wp, na, env->light2, env->light2_range);
            }
            if (normal_out) {
                normal_out[pi * 3 + 0] = na[0];
                normal_out[pi * 3 + 1] = na[1];
                normal_out[pi * 3 + 2] = na[2];
            }
            for (int k = 0; k < 3; ++k) {
                float lit = col[k] * (env->colour[k] * band * 0.88f * sh +
                                      env->ambient[k] * hemi * 0.52f +
                                      env->ground[k] * (1.0f - hemi) * 0.36f +
                                      env->colour[k] * rim * 0.20f * sh);
                lit += col[k] * env->light_colour[k] * p1 * 2.4f;
                lit += col[k] * env->light2_colour[k] * p2 * 2.0f;
                lit += emi[k] * 1.75f;
                float fog = 1.0f - expf(-env->fog_density * z * z);
                lit = lit * (1.0f - fog) + env->fog[k] * fog;
                lin[pi * 3 + k] = lit < 0.0f ? 0.0f : lit;
            }
            if (emissive > 0.01f) glow[pi] = fminf(1.0f, emissive * 0.5f);
        }
    }
}

/* ------------------------------------------------------------------ render */
void render(const Mesh *meshes, int nmesh, const Camera *cam, const Env *env,
            uint8_t *out, float *depth_out, float *normal_out) {
    const int W = cam->w, H = cam->h;
    float right[3], up[3], fwd[3];
    camera_basis(cam, right, up, fwd);
    const float tan_half = tanf(cam->fov * 0.5f);
    const float aspect = (float)W / (float)H;
    const size_t NP = (size_t)W * H;

    if (!g_shadow) g_shadow = (float *)malloc(sizeof(float) * SMP * SMP);
    light_basis(env);
    build_shadow(meshes, nmesh);

    float *zbuf = (float *)malloc(sizeof(float) * NP);
    float *lin = (float *)malloc(sizeof(float) * NP * 3);
    float *glow = (float *)calloc(NP, sizeof(float));
    if (normal_out) {
        for (size_t i = 0; i < NP * 3; ++i) normal_out[i] = 0.0f;
    }
    for (size_t i = 0; i < NP; ++i) {
        zbuf[i] = 1e30f;
        lin[i * 3] = lin[i * 3 + 1] = lin[i * 3 + 2] = 0.0f;
    }

    const float ao_strength = env->ao_strength > 0.0f ? env->ao_strength : 0.65f;
    const float bloom_amt = env->bloom >= 0.0f ? env->bloom : 0.55f;
    const int nightish = env->night;

    /* ------------------------------------------------- geometry (clipped) */
    for (int mi = 0; mi < nmesh; ++mi) {
        const Mesh *mesh = &meshes[mi];
        for (int ti = 0; ti < mesh->nt; ++ti) {
            const int32_t *idx = &mesh->t[ti * 3];
            Vtx tri[3];
            for (int k = 0; k < 3; ++k) {
                const int vi = idx[k];
                for (int a = 0; a < 3; ++a) {
                    tri[k].p[a] = mesh->v[vi * 3 + a];
                    tri[k].n[a] = mesh->n[vi * 3 + a];
                    tri[k].c[a] = mesh->c[vi * 3 + a];
                    tri[k].e[a] = mesh->e[vi * 3 + a];
                }
                float d[3];
                vsub(tri[k].p, cam->pos, d);
                tri[k].cz = vdot(d, fwd);
                tri[k].cx = vdot(d, right);
                tri[k].cy = vdot(d, up);
            }
            /* clip against the near plane so huge ground triangles never wrap */
            Vtx poly[4];
            int np = 0;
            for (int k = 0; k < 3; ++k) {
                const Vtx *a = &tri[k], *b = &tri[(k + 1) % 3];
                int ain = a->cz >= cam->nearz, bin = b->cz >= cam->nearz;
                if (ain) poly[np++] = *a;
                if (ain != bin) {
                    float t = (cam->nearz - a->cz) / (b->cz - a->cz);
                    Vtx o;
                    for (int q = 0; q < 3; ++q) {
                        o.p[q] = a->p[q] + (b->p[q] - a->p[q]) * t;
                        o.n[q] = a->n[q] + (b->n[q] - a->n[q]) * t;
                        o.c[q] = a->c[q] + (b->c[q] - a->c[q]) * t;
                        o.e[q] = a->e[q] + (b->e[q] - a->e[q]) * t;
                    }
                    o.cx = a->cx + (b->cx - a->cx) * t;
                    o.cy = a->cy + (b->cy - a->cy) * t;
                    o.cz = cam->nearz;
                    if (np < 4) poly[np++] = o;
                }
            }
            for (int f = 1; f + 1 < np; ++f) {
                raster_tri(&poly[0], &poly[f], &poly[f + 1], cam, env, W, H,
                           tan_half, aspect, zbuf, lin, glow, normal_out, cam->pos);
            }
        }
    }

    /* ------------------------------------------------------- sky (linear) */
    for (int y = 0; y < H; ++y) {
        for (int x = 0; x < W; ++x) {
            size_t pi = (size_t)y * W + x;
            float ndx = (x + 0.5f) / W * 2.0f - 1.0f;
            float ndy = 1.0f - (y + 0.5f) / H * 2.0f;
            float t = smoothstepf(-0.55f, 0.95f, ndy);

            float hor[3], top[3];
            if (env->sky_hor[0] + env->sky_hor[1] + env->sky_hor[2] > 1e-4f) {
                for (int k = 0; k < 3; ++k) { hor[k] = env->sky_hor[k]; top[k] = env->sky_top[k]; }
            } else {
                for (int k = 0; k < 3; ++k) {
                    hor[k] = nightish ? 0.09f : 0.70f;
                    top[k] = nightish ? 0.02f : 0.28f;
                }
                hor[0] = nightish ? 0.10f : 0.78f; hor[2] = nightish ? 0.20f : 0.52f;
                top[0] = nightish ? 0.012f : 0.20f; top[2] = nightish ? 0.075f : 0.55f;
            }
            float sky[3];
            for (int k = 0; k < 3; ++k) sky[k] = hor[k] * (1 - t) + top[k] * t;

            /* milky way band + stars (night) */
            if (nightish) {
                float band = expf(-powf((ndy - 0.30f + 0.55f * ndx * ndx) * 2.1f, 2.0f));
                float n = fbm(ndx * 5.5f + 11.0f, ndy * 9.5f + 3.0f, 4);
                float n2 = fbm(ndx * 16.0f, ndy * 22.0f, 3);
                float mw = band * (0.045f * n + 0.070f * n * n2) * env->milky;
                sky[0] += mw * 0.62f; sky[1] += mw * 0.68f; sky[2] += mw * 0.92f;

                if (ndy > 0.05f) {
                    uint32_t h = hash32((uint32_t)(x * 7919 + y * 104729));
                    float s = (h & 0xFFFF) / 65535.0f;
                    if (s > 0.9972f) {
                        float br = ((h >> 16) & 0xFF) / 255.0f;
                        float big = ((h >> 8) & 0x7) == 0 ? 1.7f : 1.0f;
                        float k2 = (0.30f + 0.85f * br) * big;
                        sky[0] += k2 * 0.95f; sky[1] += k2; sky[2] += k2 * 1.08f;
                    }
                }
            } else if (env->cloud > 0.01f) {
                /* soft cloud banks near the horizon */
                float c = fbm(ndx * 2.2f + 4.0f, ndy * 6.5f, 5);
                float mask = smoothstepf(0.52f, 0.95f, c) * smoothstepf(0.05f, 0.45f, ndy)
                             * (1.0f - smoothstepf(0.55f, 0.95f, ndy));
                float cl = mask * env->cloud * 0.9f;
                sky[0] += cl * 1.05f; sky[1] += cl * 1.00f; sky[2] += cl * 0.94f;
            }

            /* sun / moon disc, phase and halo */
            float dx = ndx - env->moon[0], dy = ndy - env->moon[1];
            float rad = env->moon[2];
            float dd = sqrtf(dx * dx + dy * dy);
            if (rad > 0 && dd < rad * 3.4f) {
                float core = fmaxf(0.0f, 1.0f - dd / rad);
                float halo = fmaxf(0.0f, 1.0f - dd / (rad * 3.4f));
                float shade = 1.0f;
                if (nightish) {
                    /* crescent: darken the lit-side offset */
                    float cr = (dx * 0.72f + dy * 0.30f) / (rad + 1e-5f);
                    shade = 0.45f + 0.55f * smoothstepf(-0.2f, 0.9f, cr);
                }
                float glow = core * core * 1.5f * shade + halo * halo * halo * 0.30f;
                if (nightish) {
                    sky[0] += glow * 0.92f; sky[1] += glow * 0.95f; sky[2] += glow * 1.05f;
                } else {
                    sky[0] += glow * 1.25f; sky[1] += glow * 1.00f; sky[2] += glow * 0.66f;
                }
            }

            if (zbuf[pi] > 1e29f) {
                lin[pi * 3] = sky[0]; lin[pi * 3 + 1] = sky[1]; lin[pi * 3 + 2] = sky[2];
            }
            if (depth_out) depth_out[pi] = zbuf[pi];
        }
    }

    /* ------------------------------------------------- screen-space AO */
    if (ao_strength > 0.001f) {
        float *ao = (float *)malloc(sizeof(float) * NP);
        const int R = 9;
        const int NS = 8;
        for (int y = 0; y < H; ++y) {
            for (int x = 0; x < W; ++x) {
                size_t pi = (size_t)y * W + x;
                float z0 = zbuf[pi];
                if (z0 > 1e28f || glow[pi] > 0.4f) { ao[pi] = 1.0f; continue; }
                float ndx0 = (x + 0.5f) / W * 2.0f - 1.0f;
                float ndy0 = 1.0f - (y + 0.5f) / H * 2.0f;
                float dir0[3] = {fwd[0] + right[0] * ndx0 * tan_half * aspect + up[0] * ndy0 * tan_half,
                                 fwd[1] + right[1] * ndx0 * tan_half * aspect + up[1] * ndy0 * tan_half,
                                 fwd[2] + right[2] * ndx0 * tan_half * aspect + up[2] * ndy0 * tan_half};
                float p0[3] = {cam->pos[0] + dir0[0] * z0, cam->pos[1] + dir0[1] * z0,
                               cam->pos[2] + dir0[2] * z0};
                const float *n0 = &normal_out[(size_t)y * W * 3 + (size_t)x * 3];
                float occ = 0.0f;
                float scale = z0 * 0.035f + 0.10f;   /* world-space sampling radius */
                for (int s = 0; s < NS; ++s) {
                    float a = (float)s * 2.39996323f;
                    float rr = scale * (0.45f + 0.85f * ((float)((s * 37) % 17) / 17.0f));
                    int px = x + (int)(cosf(a) * rr / (z0 * 0.0022f) * 0.5f);
                    int py = y + (int)(sinf(a) * rr / (z0 * 0.0022f) * 0.5f);
                    if (px < 1 || py < 1 || px >= W - 1 || py >= H - 1) continue;
                    size_t pj = (size_t)py * W + px;
                    float z1 = zbuf[pj];
                    if (z1 > 1e28f) continue;
                    float ndx1 = (px + 0.5f) / W * 2.0f - 1.0f;
                    float ndy1 = 1.0f - (py + 0.5f) / H * 2.0f;
                    float dir1[3] = {fwd[0] + right[0] * ndx1 * tan_half * aspect + up[0] * ndy1 * tan_half,
                                     fwd[1] + right[1] * ndx1 * tan_half * aspect + up[1] * ndy1 * tan_half,
                                     fwd[2] + right[2] * ndx1 * tan_half * aspect + up[2] * ndy1 * tan_half};
                    float p1[3] = {cam->pos[0] + dir1[0] * z1, cam->pos[1] + dir1[1] * z1,
                                   cam->pos[2] + dir1[2] * z1};
                    float v[3]; vsub(p1, p0, v);
                    float dist = sqrtf(vdot(v, v)) + 1e-5f;
                    if (dist > scale * 3.0f) continue;
                    float cosang = vdot(v, n0) / dist;
                    float w = 1.0f - dist / (scale * 3.0f);
                    occ += fmaxf(0.0f, cosang) * w;
                }
                occ /= (float)NS;
                ao[pi] = fmaxf(0.0f, 1.0f - occ * 2.2f);
            }
        }
        for (size_t pi = 0; pi < NP; ++pi) {
            float a = 1.0f - ao_strength * 0.55f * (1.0f - ao[pi]);
            if (glow[pi] > 0.4f) a = 1.0f;
            lin[pi * 3] *= a; lin[pi * 3 + 1] *= a; lin[pi * 3 + 2] *= a;
        }
        free(ao);
    }

    /* ------------------------------------------------------------- bloom */
    if (bloom_amt > 0.001f) {
        int bw = W / 4 > 1 ? W / 4 : 1, bh = H / 4 > 1 ? H / 4 : 1;
        float *bl = (float *)calloc((size_t)bw * bh * 3, sizeof(float));
        for (int y = 0; y < bh; ++y) {
            for (int x = 0; x < bw; ++x) {
                float acc[3] = {0, 0, 0};
                for (int sy2 = 0; sy2 < 4; ++sy2) {
                    for (int sx2 = 0; sx2 < 4; ++sx2) {
                        int px = x * 4 + sx2, py = y * 4 + sy2;
                        if (px >= W || py >= H) continue;
                        size_t pi = (size_t)py * W + px;
                        float l = lin[pi * 3] + lin[pi * 3 + 1] + lin[pi * 3 + 2];
                        float wt = glow[pi];
                        if (l > 1.7f) wt = fmaxf(wt, fminf(1.0f, (l - 1.7f) / l));
                        if (wt > 0.01f) {
                            acc[0] += lin[pi * 3] * wt;
                            acc[1] += lin[pi * 3 + 1] * wt;
                            acc[2] += lin[pi * 3 + 2] * wt;
                        }
                    }
                }
                for (int k = 0; k < 3; ++k) bl[((size_t)y * bw + x) * 3 + k] = acc[k] / 16.0f;
            }
        }
        /* separable blur, two passes */
        float *tmp = (float *)malloc(sizeof(float) * bw * bh * 3);
        for (int pass = 0; pass < 2; ++pass) {
            for (int y = 0; y < bh; ++y) {
                for (int x = 0; x < bw; ++x) {
                    float acc[3] = {0, 0, 0};
                    float wsum = 0.0f;
                    for (int o = -3; o <= 3; ++o) {
                        int xx = x + o * (pass == 0 ? 1 : 0);
                        int yy = y + o * (pass == 1 ? 1 : 0);
                        if (xx < 0 || yy < 0 || xx >= bw || yy >= bh) continue;
                        float w = 1.0f / (1.0f + fabsf((float)o) * 1.1f);
                        for (int k = 0; k < 3; ++k)
                            acc[k] += bl[((size_t)yy * bw + xx) * 3 + k] * w;
                        wsum += w;
                    }
                    for (int k = 0; k < 3; ++k) tmp[((size_t)y * bw + x) * 3 + k] = acc[k] / wsum;
                }
            }
            memcpy(bl, tmp, sizeof(float) * bw * bh * 3);
        }
        free(tmp);
        for (int y = 0; y < H; ++y) {
            for (int x = 0; x < W; ++x) {
                int bx = x / 4, by = y / 4;
                size_t pi = (size_t)y * W + x;
                for (int k = 0; k < 3; ++k)
                    lin[pi * 3 + k] += bl[((size_t)by * bw + bx) * 3 + k] * bloom_amt * 0.85f;
            }
        }
        free(bl);
    }

    /* ------------------------------------------------ tone map + finish */
    for (int y = 0; y < H; ++y) {
        for (int x = 0; x < W; ++x) {
            size_t pi = (size_t)y * W + x;
            float ndx = (x + 0.5f) / W * 2.0f - 1.0f;
            float ndy = 1.0f - (y + 0.5f) / H * 2.0f;

            float vx = ndx * 0.82f, vy = ndy * 0.62f;
            float vig = 1.0f - 0.30f * (vx * vx + vy * vy);
            vig = fmaxf(0.42f, vig);

            uint32_t h = hash32((uint32_t)(x * 1973 + y * 9277 + 17));
            float grain = (((h >> 8) & 0xFF) / 255.0f - 0.5f) * 0.018f;

            float tm[3];
            for (int k = 0; k < 3; ++k) {
                float c = lin[pi * 3 + k] * env->exposure;
                float t = aces(c);
                tm[k] = powf(fmaxf(0.0f, t), 1.0f / 2.2f);
            }
            /* gentle saturation lift, cool shadows, warm highlights */
            float luma = 0.2126f * tm[0] + 0.7152f * tm[1] + 0.0722f * tm[2];
            for (int k = 0; k < 3; ++k) {
                float t = luma + (tm[k] - luma) * 1.16f;
                t += (k == 2 ? 0.016f : (k == 0 ? 0.020f : 0.0f)) * (1.0f - t) * t * 3.0f;
                float v = t * vig + grain;
                int iv = (int)(v * 255.0f + 0.5f);
                if (iv < 0) iv = 0;
                if (iv > 255) iv = 255;
                out[pi * 3 + k] = (uint8_t)iv;
            }
        }
    }
    free(zbuf); free(lin); free(glow);
}
