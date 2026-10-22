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
    const float *uv;     /* V x 2 surface coords (m)   */
    const float *m;      /* V material id              */
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
    float dof_focus;        /* focus distance (world units)      */
    float dof_amt;          /* 0 = off                           */
    float mist[3];          /* ground-hugging mist colour         */
    float mist_amount;      /* 0..1                               */
    float mist_height;      /* metres; e-folding height           */
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
            /* photo cards do not cast shadow-map shadows (their silhouette is
               a flat plane); they get a contact-shadow mesh instead */
            if (mesh->m && mesh->m[idx[0]] >= 20.0f) continue;
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

/* ------------------------------------------------------- material shading
 * Procedural, per-pixel surface detail. Everything is evaluated from the
 * interpolated surface coords (in metres) and the shading normal, so the
 * detail is baked into the surface rather than crawling with the camera.
 */
static inline float n3hash(int x, int y, int z) {
    uint32_t h = hash32((uint32_t)(x * 374761393 + y * 668265263 + z * 2147483647));
    return (h & 0xFFFFFF) / 16777215.0f;
}

static float noise3(float x, float y, float z) {
    int xi = (int)floorf(x), yi = (int)floorf(y), zi = (int)floorf(z);
    float xf = x - xi, yf = y - yi, zf = z - zi;
    float u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf), w = zf * zf * (3 - 2 * zf);
    float c000 = n3hash(xi, yi, zi), c100 = n3hash(xi + 1, yi, zi);
    float c010 = n3hash(xi, yi + 1, zi), c110 = n3hash(xi + 1, yi + 1, zi);
    float c001 = n3hash(xi, yi, zi + 1), c101 = n3hash(xi + 1, yi, zi + 1);
    float c011 = n3hash(xi, yi + 1, zi + 1), c111 = n3hash(xi + 1, yi + 1, zi + 1);
    float x00 = c000 + (c100 - c000) * u, x10 = c010 + (c110 - c010) * u;
    float x01 = c001 + (c101 - c001) * u, x11 = c011 + (c111 - c011) * u;
    float y0 = x00 + (x10 - x00) * v, y1 = x01 + (x11 - x01) * v;
    return y0 + (y1 - y0) * w;
}

static float fbm3(float x, float y, float z, int oct) {
    float sum = 0.0f, amp = 0.55f, f = 1.0f;
    for (int i = 0; i < oct; ++i) {
        sum += amp * noise3(x * f, y * f, z * f);
        f *= 2.13f;
        amp *= 0.5f;
    }
    return sum;
}

/* pore field: blobby pits around 0.4-1.2 mm across */
static float pore_field(float u, float v, float seed) {
    float base = fbm3(u * 260.0f + seed, v * 260.0f, seed * 3.1f, 3);
    float fine = noise3(u * 900.0f + seed, v * 900.0f, seed);
    return base * 0.70f + fine * 0.30f;
}

/* tangent frame from an arbitrary normal */
static inline void tangent_frame(const float *n, float *t1, float *t2) {
    float helper[3] = {0.0f, 1.0f, 0.0f};
    if (fabsf(n[1]) > 0.9f) { helper[0] = 1.0f; helper[1] = 0.0f; }
    vcross(n, helper, t1); vnorm(t1);
    vcross(n, t1, t2); vnorm(t2);
}

typedef struct {
    float p[3], n[3], c[3], e[3];
    float uv[2];
    float mat;
    float cx, cy, cz;
} Vtx;


/* ------------------------------------------------------------ photo sprites */
/* Material ids >= 20 are billed as RGBA photo cards: the texture is sampled
   with bilinear filtering, alpha-tested and alpha-blended, and shaded by the
   same sun / fire / fog / mist model as the rest of the scene. This is how the
   AI-generated photoreal humans are placed inside the 3D world. */
static const uint8_t *g_tex = NULL;
static int g_tex_w = 0, g_tex_h = 0;

void set_texture(const uint8_t *rgba, int w, int h) {
    g_tex = rgba;
    g_tex_w = w;
    g_tex_h = h;
}

static inline int tex_ready(void) { return g_tex != NULL && g_tex_w > 0 && g_tex_h > 0; }

