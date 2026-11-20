# Loyalty Point Blockchain

Aplikasi sistem poin loyalitas berbasis blockchain menggunakan **Solidity, Hardhat, Streamlit, Web3.py, dan MetaMask**. Aplikasi menyediakan pengelolaan customer, merchant, poin, katalog reward, riwayat transaksi, serta NFT reward.

## Fitur

- **Dashboard:** menampilkan total customer, total poin beredar, jumlah transaksi, dan peran wallet yang sedang terhubung.
- **Login berbasis wallet:** MetaMask digunakan untuk mengenali akun dan menentukan peran.
- **Admin:** mengatur status merchant, menyetujui atau menolak pengajuan poin, mengelola katalog reward, serta melihat customer dan transaksi.
- **Merchant:** mendaftarkan customer, mengajukan poin, dan menukarkan poin dengan reward.
- **Customer:** melihat saldo poin, NFT reward, katalog reward, dan riwayat transaksi milik wallet sendiri.
- **Blockchain Lab:** membaca dan menjalankan fungsi Smart Contract melalui aplikasi.

## Teknologi dan versi

| Komponen | Versi |
|---|---|
| Python | Disarankan Python 3.11 atau lebih baru |
| Streamlit | `1.67.0` |
| Web3.py | `8.0.0` |
| Solidity | `0.8.28` |
| Hardhat | Gunakan versi yang tercantum pada `package.json` proyek |
| MetaMask | Ekstensi browser MetaMask |

> Solidity merupakan compiler Smart Contract, bukan paket Python. Versinya diatur pada `hardhat.config.js`.

## Struktur proyek

Pastikan repository memiliki file dan folder utama seperti berikut. Nama file aplikasi dapat disesuaikan dengan nama yang digunakan di repository.

```text
Loyalty_Blockchain/
├── contracts/
│   └── LoyaltyPoint.sol
├── scripts/
│   └── deploy.js
├── artifacts/                 # Dibuat otomatis setelah compile
├── cache/                     # Dibuat otomatis oleh Hardhat
├── node_modules/              # Dibuat oleh npm install
├── .venv/                     # Virtual environment Python
├── loyaltyapp.py              # Aplikasi Streamlit
├── hardhat.config.js
├── package.json
├── package-lock.json
├── requirements.txt
├── .gitignore
└── README.md
```

Folder `artifacts`, `cache`, `node_modules`, dan `.venv` tidak perlu diunggah ke GitHub. Folder tersebut dapat dibuat kembali dengan langkah instalasi di bawah ini.

## Persyaratan

Sebelum memulai, instal:

1. Python (disarankan 3.11 atau lebih baru).
2. Node.js versi LTS dan npm.
3. MetaMask pada browser.
4. Git (jika mengambil repository melalui Git).

## 1. Clone repository

```bash
git clone <URL_REPOSITORY_GITHUB>
cd <NAMA_FOLDER_REPOSITORY>
```

Jika repository sudah diunduh, buka terminal pada folder utama proyek.

## 2. Instal dependency Node.js

```bash
npm install
```

Pastikan `package.json` mencantumkan Hardhat serta dependency yang digunakan kontrak. Jika `LoyaltyPoint.sol` menggunakan OpenZeppelin ERC-721, pastikan `@openzeppelin/contracts` juga tercantum sebagai dependency.

## 3. Atur versi Solidity

Pastikan `hardhat.config.js` mengatur compiler Solidity ke `0.8.28`. Contoh konfigurasi untuk Hardhat 2 dengan CommonJS:

```javascript
require("@nomicfoundation/hardhat-toolbox");

module.exports = {
  solidity: "0.8.28",
  networks: {
    localhost: {
      url: "http://127.0.0.1:8545"
    }
  }
};
```

Jika konfigurasi proyek sudah memiliki plugin atau pengaturan lain, pertahankan pengaturan tersebut dan pastikan nilai `solidity` adalah `"0.8.28"`.

## 4. Instal dependency Python

Buat virtual environment:

**Windows PowerShell**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Jika PowerShell memblokir aktivasi script, gunakan Command Prompt:

```bat
.venv\Scripts\activate.bat
```

Kemudian instal paket sesuai `requirements.txt`:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Isi `requirements.txt` yang digunakan:

```text
streamlit==1.67.0
web3==8.0.0
```

## 5. Compile Smart Contract

Dari folder utama proyek, jalankan:

```bash
npx hardhat compile
```

Jika berhasil, Hardhat akan membuat folder `artifacts/` dan `cache/`. Aplikasi Streamlit membaca ABI dari:

```text
artifacts/contracts/LoyaltyPoint.sol/LoyaltyPoint.json
```

Karena itu, jangan menghapus hasil compile ketika aplikasi sedang dijalankan.

## 6. Jalankan blockchain lokal

Buka **Terminal 1** pada folder proyek:

```bash
npx hardhat node
```

Hardhat akan menjalankan jaringan lokal pada:

```text
RPC URL : http://127.0.0.1:8545
Chain ID: 31337 (0x7a69)
```

Biarkan terminal ini tetap berjalan. Hardhat akan menampilkan beberapa akun pengujian beserta private key. Akun tersebut hanya untuk jaringan lokal/pengembangan; jangan gunakan private key pengujian untuk aset sungguhan.

