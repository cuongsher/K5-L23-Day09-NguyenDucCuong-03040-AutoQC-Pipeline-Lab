# Báo cáo Day 09 — Nguyễn Đức Cường, 03040

## 1. Kết luận trước
**Hold.** Quét 224 ảnh → loại 22 ở bước 1 → **202 ảnh** vào dataset `clean_v1` (đã xuất, kèm nhãn Hold trong `manifest.json`).
Không còn lỗi bắt buộc (`07_error_list_v3`: 0 error), nhưng **38/202 ảnh (18,8%)** còn cảnh báo chưa người duyệt, vượt ngưỡng `gate.warn_ratio_hold = 10%` (`08_summary.json`).

## 2. Lỗi và phân việc
Từ `02_error_list_v1` (211 dòng trên 149 ảnh, mẫu số 224 ảnh quét):

| Mã lỗi | Số ảnh/dòng | Ai sửa | Vì sao |
|---|---:|---|---|
| CORRUPT_IMAGE | 2 ảnh | máy (loại) | không mở được, không cứu được |
| BAD_SIZE | 3 ảnh | máy (loại) | cạnh ngắn < 250px, dưới chuẩn guideline |
| DUP_IMAGE_EXACT | 8 ảnh | máy (loại) | trùng byte, giữ 1 bản |
| DUP_IMAGE_NEAR | 4 ảnh | máy (loại) | phash ≤ 10 |
| LEAK_TEST | 5 ảnh | máy (loại) | trùng ảnh test/val → rò rỉ |
| BAD_CLASS_NAME | 1 tệp (`data.yaml`, 2 dòng) | máy | đổi tên lớp về chuẩn (`Person`→`person`, `Bus`→`bus`) |
| BAD_CLASS_ID | 6 dòng / 6 ảnh | máy (`drop_line`) | id ngoài 0–3, không đoán được lớp đúng |
| BAD_FORMAT | 3 dòng / 3 ảnh | máy (`drop_line`) | dòng hỏng không parse được |
| BOX_ZERO | 4 dòng / 4 ảnh | máy (`drop_line`) | box diện tích 0 |
| DUP_BOX | 7 dòng / 7 ảnh | máy (`drop_line`) | box lặp, xoá bản thừa |
| BOX_OUT_OF_IMAGE | 8 dòng / 8 ảnh | máy (`clip_box`) | cắt về trong khung ảnh |
| MISSING_LABEL_FILE | 6 ảnh | **người** | không có nhãn → phải gán tay (`needs_label`) |
| POSSIBLE_MISSING | 53 dòng / 52 ảnh | **người** | gợi ý của model, cần xác nhận |
| POSSIBLE_FALSE_POS | 29 dòng / 27 ảnh | **người** | như trên |
| POSSIBLE_LOOSE_BOX | 28 dòng / 24 ảnh | **người** | như trên |
| POSSIBLE_WRONG_CLASS | 18 dòng / 18 ảnh | **người** | như trên |
| EMPTY_LABEL | 12 ảnh | **người** | có thể ảnh nền thật hoặc quên gán |
| BOX_TINY / BOX_HUGE / CLASS_RARE | 6 / 3 / 4 dòng | người (ưu tiên thấp) | chỉ cảnh báo |

Máy sửa 35 thay đổi (`03_fixes.csv`: 20 `drop_line`, 8 `clip_box`, 1 `rename_classes`, 6 `needs_label` chuyển người). Sau autofix (`04_error_list_v2`) chỉ còn 6 error `MISSING_LABEL_FILE`.

**Hàng đợi** (`05_review_queue.csv`, 125 ảnh) xếp theo tổng trọng số mã lỗi trong `review.weights`: `NEEDS_LABEL` = 10 nên 6 ảnh thiếu nhãn lên đầu (ảnh đầu `img_0020` = 11,5 vì có `FIXED_DROP_LINE` + `POSSIBLE_MISSING` + `POSSIBLE_WRONG_CLASS`), sau đó tới ảnh có nhiều cảnh báo ngữ nghĩa (`WRONG_CLASS` 3 > `MISSING`/`FALSE_POS` 2 > `LOOSE_BOX` 1,5). Với ngân sách 80 ảnh: người duyệt 80 ảnh, trong đó **74 ảnh có cảnh báo ngữ nghĩa (88 lượt mã)** trên tổng 103 ảnh có cảnh báo ngữ nghĩa trong hàng đợi.

