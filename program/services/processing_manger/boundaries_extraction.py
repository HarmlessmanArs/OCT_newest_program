import numpy as np
import pandas as pd
import cv2
from scipy.signal import savgol_filter
from scipy.ndimage import median_filter
from ..state.project_state import PROJECT_CONSTANTS


# ============================================================
# ---------------------- ALGORITHM ---------------------------
# ============================================================

def viterbi_trace_l1_fast(score: np.ndarray, zmin: int, zmax: int, smoothness: float = 3.0) -> np.ndarray:
    """Алгоритм Витерби для поиска оптимального пути (границы) с L1-регуляризацией."""
    H, W = score.shape
    zmin = max(0, int(zmin))
    zmax = min(H - 1, int(zmax))

    S = score[zmin:zmax + 1, :]
    h = S.shape[0]

    dp_prev = S[:, 0].astype(np.float32).copy()
    ptr = np.zeros((h, W), dtype=np.int32)
    lam = float(smoothness)

    left_val = np.empty(h, dtype=np.float32)
    right_val = np.empty(h, dtype=np.float32)
    left_arg = np.empty(h, dtype=np.int32)
    right_arg = np.empty(h, dtype=np.int32)

    for x in range(1, W):
        prev = dp_prev

        # Проход слева направо (сверху вниз)
        left_val[0] = prev[0]
        left_arg[0] = 0
        for i in range(1, h):
            cand = left_val[i - 1] - lam
            if prev[i] >= cand:
                left_val[i], left_arg[i] = prev[i], i
            else:
                left_val[i], left_arg[i] = cand, left_arg[i - 1]

        # Проход справа налево (снизу вверх)
        right_val[h - 1] = prev[h - 1]
        right_arg[h - 1] = h - 1
        for i in range(h - 2, -1, -1):
            cand = right_val[i + 1] - lam
            if prev[i] >= cand:
                right_val[i], right_arg[i] = prev[i], i
            else:
                right_val[i], right_arg[i] = cand, right_arg[i + 1]

        # Выбор лучшего пути
        use_left = left_val >= right_val
        best_val = np.where(use_left, left_val, right_val)
        best_arg = np.where(use_left, left_arg, right_arg)

        ptr[:, x] = best_arg
        dp_prev = S[:, x].astype(np.float32) + best_val

    # Обратный проход (Backtracking)
    z_idx = np.zeros(W, dtype=np.int32)
    z_idx[-1] = int(np.argmax(dp_prev))

    for x in range(W - 1, 0, -1):
        z_idx[x - 1] = ptr[z_idx[x], x]

    return z_idx + zmin


# ============================================================
# ---------------------- PREPROCESS --------------------------
# ============================================================

def preprocess_roi(roi: np.ndarray) -> np.ndarray:
    """Подготовка ROI: вычитание фона, логарифмирование и сглаживание."""
    roi = roi.astype(np.float32)

    bg = np.percentile(roi, 5)
    roi = np.clip(roi - bg, 0, None)

    roi = np.log1p(roi)
    roi = cv2.GaussianBlur(roi, (0, 0), 1.2)

    return roi


# ============================================================
# ------------------- DETECT BOUNDARIES ----------------------
# ============================================================

