import numpy as np
import pandas as pd
import cv2
from scipy.signal import savgol_filter
from ..state.project_state import PROJECT_CONSTANTS


def viterbi_trace_l1_fast(score, zmin, zmax, smoothness=3.0):

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

        left_val[0] = prev[0]
        left_arg[0] = 0
        for i in range(1, h):
            cand = left_val[i - 1] - lam
            if prev[i] >= cand:
                left_val[i] = prev[i]
                left_arg[i] = i
            else:
                left_val[i] = cand
                left_arg[i] = left_arg[i - 1]

        right_val[h - 1] = prev[h - 1]
        right_arg[h - 1] = h - 1
        for i in range(h - 2, -1, -1):
            cand = right_val[i + 1] - lam
            if prev[i] >= cand:
                right_val[i] = prev[i]
                right_arg[i] = i
            else:
                right_val[i] = cand
                right_arg[i] = right_arg[i + 1]

        use_left = left_val >= right_val
        best_val = np.where(use_left, left_val, right_val)
        best_arg = np.where(use_left, left_arg, right_arg)

        ptr[:, x] = best_arg
        dp_prev = S[:, x].astype(np.float32) + best_val

    z_idx = np.zeros(W, dtype=np.int32)
    z_idx[-1] = int(np.argmax(dp_prev))

    for x in range(W - 1, 0, -1):
        z_idx[x - 1] = ptr[z_idx[x], x]

    return z_idx + zmin


# ============================================================
# ---------------------- PREPROCESS --------------------------
# ============================================================

def preprocess_roi(roi: np.ndarray) -> np.ndarray:

    roi = roi.astype(np.float32)

    bg = np.percentile(roi, 5)
    roi = np.clip(roi - bg, 0, None)

    roi = np.log1p(roi)
    roi = cv2.GaussianBlur(roi, (0, 0), 1.2)

    return roi


# ============================================================
# ------------------- DETECT BOUNDARIES ----------------------
# ============================================================

def detect_boundaries(img_gray, x1, x2, y1, y2, n_bounds, shift):

    roi = img_gray[y1:y2, x1:x2]

    if roi.size == 0:
        return []

    roi_proc = preprocess_roi(roi)

    h, w = roi_proc.shape

    grad = cv2.Sobel(roi_proc, cv2.CV_32F, 0, 1, ksize=3)
    ridge = roi_proc - cv2.GaussianBlur(roi_proc, (0, 0), 25)

    boundaries = []

    # -------- 1. Верхняя граница (по градиенту) --------

    top = viterbi_trace_l1_fast(
        grad,
        zmin=int(0.01 * h),
        zmax=int(0.4 * h),
        smoothness=3.0
    )

    boundaries.append(top)

    score = ridge.copy()
    # подавляем верхнюю
    for x in range(w):
        z = int(top[x])
        score[max(0, z - abs(shift-40)):min(h, z + abs(shift-40)), x] = -1e9

    # -------- остальные границы --------

    for _ in range(1, n_bounds):

        boundary = viterbi_trace_l1_fast(
            score,
            zmin=0,
            zmax=h - 1,
            smoothness=3.0
        )

        boundaries.append(boundary)

        for x in range(w):
            z = int(boundary[x])
            score[max(0, z - shift):min(h, z + shift), x] = -1e9

    # постобработка
    final = []
    for b in boundaries:
        final.append(post_process_boundary(b.astype(float)))

    return final


# ============================================================
# ------------------- POST PROCESS ---------------------------
# ============================================================

def post_process_boundary(y_array):

    if np.all(np.isnan(y_array)):
        return y_array

    y_series = pd.Series(y_array)

    y_interp = y_series.interpolate(method='linear', limit_direction='both')
    y_interp = y_interp.ffill().bfill()

    data = y_interp.to_numpy()

    if len(data) >= 5:
        data = median_filter_1d(data, 5)

    window_length = min(11, len(data))
    if window_length % 2 == 0:
        window_length -= 1

    if window_length > 3:
        try:
            data = savgol_filter(data, window_length, 2)
        except:
            pass

    return data


def median_filter_1d(arr, kernel_size=3):
    result = np.copy(arr)
    pad = kernel_size // 2
    for i in range(pad, len(arr) - pad):
        result[i] = np.median(arr[i - pad:i + pad + 1])
    return result


# ============================================================
# ------------------- DRAWING -------------------------------
# ============================================================

def draw_boundaries(img_gray, boundaries, x1, x2, y1, y2):

    img_color = cv2.cvtColor(img_gray, cv2.COLOR_GRAY2BGR)
    h_img, w_img = img_gray.shape

    for b_idx, boundary in enumerate(boundaries):

        color = PROJECT_CONSTANTS.colourmap.get(b_idx, (255, 255, 255))

        for x_rel, y_rel in enumerate(boundary):

            if np.isnan(y_rel):
                continue

            x_abs = x1 + x_rel
            y_abs = int(y_rel + y1)

            if 0 <= x_abs < w_img and 0 <= y_abs < h_img:
                img_color[y_abs, x_abs] = color

    return img_color


def process_single_image(img_gray: np.ndarray, graph_coordinates: list, amount_of_bounds: int, shift: int):
    if img_gray is None:
        return None

    if graph_coordinates == [0, 0, 0, 0]:
        print('[Boundary processing]: ROI not selected')
        return cv2.cvtColor(img_gray, cv2.COLOR_GRAY2BGR)

    x1, x2, y1, y2 = graph_coordinates

    h_img, w_img = img_gray.shape
    x1, x2 = max(0, int(x1)), min(w_img, int(x2))
    y1, y2 = max(0, int(y1)), min(h_img, int(y2))

    if x2 <= x1 or y2 <= y1:
        return cv2.cvtColor(img_gray, cv2.COLOR_GRAY2BGR)

    boundaries = detect_boundaries(
        img_gray, x1, x2, y1, y2, amount_of_bounds, shift)

    result = draw_boundaries(
        img_gray, boundaries,
        x1, x2, y1, y2
    )

    return result