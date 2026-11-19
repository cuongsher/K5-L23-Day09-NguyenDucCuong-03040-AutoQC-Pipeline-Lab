"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line


def _check_file(ds, cfg, stem):
    lf = cfg["label_format"]
    tol, min_px = lf["overflow_tol"], lf["min_box_px"]
    max_frac, dup_iou = lf["max_box_frac"], lf["dup_box_iou"]
    n_cls = len(ds.classes)
    size, size_known = None, False
    issues = []
    kept = []                     # (số dòng, lớp, box) của các dòng hợp lệ phía trước, để so DUP_BOX

    def add(sev, code, ln, msg, **extra):
        issues.append(Issue("label_format", sev, code, stem, msg, ln, extra))

    for ln, text in ds.read_label_lines(stem) or []:      # read_label_lines giữ số dòng GỐC (bỏ dòng trống)
        try:
            c, x, y, w, h = parse_yolo_line(text)
        except ValueError as e:
            add(ERROR, "BAD_FORMAT", ln, f"dòng sai định dạng: {text.strip()!r} ({e})")
            continue
        if not 0 <= c < n_cls:
            add(ERROR, "BAD_CLASS_ID", ln, f"id lớp {c} ngoài 0..{n_cls - 1}", id=c)
            continue
        if w <= 0 or h <= 0:
            add(ERROR, "BOX_ZERO", ln, f"box không có diện tích (w={w}, h={h})")
            continue

        # mức tràn = phần mép box vượt ra ngoài [0,1] lớn nhất trong 4 cạnh
        overflow = max(0.0, -(x - w / 2), (x + w / 2) - 1.0, -(y - h / 2), (y + h / 2) - 1.0)
        if overflow > tol:
            add(ERROR, "BOX_OUT_OF_IMAGE", ln, f"box tràn ra ngoài ảnh {overflow:.4f}", overflow=round(overflow, 6))

        box = (x, y, w, h)
        for prev_ln, prev_c, prev_box in kept:
            if prev_c == c:
                iou = iou_xywh(prev_box, box)
                if iou > dup_iou:
                    add(ERROR, "DUP_BOX", ln, f"trùng box dòng {prev_ln} (IoU {iou:.3f})", iou=round(iou, 4), dup_of=prev_ln)
                    break
        kept.append((ln, c, box))

        if not size_known:
            size, size_known = ds.image_size(stem), True
        if size:
            short = min(w * size[0], h * size[1])
            if short < min_px:
                add(WARN, "BOX_TINY", ln, f"box nhỏ: cạnh ngắn {short:.1f}px < {min_px}px", short_px=round(short, 2))
        if w * h > max_frac:
            add(WARN, "BOX_HUGE", ln, f"box gần phủ cả ảnh ({w * h:.3f})", area_frac=round(w * h, 4))
    return issues


def run(ds, cfg):
    issues = []
    for lp in ds.label_files():
        issues.extend(_check_file(ds, cfg, lp.stem))
    return issues
