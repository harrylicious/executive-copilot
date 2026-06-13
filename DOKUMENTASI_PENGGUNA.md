# 📘 Dokumentasi Pengguna — Executive Copilot

> Panduan lengkap untuk pengguna non-teknis aplikasi Executive Copilot milik PT. Jembatan Baru.

---

## Daftar Isi

- [Apa Itu Executive Copilot?](#apa-itu-executive-copilot)
- [Siapa yang Menggunakan?](#siapa-yang-menggunakan)
- [Fitur Utama](#fitur-utama)
- [Cara Mengakses Aplikasi](#cara-mengakses-aplikasi)
- [Halaman-Halaman Aplikasi](#halaman-halaman-aplikasi)
- [Cara Menggunakan Copilot Chat (Tanya AI)](#cara-menggunakan-copilot-chat-tanya-ai)
- [Pengelolaan Knowledge Base (Basis Pengetahuan)](#pengelolaan-knowledge-base-basis-pengetahuan)
- [Struktur Knowledge Base di Backend](#struktur-knowledge-base-di-backend)
- [Hak Akses Berdasarkan Peran](#hak-akses-berdasarkan-peran)
- [Pengaturan Aplikasi](#pengaturan-aplikasi)
- [FAQ (Pertanyaan Umum)](#faq-pertanyaan-umum)

---

## Apa Itu Executive Copilot?

Executive Copilot adalah **asisten digital cerdas berbasis AI** yang dibuat khusus untuk PT. Jembatan Baru. Bayangkan memiliki seorang asisten yang sudah membaca dan memahami semua dokumen perusahaan — mulai dari data barang, data outlet, laporan keuangan, hingga dokumen logistik — dan bisa menjawab pertanyaan Anda kapan saja dalam Bahasa Indonesia.

### Apa yang bisa dilakukan?

| Kebutuhan Anda | Yang Dilakukan Executive Copilot |
|---|---|
| "Berapa jumlah outlet di Mataram?" | Menjawab langsung dari data master outlet |
| "Produk Blue Band mana yang paling mahal?" | Mencari dan membandingkan harga dari database |
| "Tampilkan dokumen departemen Finance" | Menampilkan daftar file terorganisir per departemen |
| "Hubungan antara dokumen A dan B?" | Menampilkan graph visual koneksi antar dokumen |

---

## Siapa yang Menggunakan?

Aplikasi ini dirancang untuk tiga jenis pengguna:

| Peran | Untuk Siapa | Akses |
|---|---|---|
| **Admin** | Tim IT / Administrator | Akses penuh ke semua fitur dan departemen |
| **Executive** | Direksi / Manajer Senior | Akses semua data dan departemen, tanpa manajemen user |
| **Staff** | Karyawan Departemen | Hanya akses data departemennya sendiri |

---

## Fitur Utama

### 1. 💬 Copilot Chat (Tanya AI)
Tanyakan apa saja dalam Bahasa Indonesia tentang data perusahaan. AI akan mencari jawaban dari dokumen yang sudah di-upload dan memberikan jawaban dengan sumber yang jelas.

### 2. 📁 Knowledge Base (Basis Pengetahuan)
Tempat semua dokumen perusahaan disimpan, dikelola, dan diindeks. Dokumen diorganisir per departemen.

### 3. 📊 Dashboard
Ringkasan aktivitas: jumlah dokumen, tren pertanyaan, statistik per departemen.

### 4. 🔍 Search (Pencarian)
Cari dokumen atau informasi spesifik menggunakan pencarian cerdas berbasis vektor.

### 5. 🕸️ Knowledge Graph
Visualisasi interaktif yang menunjukkan hubungan antar dokumen (misal: dokumen A mereferensi dokumen B).

### 6. 📥 Ingestion (Upload Dokumen)
Sistem untuk mengunggah dokumen baru ke dalam knowledge base dengan proses validasi otomatis.

### 7. 👥 Manajemen User & Departemen
(Khusus Admin) Kelola pengguna dan struktur departemen.

---

## Cara Mengakses Aplikasi

1. Buka browser (Chrome/Edge/Firefox disarankan)
2. Akses alamat: `http://[alamat-server]:5173`
3. Masukkan email dan password
4. Anda akan masuk ke halaman Dashboard

### Akun Demo

| Email | Password | Peran | Departemen |
|---|---|---|---|
| admin@jembatanbaru.co.id | admin123 | Admin | Accounting Tax |
| director@jembatanbaru.co.id | exec123 | Executive | Board |
| demand@jembatanbaru.co.id | demand123 | Staff | Demand Supply |
| finance@jembatanbaru.co.id | finance123 | Staff | Finance |

---

## Halaman-Halaman Aplikasi

### Dashboard
- Melihat ringkasan KPI (jumlah dokumen, jumlah query, akurasi)
- Grafik tren pertanyaan 7 hari terakhir
- Distribusi query per departemen
- Aktivitas terbaru

### Chat (Copilot)
- Antarmuka percakapan dengan AI
- Jawaban real-time (streaming)
- Setiap jawaban disertai sumber dokumen
- Mendukung percakapan multi-giliran (bisa tanya lanjutan)

### Knowledge Base
- Jelajahi dokumen per departemen
- Upload dokumen baru
- Lihat detail file (tipe, ukuran, tag, status)
- Kelola tag dokumen

### Explorer
- Jelajahi struktur folder knowledge base
- Navigasi berdasarkan hierarki departemen

### Graph (Visualisasi)
- Lihat peta hubungan antar dokumen
- Node = dokumen, garis = hubungan/referensi
- Bisa tambah/hapus hubungan manual

### Search
- Pencarian cerdas berbasis makna (bukan hanya kata kunci)
- Tiga mode: lokal (vektor), global (komunitas), kombinasi

### Ingestion Dashboard
- (Khusus Admin) Pantau proses upload dan indexing dokumen
- Lihat status job: berhasil, gagal, dalam proses

### Pengaturan
- Ubah profil
- Konfigurasi chatbot (bahasa, nuansa formal/santai)
- Atur notifikasi

---

## Cara Menggunakan Copilot Chat (Tanya AI)

### Langkah-langkah:
1. Klik ikon 💬 (pesan) di pojok kanan bawah, atau pilih menu "Chat" di sidebar
2. Ketik pertanyaan Anda dalam Bahasa Indonesia
3. Tunggu jawaban muncul secara streaming (kata per kata)
4. Perhatikan bagian **"Sumber"** di bawah jawaban — ini menunjukkan dokumen mana yang digunakan

### Contoh Pertanyaan yang Bisa Ditanyakan:

| Kategori | Contoh Pertanyaan |
|---|---|
| Data Barang | "Berapa harga Sania Botol 1 liter?" |
| Data Barang | "Produk apa saja yang harganya di atas Rp 500.000?" |
| Data Barang | "Ada berapa total produk dari vendor Upfield?" |
| Data Outlet | "Berapa jumlah outlet di kota Lombok Barat?" |
| Data Outlet | "Sebutkan outlet bertipe Wholesale di Mataram" |
| Data Distributor | "Siapa saja vendor/distributor yang terdaftar?" |
| Umum | "Apa saja isi dokumen master data ini?" |

### Tips Agar Jawaban Lebih Akurat:
- Gunakan istilah yang spesifik (nama produk, nama kota, tipe outlet)
- Untuk pertanyaan angka/total, AI sudah memiliki ringkasan statistik lengkap
- Jika jawaban kurang tepat, coba rephrase pertanyaan dengan lebih detail
- Anda bisa bertanya lanjutan ("Bandingkan dengan Q2", "Jelaskan lebih detail")

### Mode Pencarian dalam Chat:
- **Local**: Mencari kesamaan makna di dokumen (cocok untuk pertanyaan spesifik)
- **Global**: Mencari berdasarkan topik/komunitas dokumen (cocok untuk pertanyaan luas)
- **Combined**: Gabungan keduanya (default, paling lengkap)

---

## Pengelolaan Knowledge Base (Basis Pengetahuan)

### Apa Itu Knowledge Base?
Knowledge Base adalah **kumpulan semua dokumen perusahaan** yang sudah diproses dan disimpan agar bisa dicari dan ditanyakan melalui AI. Ini seperti "otak" dari Executive Copilot.

### Format Dokumen yang Didukung:
- 📄 PDF
- 📝 Word (.docx)
- 📊 Excel (.xlsx, .xls)
- 📋 CSV
- 📑 Text (.txt)
- 📝 Markdown (.md)
- 🖼️ Gambar (.png, .jpg, .tiff) — diproses dengan OCR

### Cara Upload Dokumen:
1. Buka halaman **Knowledge Base** atau **Ingestion**
2. Pilih departemen tujuan
3. Pilih subfolder yang sesuai
4. Upload file
5. Sistem akan otomatis memproses: validasi → ekstraksi teks → pemotongan → embedding

### Proses di Balik Layar (Apa yang Terjadi Setelah Upload):
```
Upload File
    ↓
1. Validasi (cek format, ukuran, duplikat)
    ↓
2. Preprocessing (OCR jika gambar, normalisasi teks, redaksi PII)
    ↓
3. Chunking (potong dokumen jadi bagian-bagian kecil yang bermakna)
    ↓
4. Embedding (ubah teks jadi representasi numerik untuk pencarian)
    ↓
5. Tersimpan dan Siap Dicari!
```

---

## Struktur Knowledge Base di Backend

Ini adalah bagian penting yang menjelaskan bagaimana dokumen diorganisir di dalam sistem.

### Struktur Folder

```
knowledge_base/
├── master/                          ← DATA MASTER (induk)
│   ├── barang/                      ← Data produk/barang
│   │   └── Master_Barang_xxx.xlsx
│   ├── outlet/                      ← Data outlet/toko
│   └── distributor/                 ← Data vendor/distributor
│
└── departments/                     ← DOKUMEN DEPARTEMEN
    ├── demand_supply/               ← Dept. Demand-Supply Planning
    │   ├── demand_plans/
    │   ├── supply_plans/
    │   ├── deal_orders/
    │   ├── forecasts/
    │   └── reference/
    │
    ├── accounting_tax/              ← Dept. Controller Accounting Tax
    │   ├── invoices/
    │   ├── transactions/
    │   ├── tax_reports/
    │   ├── journal_entries/
    │   └── policies/
    │
    ├── logistic/                    ← Dept. Logistic
    │   ├── inbound/
    │   ├── outbound/
    │   ├── warehouse/
    │   ├── shipping_docs/
    │   └── sops/
    │
    └── finance/                     ← Dept. Finance
        ├── cashflow/
        ├── payments/
        ├── receivables/
        ├── budgets/
        └── reports/
```

### Penjelasan Dua Jenis Data

#### 1. 📘 Master Data (`master/`)
Ini adalah **data referensi utama** perusahaan yang digunakan oleh semua departemen:

| Subfolder | Isi | Contoh |
|---|---|---|
| `barang` | Data produk/SKU | Nama produk, harga, satuan, dimensi, vendor |
| `outlet` | Data toko/pelanggan | Nama outlet, tipe, alamat, kota, area |
| `distributor` | Data supplier/vendor | Nama vendor, alamat, status |

Master data ini bersifat **lintas departemen** — artinya semua pengguna bisa mengakses data ini saat bertanya ke AI. Saat ini berisi:
- **45 produk** (Blue Band, Sania, Fortune, dll.)
- **760 outlet** tersebar di Mataram, Lombok Barat, Lombok Tengah, dll.
- **2 vendor** (Sari Agrotama Persada D dan Upfield Distribution Indonesia)

#### 2. 📂 Dokumen Departemen (`departments/`)
Ini adalah **dokumen spesifik per departemen** yang hanya bisa diakses sesuai peran:

| Departemen | Deskripsi | Subfolder Utama |
|---|---|---|
| **Demand Supply** | Rencana beli dan jual | demand_plans, supply_plans, deal_orders, forecasts |
| **Accounting Tax** | Pencatatan deal dan transaksi | invoices, transactions, tax_reports, journal_entries |
| **Logistic** | Terima, kirim, simpan barang | inbound, outbound, warehouse, shipping_docs, sops |
| **Finance** | Pengelolaan keuangan | cashflow, payments, receivables, budgets, reports |

### Sistem Dual-Index (Dua Indeks Pencarian)

Sistem Executive Copilot menggunakan **dua indeks terpisah** untuk pencarian yang lebih cerdas:

```
┌─────────────────────────────────────────────────────┐
│              PERTANYAAN PENGGUNA                      │
│         "Berapa harga Sania Botol 1l?"              │
└────────────────────────┬────────────────────────────┘
                         │
                    Query Router
                  (Deteksi Keyword)
                         │
         ┌───────────────┼───────────────┐
         ▼                               ▼
┌─────────────────┐            ┌─────────────────┐
│  MASTER INDEX   │            │   DEPT INDEX    │
│                 │            │                 │
│ Data barang,    │            │ Dokumen per     │
│ outlet,         │            │ departemen      │
│ distributor     │            │                 │
└─────────────────┘            └─────────────────┘
```

**Bagaimana cara kerjanya?**

1. **Query Router** menganalisis pertanyaan Anda dan mendeteksi kata kunci dalam Bahasa Indonesia
2. Jika pertanyaan tentang barang/produk/harga → sistem mencari di **Master Index**
3. Jika pertanyaan tentang outlet/toko → sistem mencari di **Master Index**
4. Jika pertanyaan tentang dokumen departemen → sistem mencari di **Dept Index**
5. Hasil dari kedua indeks bisa digabung untuk jawaban yang lebih lengkap

### Tingkat Kerahasiaan Dokumen (Sensitivity Level)

Setiap subfolder memiliki tingkat kerahasiaan otomatis:

| Level | Subfolder | Artinya |
|---|---|---|
| 🔴 **Confidential** | deal_orders, tax_reports, reports, budgets, payments | Hanya yang berwenang |
| 🟡 **Internal** | invoices, transactions, warehouse, forecasts, dll. | Untuk internal perusahaan |
| 🟢 **Public Internal** | sops, reference, policies, shipping_docs | Bisa dilihat lebih luas |

### Auto-Tagging (Pemberian Tag Otomatis)

Saat dokumen di-upload, sistem secara otomatis memberikan tag berdasarkan nama file:

| Kata Kunci di Nama File | Tag yang Diberikan |
|---|---|
| "invoice" | invoice, accounting |
| "deal_beli" | deal, pembelian, demand_supply |
| "cashflow" | cashflow, keuangan, finance |
| "stok" | stok, warehouse, logistic |
| "forecast" | forecast, perencanaan |
| "tax" | pajak, tax, accounting |

---

## Hak Akses Berdasarkan Peran

| Fitur | Admin | Executive | Staff |
|---|---|---|---|
| Dashboard (semua data) | ✅ | ✅ | Dept sendiri saja |
| Copilot Chat | Semua dept | Semua dept | Dept sendiri + master |
| Knowledge Base | Semua dept | Semua dept | Dept sendiri saja |
| Upload Dokumen | ✅ | ✅ | Dept sendiri saja |
| Manajemen User | ✅ | ❌ | ❌ |
| Manajemen Departemen | ✅ (CRUD) | Lihat saja | ❌ |
| Ingestion Dashboard | ✅ | ❌ | ❌ |
| Pengaturan Profil | ✅ | ✅ | ✅ |

> **Catatan penting**: Staff hanya bisa bertanya dan melihat dokumen dari departemennya sendiri. Namun, data master (barang, outlet, distributor) bisa diakses oleh semua peran.

---

## Pengaturan Aplikasi

### Konfigurasi Chatbot

Di halaman Settings, Anda bisa mengatur:

| Pengaturan | Pilihan | Keterangan |
|---|---|---|
| **Bahasa** | Indonesia, English | Bahasa jawaban AI |
| **Nuansa** | Formal, Santai, Profesional, Ramah, Tegas | Gaya bahasa jawaban |
| **Batasi Lintas Dept** | Ya / Tidak | Apakah staff hanya bisa tanya seputar dept-nya |

### Tema Tampilan
- **Dark Mode** (gelap) — default
- **Light Mode** (terang) — bisa diubah lewat tombol ☀️/🌙

---

## FAQ (Pertanyaan Umum)

### Q: Berapa besar file yang bisa di-upload?
**A:** Maksimal 100 MB per file.

### Q: Format apa saja yang didukung?
**A:** PDF, DOCX, XLSX, XLS, CSV, TXT, MD, PNG, JPG, TIFF.

### Q: Berapa lama proses setelah upload?
**A:** Untuk dokumen teks biasa (PDF, Word), biasanya beberapa detik. Untuk file gambar yang perlu OCR, bisa memakan waktu lebih lama.

### Q: Kenapa AI tidak bisa menjawab pertanyaan saya?
**A:** Kemungkinan:
1. Data yang ditanyakan belum di-upload ke knowledge base
2. Pertanyaan terlalu ambigu — coba lebih spesifik
3. Data yang diminta memang tidak ada di dokumen (misal: data penjualan/transaksi belum di-upload)

### Q: Apakah AI bisa salah?
**A:** Ya, AI bisa salah. Selalu perhatikan bagian "Sumber" di jawaban untuk memverifikasi. Jika tidak yakin, cross-check dengan dokumen asli.

### Q: Apakah data saya aman?
**A:** Ya. Sistem menggunakan:
- Role-based access control (akses berdasarkan peran)
- Tingkat kerahasiaan per subfolder
- Redaksi PII (data pribadi) otomatis saat ingestion
- Data tidak dikirim ke luar server kecuali ke OpenAI untuk generate jawaban

### Q: Siapa yang harus saya hubungi jika ada masalah?
**A:** Hubungi tim IT/Administrator yang mengelola sistem ini.

---

## Glosarium (Istilah Teknis)

| Istilah | Artinya |
|---|---|
| **Knowledge Base** | Kumpulan dokumen perusahaan yang sudah diindeks |
| **Embedding** | Representasi numerik dari teks agar bisa dicari berdasarkan makna |
| **Chunking** | Proses memotong dokumen besar menjadi bagian-bagian kecil |
| **Vector Search** | Pencarian berdasarkan kesamaan makna (bukan hanya kata yang sama) |
| **RAG** | Retrieval-Augmented Generation — AI menjawab berdasarkan dokumen, bukan mengarang |
| **Index/Indeks** | Struktur data yang memungkinkan pencarian cepat |
| **OCR** | Optical Character Recognition — mengubah gambar menjadi teks |
| **PII** | Personally Identifiable Information — data pribadi yang disamarkan |
| **Sync** | Proses sinkronisasi antara file di folder dan database |
| **SSE** | Server-Sent Events — teknologi untuk jawaban streaming (kata per kata) |

---

*Dokumentasi ini terakhir diperbarui: Juni 2026*
*Versi aplikasi: 0.1.0*
