"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict

import yaml

from ..common import ERROR, parse_yolo_line

DROP_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
REMOVE_CODES = {"LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}          # + mọi mã bắt đầu bằng DUP_IMAGE_


def _is_remove(code):
    return code in REMOVE_CODES or code.startswith("DUP_IMAGE_")


def _fmt(v):
    return f"{v:.6f}".rstrip("0").rstrip(".") or "0"


def _clip(text):
    """Cắt box về [0,1]. Trả dòng mới, hoặc None nếu box không còn diện tích."""
    c, x, y, w, h = parse_yolo_line(text)
    x1, y1 = max(0.0, x - w / 2), max(0.0, y - h / 2)
    x2, y2 = min(1.0, x + w / 2), min(1.0, y + h / 2)
    if x2 - x1 <= 0 or y2 - y1 <= 0:
        return None
    return f"{c} {_fmt((x1 + x2) / 2)} {_fmt((y1 + y2) / 2)} {_fmt(x2 - x1)} {_fmt(y2 - y1)}"


def _remove_image(ds, stem):
    p = ds.image_path(stem)
    if p is not None:
        p.unlink()
    lp = ds.label_path(stem)
    if lp.exists():
        lp.unlink()


def fix(ds, issues, cfg):
    errs = [i for i in issues if i.severity == ERROR]          # WARN là việc của người: không động tới
    fixes = []

    # 1) xoá ảnh trước: issue theo dòng của ảnh đã xoá sẽ được bỏ qua êm
    removed = set()
    for i in errs:
        if _is_remove(i.code) and i.image not in removed:
            removed.add(i.image)
            if ds.image_path(i.image) is None and not ds.label_path(i.image).exists():
                continue                                       # đã không còn: idempotent
            _remove_image(ds, i.image)
            fixes.append(dict(image=i.image, line="", action="remove_image", before=i.code, after="(đã xoá ảnh + nhãn)"))

    # 2) data.yaml: ghi lại names đúng danh sách dự án
    if any(i.code == "BAD_CLASS_NAME" for i in errs) and ds.yaml_path.exists():
        d = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
        before = d.get("names")
        want = list(cfg["classes"])
        if before != want and before != dict(enumerate(want)):
            d["names"] = want
            ds.yaml_path.write_text(yaml.safe_dump(d, allow_unicode=True, sort_keys=False), encoding="utf-8")
            fixes.append(dict(image="data.yaml", line="", action="rename_classes", before=str(before), after=str(want)))

    # 3) ảnh thiếu file nhãn: KHÔNG bịa nhãn (kể cả file rỗng), chuyển người gán
    for stem in sorted({i.image for i in errs if i.code == "MISSING_LABEL_FILE"} - removed):
        fixes.append(dict(image=stem, line="", action="needs_label", before="(không có file)", after="chuyển người gán"))

    # 4) lỗi theo dòng: gom theo file, sửa MỘT lần theo số dòng GỐC (dòng trống vẫn được đếm)
    per_file = defaultdict(lambda: defaultdict(set))
    for i in errs:
        if i.line not in (None, "") and (i.code in DROP_CODES or i.code == "BOX_OUT_OF_IMAGE") and i.image not in removed:
            per_file[i.image][int(i.line)].add(i.code)
    for stem in sorted(per_file):
        lp = ds.label_path(stem)
        if not lp.exists():
            continue
        raw = lp.read_text(encoding="utf-8", errors="replace").splitlines()
        out = []
        for n, text in enumerate(raw, 1):
            codes = per_file[stem].get(n)
            if not codes or not text.strip():
                out.append(text)
                continue
            if codes & DROP_CODES:                             # xoá dòng thắng: không ghi thêm clip_box
                fixes.append(dict(image=stem, line=n, action="drop_line", before=text.strip(),
                                  after="(xoá: " + ",".join(sorted(codes & DROP_CODES)) + ")"))
                continue
            try:
                new = _clip(text)
            except ValueError:
                new = None
            if new is None:                                    # nằm hẳn ngoài ảnh: xoá thay vì ghi box rỗng
                fixes.append(dict(image=stem, line=n, action="drop_line", before=text.strip(), after="(xoá: box nằm ngoài ảnh)"))
                continue
            fixes.append(dict(image=stem, line=n, action="clip_box", before=text.strip(), after=new))
            out.append(new)
        lp.write_text("".join(ln + "\n" for ln in out), encoding="utf-8")
    return fixes
