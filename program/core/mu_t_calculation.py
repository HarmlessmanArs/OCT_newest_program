import numpy as np
import cv2
from pathlib import Path


# ==========================================
# 1. ВСПОМОГАТЕЛЬНЫЕ И СЛУЖЕБНЫЕ ФУНКЦИИ
# ==========================================

def base_name_of_file(x: str) -> str:
    """Возвращает имя файла по его пути."""
    return Path(x).name if x else ''


def _sort_by_filename(entries: list) -> list:
    """Сортирует записи по имени файла."""
    return sorted(entries, key=lambda x: x.get('filename', ''))


def _safe_get_image_from_item(item: dict):
    """
    Пытается достать numpy image из словаря item.
    Вместо os.path использует Path для чистоты импортов.
    """
    for k in ('image', 'img', 'raw', 'data'):
        if k in item and item[k] is not None:
            return item[k]

    path_str = item.get('path') or item.get('filename')
    if path_str:
        path_obj = Path(path_str)
        if path_obj.exists():
            img = cv2.imread(str(path_obj), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                return img.astype(np.float32)
    return None


def get_boundary_info(path: str, boundary_list: list, global_boundary_x1: int):
    """
    Ищет границы для конкретного файла в переданном списке границ.

    Зависимости вместо STATE:
    - boundary_list: список всех границ (ранее STATE.tables.boundaries)
    - global_boundary_x1: координата смещения (ранее STATE.boundaries.global_boundary_x1)
    """
    target = base_name_of_file(path)

    if not boundary_list:
        print('[INFO] Список границ пуст (boundary_list)')
        return None, None, None

    found_idx = -1
    found_entry = None
    for i, item in enumerate(boundary_list):
        if base_name_of_file(item.get('filename')) == target:
            found_entry = item
            found_idx = i
            break

    if found_entry is None:
        print(f'[INFO] Запись для файла {target} не найдена')
        return None, None, None

    raw_p = found_entry.get('raw_p', [])
    if not raw_p:
        print(f'[INFO] Отсутствуют raw_p для файла {target}')
        return None, None, None

    x_offset = max(0, global_boundary_x1)
    length = len(raw_p[0])

    return raw_p, x_offset, length


# ==========================================
# 2. МАТЕМАТИЧЕСКОЕ ЯДРО И РАСЧЕТЫ
# ==========================================

def calculate_sigma_threshold(sum_intensity: np.ndarray, roi_mask: np.ndarray, depth_slice: int = 20) -> float:
    """
    Адаптивный расчет порога сигнала по нижней части ROI. Чистая математика.
    """
    roi_data = sum_intensity[:, roi_mask]

    if roi_data.size == 0:
        return 0.0

    bottom_slice = roi_data[-depth_slice:, :]
    non_zero = bottom_slice[bottom_slice > 0]

    if non_zero.size == 0:
        return 0.0

    mean_val = np.mean(non_zero)
    std_val = np.std(non_zero)

    threshold = max(mean_val + 3 * std_val, 1e-5)
    return float(threshold)


def focus_position(raw_p: list, air_focus_depth: float, img_width: int, x_offset: int,
                   ri_list: list = None) -> np.ndarray:
    """
    Вычисляет физическое положение фокуса по ширине изображения.

    Зависимости вместо STATE:
    - ri_list: список показателей преломления слоев (ранее STATE.param_save.ri_list).
               Если не передан, по умолчанию равен [1.0].
    """
    focus_positions = np.zeros(img_width, dtype=np.float32)

    if not raw_p or not isinstance(raw_p, (list, tuple)) or raw_p[0] is None:
        return focus_positions

    if ri_list is None:
        ri_list = [1.0]

    roi_width = len(raw_p[0])

    for col in range(roi_width):
        global_col = x_offset + col
        if global_col >= img_width:
            break

        # Сбор границ для текущего столбца
        col_borders = []
        for b_arr in raw_p:
            if col < len(b_arr) and b_arr[col] is not None and not np.isnan(b_arr[col]):
                col_borders.append(b_arr[col])
        col_borders.sort()

        # Основной расчет физического фокуса
        remaining_nom = air_focus_depth
        z_phys = 0.0
        last_border_y = 0.0
        layer_index = 0

        for border_y in col_borders:
            dist_nom = border_y - last_border_y
            current_n = ri_list[layer_index] if layer_index < len(ri_list) else 1.0

            if remaining_nom <= dist_nom:
                z_phys += remaining_nom / current_n
                remaining_nom = 0
                break
            else:
                z_phys += dist_nom / current_n
                remaining_nom -= dist_nom
                last_border_y = border_y
                layer_index += 1

        if remaining_nom > 0:
            current_n = ri_list[layer_index] if layer_index < len(ri_list) else 1.0
            z_phys += remaining_nom / current_n

        focus_positions[global_col] = z_phys

    return focus_positions


def estimate_noise_floor(sum_intensity: np.ndarray, depth_slice: int = 15) -> float:
    """
    Оценивает уровень фонового шума по самым нижним пикселям изображения,
    где полезный сигнал ОКТ гарантированно затух или отсутствует.
    """
    bottom_slice = sum_intensity[-depth_slice:, :]
    non_zero = bottom_slice[bottom_slice > 0]
    if non_zero.size == 0:
        return 0.0
    return float(np.median(non_zero))


def sliding_window_lsq(I_linear: np.ndarray, mask_sample: np.ndarray, delta: float,
                       window_size: int = 11) -> np.ndarray:
    """
    Вычисляет mu_t методом локального линейного МНК в вертикальном скользящем окне.
    Сохраняет послойную структуру даже в абсолютно прозрачных средах.

    y = ln(I), x = z_relative
    Наклон k = -2 * mu_t  =>  mu_t = -k / 2
    """
    rows, cols = I_linear.shape
    mu_t_fit = np.zeros_like(I_linear, dtype=np.float32)

    # Подготовка логарифма сигнала
    I_log = np.log(np.clip(I_linear, 1e-12, None))
    z_coords = np.arange(rows, dtype=np.float32) * delta

    half_w = window_size // 2

    # Идем скользящим окном по вертикали
    for y in range(rows):
        y_start = max(0, y - half_w)
        y_end = min(rows, y + half_w + 1)

        # Вырезаем текущий слой по всей ширине
        sub_mask = mask_sample[y_start:y_end, :]
        sub_x = z_coords[y_start:y_end, None]
        sub_y = I_log[y_start:y_end, :]

        # Маскируем элементы вне образца
        x_masked = np.where(sub_mask, sub_x, 0.0)
        y_masked = np.where(sub_mask, sub_y, 0.0)

        # Считаем компоненты МНК для каждого А-скана (столбца) параллельно
        N_points = np.sum(sub_mask, axis=0)

        # Фиттинг имеет смысл, если точек в окне достаточно (хотя бы 3)
        valid_cols = N_points >= 3
        if not np.any(valid_cols):
            continue

        sum_x = np.sum(x_masked, axis=0)
        sum_y = np.sum(y_masked, axis=0)
        sum_xy = np.sum(x_masked * y_masked, axis=0)
        sum_xx = np.sum(x_masked ** 2, axis=0)

        denominator = N_points * sum_xx - sum_x ** 2
        # Защита от деления на 0
        denominator_safe = np.where(denominator == 0, 1e-12, denominator)

        # Расчет наклона и mu_t только для валидных столбцов
        k_slope = (N_points * sum_xy - sum_x * sum_y) / denominator_safe
        mu_t_local = -k_slope / 2.0

        # Записываем результат с отсечкой отрицательных физически невозможных значений
        mu_t_fit[y, valid_cols] = np.clip(mu_t_local[valid_cols], 0.0, None)

    return mu_t_fit


def fast_process_image_universal(
        img: np.ndarray,
        raw_p: list,
        focus_positions: np.ndarray,
        params: dict,
        x_offset: int = 0,
        ri_list: list = None,
        low_boundaries: bool = False
) -> np.ndarray | None:
    """
    Универсальный физически корректный расчет mu_t без привязки к глобальному STATE.
    Адаптирован как для сильнорассеивающих (мутных), так и для прозрачных послойных сред.
    """
    if img is None or raw_p is None:
        return None

    if ri_list is None:
        ri_list = [1.0]

    img = img.astype(np.float32)
    delta = params['delta']
    omega_i = params['omega_i']
    lambda_0 = params['lambda_0']
    window_size_lsq = params.get('window_size_lsq', 11)  # Размер окна для локального МНК

    rows, cols_full = img.shape
    roi_width = len(raw_p[0])
    x_start = max(0, x_offset)
    x_end = min(cols_full, x_start + roi_width)

    # ==========================================
    # 1. Интерполяция и подготовка матриц границ
    # ==========================================
    boundaries = []
    for b in raw_p:
        b_arr = np.full(cols_full, np.nan, dtype=np.float32)
        b_roi = np.asarray(b, dtype=np.float32)
        width = min(len(b_roi), x_end - x_start)
        b_arr[x_start:x_start + width] = b_roi[:width]

        valid = np.isfinite(b_arr)
        if np.any(valid):
            b_arr[~valid] = np.interp(
                np.flatnonzero(~valid),
                np.flatnonzero(valid),
                b_arr[valid]
            )
        else:
            b_arr[:] = 0
        boundaries.append(b_arr)

    # ==========================================
    # 2. Построение карты показателей преломления n(z, x)
    # ==========================================
    n_map = np.ones((rows, cols_full), dtype=np.float32)
    for col in range(cols_full):
        col_boundaries = np.sort([b[col] for b in boundaries])
        last_y = 0
        layer_idx = 0
        for border_y in col_boundaries:
            y0 = int(max(0, round(last_y)))
            y1 = int(min(rows, round(border_y)))
            current_n = ri_list[layer_idx] if layer_idx < len(ri_list) else 1.0
            n_map[y0:y1, col] = current_n
            last_y = border_y
            layer_idx += 1
        y0 = int(max(0, round(last_y)))
        current_n = ri_list[layer_idx] if layer_idx < len(ri_list) else 1.0
        n_map[y0:, col] = current_n

    # ==========================================
    # 3. Расчет геометрии пучка и конфокальной функции (Рэлей)
    # ==========================================
    surface = boundaries[0]
    z_pixels = np.arange(rows)[:, None]
    z_relative = (z_pixels - surface[None, :]) * delta
    z_focus = (focus_positions * delta)[None, :]

    z_i_map = (np.pi * n_map * (omega_i ** 2)) / lambda_0
    h_matrix = 1.0 / ((((z_relative - z_focus) / z_i_map) ** 2) + 1.0)

    # Зачистка воздуха над поверхностью образца
    mask_air = z_relative < 0
    img[mask_air] = 0.0
    h_matrix[mask_air] = 1.0

    mask_below = None
    if low_boundaries and len(boundaries) > 1:
        bottom_surface = boundaries[-1]
        mask_below = z_pixels >= bottom_surface[None, :]
        img[mask_below] = 0.0
        h_matrix[mask_below] = 1.0

    # Коррекция геометрии с защитой от деления на ноль
    I_corrected = img / (h_matrix + 1e-12)

    # ==========================================
    # 4. Очистка от шумовой полки (Noise Floor)
    # ==========================================
    noise_floor = estimate_noise_floor(I_corrected, depth_slice=15)
    I_clean = np.maximum(I_corrected - noise_floor, 0.0)

    # Формируем чистую маску ткани
    mask_sample = ~mask_air
    if mask_below is not None:
        mask_sample = mask_sample & ~mask_below

    # Гасим сигнал за пределами ткани
    I_clean[~mask_sample] = 0.0

    # ==========================================
    # 5. Модифицированный алгоритм Вермеера (Boundary Condition)
    # ==========================================
    # Прямой кумулятивный интеграл снизу вверх
    sum_intensity = np.cumsum(I_clean[::-1, :], axis=0)[::-1, :]
    sum_shifted = np.roll(sum_intensity, -1, axis=0)
    sum_shifted[-1, :] = 0.0

    # Оценка остаточной интенсивности на нижней границе образца для каждого А-скана
    # Спасет от деления на ноль и взрыва "хвостов" в прозрачных средах
    I_end = np.zeros(cols_full, dtype=np.float32)
    for col in range(cols_full):
        valid_idx = np.where(mask_sample[:, col])[0]
        if valid_idx.size > 0:
            I_end[col] = I_clean[valid_idx[-1], col]

    # Интегральное среднее затухание на границе (эвристический регуляризатор Фабера)
    mu_t_end_estimate = 0.05
    residual_energy = I_end / (mu_t_end_estimate + 1e-12)

    # Стабилизированный знаменатель
    denominators_vermeer = 2.0 * delta * sum_shifted + residual_energy[None, :] + 1e-8

    mu_t_vermeer = np.zeros_like(I_clean, dtype=np.float32)
    mask_valid_vermeer = (sum_shifted > 1e-10) & mask_sample
    mu_t_vermeer[mask_valid_vermeer] = I_clean[mask_valid_vermeer] / denominators_vermeer[mask_valid_vermeer]

    # ==========================================
    # 6. Расчет локального скользящего МНК
    # ==========================================
    mu_t_fit = sliding_window_lsq(I_clean, mask_sample, delta, window_size=window_size_lsq)

    # ==========================================
    # 7. Адаптивное гибридное слияние (Smart Weighting)
    # ==========================================
    # Индекс прозрачности оценивается по тому, сколько энергии дошло до нижних слоев
    max_depths = np.max(np.where(mask_sample, z_relative, 0.0), axis=0)
    tail_mask = mask_sample & (z_relative > 0.8 * max_depths[None, :])

    tail_energy = np.sum(I_clean * tail_mask, axis=0)
    total_energy = np.sum(I_clean * mask_sample, axis=0)
    total_energy = np.clip(total_energy, 1e-12, None)

    transparency_index = tail_energy / total_energy

    # Мягкое скольжение весов:
    # В мутных средах (индекс < 0.02) весит чистый Вермеер.
    # В прозрачных послойных (индекс > 0.10) доминирует локальный МНК.
    t_min, t_max = 0.02, 0.10
    fit_weight = (transparency_index - t_min) / (t_max - t_min)
    fit_weight = np.clip(fit_weight, 0.0, 1.0)

    # Результирующее слияние двух подходов
    mu_t = mu_t_vermeer * (1.0 - fit_weight[None, :]) + mu_t_fit * fit_weight[None, :]

    # ==========================================
    # 8. Финальное маскирование и очистка ROI
    # ==========================================
    roi_mask = np.zeros(cols_full, dtype=bool)
    roi_mask[x_start:x_end] = True

    # Адаптивный порог валидности по СКО сигнала
    sigma_threshold = max(np.mean(I_clean[mask_sample]) + 2 * np.std(I_clean[mask_sample]), 1e-4) if np.any(
        mask_sample) else 1e-4
    mu_t[I_clean < sigma_threshold] = 0.0

    if mask_below is not None:
        mu_t[mask_below] = 0.0

    mu_t[:, ~roi_mask] = 0.0

    return mu_t

# ==========================================
# 3. СТАТИСТИКА И ПОСТ-ОБРАБОТКА
# ==========================================

def compute_roi_stats(
        idx: str,
        mu_t_matrix: np.ndarray,
        raw_boundaries: list,
        global_x1: int = None,
        global_x2: int = None
) -> dict:
    """
    Вычисляет статистику по зонам интереса (ROI).

    Зависимости вместо STATE:
    - global_x1: левая граница кропа (ранее STATE.boundaries.global_boundary_x1).
    - global_x2: правая граница кропа (ранее STATE.boundaries.global_boundary_x2).
    """
    if mu_t_matrix is None:
        return None

    rows, cols = mu_t_matrix.shape

    # Инициализация дефолтных границ, если они не переданы
    x1 = global_x1 if global_x1 is not None else 0
    x2 = global_x2 if global_x2 is not None else cols

    x1 = int(max(0, min(cols - 1, int(x1))))
    x2 = int(max(0, min(cols - 1, int(x2))))
    if x2 <= x1:
        x2 = cols - 1

    def get_stats_in_rect(y_top, y_bottom, x_start, x_end):
        y_top = max(0, min(rows - 1, y_top))
        y_bottom = max(0, min(rows - 1, y_bottom))
        if y_bottom <= y_top:
            y_bottom = min(y_top + 1, rows - 1)

        crop = mu_t_matrix[y_top:y_bottom + 1, x_start:x_end + 1]
        vals = crop[(np.isfinite(crop)) & (crop > 0)]
        med = float(np.nanmedian(vals)) if vals.size > 0 else 0.0
        st = float(np.nanstd(vals)) if vals.size > 0 else 0.0
        return med, st, vals

    roi_stats = []
    raw_mu_s_arrays = []

    present_rb = [rb for rb in raw_boundaries if rb and len(rb) > 0]
    num_boundaries = len(present_rb)

    total_median, total_std, total_vals = 0.0, 0.0, np.array([])

    if num_boundaries == 0:
        return {'filename': idx, 'roi_stats': [], 'total': {'median': 0.0, 'std': 0.0}, 'raw_mu_s_data': []}

    if num_boundaries == 1:
        rb_top = present_rb[0]
        y_top = int(np.nanmax(rb_top) + 1)
        y_bottom = rows - 1

        median, std, vals = get_stats_in_rect(y_top, y_bottom, x1, x2)
        roi_stats.append({'median': median, 'std': std})
        raw_mu_s_arrays.append(vals)
        total_median, total_std = median, std
        total_vals = vals
    else:
        all_vals_for_total = []

        for i in range(num_boundaries - 1):
            rb_top = present_rb[i]
            rb_bottom = present_rb[i + 1]
            y_top = int(np.nanmax(rb_top) + 1)
            y_bottom = int(np.nanmin(rb_bottom) - 1)

            median, std, vals = get_stats_in_rect(y_top, y_bottom, x1, x2)
            roi_stats.append({'median': median, 'std': std})
            raw_mu_s_arrays.append(vals)
            all_vals_for_total.append(vals)

        if all_vals_for_total:
            total_vals = np.concatenate(all_vals_for_total)
            if total_vals.size > 0:
                total_median = float(np.nanmedian(total_vals))
                total_std = float(np.nanstd(total_vals))

    raw_mu_s_arrays.append(total_vals)

    return {
        'filename': idx,
        'roi_stats': roi_stats,
        'total': {'median': total_median, 'std': total_std},
        'raw_mu_s_data': raw_mu_s_arrays
    }