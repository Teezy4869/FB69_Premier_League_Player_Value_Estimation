# FB69 — Premier League Player Market Value Estimation

Dự án ước lượng giá trị thị trường cầu thủ English Premier League (EPL), kết hợp chỉ số thi đấu từ **FotMob** với lịch sử định giá **Transfermarkt**.

- Phạm vi nghiên cứu: 5 mùa **2020/21 – 2024/25** (`configs/research_scope.yaml`).
- Mùa **2025/26** là holdout, chỉ chấm điểm một lần.

## Project Goals

1. Thu thập và kiểm định dữ liệu FotMob (audit, collection, release v3.1).
2. Tích hợp target giá trị Transfermarkt cuối mùa (latest valuation ≤ season end), entity resolution FotMob ↔ Transfermarkt.
3. Phân tích khám phá (EDA) và xây dựng đặc trưng.
4. Huấn luyện và đánh giá mô hình hồi quy giá trị cầu thủ, so sánh với baseline persistence.
5. Đánh giá trên mùa holdout 2025/26.

## Repository Structure

```text
├── Report/
│   ├── FB69_report.ipynb      # Notebook báo cáo chính
│   └── reports/               # Báo cáo, audit và manifest theo từng phase
├── SourceCode/
│   ├── src/                   # Pipeline: audit, collection, phase3, phase4, phase5, holdout, research_scope
│   ├── tests/                 # Unit/integration tests
│   └── configs/               # Cấu hình YAML/JSON
├── requirements.txt
└── README.md
```

## Technologies Used

Python 3.10+, pandas, PyArrow (Parquet), DuckDB, PyYAML, RapidFuzz, scikit-learn, LightGBM, requests, Matplotlib/Seaborn.

## Setup

```bash
python -m venv .venv
pip install -r requirements.txt
cd SourceCode
python -m unittest discover -s tests -v
```

Chạy các module từ thư mục `SourceCode/`, ví dụ `python -m src.audit.final_review`.

## Data Sources

- FotMob — chỉ số thi đấu cầu thủ.
- Transfermarkt historical valuations qua [dcaribou/transfermarkt-datasets](https://github.com/dcaribou/transfermarkt-datasets).

Thư mục `data/` **không được đưa lên repo** (dung lượng lớn và điều khoản của nguồn dữ liệu). Pipeline trong `SourceCode/` tái tạo dữ liệu từ nguồn.

## License

Dự án phục vụ mục đích học tập và nghiên cứu (PTIT — Học máy). Không sử dụng dữ liệu thu thập cho mục đích thương mại.
