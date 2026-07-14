import numpy as np
import cv2
from pathlib import Path
from ..state.project_state import PROJECT_CONSTANTS

def boundaries_searching_npy(folder: Path, files_name: list[str], x_min: list, x_max: list):
    """
    Поиск границ на изображениях.
    """
    out_list: list = []
    k = 1

    for name in files_name:

        in_ = []
        full_path = folder / name
        if not full_path.is_file():
            continue

        img = cv2.imread(str(full_path))
        if img is None:
            out_list.append([])
            continue

        for boundary_idx in sorted(PROJECT_CONSTANTS.colourmap.keys()):
            boundary_idx_mass = np.asarray(PROJECT_CONSTANTS.colourmap[boundary_idx])
            mask_exact = np.all(img == boundary_idx_mass, axis=2)
            y, x = np.where(mask_exact)
            in_.append({
                "x": x.tolist(),
                "y": y.tolist()
            })

            if len(x) > 0:
                x_min.append(np.min(x).tolist())
                x_max.append(np.max(x).tolist())

        out_list.append(in_)
        k += 1

    return out_list


def _boundary_to_xy(boundary) -> tuple[np.ndarray, np.ndarray]:
    """
    Нормализует представление границы в (x, y).

    Поддержка:
    - legacy: np.ndarray/list только с y
    - new: dict {'x': [...], 'y': [...]}
    """
    if isinstance(boundary, dict):
        x = np.asarray(boundary.get("x", []))
        y = np.asarray(boundary.get("y", []))
        return x, y

    y = np.asarray(boundary)
    x = np.arange(len(y))
    return x, y


def _aligned_diff(boundary_a, boundary_b) -> np.ndarray:
    """
    Возвращает |y_b - y_a| для совпадающих x-координат.
    """
    x_a, y_a = _boundary_to_xy(boundary_a)
    x_b, y_b = _boundary_to_xy(boundary_b)

    if len(x_a) == 0 or len(x_b) == 0:
        return np.array([])

    common_x = np.intersect1d(x_a, x_b)
    if len(common_x) == 0:
        return np.array([])

    map_a = {int(x): float(y) for x, y in zip(x_a, y_a)}
    map_b = {int(x): float(y) for x, y in zip(x_b, y_b)}

    return np.asarray([abs(map_b[int(x)] - map_a[int(x)]) for x in common_x], dtype=float)


def distances_function(in_list: list):
    """
    Вычисление статистик + СБОР СЫРЫХ ДАННЫХ для Origin Pro.
    """
    # Списки для статистик (как раньше)
    med_pixel_position, min_pixel_position, max_pixel_position = [], [], []
    med_distance, min_distance, max_distance = [], [], []
    med_total_dist, min_total_dist, max_total_dist = [], [], []

    # --- НОВЫЕ Списки для сырых данных (массивов точек) ---
    # Структура: Список [ Изображение 1 [Граница 1 массив, Граница 2 массив...], Изображение 2 ... ]
    raw_pixel_position = []
    raw_distance = []
    raw_total_dist = []  # Тут будет массив разниц для общей толщины

    for i in range(len(in_list)):
        # Временные списки для статистики текущего кадра
        med_pixel_position_in, min_pixel_position_in, max_pixel_position_in = [], [], []
        med_distance_in, min_distance_in, max_distance_in = [], [], []

        # Временные списки для СЫРЫХ данных текущего кадра
        raw_pixel_position_in = []
        raw_distance_in = []
        raw_total_dist_in = []  # Или None, если нет данных

        # Значения для статистики общей толщины
        m_tot, min_tot, max_tot = np.nan, np.nan, np.nan

        # 1. Отбор и сортировка (Верх -> Низ)
        present_boundaries = []
        for b in in_list[i]:
            _, y = _boundary_to_xy(b)
            if len(y) > 0:
                present_boundaries.append(b)
        # Важно: Сортировка по медиане Y, чтобы порядок границ был правильным (сверху вниз)
        present_boundaries.sort(key=lambda b: np.median(_boundary_to_xy(b)[1]))

        # 2. Обработка ПОЗИЦИЙ (Positions)
        for bound in present_boundaries:
            _, arr = _boundary_to_xy(bound)

            # Статистика
            med_pixel_position_in.append(np.median(arr).item())
            min_pixel_position_in.append(np.min(arr).item())
            max_pixel_position_in.append(np.max(arr).item())

            # --- Сохраняем сырой массив ---
            # Используем tolist(), чтобы сохранить как обычный список Python внутри структуры,
            # это безопаснее для JSON/хранения, чем np.array разной длины.
            raw_pixel_position_in.append(arr.tolist())

            # 3. Обработка ДИСТАНЦИЙ (Distances)
        if len(present_boundaries) > 1:
            # А) Последовательные дистанции (1-2, 2-3...)
            for v in range(1, len(present_boundaries)):
                diff = _aligned_diff(present_boundaries[v - 1], present_boundaries[v])

                if len(diff) > 0:
                    # Статистика
                    med_distance_in.append(np.median(diff).item())
                    min_distance_in.append(np.min(diff).item())
                    max_distance_in.append(np.max(diff).item())

                    # --- Сохраняем сырой массив разниц ---
                    raw_distance_in.append(diff.tolist())
                else:
                    med_distance_in.append(np.nan)
                    min_distance_in.append(np.nan)
                    max_distance_in.append(np.nan)
                    raw_distance_in.append([])  # Пустой список, если нет перекрытия

            # Б) ОБЩАЯ толщина (Самая нижняя - Самая верхняя)
            diff_total = _aligned_diff(present_boundaries[0], present_boundaries[-1])
            if len(diff_total) > 0:
                m_tot = np.median(diff_total).item()
                min_tot = np.min(diff_total).item()
                max_tot = np.max(diff_total).item()

                # --- Сохраняем сырой массив общей толщины ---
                raw_total_dist_in = diff_total.tolist()
            else:
                raw_total_dist_in = []

        # Сохранение результатов текущего кадра (статистика)
        med_pixel_position.append(med_pixel_position_in)
        min_pixel_position.append(min_pixel_position_in)
        max_pixel_position.append(max_pixel_position_in)

        med_distance.append(med_distance_in)
        min_distance.append(min_distance_in)
        max_distance.append(max_distance_in)

        med_total_dist.append(m_tot)
        min_total_dist.append(min_tot)
        max_total_dist.append(max_tot)

        # Сохранение СЫРЫХ результатов текущего кадра
        raw_pixel_position.append(raw_pixel_position_in)
        raw_distance.append(raw_distance_in)
        raw_total_dist.append(raw_total_dist_in)

    return (med_pixel_position, min_pixel_position, max_pixel_position,
            med_distance, min_distance, max_distance,
            med_total_dist, min_total_dist, max_total_dist,
            # Возвращаем новые сырые данные
            raw_pixel_position, raw_distance, raw_total_dist)