## 3. Calibration (2 ngưỡng)
Số từ `submission/calibration/calibration_report.md` (bộ calib có lỗi chèn sẵn):

| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | 10 | NEAR: 1,00/0,50 → 1,00/0,67 (EXACT giữ 1,00/1,00) | Recall tăng từ 4, phẳng tới 14, precision vẫn 1,00. Không lấy 16 (R 0,83) vì càng xa càng dễ gộp nhầm 2 cảnh giống nhau trên raw; ở 20 EXACT tụt R 0,33. Chọn giữa vùng phẳng cho an toàn. |
| `second_opinion.conf` | 0.25 | 0.6 | WRONG_CLASS 0,56/0,83 → 0,62/0,83; MISSING 0,50/1,00 → 0,57/1,00; LOOSE_BOX 0,29/0,40 → 0,20/0,20; FALSE_POS 0,31/1,00 (không đổi) | Tăng precision cho 2 mã trọng số cao mà giữ recall. Bỏ 0,7–0,8 vì MISSING tụt recall (0,88 / 0,75). Chấp nhận LOOSE_BOX kém hơn vì trọng số thấp nhất. |

**Một chỗ calibration có thể đánh lừa:** bộ calib rất nhỏ (DUP_IMAGE_NEAR chỉ 6 ca chèn, WRONG_CLASS 6, LOOSE_BOX 5), nên 1 ca TP/FN đổi recall 0,17–0,20 → vùng "phẳng" 4–14 có thể chỉ là ngẫu nhiên. Trên raw, `phash_dist = 10` bắt thêm 2 cặp mà ngưỡng 2 bỏ qua: `img_0186`↔`img_0061` (phash 10, đúng sát ngưỡng) và `img_0223`↔`img_0077` (phash 6).

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
**(a) Gate chặn đúng.** Chạy `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb`:
```
kết luận: REWORK — còn 6 lỗi bắt buộc (MISSING_LABEL_FILE) trên 6 ảnh/tệp
Bước 5/5  KHÔNG xuất: còn lỗi bắt buộc (Rework) — trả về bước 3
```
Mã thoát **20**, thư mục `work/exp_nb` **không được tạo**. Không có người duyệt thì 6 ảnh thiếu nhãn không được gán, gate chặn đúng.

**(b) Điểm mù:**
1. **Box lỏng nhẹ:** `POSSIBLE_LOOSE_BOX` trên calib chỉ P 0,20 / R 0,20 (bắt 1/5 ca chèn) ở conf 0,6. Box lệch nhẹ gần như lọt hết. `07_error_list_v3` vẫn còn 20 cảnh báo loose box chưa ai xem.
2. **Ảnh trùng biến đổi mạnh:** DUP_IMAGE_NEAR recall chỉ 0,67 (bỏ sót 2/6 ca chèn) dù đã nới tới 10. Ảnh crop/lật/đổi màu mạnh vẫn qua được, có thể rò vào train.
3. **Nhầm lớp mà model lớn cũng nhầm:** WRONG_CLASS bỏ sót 1/6 (R 0,83). Second opinion chỉ bắt được khi model checker đúng. Còn POSSIBLE_FALSE_POS P 0,31: 11 báo động giả trên 16, tốn ngân sách người duyệt.

## 5. Train: raw vs clean
`yolo26n.pt`, 20 epoch, batch 16, imgsz 640, seed 0 và 1, Colab T4; chung val (`gold_val`, 40 ảnh) và test (`data/test`, 100 ảnh). Số từ `submission/results/comparison.md`:

| biến thể | #ảnh | mAP50 | mAP50-95 | AP50 car / person / truck / bus (TB 2 seed) |
|---|---:|---|---|---|
| raw | 224 (thực dùng 213) | 0.726 ± 0.000 | 0.512 ± 0.004 | 0.738 / 0.822 / 0.648 / 0.695 |
| clean | 202 | 0.701 ± 0.025 | 0.487 ± 0.008 | 0.738 / 0.823 / **0.538** / 0.703 |

