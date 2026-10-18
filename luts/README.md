# VIGEN LUTs: Sony S-Log3 → Rec.709

| Файл | Look |
|---|---|
| `VIGEN_Dense_SLog3SGamut3Cine_to_709.cube` | Плотная нейтральная картинка: глубокие чёрные, плотные цвета, мягкий скат светов |
| `VIGEN_Dense_Warm_SLog3SGamut3Cine_to_709.cube` | То же, теплее: golden hour, пустыня, интерьеры |

- **Вход:** S-Log3 / **S-Gamut3.Cine** (PP8 на A7C II). Для S-Gamut3 (PP9) не подходит.
- **Выход:** Rec.709, gamma 2.4.
- 33×33×33, `.cube` — DaVinci Resolve, Premiere, Final Cut, а также User LUT в камере.

Перед LUT сначала выставь экспозицию и баланс белого. LUT рассчитан на нормальную экспозицию: серый 18% = 41% S-Log3.

Пересобрать / подправить: `python3 luts/generate_luts.py` (параметры look в словаре `LOOKS`).
