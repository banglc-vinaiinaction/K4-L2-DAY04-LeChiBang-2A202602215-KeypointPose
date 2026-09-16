# Mini guideline - nhóm: Lê Chí Bằng  |  người gán: lechibang  |  ngày: 2026-09-16

> Điền file này **trong lúc** gán nhãn, không phải sau khi xong. Mỗi lần bạn dừng lại
> hơn 10 giây để phân vân, đó là một dòng phải ghi vào đây.

## 1. Luật bắt buộc (đã thống nhất cả lớp - không sửa)

- Bộ 17 điểm COCO, đúng tên, đúng thứ tự. Lấy từ file `.SVG` chung.
- Mọi người trong ảnh đều có **đủ 17 điểm**. Điểm không dùng được thì gắn cờ, không xoá.
- Trái/phải tính theo **cơ thể người**, không theo bức ảnh.
- Bị che, còn trong khung -> `v = 1`, **vẫn đặt chấm** ở vị trí ước lượng.
- Ra ngoài mép ảnh -> `v = 0`, **không** đặt chấm.
- Không dùng `Hidden` (`h`) - nó không được lưu vào file.

## 2. Luật của nhóm bạn (phải điền)

| Tình huống | Luật nhóm bạn chọn | Vì sao |
| --- | --- | --- |
| Hông của người mặc quần áo dài | Đặt v=1 (occluded), ước lượng vị trí dựa trên giữa thân và đường vai. Hông nằm ở ~1/3 từ eo xuống đùi, ngang trung điểm giữa eo và đầu gối | Hông luôn bị quần áo che, nhưng vị trí giải phẫu ổn định. Nếu để v=0 sẽ mất toàn bộ thông tin posture phần dưới |
| Tai bị tóc hoặc mũ bảo hiểm che một phần | v=1 (occluded), đặt chấm ở vị trí ước lượng tai dựa trên đường đầu | Tai bị che một phần vẫn nằm trong khung hình, chỉ bị vật thể che chứ không bị cắt |
| Người bị cắt ở mép ảnh (chỉ thấy từ hông trở lên) | Gán đủ 17 điểm. Khớp nằm trong khung: v=1 hoặc v=2. Khớp tràn mép ảnh (≤6px): v=0 (outside) | Giữ đầy đủ skeleton topology cho mọi trường hợp |
| Cổ tay nằm sau tay lái / sau thân mình | v=1 (occluded), đặt chấm ở vị trí ước lượng dựa trên hướng cánh tay | Cổ tay vẫn tồn tại, chỉ bị vật thể che. Model cần biết hướng tay |
| Hai người chồng lên nhau | Gán riêng từng skeleton. Khớp bị người khác che: v=1 (occluded). Hoàn thành hết 1 người trước khi sang người kế | Tránh nhầm lẫn khớp giữa hai skeleton |
| Người nhỏ đến mức nào thì không gán nữa | Gán tất cả, bộ ảnh đã được chọn sao cho mọi người đều đủ lớn | Theo hướng dẫn GUIDE.md, không có ca quá nhỏ |

## 3. Ba ca mơ hồ đã gặp (bắt buộc, ghi ít nhất 3)

### Ca 1 - ảnh `train_09`, người thứ `1`, khớp `nose, left_eye, right_eye`

- Mơ hồ ở chỗ nào: Người ngồi xe máy quay lưng lại camera. Mặt hoàn toàn không nhìn thấy.
- Bạn quyết thế nào: v=1 (occluded), đặt chấm ước lượng ở vị trí mặt dựa trên hướng đầu.
- Vì sao: Mặt vẫn nằm trong khung hình, chỉ bị đầu và mũ che. Theo luật: "bị che, còn trong khung → v=1".
- Nếu người khác quyết ngược lại thì model học sai cái gì: Nếu đặt v=0, model sẽ học rằng người quay lưng không có mặt, mất thông tin hướng đầu.

### Ca 2 - ảnh `train_16`, người thứ `1` và `2`, khớp `left/right shoulders, hips`

- Mơ hồ ở chỗ nào: Hai người nhảy bắt đĩa bay, tay vươn cao, thân xoay. Khó phân biệt trái/phải khi cơ thể xoay 3D.
- Bạn quyết thế nào: Dùng quy tắc "tưởng tượng đứng vào chỗ người đó" để xác định trái/phải theo giải phẫu.
- Vì sao: Trái/phải phải nhất quán theo cơ thể, không theo góc camera. Ban đầu bị gán ngược, đã phát hiện qua checker (xương vai chéo nhau) và sửa lại.
- Nếu người khác quyết ngược lại thì model học sai cái gì: Đảo trái/phải là lỗi nghiêm trọng nhất — augmentation lật ảnh sẽ dạy sai gấp đôi, model không bao giờ học được hướng cơ thể.

### Ca 3 - ảnh `train_13`, người thứ `2` (nhỏ, bên trái), khớp `left_elbow, left_wrist`

- Mơ hồ ở chỗ nào: Người nhỏ bị phần lớn thân che bởi người đứng trước. Tay trái gần như không nhìn thấy, chỉ đoán được hướng.
- Bạn quyết thế nào: v=1 (occluded), đặt chấm ước lượng dựa trên hướng vai và cạnh thân nhìn thấy.
- Vì sao: Tay nằm trong khung hình, chỉ bị người khác che. Không phải outside.
- Nếu người khác quyết ngược lại thì model học sai cái gì: Nếu đặt v=0, model mất thông tin pose hoàn chỉnh cho người bị che một phần, giảm khả năng xử lý crowd scene.

## 4. Sau khi so visibility report với bạn cùng nhóm

- Khớp lệch `%v=1` nhiều nhất: `left_hip / right_hip` (97% v=1 — hông luôn bị che bởi quần áo)
- Nguyên nhân là **guideline chưa rõ** hay **một trong hai bên gán sai**: Guideline đã rõ: hông luôn v=1.
- Luật mới bổ sung vào mục 2 sau khi thống nhất: Không cần bổ sung — hông v=1 là quy ước chung, không có bất đồng.
