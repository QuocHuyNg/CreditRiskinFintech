# 📊 CreditScore AI – Intelligent Credit Scoring & Risk-Based Pricing System

**CreditScore AI** là một hệ thống ứng dụng tài chính thông minh (Fintech) được xây dựng để đánh giá rủi ro tín dụng của khách hàng cá nhân dựa trên các thuật toán Học máy (Machine Learning) tiên tiến. Ứng dụng cung cấp các công cụ phân tích rủi ro, dự đoán xác suất vỡ nợ (Probability of Default - PD), quy đổi điểm tín dụng chuẩn quốc tế (300 - 850), định giá khoản vay tối ưu theo mức rủi ro, và giải thích quyết định của mô hình AI (Explainable AI - XAI).

---

## ✨ Các tính năng cốt lõi

### 1. 🔐 Hệ thống Xác thực An toàn (User Authentication)
- Màn hình đăng nhập/đăng ký dạng **kính mờ (Glassmorphic Auth Overlay)** bảo vệ hệ thống, ngăn chặn truy cập trái phép vào Dashboard.
- Mã hóa mật khẩu bảo mật một chiều bằng thuật toán băm **PBKDF2** thông qua thư viện `werkzeug.security`.
- Lưu trữ tài khoản người dùng bằng cơ sở dữ liệu **SQLite** (`users.db`).
- Duy trì phiên đăng nhập an toàn bằng cơ chế **Flask Session** (cookie được ký mã hóa).
- Tự động hiển thị tên người dùng và tạo avatar chữ cái đầu tiên (ví dụ: `Huy` ➔ `H`).

### 2. 🎯 Đánh giá Điểm tín dụng Cá nhân (Personal Credit Scoring)
- Biểu mẫu nhập liệu trực quan với **tooltip hướng dẫn chi tiết** cho từng biến tài chính.
- Trực quan hóa điểm tín dụng bằng biểu đồ đồng hồ đo (**Gauge Chart**) và phân lớp rủi ro từ *Excellent* (Xanh) đến *Very Poor* (Đỏ).
- Phân tích các nhân tố tài chính tác động tích cực hoặc tiêu cực đến điểm số.
- **Giải thích AI (Explainable AI - XAI)**: Biểu đồ thác nước (**Waterfall Chart**) mô phỏng cách mô hình cộng/trừ điểm tín dụng từ mức trung vị (Baseline) của tập dữ liệu dựa trên hồ sơ khách hàng.

### 3. 🤖 Trợ lý ảo tư vấn tài chính (NLP Chatbot)
- Cho phép người dùng nhập thông tin hồ sơ tài chính bằng ngôn ngữ tự nhiên (ví dụ: *"Tôi 35 tuổi, thu nhập 5000 USD, tỷ lệ sử dụng thẻ 20%..."*).
- Bộ phân tích cú pháp ngôn ngữ tự nhiên **Rule-based NLP Parser** tự động bóc tách các chỉ số tài chính từ câu thoại để chấm điểm trực tiếp trong khung chat.

### 4. 📂 Chấm điểm tín dụng Hàng loạt (Batch Scoring)
- Tải lên danh sách hàng nghìn khách hàng dưới dạng file **CSV** hoặc **Excel** (`.xlsx`, `.xls`).
- **Thuật toán tự động ánh xạ cột (Column Mapping)**: Tự động nhận diện và chuẩn hóa tên cột tiếng Anh hoặc tiếng Việt (có dấu/không dấu, ví dụ: `thunhap` / `tuổi` / `MonthlyIncome` ➔ chuẩn hóa cột dữ liệu đầu vào của mô hình).
- Xuất file kết quả đã chấm điểm bao gồm các trường điểm tín dụng dự báo, xác suất vỡ nợ và xếp hạng rủi ro để tải xuống nhanh chóng.

### 5. 💰 Định giá Khoản vay theo Mức rủi ro (Risk-Based Pricing)
- Tự động điều chỉnh lãi suất cho vay (Interest Rate) và phê duyệt hạn mức tối đa (Max Approved Limit) dựa trên điểm tín dụng.
- Người dùng có thể kéo trượt số tiền vay và chọn các kỳ hạn trả nợ (12 - 60 tháng).
- Tự động lập lịch trả nợ chi tiết hàng tháng (**Amortization Schedule**) hiển thị rõ số tiền gốc, tiền lãi và số dư giảm dần.

