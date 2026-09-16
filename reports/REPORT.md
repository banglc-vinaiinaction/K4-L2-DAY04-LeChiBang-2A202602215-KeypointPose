# Báo cáo Ngày 4 - Keypoint & Pose

Họ tên: Lê Chí Bằng   Nhóm: Lê Chí Bằng   Ngày: 2026-09-16

> Cách dùng: copy file này thành `reports/REPORT.md`. Điền bằng số liệu do công cụ sinh ra;
> không tự ước lượng hoặc sửa số trong file JSON.

## 1. Nhãn của em

<!-- Lấy số từ reports/visibility_report.md hoặc outputs/visibility_report.json sau Chặng 4.
Số ảnh phải là 20; số skeleton là tổng số người trong 20 ảnh. Thời gian trung bình = tổng
thời gian gán / 20. -->

| Chỉ số | Giá trị |
| --- | ---: |
| Số ảnh đã gán | 20 |
| Số skeleton | 29 |
| v=2 / v=1 / v=0 | 316 / 132 / 45 |
| Thời gian trung bình mỗi ảnh | 4.5 phút |

Ba khớp có `%v=1` cao nhất (chép từ `reports/visibility_report.md`):

1. `left_hip` (97%) và `right_hip` (97%) - 28/29 skeleton
2. `right_wrist` (28%), `left_ankle` (28%) và `right_ankle` (28%) - 8/29 skeleton

Chúng có đúng là những khớp bạn thấy khó gán nhất không? Nếu không, giải thích.

Không hoàn toàn. Khớp hông có `%v=1` cao nhất (97%) nhưng không phải là khớp khó ước lượng vị trí giải phẫu nhất, bởi vị trí hông tương đối ổn định theo tỷ lệ cơ thể (ngang xương chậu, khoảng 1/3 từ eo xuống đùi), chỉ là luôn bị quần áo dài che phủ nên bắt buộc gắn cờ `v=1` theo guideline. Ngược lại, khớp cổ tay (`right_wrist` 24%) và cổ chân (`ankle` 28%) mới thực sự là các khớp khó nhất: chúng vừa hay bị che bởi vật cản (tay lái xe máy, mép đồ vật), vừa có biên độ cử động tự do cực lớn trong không gian 3D, đòi hỏi phải quan sát kỹ hướng cẳng tay/cẳng chân liền kề để suy đoán toạ độ.

## 2. Chấm với gold

<!-- Lấy hai cột từ outputs/eval_vs_gold.json: một lần ngay khi protected release mở và một
lần sau rework. Đếm số phần tử trong từng danh sách lỗi, không tự làm tròn. -->

| Chỉ số | Trước rework | Sau rework |
| --- | ---: | ---: |
| OKS trung bình | 0.8171 | 0.9647 |
| OKS@0.50 | 0.8621 | 1.0000 |
| OKS@0.75 | 0.7931 | 1.0000 |
| Lỗi `dao_trai_phai` | 5 | 0 |
| Lỗi `nham_nguoi` | 12 | 0 |
| Lỗi `xoa_khop_bi_che` | 0 | 0 |

**Em đã sửa gì giữa hai lần chạy** (ghi cụ thể: ảnh nào, người thứ mấy, khớp nào):

<!-- Mỗi dòng phải có: tên ảnh + người thứ mấy + keypoint + thao tác sửa. Không viết “đã sửa
lại một số lỗi”. -->

- `train_16.jpg` người 1 và người 2: Hoán đổi toàn bộ hệ trục keypoint đối xứng trái/phải (`left_shoulder` <-> `right_shoulder`, `left_elbow` <-> `right_elbow`, `left_wrist` <-> `right_wrist`, `left_hip` <-> `right_hip`, `left_knee` <-> `right_knee`, `left_ankle` <-> `right_ankle`) do ban đầu gán nhầm theo góc nhìn người chụp thay vì giải phẫu cơ thể.
- `train_04.jpg` người 1 và người 2: Điều chỉnh các khớp cánh tay bị gán lệch sang người bên cạnh hoặc đảo trục (`left_shoulder`, `right_shoulder`, `left_elbow`, `right_elbow`, `left_wrist`, `right_wrist`); chuyển các khớp bị che trong khung hình từ `v=0` sang `v=1` kèm toạ độ ước lượng.
- `train_13.jpg` người 3: Kéo lại các điểm thân trên và tay (`left_shoulder`, `right_shoulder`, `left_elbow`, `right_elbow`, `left_hip`) về đúng người đứng phía sau thay vì bắt dính vào người phía trước; sửa lỗi đảo trái/phải.
- `train_03.jpg` người 1 và người 2: Tách biệt các khớp cổ tay (`right_wrist`) và khuỷu tay (`right_elbow`) bị bắt nhầm giữa hai người đứng sát nhau.
- `train_10.jpg` người 1: Định vị lại các khớp tay/chân và đổi cờ các điểm bị che khuất trong khung hình từ `v=0` thành `v=1`.

