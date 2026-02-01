# Document_Management_System
### MinIO + FastAPI + docker + Intelligent Compression

Bu proje; PDF ve görsel sözleşme dosyalarının **MinIO (S3 uyumlu)** object storage üzerinde,
**akıllı sıkıştırma**, **metadata yönetimi** ve **ölçeklenebilir mimari** ile saklanmasını sağlayan
bir **Doküman Yönetim Sistemi (DMS) Prototipi**dir.

Proje; mevcut DYS sistemlerinden veri alıp MinIO tabanlı yeni bir mimariye geçişi
test etmek amacıyla geliştirilmiştir.

---

## Amaç & Kapsam

- Günlük yüksek hacimli doküman yüklerini (≈13 GB/gün) yönetmek
- PDF ve görselleri akıllı biçimde sıkıştırarak depolama maliyetini düşürmek
- Metadata’yı dosyadan bağımsız, yapılandırılmış biçimde saklamak
- Mevcut sistemlerden (DYS) bağımsız, yatayda ölçeklenebilir mimari oluşturmak
- POC → PROD geçişine hazır altyapı kurmak

---

##  Mimari Genel Bakış

Client (curl / UI / servis)
|
v
FastAPI (Upload API)
|
|--> Compression Engine
| -> JPEG re-encode
| -> PDF (Ghostscript / PikePDF)
|
v
MinIO (S3 Compatible Storage)
|
|--> PDF / Image
|--> metadata.pb (Protobuf)

## Path & Bucket Yapısı

# MinIO’da her dosya aşağıdaki formatta saklanır:

K/{user_uuid}/{timestamp}/upload_pdf/
├── sozlesme.pdf
└── metadata.pb


> MinIO’da klasör yoktur, bu yapı **object key prefix** olarak tutulur.

---

##  Kullanılan Teknolojiler

- **FastAPI** – REST API
- **MinIO** – Object Storage (S3 compatible)
- **Docker / Docker Compose**
- **Ghostscript** – Agresif PDF sıkıştırma (scan PDF)
- **PikePDF** – Hafif PDF optimizasyonu (text PDF)
- **Pillow (PIL)** – JPEG sıkıştırma
- **Protobuf** – Metadata serialization
- **Python 3.9+** (önerilen: 3.10 / 3.11)

---

##  Gereksinimler

### Ortak
- Git
- Docker Desktop
- Python 3.9+

### macOS
- Homebrew
- Ghostscript

### Windows
- Ghostscript (gswin64c.exe)
- PATH veya `GHOSTSCRIPT_PATH` tanımı

---

## Kurulum Adımları

### Repoyu Klonla

git clone https://github.com/RamenChan/Document_Management_System.git
cd Document_Management_System

### Python Virtual Environment
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip


### Bağımlılıkları kurun:

pip install -r requirements.txt


### requirements.txt yoksa:

pip install fastapi uvicorn boto3 python-multipart pillow pikepdf protobuf

### MinIO’yu Docker ile Başlat
docker compose up -d


## Kontroller:

MinIO API: http://localhost:9000

MinIO Console: http://localhost:9001

Varsayılan bilgiler:

Username: minioadmin

Password: minioadmin123