## 7. Deploy Smart Contract

Buka **Terminal 2** pada folder proyek, lalu jalankan:

```bash
npx hardhat run scripts/deploy.js --network localhost
```

Salin alamat kontrak yang ditampilkan setelah deployment. Setiap deployment baru menghasilkan alamat kontrak baru.

### Mengatur alamat kontrak pada aplikasi

Aplikasi menggunakan alamat kontrak default pada variabel `DEFAULT_CONTRACT`. Perbarui nilainya dengan alamat hasil deployment terbaru, atau gunakan environment variable `LOYALTY_CONTRACT` jika aplikasi telah dikonfigurasi untuk membacanya.

Contoh PowerShell:

```powershell
$env:LOYALTY_CONTRACT="ALAMAT_KONTRAK_HASIL_DEPLOY"
```

Pastikan alamat kontrak tersebut berasal dari deployment pada Hardhat Local yang sedang berjalan.

## 8. Hubungkan MetaMask ke Hardhat Local

Tambahkan jaringan berikut pada MetaMask:

| Pengaturan | Nilai |
|---|---|
| Network Name | Hardhat Local |
| RPC URL | `http://127.0.0.1:8545` |
| Chain ID | `31337` |
| Currency Symbol | `ETH` |

Pilih jaringan **Hardhat Local**. Untuk pengujian, impor salah satu akun pengujian yang ditampilkan oleh perintah `npx hardhat node` ke MetaMask. Private key tersebut hanya untuk blockchain lokal.

Peran ditentukan dari data Smart Contract:

- **Admin:** akun yang melakukan deployment kontrak.
- **Merchant:** wallet yang diaktifkan oleh Admin melalui fungsi pengaturan merchant.
- **Customer:** wallet yang didaftarkan oleh Merchant.
- **Guest:** wallet yang belum terdaftar sebagai Admin, Merchant, atau Customer.

Menu yang tersedia pada aplikasi mengikuti peran wallet yang terhubung. Customer hanya dapat melihat data customer milik wallet yang sedang login.

## 9. Jalankan aplikasi Streamlit

Pastikan Hardhat node masih berjalan dan kontrak sudah berhasil di-deploy. Pada terminal berikutnya, aktifkan virtual environment jika belum aktif, lalu jalankan:

```bash
streamlit run loyaltyapp.py
```

Jika nama file aplikasi berbeda, ganti `loyaltyapp.py` dengan nama file yang benar, misalnya:

```bash
streamlit run loyaltyapp_admin_table_see_more.py
```

Streamlit biasanya membuka aplikasi pada alamat:

```text
http://localhost:8501
```

Klik **Connect Wallet**, pilih akun MetaMask, dan pastikan jaringan yang dipilih adalah Hardhat Local.

## 10. Urutan pengujian aplikasi

1. Hubungkan akun Admin (akun yang digunakan saat deployment).
2. Buka halaman Admin dan aktifkan alamat wallet sebagai Merchant.
3. Ganti MetaMask ke akun Merchant yang telah diaktifkan.
4. Daftarkan alamat wallet lain sebagai Customer.
5. Ajukan poin untuk ID Customer tersebut.
6. Kembali ke akun Admin dan setujui atau tolak pengajuan poin.
7. Dari akun Admin, tambahkan reward pada Reward Catalog.
8. Kembali ke akun Merchant untuk menukarkan poin Customer dengan reward.
9. Hubungkan akun Customer untuk memeriksa saldo, riwayat transaksi, dan NFT reward.

## Catatan penting

- Jalankan `npx hardhat node` sebelum deployment dan sebelum menggunakan aplikasi.
- Jangan menutup terminal Hardhat node selama aplikasi digunakan.
- Jika Hardhat node dihentikan dan dijalankan ulang, blockchain lokal biasanya kembali ke kondisi awal. Kontrak perlu di-deploy ulang dan alamat kontrak pada aplikasi perlu diperbarui.
- Deployment ulang membuat kontrak baru dengan data kosong. Customer, merchant, saldo, reward, transaksi, dan NFT dari deployment sebelumnya tidak otomatis dipindahkan.
- Jangan pernah mengunggah private key, seed phrase, file `.env`, atau kredensial pribadi ke repository publik.
- `artifacts/`, `cache/`, `node_modules/`, dan `.venv/` dapat dibuat kembali dan sebaiknya dimasukkan ke `.gitignore`.

## Troubleshooting

**Hardhat RPC tidak dapat diakses**

Pastikan `npx hardhat node` sedang berjalan pada `http://127.0.0.1:8545`.

**ABI tidak ditemukan**

Jalankan kembali:

```bash
npx hardhat compile
```

**Alamat kontrak tidak memiliki kode**

Periksa apakah alamat kontrak pada aplikasi sama dengan alamat hasil deployment terbaru pada jaringan Hardhat Local.

**MetaMask menunjukkan jaringan berbeda**

Pilih jaringan Hardhat Local dengan Chain ID `31337`.

**Transaksi gagal karena akun bukan Admin atau Merchant**

Pastikan wallet yang terhubung memiliki peran yang sesuai dan gunakan akun Admin yang melakukan deployment untuk fungsi khusus Admin.

---

Dibuat untuk proyek praktikum **Loyalty Point Blockchain**.