static inline void sample_tex(float u, float v, float *out) {
    if (!tex_ready()) { out[0] = out[1] = out[2] = 1.0f; out[3] = 1.0f; return; }
    if (u < 0.0f) u = 0.0f;
    if (u > 0.999999f) u = 0.999999f;
    if (v < 0.0f) v = 0.0f;
    if (v > 0.999999f) v = 0.999999f;
    float fx = u * (float)g_tex_w - 0.5f, fy = v * (float)g_tex_h - 0.5f;
    int x0 = (int)floorf(fx), y0 = (int)floorf(fy);
    float tx = fx - (float)x0, ty = fy - (float)y0;
    int x1 = x0 + 1, y1 = y0 + 1;
    if (x0 < 0) x0 = 0;
    if (y0 < 0) y0 = 0;
    if (x1 > g_tex_w - 1) x1 = g_tex_w - 1;
    if (y1 > g_tex_h - 1) y1 = g_tex_h - 1;
    if (x0 > g_tex_w - 1) x0 = g_tex_w - 1;
    if (y0 > g_tex_h - 1) y0 = g_tex_h - 1;
    const uint8_t *p00 = g_tex + ((size_t)y0 * g_tex_w + x0) * 4;
    const uint8_t *p10 = g_tex + ((size_t)y0 * g_tex_w + x1) * 4;
    const uint8_t *p01 = g_tex + ((size_t)y1 * g_tex_w + x0) * 4;
    const uint8_t *p11 = g_tex + ((size_t)y1 * g_tex_w + x1) * 4;
    for (int k = 0; k < 4; ++k) {
        float a = (float)p00[k] * (1 - tx) + (float)p10[k] * tx;
        float b = (float)p01[k] * (1 - tx) + (float)p11[k] * tx;
        out[k] = (a * (1 - ty) + b * ty) / 255.0f;
    }
    /* sRGB -> linear for the colour channels; alpha stays linear */
    for (int k = 0; k < 3; ++k) {
        float c = out[k];
        out[k] = c <= 0.04045f ? c / 12.92f : powf((c + 0.055f) / 1.055f, 2.4f);
    }
}

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
            float b0 = w0 * invz[0] * z, b1 = w1 * invz[1] * z, b2 = w2 * invz[2] * z;
            int tmat = (int)(A->mat + 0.35f);
            float tcol[4] = {1.0f, 1.0f, 1.0f, 1.0f};
            if (tmat >= 20) {
                float tu = A->uv[0] * b0 + B->uv[0] * b1 + C->uv[0] * b2;
                float tv = A->uv[1] * b0 + B->uv[1] * b1 + C->uv[1] * b2;
                sample_tex(tu, tv, tcol);
                if (tcol[3] < 0.004f) continue;
            }
            if (z >= zbuf[pi]) continue;
            if (tmat < 20 || tcol[3] > 0.55f) zbuf[pi] = z;
            if (tmat >= 20) {
                /* ---- photo card: texture albedo under the scene light ---- */
                float wp[3], na[3];
                for (int k = 0; k < 3; ++k) {
                    wp[k] = A->p[k] * b0 + B->p[k] * b1 + C->p[k] * b2;
                    na[k] = A->n[k] * b0 + B->n[k] * b1 + C->n[k] * b2;
                }
                vnorm(na);
                /* ---- rounded-body shading ----------------------------------
                   A photo card is a flat quad, but the person on it is roughly
                   a vertical cylinder. The vertex colour carries the card-local
                   u (0..1) in its blue channel, so the shading normal can be
                   swung around the body axis: light then falls off towards the
                   silhouettes instead of lighting the cut-out flat. */
                {
                    float lu = A->c[2] * b0 + B->c[2] * b1 + C->c[2] * b2;
                    if (lu < 0.0f) lu = 0.0f;
                    if (lu > 1.0f) lu = 1.0f;
                    if (lu >= 0.0f && lu <= 1.0f) {
                        float upv[3] = {0.0f, 1.0f, 0.0f};
                        float sidev[3];
                        vcross(upv, na, sidev);
                        float sl = sqrtf(sidev[0] * sidev[0] + sidev[1] * sidev[1]
                                        + sidev[2] * sidev[2]);
                        if (sl > 1e-4f) {
                            float ang = (lu - 0.5f) * 2.7f;
                            float sa = sinf(ang), ca = cosf(ang);
                            float nn2[3];
                            for (int q = 0; q < 3; ++q)
                                nn2[q] = sidev[q] / sl * sa + na[q] * ca + 0.10f * (0.5f - lu) * 0.0f;
                            vnorm(nn2);
                            for (int q = 0; q < 3; ++q) na[q] = nn2[q];
                        }
                    }
                }
                float ndl = vdot(na, env->dir);
                float sh = 1.0f;
                float bias = 0.0014f + 0.0130f * (1.0f - fmaxf(0.0f, ndl));
                sh = shadow_factor(wp, bias);
                sh = 1.0f - env->shadow_strength * (1.0f - sh)
                     * smoothstepf(0.02f, 0.28f, ndl);
                float band = 0.30f + 0.70f * smoothstepf(0.0f, 0.72f, fmaxf(0.0f, ndl));
                float hemi = 0.5f + 0.5f * na[1];
                float p1 = point_term(wp, na, env->light, env->light_range);
                float p2 = point_term(wp, na, env->light2, env->light2_range);
                float alpha = tcol[3] < 0.0f ? 0.0f : (tcol[3] > 1.0f ? 1.0f : tcol[3]);
                for (int k = 0; k < 3; ++k) {
                    float lit = tcol[k] * (env->ambient[k] * 1.35f * hemi
                                           + env->ground[k] * (1.0f - hemi) * 0.55f
                                           + env->colour[k] * band * 0.82f * sh)
                                + tcol[k] * env->light_colour[k] * p1 * 2.6f
                                + tcol[k] * env->light2_colour[k] * p2 * 2.1f;
                    float fog = 1.0f - expf(-env->fog_density * z * z);
                    lit = lit * (1.0f - fog) + env->fog[k] * fog;
                    if (env->mist_amount > 0.001f && wp[1] < 3.0f) {
                        float h = wp[1] < 0.0f ? 0.0f : wp[1];
                        float fall = expf(-h / fmaxf(0.05f, env->mist_height));
                        float reach = 1.0f - expf(-z * 0.28f);
                        float m = env->mist_amount * fall * (0.30f + 0.70f * reach);
                        lit = lit * (1.0f - m) + env->mist[k] * m;
                    }
                    if (lit < 0.0f) lit = 0.0f;
                    if (alpha >= 0.999f) {
                        lin[pi * 3 + k] = lit;
                    } else {
                        lin[pi * 3 + k] = lin[pi * 3 + k] * (1.0f - alpha) + lit * alpha;
                    }
                }
                continue;
            }

            float wp[3], na[3], col[3], emi[3];
            for (int k = 0; k < 3; ++k) {
                wp[k] = A->p[k] * b0 + B->p[k] * b1 + C->p[k] * b2;
                na[k] = A->n[k] * b0 + B->n[k] * b1 + C->n[k] * b2;
                col[k] = A->c[k] * b0 + B->c[k] * b1 + C->c[k] * b2;
                emi[k] = A->e[k] * b0 + B->e[k] * b1 + C->e[k] * b2;
            }
            vnorm(na);
            float uv0 = A->uv[0] * b0 + B->uv[0] * b1 + C->uv[0] * b2;
            float uv1 = A->uv[1] * b0 + B->uv[1] * b1 + C->uv[1] * b2;
            int mat = (int)(A->mat + 0.35f);
            float spec = 0.0f;          /* additive specular, filled below */
            float fuzz = 0.0f;          /* forward-scatter rim            */
            float relief[3] = {na[0], na[1], na[2]};

            float emissive = fabsf(emi[0]) + fabsf(emi[1]) + fabsf(emi[2]);
            float ndl = vdot(na, env->dir);
            float sh = 1.0f;
            if (emissive < 1e-4f) {
                /* grazing angles need a bigger bias, otherwise the map acne
                   speckles exactly where the terminator sweeps the surface */
                float bias = 0.0014f + 0.0130f * (1.0f - fmaxf(0.0f, ndl));
                sh = shadow_factor(wp, bias);
                float soft = smoothstepf(0.02f, 0.28f, ndl);
                sh = 1.0f - env->shadow_strength * (1.0f - sh) * soft;
            }
            float diff = fmaxf(0.0f, ndl);
            /* banding is computed from the smooth normal; micro-relief from the
               pore/noise shader must never be allowed to strobe the toon steps */
            /* continuous, slightly wrapped diffuse: no visible toon steps */
            float band = 0.28f + 0.72f * smoothstepf(0.0f, 0.78f, diff);
            band = band * 0.55f + powf(fmaxf(0.0f, ndl), 0.85f) * 0.45f;
            float ndl_r = vdot(relief, env->dir);
            float drel = (ndl_r - ndl) * 1.7f;
            if (drel > 0.20f) drel = 0.20f;
            if (drel < -0.28f) drel = -0.28f;
            band *= 1.0f + drel;
            float hemi = 0.5f + 0.5f * na[1];
            float viewv[3];
            vsub(campos, wp, viewv); vnorm(viewv);
            float fres = 1.0f - fmaxf(0.0f, vdot(na, viewv));
            float rim = powf(fres, 3.0f);

            /* ---------------- procedural surface detail ---------------- */
            /* detail LOD: micro texture fades with distance so it cannot alias */
            float lod = 1.75f / (z + 1.2f);
            if (lod > 1.0f) lod = 1.0f;
            float ao_local = 1.0f;
            if (emissive < 1e-4f && mat > 0) {
                float t1[3], t2[3];
                tangent_frame(na, t1, t2);
                if (mat == 1) {
                    /* ---- skin: pores, mottling, oil, subsurface ---- */
                    float pf = pore_field(uv0, uv1, 3.7f);
                    float pore = (pf - 0.5f) * 2.0f;   /* continuous, centred */
                    float pf2 = pore_field(uv0 + 0.0011f, uv1, 3.7f);
                    float pf3 = pore_field(uv0, uv1 + 0.0011f, 3.7f);
                    float gx = (pf2 - pf) * 210.0f;
                    float gy = (pf3 - pf) * 210.0f;
                    float bump = 0.10f;
                    float nn[3];
                    for (int k = 0; k < 3; ++k)
                        nn[k] = na[k] - t1[k] * gx * bump - t2[k] * gy * bump;
                    vnorm(nn);
                    /* keep the toon normal for banding, use the relief only for
                       the specular highlight */
                    for (int k = 0; k < 3; ++k) relief[k] = nn[k];
                    /* blotchy melanin + capillary redness */
                    float mott = fbm3(uv0 * 70.0f, uv1 * 70.0f, 1.3f, 3);
                    float red = fbm3(uv0 * 16.0f + 5.0f, uv1 * 16.0f, 9.1f, 2);
                    float tone = 1.0f + 0.085f * (mott - 0.4f) * lod;
                    float pm = 1.0f + 0.135f * pore * lod;   /* pore relief shading */
                    float dots = smoothstepf(0.66f, 0.80f, noise3(uv0 * 1250.0f, uv1 * 1250.0f, 17.0f));
                    float dots2 = smoothstepf(0.68f, 0.84f, noise3(uv0 * 2100.0f + 3.0f, uv1 * 2100.0f, 29.0f));
                    pm *= 1.0f - (0.10f * dots + 0.06f * dots2) * lod;
                    col[0] *= tone * pm * (0.975f + 0.055f * red * lod);
                    col[1] *= tone * pm * (0.992f + 0.018f * red * lod);
                    col[2] *= tone * pm * (1.000f - 0.030f * red * lod);
                    ao_local = 1.0f - 0.10f * pore * lod;
                    ao_local *= 0.985f + 0.03f * (fbm3(uv0 * 90.0f, uv1 * 90.0f, 2.0f, 2) - 0.5f) * lod;
                    (void)pore;
                    diff = (diff + 0.34f) / 1.34f;         /* wrap lighting */
                    if (diff > 0.98f) diff = 0.98f;
                    float ndv = fmaxf(0.0f, vdot(na, viewv));
                    spec = 0.30f * powf(1.0f - ndv, 4.0f);
                    fuzz = 0.10f;
                } else if (mat == 2) {
                    /* ---- hide tunic: woven threads + felt fuzz ---- */
                    float wx = sinf(uv0 * 2400.0f) * 0.5f + 0.5f;
                    float wy = sinf(uv1 * 2400.0f) * 0.5f + 0.5f;
                    float weave = wx * 0.5f + wy * 0.5f;
                    float grain = fbm3(uv0 * 900.0f, uv1 * 900.0f, 4.4f, 2);
                    float k = 0.955f + 0.035f * weave * lod + 0.045f * grain * lod;
                    float patchy = fbm3(uv0 * 18.0f, uv1 * 18.0f, 7.7f, 3);
                    float stain = smoothstepf(0.55f, 0.85f, fbm3(uv0 * 6.0f, uv1 * 6.0f, 2.2f, 3));
                    for (int q = 0; q < 3; ++q) col[q] *= k * (0.86f + 0.22f * patchy);
                    col[0] *= 1.0f - 0.10f * stain;
                    col[1] *= 1.0f - 0.13f * stain;
                    col[2] *= 1.0f - 0.16f * stain;
                    ao_local = 0.93f + 0.10f * weave;
                    fuzz = 0.16f;
                } else if (mat == 3) {
                    /* ---- hair: strands running along the scalp ---- */
                    float strand = noise3(uv0 * 900.0f, uv1 * 120.0f, 2.2f);
                    float strand2 = noise3(uv0 * 2200.0f, uv1 * 260.0f, 5.5f);
                    float k = 0.72f + 0.55f * strand * strand2 * 2.0f;
                    for (int q = 0; q < 3; ++q) col[q] *= k;
                    spec = 0.22f * powf(1.0f - fmaxf(0.0f, vdot(na, viewv)), 2.0f);
                    fuzz = 0.22f;
                } else if (mat == 4) {
                    /* ---- stone: grain, lichen, pits ---- */
                    float g = fbm3(uv0 * 40.0f, uv1 * 40.0f, 1.7f, 3);
                    float fine = noise3(uv0 * 340.0f, uv1 * 340.0f, 8.8f);
                    float lichen = smoothstepf(0.62f, 0.80f, fbm3(uv0 * 9.0f, uv1 * 9.0f, 3.3f, 3));
                    float k = 0.90f + 0.18f * g + 0.07f * fine * lod;
                    for (int q = 0; q < 3; ++q) col[q] *= k;
                    col[1] += 0.055f * lichen;
                    col[0] *= 1.0f - 0.22f * lichen;
                    ao_local = 0.90f + 0.14f * fine;
                } else if (mat == 5) {
                    /* ---- foliage: leaf clumps, translucent edge ---- */
                    float leaf = noise3(uv0 * 260.0f, uv1 * 260.0f, 2.9f);
                    float clump = fbm3(uv0 * 26.0f, uv1 * 26.0f, 6.1f, 3);
                    float k = 0.84f + 0.26f * leaf * lod + 0.16f * clump;
                    for (int q = 0; q < 3; ++q) col[q] *= k;
                    fuzz = 0.30f;
                    ao_local = 0.88f + 0.16f * clump;
                } else if (mat == 6) {
                    /* ---- eyes: wet cornea ---- */
                    spec = 0.85f * powf(1.0f - fmaxf(0.0f, vdot(na, viewv)), 1.6f);
                } else if (mat == 7) {
                    /* ---- wood: bark ridges ---- */
                    float bark = noise3(uv0 * 120.0f, uv1 * 900.0f, 4.1f);
                    float k = 0.80f + 0.40f * bark;
                    for (int q = 0; q < 3; ++q) col[q] *= k;
                    ao_local = 0.86f + 0.20f * bark;
                } else if (mat == 8) {
                    /* ---- ground: soil grain, pebbles, dry grass ---- */
                    float g = fbm3(uv0 * 7.0f, uv1 * 7.0f, 2.6f, 4);
                    float peb = smoothstepf(0.68f, 0.86f, noise3(uv0 * 34.0f, uv1 * 34.0f, 1.1f));
                    float fine = noise3(uv0 * 220.0f, uv1 * 220.0f, 3.9f);
                    float k = 0.90f + 0.15f * g + 0.07f * fine * lod;
                    for (int q = 0; q < 3; ++q) col[q] *= k;
                    col[0] += 0.05f * peb;
                    col[1] += 0.04f * peb;
                    col[2] += 0.03f * peb;
                    ao_local = 0.90f + 0.12f * fine;
                }
            }

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
            float half_v[3] = {env->dir[0] + viewv[0], env->dir[1] + viewv[1],
                               env->dir[2] + viewv[2]};
            vnorm(half_v);
            float ndh = fmaxf(0.0f, vdot(relief, half_v));
            float spec_term = spec * powf(ndh, 46.0f);
            float spec2 = spec * powf(ndh, 420.0f) * 2.2f;
            for (int k = 0; k < 3; ++k) {
                float lit = col[k] * ao_local * (env->colour[k] * band * 0.88f * sh +
                                      env->ambient[k] * hemi * 0.52f +
                                      env->ground[k] * (1.0f - hemi) * 0.36f +
                                      env->colour[k] * rim * 0.20f * sh);
                lit += col[k] * env->light_colour[k] * p1 * 2.4f;
                lit += col[k] * env->light2_colour[k] * p2 * 2.0f;
                lit += (spec_term + spec2) * (env->colour[k] * sh + env->light_colour[k] * p1);
                lit += col[k] * fuzz * rim * (env->colour[k] * 0.35f * sh +
                                              env->light_colour[k] * p1 * 0.9f);
                lit += emi[k] * 1.75f;
                float fog = 1.0f - expf(-env->fog_density * z * z);
                lit = lit * (1.0f - fog) + env->fog[k] * fog;
                if (env->mist_amount > 0.001f && wp[1] < 3.0f) {
                    /* mist pools in the low ground: dense at the feet, gone by
                       chest height, and it thickens with distance */
                    float h = wp[1] < 0.0f ? 0.0f : wp[1];
                    float fall = expf(-h / fmaxf(0.05f, env->mist_height));
                    float reach = 1.0f - expf(-z * 0.28f);
                    float m = env->mist_amount * fall * (0.30f + 0.70f * reach);
                    lit = lit * (1.0f - m) + env->mist[k] * m;
                }
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
                tri[k].uv[0] = mesh->uv ? mesh->uv[vi * 2 + 0] : 0.0f;
                tri[k].uv[1] = mesh->uv ? mesh->uv[vi * 2 + 1] : 0.0f;
                tri[k].mat = mesh->m ? mesh->m[vi] : 0.0f;
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
                    for (int q = 0; q < 2; ++q)
                        o.uv[q] = a->uv[q] + (b->uv[q] - a->uv[q]) * t;
                    o.mat = a->mat;
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
                /* filmic S-curve: deeper shadows, cleaner highlights */
                t = (t - 0.5f) * 1.10f + 0.5f;
                if (t < 0.0f) t = 0.0f;
                if (t > 1.0f) t = 1.0f;
                t = t * t * (3.0f - 2.0f * t) * 0.45f + t * 0.55f;
                t += 0.012f * (1.0f - t) * (k == 2 ? 1.2f : 1.0f);
                float v = t * vig + grain;
                int iv = (int)(v * 255.0f + 0.5f);
                if (iv < 0) iv = 0;
                if (iv > 255) iv = 255;
                out[pi * 3 + k] = (uint8_t)iv;
            }
        }
    }
    /* ------------------------------------------------- depth of field */
    if (env->dof_amt > 0.001f) {
        uint8_t *copy = (uint8_t *)malloc(NP * 3);
        memcpy(copy, out, NP * 3);
        const float focus = env->dof_focus > 0.01f ? env->dof_focus : 4.0f;
        for (int y = 0; y < H; ++y) {
            for (int x = 0; x < W; ++x) {
                size_t pi = (size_t)y * W + x;
                float z = zbuf[pi];
                if (z > 1e28f) z = 60.0f;
                float coc = env->dof_amt * fabsf(z - focus) / fmaxf(z, 0.5f);
                if (coc > 1.0f) coc = 1.0f;
                if (coc < 0.06f) continue;
                float radius = coc * 9.0f;
                int ri = (int)radius;
                float acc[3] = {0, 0, 0};
                float wsum = 0.0f;
                for (int s = 0; s < 7; ++s) {
                    float ang = (float)s * 2.39996323f;
                    float rr = radius * (0.35f + 0.65f * ((float)((s * 29) % 11) / 11.0f));
                    int sx2 = x + (int)(cosf(ang) * rr);
                    int sy2 = y + (int)(sinf(ang) * rr);
                    if (sx2 < 0 || sy2 < 0 || sx2 >= W || sy2 >= H) continue;
                    size_t pj = (size_t)sy2 * W + sx2;
                    for (int k = 0; k < 3; ++k) acc[k] += copy[pj * 3 + k];
                    wsum += 1.0f;
                }
                if (wsum < 1.0f) continue;
                float mixAmt = fminf(1.0f, coc * 1.4f);
                for (int k = 0; k < 3; ++k) {
                    float blurred = acc[k] / wsum;
                    out[pi * 3 + k] = (uint8_t)(copy[pi * 3 + k] * (1.0f - mixAmt) +
                                                blurred * mixAmt + 0.5f);
                }
                (void)ri;
            }
        }
        free(copy);
    }

    free(zbuf); free(lin); free(glow);
}