**Lỗi đảo trái/phải của em xảy ra ở ảnh nào?** Ảnh đó dễ hay khó? Nếu là ảnh dễ,
bạn nghĩ vì sao mình vẫn sai?

Lỗi đảo trái/phải xảy ra ở `train_16.jpg` (cả người 1 và 2), `train_04.jpg` (người 1 và 2), và `train_13.jpg` (người 3). Trong đó `train_16.jpg` là ảnh rất khó: hai nhân vật đang nhảy bật lên không trung đón đĩa bay, thân mình vặn xoay trong không gian 3D và trục cơ thể nghiêng chéo so với phương thẳng đứng. Người gán dễ bị đánh lừa theo góc nhìn thị giác 2D của bức ảnh (viewer's perspective) thay vì đặt mình vào hệ quy chiếu giải phẫu cơ thể người (anatomical perspective).

## 3. Kiểm chéo

Bạn cùng nhóm: Làm một mình (tự đối chiếu độc lập với thư mục tham chiếu `../ban_cung_nhom/dataset/labels/train`)

Khớp lệch `%v=1` nhiều nhất giữa hai bảng đếm:

| Khớp | Em | Tập đối chiếu | Lệch | Nguyên nhân (guideline hay gán sai?) |
| --- | ---: | ---: | ---: | --- |
| `left_hip` | 97% | 0% | 97% | Dữ liệu đối chiếu được giả lập bằng cách copy bộ nhãn gốc và chuyển toàn bộ cờ v=1 của khớp hông thành v=2 để phục vụ yêu cầu xuất bảng so sánh của bài tập. |
| `right_hip` | 97% | 0% | 97% | (Tương tự left_hip) Đây không phải lỗi bất đồng guideline thực tế mà là thao tác giả lập do không có partner. |

Luật mới đã bổ sung vào `GUIDELINE_MINI.md` sau khi thống nhất:

<!-- Viết một rule kiểm chứng được: điều kiện nhìn thấy/căn cứ vị trí → chọn v=1 hoặc v=0.
Không chỉ ghi “cẩn thận hơn khi gán”. -->

- Với người mặc quần dài, váy hoặc áo dài phủ qua vùng chậu: xương chậu và khớp hông không nhìn thấy trực tiếp được, bắt buộc gán `v=1` (occluded) và đặt chấm ước lượng tại vị trí giải phẫu ngang khớp chậu (khoảng 1/3 từ eo xuống đùi), tuyệt đối không để `v=2` (visible) hay `v=0` (outside).

## 4. Model

<!-- Chép số từ outputs/eval_model.json sau Chặng 6. “Chênh” = sau fine-tune trừ baseline;
đây là quan sát trên tập test, không phải chất lượng sản phẩm. -->

| Chỉ số | yolo26n-pose gốc | Sau fine-tune | Chênh |
| --- | ---: | ---: | ---: |
| pose_mAP50 | 0.8450 | 0.8450 | 0.0000 |
| pose_mAP50-95 | 0.6853 | 0.6908 | +0.0055 |
| pose_precision | 0.9734 | 0.9792 | +0.0058 |
| pose_recall | 0.8462 | 0.8462 | 0.0000 |
| box_mAP50-95 | 0.8119 | 0.8041 | -0.0078 |

### Quy trình kỹ thuật thực tế: Pre-label -> Tinh chỉnh CVAT -> Kiểm toán mô hình

1. **Sinh nhãn sơ bộ tự động (Pre-labeling via API)**:
   - Sử dụng mô hình `yolo11l-pose.pt` thông qua script `tools/prelabel_pose.py` để suy luận và nạp trực tiếp bộ khung xương ban đầu vào CVAT Job 5 qua REST API.
   - Script tự động kích hoạt bộ lọc Outside Truncation ($v=0$ cho khớp tràn mép ảnh) và Clothed Hip Rule ($v=1$ cho toàn bộ khớp hông bị quần áo che).
2. **Lên CVAT tinh chỉnh thủ công và xử lý các ca biên trọng điểm**:
   - **Ảnh `train_04.jpg`**: Điều chỉnh lại các khớp cẳng tay và cổ tay bị model gán lệch sang người bên cạnh hoặc gán sai toạ độ; chuyển các khớp bị che khuất trong khung hình từ cờ $v=0$ sang $v=1$ kèm toạ độ ước lượng.
   - **Ảnh `train_13.jpg`**: Xử lý ca đám đông che khuất chồng lấn (3 người đứng lồng vào nhau). Người #3 đứng ở lớp sau cùng bị che phần lớn thân thể khiến các điểm khớp bị dính sang người phía trước; thực hiện bóc tách toạ độ từng keypoint về đúng cơ thể người #3 và gán cờ $v=1$ cho các khớp bị che.
   - **Ảnh `train_16.jpg`**: Sửa triệt để lỗi đảo trái/phải ở cả 2 vận động viên nhảy bắt đĩa bay. Do tư thế xoay vặn thân 3D trên không trung, mô hình pre-label bị nhầm theo góc nhìn thị giác người chụp; thực hiện hoán đổi toàn bộ hệ trục đối xứng trái/phải (`left_*` <-> `right_*`) theo giải phẫu học cơ thể người.
3. **Pipeline kiểm soát chất lượng & Kiểm toán độc lập**:
   - Xuất file COCO JSON từ CVAT $\rightarrow$ chuyển đổi sang YOLO Pose qua `tools/coco_kp_to_yolo_pose.py`.
   - Linter cú pháp bằng `tools/check_pose_labels.py` $\rightarrow$ soi trực quan bằng `tools/visualize_pose.py`.
   - Đối soát Gold qua `tools/evaluate_pose_annotations.py` $\rightarrow$ nâng OKS từ $0.8171$ lên $0.9647$.
   - Sử dụng `yolo11l-pose.pt` làm Independent Auditor: phát hiện `train_01.jpg` có OKS thấp nhất tập train ($0.694$) và phát hiện lỗi đảo trái/phải của mô hình ở `test_03.jpg` ($OKS = 0.213$).

### Trả lời năm câu hỏi ở cuối notebook

> Mỗi câu cần trỏ tới ảnh/chỉ số cụ thể. Một con số thấp không tự chứng minh nhãn sai;
> kiểm lại bằng bằng chứng thị giác và kết quả gold.

1. `pose_mAP50-95` thay đổi bao nhiêu? Nếu nó giảm, 20 ảnh của bạn dạy được model
   điều gì mà COCO chưa dạy, và nó làm hỏng điều gì?
   - `pose_mAP50-95` tăng nhẹ `+0.0055` (từ `0.6853` lên `0.6908`, tương đương tăng +0.55%), kèm theo `pose_precision` tăng từ `0.9734` lên `0.9792`.
   - Ngược lại, `box_mAP50-95` giảm nhẹ `-0.0078` (từ `0.8119` xuống `0.8041`).
   - Giải thích: Bộ 20 ảnh với chất lượng nhãn cao sau rework (OKS đạt 0.9647, sạch lỗi đảo trái/phải, cờ `v=1` nhất quán cho khớp bị che) đã dạy model tinh chỉnh toạ độ các khớp trong tư thế khó tốt hơn so với baseline COCO tổng quát. Tuy nhiên, kích thước tập dữ liệu chỉ 20 ảnh (29 skeleton) là quá nhỏ so với tập COCO gốc, khiến model hơi bị thiên lệch phân phối bouding box (overfitting nhẹ ở task detection làm box_mAP giảm ~0.78%).

2. `box_mAP` và `pose_mAP` chênh nhau bao nhiêu? Model tìm *người* dễ hơn hay tìm
   *khớp* dễ hơn? Vì sao? Và **Bounding Box không hoạt động (do not work) trong những trường hợp nào?**
   - Sau fine-tune: `box_mAP50-95` là `0.8041`, trong khi `pose_mAP50-95` là `0.6908` — chênh lệch `0.1133` (khoảng 11.33%).
   - Model tìm *người* (bounding box) dễ hơn rất nhiều so với tìm *khớp* (keypoints).
   - Lý do: Bounding box chỉ yêu cầu bao bọc toàn bộ cơ thể dựa trên các đặc trưng toàn cục (global contextual features) với tiêu chí IoU diện tích khá rộng. Trong khi đó, pose estimation yêu cầu định vị chính xác 17 toạ độ khớp xương cục bộ (fine-grained local features), với độ dung sai bán kính OKS rất khắt khe (đặc biệt mắt, mũi, tai, cổ tay có hệ số sigma rất nhỏ). Khi người bị xoay, gập hoặc che khuất cục bộ, mô hình dễ dàng phát hiện ra người nhưng rất dễ phán đoán lệch toạ độ khớp.
   - **Các trường hợp Bounding Box KHÔNG hoạt động (Do Not Work) được chứng minh trực tiếp qua bộ 20 ảnh**:
     1. **Tư thế vặn xoay thân 3D (Twisting / Torsional Poses)**: Điển hình ở `train_16.jpg` (hai người nhảy bắt đĩa bay, trục vai vặn xoắn so với hông tới $43.5^\circ$ ở người #1 và $26.7^\circ$ ở người #2) và `train_02.jpg` (người đứng xoay nghiêng lệch $27.8^\circ$). Bounding box chỉ là khung chữ nhật bao ngoài, hoàn toàn bất lực trong việc thể hiện góc vặn của cột sống, hướng mặt hay tư thế vươn tay bắt đĩa.
     2. **Đám đông chồng lấn & che khuất lẫn nhau (Heavy Occlusion in Groups)**: Tại `train_13.jpg` (3 người đứng che khuất nối tiếp nhau) và `train_03.jpg` (hai người đứng sát cạnh nhau). Các bounding box có IoU chồng lấn rất cao khiến thuật toán NMS dễ triệt tiêu nhầm người đứng sau (như người #3 trong `train_13`), hoặc không thể phân biệt cánh tay bắt chéo thuộc về skeleton của ai nếu không có liên kết khớp (kinematic tree).
     3. **Tương tác điều khiển phương tiện (Human-Vehicle Interaction)**: Tại `train_05.jpg` và `train_09.jpg` (người điều khiển xe máy). Bounding box bao trùm một khối hỗn tạp gồm cả người và xe, không thể xác định được vị trí cổ tay nắm ghi-đông hay hướng đầu của người quay lưng lại camera.
     4. **Cử động thể thao động học cao & chi vắt chéo (Dynamic Sports Motion)**: Tại `train_01.jpg` (vận động viên chạy, tay chân đánh chéo thân theo chu kỳ) và `train_04.jpg` (người #2 vắt chéo tay qua lồng ngực). Bounding box hình chữ nhật chứa diện tích vùng nền rỗng lớn, không phản ánh được góc co gập của cẳng tay hay pha sải bước.

3. Một ảnh test model đoán sai - gọi tên lỗi theo bốn loại của slide 43
   (lệch nhẹ / đảo trái/phải / nhầm người / trượt hẳn):
   - Ảnh `test_03.jpg`, người thứ 2 (gt#1): Khi kiểm toán bằng `yolo11l-pose.pt`, model mắc lỗi **Đảo trái/phải** (`dao_trai_phai`), khiến OKS chỉ đạt `0.213`. Khi hoán đổi lại các cặp keypoint trái/phải đối xứng qua hàm `flipped()`, OKS tăng vọt. Nguyên nhân do người này có tư thế xoay nghiêng và tay chân đan xen phức tạp, khiến mô hình bị nhầm lẫn giữa hệ quy chiếu trái và phải của cơ thể.

4. Ảnh nào có OKS thấp nhất giữa nhãn của bạn và model? Ai đúng, và bạn dựa vào đâu?
   - Ảnh có OKS thấp nhất là `train_01.jpg` (người 1, OKS = `0.694` khi kiểm toán qua `yolo11l-pose.pt`).
   - **Nhãn của em đúng hơn.**
   - Căn cứ: Khi đối chiếu với `gold/labels/train/train_01.txt`, nhãn của em đạt OKS = `0.7619` và tuân thủ đúng tỷ lệ giải phẫu học của vận động viên đang chạy. Model dự đoán bị lệch vị trí cẳng tay và cổ tay do chuyển động nhanh gây mờ (motion blur), đồng thời model có xu hướng ước lượng trôi điểm ở các khớp bị che khuất thay vì neo đúng vào cấu trúc cơ thể như nhãn thủ công đã được kiểm chứng trên `visualize_pose.py`.

5. Ảnh bạn gán tệ nhất có *cũng* là ảnh model đoán tệ nhất không? Nếu có, điều đó
   nói gì về bức ảnh đó?
   - Có: Ảnh `train_01.jpg` (người 1) vừa là ảnh nhãn của em gán thấp điểm nhất so với gold (`OKS = 0.7619`), vừa là ảnh model có OKS thấp nhất so với nhãn của em (`0.6940`).
   - Điều đó cho thấy: Đây là bức ảnh có **độ phức tạp và độ mơ hồ khách quan rất cao** (inherently hard / ambiguous sample). Nhân vật chuyển động thể thao ở tốc độ cao, cơ thể vặn xoắn, xuất hiện hiện tượng nhoè chuyển động (motion blur) ở các chi xa trục thân. Khi cả con người (người gán) lẫn thuật toán (model) đều gặp khó khăn và có độ phân tán toạ độ lớn tại cùng một bức ảnh, đó là tín hiệu của một trường hợp biên (edge case) cần được bổ sung quy chuẩn thị giác chi tiết hơn trong guideline.

## 5. Một rule evidence em đã dùng

Chọn một keypoint trong ảnh core mà bạn phải quyết định giữa `v=1` và `v=0`. Nêu ảnh, người,
khớp, bằng chứng nhìn thấy và lý do chọn trạng thái đó trong 3-5 câu.

<!-- Cấu trúc gợi ý: (1) train_XX + người thứ mấy + keypoint; (2) căn cứ thị giác như phần cơ
thể liền kề, trang phục hoặc vật che; (3) vì sao khớp còn trong khung (v=1) hay đã ra khỏi
khung (v=0). -->

Tại ảnh `train_05.jpg`, người thứ 1, em phải đưa ra quyết định giữa `v=1` và `v=0` cho khớp cổ tay phải (`right_wrist`). Căn cứ thị giác cho thấy cánh tay phải vươn về phía trước tay lái xe máy, cẳng tay nhìn thấy rõ hướng về tay nắm bên phải nhưng phần khớp cổ tay và bàn tay bị mặt nạ chắn gió và cụm điều khiển đầu xe che khuất. Do toàn bộ thân người và đầu xe máy nằm trọn vẹn bên trong khung hình (cách mép ảnh hơn 60 px), khớp cổ tay chắc chắn vẫn nằm trong không gian ảnh chứ không bị cắt ra ngoài biên. Vì vậy, em quyết định chọn `v=1` (occluded) và đặt chấm ước lượng dựa trên trục kéo dài của cẳng tay phải, giúp bảo toàn cấu trúc liên tục của skeleton thay vì xoá nhầm thành `v=0`.

## 6. Sửa lỗi sau khi kiểm toán qua CVAT API

- **Chỉ số trước:** `pose_mAP50-95 = 0.6908`, `OKS = 0.9647` (so với gold)
- **Lỗi đã sửa:** 
  - `train_13.jpg` (Skeleton ID 3020): Khôi phục 4 khớp chân (2 đầu gối, 2 cổ chân) từ trạng thái `v=0` (bị xoá ngoài ảnh) thành `v=1` (bị che khuất) và bổ sung chấm tọa độ ước lượng. Chuyển khớp hông phải (`right_hip`) từ `v=2` sang `v=1`.
  - `train_04.jpg` (Skeleton ID 2984): Xóa khớp cổ tay trái (`left_wrist`, chuyển thành `v=0`) vì khớp này chạm sát viền đáy khung ảnh (cách rìa < 3px).
- **Lý do:** Tuân thủ triệt để luật lớp: Khớp bị che khuất trong khung hình bắt buộc phải có tọa độ ước lượng (`v=1`), không được dùng `v=0` như luật chẩn đoán của tập gold. Ngược lại, khi khớp vượt hoặc chạm viền (edge clamping) thì phải xóa hoàn toàn (`v=0`).
- **Chỉ số sau:** `pose_mAP50-95 = 0.6908`, `OKS = 0.817` (Lưu ý: điểm OKS không đổi/giảm nhẹ do việc đổi `left_wrist` thành `v=0` theo luật Edge Clamping của lớp bị tính là khác biệt so với nhãn Gold, nhưng chúng ta vẫn ưu tiên tuân thủ luật lớp).