### 6. 📈 Kế hoạch hành động Cải thiện điểm tín dụng (Improvement Roadmap)
- Chạy thử nghiệm giả lập thay đổi chỉ số (**What-if Analysis**) để xem điểm số biến động tức thời.
- Tự động đề xuất lộ trình hành động thiết thực được thiết kế theo dạng ngăn kéo trượt mở rộng (**Collapsible Detailed Action Plan**) với các hướng dẫn chi tiết dành riêng cho từng hạng mục rủi ro của bạn.

---

## 🛠️ Công nghệ sử dụng

### Backend (Python/Flask)
- **Flask**: Máy chủ RESTful API xử lý logic xác thực và dự báo.
- **Scikit-Learn**: Huấn luyện và dự đoán bằng thuật toán `HistGradientBoostingClassifier` (độ chính xác ROC-AUC đạt ~0.87, hệ số Gini ~0.74, KS ~0.58).
- **SQLite3**: Cơ sở dữ liệu lưu trữ tài khoản người dùng.
- **Pandas & Numpy**: Xử lý và chuẩn hóa dữ liệu hàng loạt.
- **Joblib**: Đóng gói mô hình máy học đã huấn luyện (`model.pkl`).

### Frontend (HTML5 / CSS3 / Vanilla JS)
- Giao diện xây dựng hoàn toàn bằng **Vanilla CSS3** và **HTML5** thuần giúp tối ưu hiệu năng tải trang.
- **Vanilla Javascript** điều khiển toàn bộ tương tác Single Page Application (SPA), biểu đồ SVG và gọi REST API.
- Google Material Icons & Inter Font.

---

## ⚙️ Hướng dẫn Khởi chạy ứng dụng (Windows)

Dự án cung cấp sẵn hai tệp tập lệnh `.bat` giúp quản lý server dễ dàng:

### 1. Khởi chạy Server
Bạn chỉ cần nhấp đúp vào tệp **`start.bat`** ở thư mục gốc của dự án. File này sẽ tự động:
- Kiểm tra và dừng các tiến trình đang chiếm cổng `5000` (nếu có).
- Khởi chạy máy chủ Flask ở chế độ nền (`python backend/app.py`).
- Lưu trữ logs hoạt động vào tệp `server.log`.
- Tự động mở trình duyệt và truy cập trang web tại địa chỉ: `http://localhost:5000`.

### 2. Dừng Server
Khi không sử dụng nữa, bạn nhấp đúp vào tệp **`stop.bat`**. Tệp này sẽ:
- Tìm kiếm tiến trình đang chạy Flask trên cổng `5000` và dừng hẳn tiến trình đó (`taskkill`).
- Dọn dẹp và xóa các tệp tin logs tạm thời (`server.log`).

---

## 📁 Cấu trúc thư mục dự án

```text
CreditRiskInFintech/
├── backend/
│   ├── app.py            # Flask Web Server & REST API endpoints
│   ├── train_model.py    # Script tiền xử lý và huấn luyện mô hình ML
│   ├── model.pkl         # File lưu trữ mô hình và metadata đã đóng gói
│   └── users.db          # Cơ sở dữ liệu SQLite lưu trữ tài khoản người dùng
├── frontend/
│   ├── index.html        # Trang giao diện chính (SPA Dashboard)
│   ├── style.css         # Thiết kế giao diện (Design System & Animations)
│   └── app.js            # Điều khiển logic giao diện, chatbot & gọi API
├── start.bat             # Tập lệnh khởi chạy nhanh server
├── stop.bat              # Tập lệnh dừng server
├── cs-training.csv       # Dữ liệu huấn luyện (Give Me Some Credit - Kaggle)
├── cs-test.csv           # Dữ liệu thử nghiệm
├── UIUX.png              # Hình ảnh mô tả thiết kế giao diện
└── README.md             # Tài liệu hướng dẫn dự án
```
