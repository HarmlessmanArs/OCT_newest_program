import numpy as np


def _compute_intensity_stats(idx, image, raw_boundaries, x1, x2):
    if image is None:
        return None

    rows, cols = image.shape

    x1 = int(max(0, min(cols - 1, x1 or 0)))
    x2 = int(max(0, min(cols - 1, x2 or cols)))
    if x2 <= x1:
        x2 = cols - 1

    def get_stats_in_rect(y_top, y_bottom, x_start, x_end):
        y_top = max(0, min(rows - 1, y_top))
        y_bottom = max(0, min(rows - 1, y_bottom))
        if y_bottom <= y_top:
            y_bottom = min(y_top + 1, rows - 1)

        crop = image[y_top:y_bottom + 1, x_start:x_end + 1]
        vals = crop[np.isfinite(crop)]

        return float(np.nanmean(vals)) if vals.size else 0.0, \
               float(np.nanstd(vals)) if vals.size else 0.0, vals

    roi_stats = []
    raw_intensity_arrays = []

    present_rb = [rb for rb in raw_boundaries if rb is not None and len(rb) > 0]
    num_boundaries = len(present_rb)

    if num_boundaries == 0:
        return {'filename': idx, 'roi_stats': [], 'total': {'mean': 0.0, 'std': 0.0}, 'raw_intensity_data': []}

    total_vals = np.array([])
    total_mean = total_std = 0.0

    if num_boundaries == 1:
        rb_top = present_rb[0]
        y_top = int(np.nanmax(rb_top) + 1)
        y_bottom = rows - 1
        mean_val, std_val, vals = get_stats_in_rect(y_top, y_bottom, x1, x2)
        roi_stats.append({'mean': mean_val, 'std': std_val})
        raw_intensity_arrays.append(vals)
        total_mean, total_std, total_vals = mean_val, std_val, vals
    else:
        all_vals_for_total = []
        for i in range(num_boundaries - 1):
            rb_top = present_rb[i]
            rb_bottom = present_rb[i + 1]
            y_top = int(np.nanmax(rb_top) + 1)
            y_bottom = int(np.nanmin(rb_bottom) - 1)
            mean_val, std_val, vals = get_stats_in_rect(y_top, y_bottom, x1, x2)
            roi_stats.append({'mean': mean_val, 'std': std_val})
            raw_intensity_arrays.append(vals)
            all_vals_for_total.append(vals)

        if all_vals_for_total:
            total_vals = np.concatenate(all_vals_for_total)
            total_mean = float(np.nanmean(total_vals)) if total_vals.size else 0.0
            total_std = float(np.nanstd(total_vals)) if total_vals.size else 0.0

    raw_intensity_arrays.append(total_vals)

    return {
        'idx': idx,
        'roi_stats': roi_stats,
        'total': {'mean': total_mean, 'std': total_std},
        'raw_intensity_data': raw_intensity_arrays
    }