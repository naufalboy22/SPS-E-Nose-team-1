# Pengembangan Aplikasi GUI untuk Visualisasi Data Electronic Nose (eNose) dengan Backend Rust dan Frontend Qt Python

# Electronic Nose (eNose) Data Visualization Application  
**Signal Processing Course – Project-Based Learning (Odd Semester 2025/2026)**  
Department of Instrumentation Engineering  

![eNose System Overview](docs/images/system_overview.jpg)  
*(Ganti gambar di atas dengan foto sistem eNose kelompokmu)*

## Project Title
**Development of GUI Application for Electronic Nose (eNose) Data Visualization with Rust Backend and Qt Python Frontend**

## Team Members
| No | Name                          | Student ID     |
|----|-------------------------------|----------------|
| 1  | Naufaliano Saputra            | 2042241024     |
| 2  | Revi Azizu Rohman             | 2042241029     |
| 3  | Anisa Zulfa Ahsanah           | 2042241040     |

Tested sample: **Tembakau (Apel, Ice Melon, Malboro Ice, Malboro )** 

## Project Overview
This project implements a complete electronic nose system capable of:
- Real-time gas sensor data acquisition from Arduino Uno R4 WiFi
- Serial communication & heavy signal processing handled by a Rust backend
- Modern desktop GUI built with Python Qt6 (PySide6) for live visualization
- Saving datasets in CSV/JSON format
- Offline visualization using GNUPLOT scripts

## System Architecture
Arduino/
├── emose_backend/                  # Root folder proyek backend
│   ├── src/
│   │   └── main.rs                 # Entry point aplikasi (Rust backend)
│   ├── target/                     # Build artifacts (otomatis oleh Cargo)
│   ├── .gitignore
│   ├── Cargo.lock
│   ├── Cargo.toml                  # Konfigurasi proyek Rust & dependencies
│   ├── influxdb2-2.7.12-windows/   # Binary InfluxDB lokal (Windows)
│   ├── pbl_env/                    # Virtual environment Python
│   ├── sampling_history/           # Folder penyimpanan data sampling/history
│   └── venv/                       # Python virtual environment
│       ├── dashboard.json          # Konfigurasi dashboard (biasanya untuk Grafana/InfluxDB)
│       ├── gui_frontend.py         # Script GUI frontend (Python)
│       ├── temp_ei_upload.csv      # File CSV temporary untuk data upload EI
│       └── temp_upload_ei.csv      # File CSV temporary untuk data upload EI

