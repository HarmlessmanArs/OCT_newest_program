import numpy as np
import cv2
from pathlib import Path
from ..state.project_state import PROJECT_CONSTANTS

def boundaries_searching_npy(folder: Path, files_name: list[str], dataset_x_min: list, dataset_x_max: list):
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
            in_.append(y)

            if len(x) > 0:
                dataset_x_min.append(np.min(x).tolist())
                dataset_x_max.append(np.max(x).tolist())

        out_list.append(in_)
        k += 1

    return out_list, dataset_x_min, dataset_x_max


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
        present_boundaries = [b for b in in_list[i] if len(b) > 0]
        # Важно: Сортировка по медиане Y, чтобы порядок границ был правильным (сверху вниз)
        present_boundaries.sort(key=lambda b: np.median(b))

        # 2. Обработка ПОЗИЦИЙ (Positions)
        for bound in present_boundaries:
            arr = np.asarray(bound)

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
                arr_curr = np.asarray(present_boundaries[v])
                arr_prev = np.asarray(present_boundaries[v - 1])

                # Обрезаем по минимальной длине, чтобы вычесть массивы
                slice_ = min(len(arr_curr), len(arr_prev))

                if slice_ > 0:
                    diff = np.abs(arr_curr[:slice_] - arr_prev[:slice_])

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
            arr_first = np.asarray(present_boundaries[0])
            arr_last = np.asarray(present_boundaries[-1])

            slice_total = min(len(arr_first), len(arr_last))
            if slice_total > 0:
                diff_total = np.abs(arr_last[:slice_total] - arr_first[:slice_total])
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