**Kết luận:** chênh mAP50 (clean − raw) = **−0.025**, bằng độ lệch giữa 2 seed của clean (0.718 vs 0.683) → **nằm trong nhiễu, chưa kết luận được**; chỉ nói được là không có bằng chứng làm sạch giúp tăng mAP. Toàn bộ mức tụt nằm ở **truck** (−0.11), 3 lớp kia gần như không đổi. 2 seed quá ít để tin độ lệch (raw ± 0.000 là trùng hợp).

1. Chênh lệch so với nhiễu: clean thấp hơn raw 0.025 mAP50, bằng đúng độ lệch giữa 2 seed. Vì vậy chưa kết luận được clean tốt hơn hay kém hơn.
2. Raw thật sự train bao nhiêu ảnh: 213/224. Có bảng 11 ảnh bị Ultralytics bỏ, ghi lý do của từng ảnh và mã lỗi pipeline đã bắt tương ứng.
3. Rò rỉ test: có 5 ảnh raw trùng với ảnh test, tao liệt kê đủ cả 5 cặp. Chưa đo được điểm raw bị thổi phồng bao nhiêu; trong file có ghi cách đo bằng tập test 95 ảnh (bỏ 5 ảnh trùng).
4. Lớp nào được lợi: không lớp nào lợi rõ rệt. Bus tăng +0.008, nằm trong nhiễu. Truck tụt −0.11. Giải thích bằng các loại lỗi trong 02_error_list_v1, cộng thêm việc pretrain COCO lấn át tác động của nhãn.
5. Clean còn lỗi gì: hàng đợi 125 ảnh vượt ngân sách 80, còn 38 ảnh cảnh báo chưa ai duyệt. Như vậy clean chưa phải chặn trên; muốn có chặn trên phải train thêm biến thể oracle.

**Giả thuyết → cách kiểm:**
1. **Raw được lợi nhờ rò test:** 5 ảnh raw trùng test (`img_0049`↔`test_033`, `img_0101`↔`test_039`, `img_0167`↔`test_044`, `img_0174`↔`test_085`, `img_0221`↔`test_009`), clean đã loại. → Đánh giá lại 2 model trên 95 ảnh test còn lại.
2. **Truck ít mẫu, nhãn bị đổi nhiều:** test chỉ 24 box truck; AP truck của clean lệch 0.59 / 0.49 giữa 2 seed. Sau người duyệt truck tăng 32 → 41 box (+28%), lớp đổi mạnh nhất, có thể lệch quy ước truck/car của nhãn test. → Thêm seed; xem các ảnh đổi nhãn truck trong `06_review_log.csv`.
3. **Clean chưa thật sạch:** hàng đợi 125 > ngân sách 80, còn 38/202 ảnh cảnh báo chưa duyệt, LOOSE_BOX gần như không bắt → clean chưa phải chặn trên. → Train biến thể `oracle` (nhãn người).

## 6. Quyết định và ghi chú AI
**(a)** **Hold**. Muốn thành **Release** thì cần đưa số ảnh còn cảnh báo chưa duyệt xuống < 10% (≤ 20/202). Hiện còn 38 ảnh chưa duyệt. `07_error_list_v3` có cảnh báo trên 63 ảnh (gồm cả ảnh đã duyệt): 21 FALSE_POS, 20 LOOSE_BOX, 13 MISSING, 3 WRONG_CLASS, 4 EMPTY_LABEL, 10 BOX_TINY/HUGE. Hai cách: tăng ngân sách duyệt thêm khoảng 18–20 ảnh (đi tiếp hàng đợi từ vị trí 81), hoặc giảm báo động giả FALSE_POS (P 0,31) để hàng đợi ngắn lại. Không hạ `warn_ratio_hold` chỉ để qua cửa.

**(b) Dùng AI:** (Claude)
- Prompt: Đọc đề bài, giải thích đề bài + viết giải pháp ( giải thích chi tiết giải pháp) cho t
- 1 lần AI sai: lần đầu AI ghi code bằng một lệnh bash có heredoc lồng nhau → lỗi cú pháp shell, không file nào được ghi; phải viết lại từng file riêng.
- - Cách kiểm: `pytest` 79/79 xanh