def detect_boundaries(img_gray: np.ndarray, x1: int, x2: int, y1: int, y2: int, n_bounds: int, shift: int) -> list:
    """Поиск заданного количества границ на ОКТ-снимке."""
    roi = img_gray[y1:y2, x1:x2]
    if roi.size == 0:
        return []

    roi_proc = preprocess_roi(roi)
    h, w = roi_proc.shape

    # Ищем градиенты и хребты
    grad = cv2.Sobel(roi_proc, cv2.CV_32F, 0, 1, ksize=3)
    ridge = roi_proc - cv2.GaussianBlur(roi_proc, (0, 0), 25)

    boundaries = []
    y_indices = np.arange(h)[:, None]  # Матрица индексов Y для векторизованного подавления (shape: hx1)

    # -------- 1. Верхняя граница (по градиенту) --------
    top = viterbi_trace_l1_fast(
        grad,
        zmin=int(0.01 * h),
        zmax=int(0.4 * h),
        smoothness=3.0
    )
    boundaries.append(top)

    score = ridge.copy()

    # Векторизованное подавление первой границы (вместо медленного for x in range(w))
    suppress_window_top = abs(shift - 40)
    mask_top = np.abs(y_indices - top) < suppress_window_top
    score[mask_top] = -1e9

    # -------- 2. Остальные границы (по хребтам) --------
    for _ in range(1, n_bounds):
        boundary = viterbi_trace_l1_fast(score, zmin=0, zmax=h - 1, smoothness=3.0)
        boundaries.append(boundary)

        # Векторизованное подавление текущей границы
        mask_bound = np.abs(y_indices - boundary) < shift
        score[mask_bound] = -1e9

    # Постобработка всех найденных границ
    final = [post_process_boundary(b.astype(float)) for b in boundaries]
    return final


# ============================================================
# ------------------- POST PROCESS ---------------------------
# ============================================================

def post_process_boundary(y_array: np.ndarray) -> np.ndarray:
    """Интерполяция, медианный и Савицкого-Голея фильтры для сглаживания линии."""
    if np.all(np.isnan(y_array)):
        return y_array

    # 1. Интерполяция NaN значений
    y_series = pd.Series(y_array)
    y_interp = y_series.interpolate(method='linear', limit_direction='both')
    data = y_interp.ffill().bfill().to_numpy()

    # 2. Быстрый медианный фильтр (заменяет медленный самописный)
    if len(data) >= 5:
        data = median_filter(data, size=5)

    # 3. Фильтр Савицкого-Голея
    window_length = min(11, len(data))
    if window_length % 2 == 0:
        window_length -= 1

    if window_length > 3:
        try:
            data = savgol_filter(data, window_length, 2)
        except Exception:
            pass

    return data


# ============================================================
# ------------------- DRAWING -------------------------------
# ============================================================

def draw_boundaries(img_gray: np.ndarray, boundaries: list, x1: int, x2: int, y1: int, y2: int) -> np.ndarray:
    """Векторизованная отрисовка найденных границ на изображении."""
    img_color = cv2.cvtColor(img_gray, cv2.COLOR_GRAY2BGR)
    h_img, w_img = img_gray.shape

    # Массив X-координат для всех пикселей ROI
    x_abs = np.arange(x1, x2)

    for b_idx, boundary in enumerate(boundaries):
        color = PROJECT_CONSTANTS.colourmap.get(b_idx, (255, 255, 255))

        # Получаем Y координаты для всей кривой сразу
        y_abs = np.round(boundary + y1).astype(int)

        # Создаем логическую маску для отсечения точек, выходящих за пределы картинки или NaN
        valid = (0 <= x_abs) & (x_abs < w_img) & (0 <= y_abs) & (y_abs < h_img) & ~np.isnan(boundary)

        # Применяем цвет ко всем валидным пикселям одновременно
        img_color[y_abs[valid], x_abs[valid]] = color

    return img_color


def process_single_image(img_gray: np.ndarray, graph_coordinates: list, amount_of_bounds: int, shift: int):
    """Главный входной метод."""
    if img_gray is None:
        return None

    if not graph_coordinates or graph_coordinates == [0, 0, 0, 0]:
        print('[Boundary processing]: ROI not selected')
        return cv2.cvtColor(img_gray, cv2.COLOR_GRAY2BGR)

    x1, x2, y1, y2 = graph_coordinates
    h_img, w_img = img_gray.shape

    x1, x2 = max(0, int(x1)), min(w_img, int(x2))
    y1, y2 = max(0, int(y1)), min(h_img, int(y2))

    if x2 <= x1 or y2 <= y1:
        return cv2.cvtColor(img_gray, cv2.COLOR_GRAY2BGR)

    # Ищем границы
    boundaries = detect_boundaries(img_gray, x1, x2, y1, y2, amount_of_bounds, shift)

    # Рисуем границы
    result = draw_boundaries(img_gray, boundaries, x1, x2, y1, y2)

    return result