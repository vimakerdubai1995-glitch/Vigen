"""Generate creative 3D LUTs for Sony S-Log3 / S-Gamut3.Cine footage.

Input:  S-Log3 / S-Gamut3.Cine (Sony A7C II, PP8 or Log Shooting mode)
Output: Rec.709, gamma 2.4 (display)

Run: python3 generate_luts.py
"""

import os

import numpy as np

SIZE = 33
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# S-Gamut3.Cine -> XYZ (D65), Sony spec
SG3C_TO_XYZ = np.array([
    [0.5990839208, 0.2489255161, 0.1024464902],
    [0.2150758201, 0.8850685017, -0.1001443219],
    [-0.0320658495, -0.0276583907, 1.4398513856],
])
# XYZ (D65) -> linear Rec.709
XYZ_TO_709 = np.array([
    [3.2404542, -1.5371385, -0.4985314],
    [-0.9692660, 1.8760108, 0.0415560],
    [0.0556434, -0.2040259, 1.0572252],
])
SG3C_TO_709 = XYZ_TO_709 @ SG3C_TO_XYZ
LUMA = np.array([0.2126, 0.7152, 0.0722])


def slog3_to_linear(v):
    """Sony S-Log3 code value (0..1, full range) -> scene linear reflectance."""
    cv = v * 1023.0
    return np.where(
        cv >= 171.2102946929,
        np.power(10.0, (cv - 420.0) / 261.5) * (0.18 + 0.01) - 0.01,
        (cv - 95.0) * 0.01125 / (171.2102946929 - 95.0),
    )


def gamut_compress(rgb):
    """Pull out-of-gamut (negative) values toward luminance instead of hard clipping."""
    y = np.maximum(rgb @ LUMA, 1e-6)[..., None]
    mn = rgb.min(axis=-1, keepdims=True)
    t = np.where(mn < 0, y / np.maximum(y - mn, 1e-6), 1.0)
    return y + (rgb - y) * t


def tone_curve(x, contrast, grey_out, peak=1.05):
    """Filmic S-curve: scene linear -> display linear. 0.18 maps to grey_out."""
    x = np.maximum(x, 0.0)
    g = 0.18 ** contrast
    k = peak * g / grey_out - g
    xp = np.power(x, contrast)
    return peak * xp / (xp + k)


def make_look(rgb_slog, p):
    lin = np.maximum(slog3_to_linear(rgb_slog), 0.0) * 2.0 ** p["exposure"]
    rgb = gamut_compress(lin @ SG3C_TO_709.T)

    # White balance trim (warm/cool) in linear
    rgb = rgb * np.array(p["wb_gain"])

    # Saturation boost around luminance
    y = (rgb @ LUMA)[..., None]
    rgb = y + (rgb - y) * p["saturation"]
    rgb = gamut_compress(rgb)

    # Subtractive "film density": saturated colours get darker and richer
    mx = np.maximum(rgb.max(axis=-1, keepdims=True), 1e-6)
    sat = np.clip((mx - rgb.min(axis=-1, keepdims=True)) / mx, 0, 1)
    rgb = rgb * (1.0 - p["density"] * sat ** 1.5)

    # Tone mapping: blend of per-channel (natural highlight roll-off)
    # and max-RGB ratio-preserving (keeps hues stable in bright colours)
    per_channel = tone_curve(rgb, p["contrast"], p["grey_out"])
    mx = np.maximum(rgb.max(axis=-1, keepdims=True), 1e-6)
    ratio = tone_curve(mx, p["contrast"], p["grey_out"]) * rgb / mx
    disp = per_channel * 0.6 + ratio * 0.4

    disp = np.clip(disp, 0.0, 1.0)
    out = np.power(disp, 1.0 / 2.4)  # Rec.709 display gamma 2.4

    # Split toning in display space: cool shadows, warm highlights.
    # Weights fade to zero at pure black and pure white so both stay neutral.
    l = np.clip(out @ LUMA, 0, 1)[..., None]
    shadow_w = 6.75 * l * (1.0 - l) ** 2
    high_w = 6.75 * l ** 2 * (1.0 - l)
    out = out + shadow_w * np.array(p["shadow_tint"]) + high_w * np.array(p["highlight_tint"])

    # Black floor so blacks are deep but not crushed to pure zero
    out = p["black"] + out * (1.0 - p["black"])
    return np.clip(out, 0.0, 1.0)


LOOKS = {
    "VIGEN_Dense_SLog3SGamut3Cine_to_709": dict(
        exposure=0.0,
        wb_gain=(1.0, 1.0, 1.0),
        saturation=1.12,
        density=0.22,
        contrast=1.35,
        grey_out=0.115,
        shadow_tint=(-0.012, 0.004, 0.016),
        highlight_tint=(0.014, 0.004, -0.014),
        black=0.012,
    ),
    "VIGEN_Dense_Warm_SLog3SGamut3Cine_to_709": dict(
        exposure=0.0,
        wb_gain=(1.05, 1.0, 0.92),
        saturation=1.10,
        density=0.25,
        contrast=1.4,
        grey_out=0.11,
        shadow_tint=(-0.008, 0.006, 0.012),
        highlight_tint=(0.022, 0.008, -0.022),
        black=0.015,
    ),
}


def write_cube(name, params):
    idx = np.linspace(0.0, 1.0, SIZE)
    # .cube order: red changes fastest, then green, then blue
    b, g, r = np.meshgrid(idx, idx, idx, indexing="ij")
    grid = np.stack([r, g, b], axis=-1).reshape(-1, 3)
    out = make_look(grid, params)
    path = os.path.join(OUT_DIR, name + ".cube")
    with open(path, "w") as f:
        f.write(f'TITLE "{name}"\n')
        f.write("# Input: Sony S-Log3 / S-Gamut3.Cine. Output: Rec.709 gamma 2.4\n")
        f.write(f"LUT_3D_SIZE {SIZE}\n")
        f.write("DOMAIN_MIN 0.0 0.0 0.0\nDOMAIN_MAX 1.0 1.0 1.0\n")
        for row in out:
            f.write(f"{row[0]:.6f} {row[1]:.6f} {row[2]:.6f}\n")
    return path, params


def lin_to_slog3(x):
    """Scene linear -> S-Log3 code value (for test values)."""
    x = np.asarray(x, dtype=float)
    return np.where(
        x >= 0.01125,
        (420.0 + np.log10((x + 0.01) / 0.19) * 261.5) / 1023.0,
        (x * (171.2102946929 - 95.0) / 0.01125 + 95.0) / 1023.0,
    )


if __name__ == "__main__":
    for name, params in LOOKS.items():
        path, p = write_cube(name, params)
        print("wrote", path)
        for label, lin in [("black 0%", 0.0), ("shadow 2%", 0.02), ("grey 18%", 0.18),
                           ("white 90%", 0.9), ("+3 stops", 1.44), ("peak", 8.0)]:
            v = lin_to_slog3(lin)
            o = make_look(np.array([[v, v, v]]), p)[0]
            print(f"  {label:10s} S-Log3 {v * 100:5.1f}% -> Rec709 {o[1] * 100:5.1f}%")
