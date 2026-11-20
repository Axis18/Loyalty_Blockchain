import json
import os
import re
from datetime import datetime
from pathlib import Path

import streamlit as st
import streamlit.components.v2 as components
from web3 import Web3
from web3.exceptions import ContractLogicError
from web3.logs import DISCARD

# =========================================================
# KONFIGURASI
# =========================================================

RPC_URL = "http://127.0.0.1:8545"

# Alamat kontrak hasil deploy (bisa diganti dari sidebar tanpa edit kode)
DEFAULT_CONTRACT = os.getenv(
    "LOYALTY_CONTRACT",
    "0x5FbDB2315678afecb367f032d93F642f64180aa3",
)

# ABI dibaca dari hasil "npx hardhat compile"
ARTIFACT = (
    Path(__file__).parent
    / "artifacts"
    / "contracts"
    / "LoyaltyPoint.sol"
    / "LoyaltyPoint.json"
)

STATUS = ["PENDING", "EARNED", "REDEEMED", "REJECTED"]

st.set_page_config(
    page_title="Loyalty Point Blockchain",
    page_icon="🛍️",
    layout="wide",
)



# =========================================================
# KOMPONEN 1: HUBUNGKAN METAMASK (dari contoh dosen)
# =========================================================

WALLET_HTML = """
<div>
  <button id="connect-wallet" type="button">
    Connect Wallet
  </button>
  <p id="wallet-status">Wallet belum terhubung.</p>
</div>
"""

WALLET_CSS = """
button {
    padding: 0.7rem 1rem;
    border: none;
    border-radius: 8px;
    background: var(--st-primary-color);
    color: white;
    font-weight: 600;
    cursor: pointer;
}

p {
    color: var(--st-text-color);
    overflow-wrap: anywhere;
}
"""

WALLET_JS = """
export default function(component) {
    const { parentElement, setStateValue } = component;

    const button = parentElement.querySelector("#connect-wallet");
    const status = parentElement.querySelector("#wallet-status");

    let mounted = true;

    function publish(accounts, chainId) {
        const connected = Boolean(accounts && accounts.length > 0);
        setStateValue("wallet", {
            address: connected ? accounts[0] : "",
            chainId: chainId,
            connected: connected
        });
        status.textContent = connected
            ? "Wallet terhubung: " + accounts[0]
            : "Wallet belum terhubung.";
    }

    async function readWallet() {
        if (!window.ethereum) {
            return;
        }
        const accounts = await window.ethereum.request({
            method: "eth_accounts"
        });
        const chainId = await window.ethereum.request({
            method: "eth_chainId"
        });
        if (!mounted) return;
        publish(accounts, chainId);
    }

    async function connectWallet() {
        if (!window.ethereum) {
            status.textContent =
                "MetaMask tidak ditemukan. Pasang ekstensi MetaMask.";
            return;
        }
        try {
            status.textContent = "Menunggu persetujuan akses akun...";
            await window.ethereum.request({
                method: "eth_requestAccounts"
            });
            await readWallet();
        } catch (error) {
            status.textContent =
                "Koneksi gagal: " +
                (error.message || "Kesalahan tidak diketahui");
        }
    }

    function onAccountsChanged(accounts) {
        if (!mounted) return;
        window.ethereum.request({ method: "eth_chainId" })
            .then((chainId) => {
                if (mounted) publish(accounts, chainId);
            })
            .catch(() => {});
    }

    function onChainChanged() {
        if (!mounted) return;
        readWallet().catch(() => {});
    }

    button.addEventListener("click", connectWallet);

    if (window.ethereum) {
        window.ethereum.on("accountsChanged", onAccountsChanged);
        window.ethereum.on("chainChanged", onChainChanged);
        readWallet().catch(() => {});
    }

    return () => {
        mounted = false;
        button.removeEventListener("click", connectWallet);
        if (window.ethereum && window.ethereum.removeListener) {
            window.ethereum.removeListener("accountsChanged", onAccountsChanged);
            window.ethereum.removeListener("chainChanged", onChainChanged);
        }
    };
}
"""

wallet_component = components.component(
    name="loyalty_metamask_wallet",
    html=WALLET_HTML,
    css=WALLET_CSS,
    js=WALLET_JS,
)

# =========================================================
# KOMPONEN 2: KIRIM TRANSAKSI LEWAT METAMASK
# =========================================================

TX_HTML = """
<div>
  <p id="tx-status">Menyiapkan transaksi...</p>
  <button id="tx-send" type="button">Kirim ulang ke MetaMask</button>
</div>
"""

TX_JS = """
export default function(component) {
    const { data, parentElement, setStateValue } = component;

    const status = parentElement.querySelector("#tx-status");
    const button = parentElement.querySelector("#tx-send");

    // Mencegah transaksi yang sama terkirim dua kali
    window.__loyaltySent = window.__loyaltySent || {};

    if (!data || !data.id) {
        status.textContent = "";
        button.style.display = "none";
        return;
    }

    async function send() {
        if (!window.ethereum) {
            status.textContent = "MetaMask tidak ditemukan.";
            setStateValue("result", {
                id: data.id, ok: false, hash: "",
                error: "MetaMask tidak ditemukan"
            });
            return;
        }

        button.disabled = true;
        status.textContent = "Menunggu persetujuan transaksi di MetaMask...";

        try {
            const hash = await window.ethereum.request({
                method: "eth_sendTransaction",
                params: [{
                    from: data.from,
                    to: data.to,
                    data: data.data
                }]
            });
            status.textContent = "Transaksi dikirim: " + hash;
            setStateValue("result", {
                id: data.id, ok: true, hash: hash, error: ""
            });
        } catch (error) {
            const msg = (error && error.message)
                ? error.message
                : "Transaksi dibatalkan";
            status.textContent = "Gagal: " + msg;
            setStateValue("result", {
                id: data.id, ok: false, hash: "", error: msg
            });
        } finally {
            button.disabled = false;
        }
    }

    button.addEventListener("click", send);

    if (!window.__loyaltySent[data.id]) {
        window.__loyaltySent[data.id] = true;
        send();
    }

    return () => {
        button.removeEventListener("click", send);
    };
}
"""

tx_component = components.component(
    name="loyalty_tx_sender",
    html=TX_HTML,
    css=WALLET_CSS,
    js=TX_JS,
)

# =========================================================
# TEMA FRONTEND
# =========================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: Inter, sans-serif; }
:root { color-scheme: light; }
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    background: #f1f6fa !important;
    color: #26384a !important;
}
/* Paksa teks utama tetap gelap meskipun preferensi tema Streamlit/OS adalah dark mode. */
.stApp p, .stApp span, .stApp label, .stApp li,
.stApp div[data-testid="stMarkdownContainer"],
.stApp div[data-testid="stMarkdownContainer"] p,
.stApp div[data-testid="stWidgetLabel"] p,
.stApp [data-testid="stCaptionContainer"],
.stApp [data-testid="stMetricLabel"],
.stApp [data-testid="stMetricValue"],
.stApp [data-testid="stMetricDelta"],
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5,
[data-testid="stSidebar"] p, [data-testid="stSidebar"] label,
[data-testid="stSidebar"] span, [data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
    color: #26384a !important;
}
.stApp a { color: #286b91 !important; }
.stApp .stButton > button, .stApp .stFormSubmitButton > button,
.stApp .stButton > button *, .stApp .stFormSubmitButton > button * {
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
}
.stApp input, .stApp textarea,
.stApp [data-baseweb="select"] div,
.stApp [data-baseweb="input"] input,
.stApp [data-baseweb="textarea"] textarea {
    color: #26384a !important;
    -webkit-text-fill-color: #26384a !important;
    background-color: #ffffff !important;
}
.stApp input::placeholder, .stApp textarea::placeholder {
    color: #8292a1 !important;
    -webkit-text-fill-color: #8292a1 !important;
    opacity: 1 !important;
}
.stApp [data-testid="stDataFrame"], .stApp [data-testid="stTable"] {
    color: #26384a !important;
}
.block-container { max-width: 1440px; padding-top: 1.35rem; padding-bottom: 3rem; }
header[data-testid="stHeader"] { background: transparent; }
.brand { color:#193653; font-size:1.75rem; font-weight:800; letter-spacing:-.6px; margin:0 0 .2rem 0; }
.subbrand { color:#6b7f91; font-size:.9rem; margin-bottom:1.15rem; }
.top-pill { display:inline-block; padding:7px 12px; border:1px solid #d6e0e8; border-radius:22px; background:#fff; color:#42566a; font-size:.78rem; margin:3px; }
.panel { background:#fff; border:1px solid #d9e3eb; border-radius:15px; padding:20px 22px; box-shadow:0 2px 8px rgba(26,55,82,.035); height:100%; }
.panel h3 { color:#193653; font-size:1.05rem; margin:0 0 14px 0; font-weight:750; }
.metric-label { color:#73879a; font-size:.83rem; }
.metric-value { color:#193653; font-size:1.8rem; font-weight:800; margin-top:4px; }
.small-muted { color:#708397; font-size:.82rem; }
.section-title { color:#193653; font-size:1.3rem; font-weight:800; margin: .5rem 0 1rem; }
div[data-testid="stMetric"] { background:#fff; border:1px solid #d9e3eb; border-radius:14px; padding:15px 17px; }
.stButton > button, .stFormSubmitButton > button { background:#477f9d; color:#fff; border:0; border-radius:9px; padding:.58rem 1rem; font-weight:650; }
.stButton > button:hover, .stFormSubmitButton > button:hover { background:#356d8c; color:#fff; border:0; }
.stTextInput input, .stNumberInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] { border-radius:9px; }
div[role="radiogroup"] { gap:8px; }
div[role="radiogroup"] label { background:#fff; color:#26384a !important; border:1px solid #d7e1e9; border-radius:10px; padding:9px 16px; }
div[role="radiogroup"] label[data-checked="true"] { background:#477f9d; color:#fff !important; border-color:#477f9d; }
hr { border-color:#dce5ec; }
[data-testid="stSidebar"] { background:#f8fbfd; }
</style>
""", unsafe_allow_html=True)

# =========================================================
# FUNGSI BANTU
# =========================================================
def singkat(alamat):
    alamat = str(alamat)
    return alamat[:6] + "..." + alamat[-4:] if len(alamat) > 12 else alamat

def waktu(ts):
    return datetime.fromtimestamp(int(ts)).strftime("%d-%m-%Y %H:%M")

def alasan(error):
    teks = getattr(error, "message", None) or str(error)
    cocok = re.search(r"reason string '([^']*)'", teks)
    if cocok: return cocok.group(1)
    teks = re.sub(r"^.*?execution reverted:?\s*", "", teks, flags=re.S)
    teks = re.sub(r"^.*?VM Exception while processing transaction:\s*", "", teks, flags=re.S)
    return teks.strip().strip("'\"") or "Transaksi ditolak kontrak"

def baris_transaksi(t):
    return {"ID":int(t[0]), "Customer":t[1], "Merchant":singkat(t[2]),
            "Jenis":"Redeem" if t[5] else "Earn", "Poin":int(t[3]),
            "Status":STATUS[int(t[4])], "Reward":t[5] or "-", "Waktu":waktu(t[6])}

def alamat_valid(teks):
    if not Web3.is_address(teks):
        st.error("Alamat wallet tidak valid.")
        return None
    return Web3.to_checksum_address(teks)

# =========================================================
# STATUS BLOCKCHAIN DAN KONTRAK
# =========================================================
w3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={"timeout":5}))
st.markdown('<div class="brand">Loyalty Point Blockchain</div><div class="subbrand">Sistem loyalitas berbasis blockchain · Hardhat + MetaMask</div>', unsafe_allow_html=True)
if not w3.is_connected():
    st.error("Hardhat RPC tidak dapat diakses. Jalankan `npx hardhat node`.")
    st.stop()
rpc_chain_id = w3.eth.chain_id
contract_text = st.sidebar.text_input("Alamat kontrak LoyaltyPoint", value=DEFAULT_CONTRACT)
manual_text = st.sidebar.text_input("Alamat wallet (mode baca saja)", value="")
if not ARTIFACT.exists():
    st.error("ABI tidak ditemukan. Jalankan `npx hardhat compile`.")
    st.code(str(ARTIFACT)); st.stop()
if not Web3.is_address(contract_text):
    st.error("Alamat kontrak tidak valid."); st.stop()
contract_address = Web3.to_checksum_address(contract_text)
if len(w3.eth.get_code(contract_address)) == 0:
    st.error("Tidak ada kontrak pada alamat ini. Periksa alamat deployment."); st.stop()
abi = json.loads(ARTIFACT.read_text(encoding="utf-8"))["abi"]
contract = w3.eth.contract(address=contract_address, abi=abi)

# =========================================================
# AUTENTIKASI WALLET / ROLE GUARD
# =================================================
# Gunakan snapshot wallet dari rerun sebelumnya agar navigasi bisa tampil
# lebih dahulu, sebelum komponen Connect Wallet.
wallet_default = {"address": "", "chainId": "", "connected": False}
wallet = st.session_state.get("wallet_snapshot", wallet_default)
address = None
can_send = False
if wallet and wallet.get("connected") and wallet.get("address"):
    address = Web3.to_checksum_address(wallet["address"])
    try: wallet_chain_id = int(wallet["chainId"], 16)
    except (ValueError, TypeError): wallet_chain_id = None
    can_send = wallet_chain_id == rpc_chain_id
elif manual_text and Web3.is_address(manual_text):
    address = Web3.to_checksum_address(manual_text)

role = "Guest"
customer_data = None
admin_address = contract.functions.admin().call()
if address:
    if address.lower() == admin_address.lower():
        role = "Admin"
    elif contract.functions.merchants(address).call():
        role = "Merchant"
    else:
        customer_data = contract.functions.customers(address).call()
        if customer_data[3]: role = "Customer"

# Secure transaction preparation: UI role guard + contract remains final authority.
ROLE_ACCESS = {
    "setMerchant":"Admin", "approveEarn":"Admin", "rejectEarn":"Admin",
    "addReward":"Admin", "updateReward":"Admin",
    "registerCustomer":"Merchant", "earnPoint":"Merchant",
    "redeemPoint":"Merchant", "redeemCatalogReward":"Merchant"
}
def siapkan(fn_name, label, *args):
    required_role = ROLE_ACCESS.get(fn_name)
    if not address or not can_send:
        st.error("Hubungkan MetaMask dengan jaringan Hardhat Local untuk mengirim transaksi."); return
    if required_role and role != required_role:
        st.error(f"Akses ditolak. Fungsi ini hanya tersedia untuk peran {required_role}."); return
    try:
        getattr(contract.functions, fn_name)(*args).call({"from":address})
    except ContractLogicError as error:
        st.error("Ditolak kontrak: " + alasan(error)); return
    except Exception as error:
        st.error("Gagal memeriksa transaksi: " + str(error)); return
    st.session_state["pending"] = {"id":str(datetime.now().timestamp()), "fn":fn_name,
        "label":label, "from":address, "to":contract_address,
        "data":contract.encode_abi(fn_name,args=list(args))}
    st.session_state["last"] = None

# Pull live on-chain data
try:
    jumlah_customer = int(contract.functions.getCustomerCount().call())
    jumlah_transaksi = int(contract.functions.getTransactionCount().call())
    daftar_customer=[]; total_poin_beredar=0
    for i in range(jumlah_customer):
        cw=contract.functions.getCustomerAt(i).call()
        cd=contract.functions.getCustomer(cw).call()
        total_poin_beredar += int(cd[2])
        daftar_customer.append({"ID Customer":cd[0],"Nama":cd[1],"Wallet":cw,
            "Saldo Poin":int(cd[2]),"Merchant Pendaftar":singkat(cd[4])})
    daftar_reward=[{"ID":int(r[0]),"Nama Reward":r[1],"Deskripsi":r[2],
        "Harga Poin":int(r[3]),"Aktif":bool(r[4])} for r in contract.functions.getAllRewards().call()]
except Exception as error:
    st.error("Tidak dapat membaca data katalog/customer. Pastikan kontrak terbaru sudah di-deploy.")
    st.exception(error); st.stop()
reward_aktif=[r for r in daftar_reward if r["Aktif"]]

# =========================================================
# NAVIGASI UTAMA — tepat di bawah judul aplikasi
# =========================================================
menu_by_role = {
    "Guest":["Beranda"],
    "Admin":["Beranda","Admin"],
    "Merchant":["Beranda","Merchant"],
    "Customer":["Beranda","Customer"],
}
menu = menu_by_role.get(role,["Beranda"])
selected = st.radio("Navigasi", menu, horizontal=True, label_visibility="collapsed", key=f"role_navigation_{role}")

# Connect Wallet ditempatkan setelah navigasi, sesuai susunan dashboard terbaru.
wallet_result = wallet_component(
    key="loyalty_metamask",
    default={"wallet": wallet_default},
    on_wallet_change=lambda: None,
)
live_wallet = wallet_result.wallet or wallet_default
if live_wallet != wallet:
    st.session_state["wallet_snapshot"] = live_wallet
    st.rerun()

st.divider()

# ---------------- BERANDA ----------------
if selected == "Beranda":
    st.markdown('<div class="section-title">Beranda</div>',unsafe_allow_html=True)
    st.markdown("### Ringkasan")
    x,y,z,q=st.columns(4)
    x.metric("Total pengguna",jumlah_customer)
    y.metric("Total poin beredar",f"{total_poin_beredar:,}".replace(",","."))
    z.metric("Jumlah transaksi",jumlah_transaksi)
    q.metric("Peran Anda",role)
    if address and can_send:
        st.success(f"Wallet aktif · {singkat(address)} · {role}")
    elif address:
        st.warning("Wallet terhubung, tetapi jaringan MetaMask berbeda dari RPC. Pilih Hardhat Local.")
    else:
        st.info("Hubungkan MetaMask untuk membuka halaman sesuai peran wallet.")
    if role == "Guest":
        st.caption("Wallet yang belum terdaftar hanya dapat mengakses Beranda.")

# ---------------- ADMIN ONLY ----------------
elif selected == "Admin" and role == "Admin":
    st.markdown('<div class="section-title">Panel Admin</div>',unsafe_allow_html=True)
    left,right=st.columns([1,1])
    with left:
        with st.container(border=True):
            st.subheader("Atur merchant")
            with st.form("admin_set_merchant"):
                merchant_wallet=st.text_input("Alamat wallet merchant",placeholder="0x...")
                merchant_active=st.selectbox("Status",[True,False],format_func=lambda v:"Aktif" if v else "Nonaktif")
                submit_merchant=st.form_submit_button("Simpan merchant")
            if submit_merchant:
                ma=alamat_valid(merchant_wallet)
                if ma: siapkan("setMerchant","Atur merchant "+singkat(ma),ma,bool(merchant_active))
            st.caption("Hanya admin. Merchant nonaktif tidak dapat mendaftarkan customer, mengajukan poin, atau menukar poin.")
    with right:
        with st.container(border=True):
            st.subheader("Ringkasan")
            st.metric("Total transaksi",jumlah_transaksi)
            pending_count=sum(1 for i in range(jumlah_transaksi) if int(contract.functions.getTransaction(i).call()[4])==0)
            st.metric("Menunggu persetujuan",pending_count)
            st.write("Peran Anda: Admin")
    st.markdown("### Pengajuan poin menunggu persetujuan")
    pending=[]
    for i in range(jumlah_transaksi):
        tx=contract.functions.getTransaction(i).call()
        if int(tx[4])==0: pending.append(tx)
    if not pending: st.info("Tidak ada pengajuan yang menunggu.")
    for tx in pending:
        ca,cb,cc,cd=st.columns([3,2,1,1])
        ca.write(f"**{tx[1]}** · Merchant {singkat(tx[2])}")
        cb.write(f"{int(tx[3])} poin · ID {int(tx[0])}")
        if cc.button("Setujui",key=f"approve_{tx[0]}"): siapkan("approveEarn","Setujui transaksi "+str(tx[0]),int(tx[0]))
        if cd.button("Tolak",key=f"reject_{tx[0]}"): siapkan("rejectEarn","Tolak transaksi "+str(tx[0]),int(tx[0]))
    st.markdown("### Reward Catalog")
    rleft,rright=st.columns(2)
    with rleft:
        with st.container(border=True):
            st.subheader("Tambah reward")
            with st.form("add_reward_form"):
                rn=st.text_input("Nama reward"); rd=st.text_area("Deskripsi"); rp=st.number_input("Harga poin",min_value=1,value=100)
                add=st.form_submit_button("Tambah ke katalog")
            if add: siapkan("addReward","Tambah reward "+rn,rn,rd,int(rp))
    with rright:
        with st.container(border=True):
            st.subheader("Ubah reward")
            if daftar_reward:
                mapping={f"{r['ID']} · {r['Nama Reward']}":r for r in daftar_reward}
                label=st.selectbox("Pilih reward",list(mapping),key="admin_edit_reward"); item=mapping[label]
                with st.form("update_reward_form"):
                    un=st.text_input("Nama",value=item["Nama Reward"]); ud=st.text_area("Deskripsi",value=item["Deskripsi"]); up=st.number_input("Harga poin",min_value=1,value=max(1,item["Harga Poin"])); ua=st.checkbox("Reward aktif",value=item["Aktif"])
                    upd=st.form_submit_button("Perbarui reward")
                if upd: siapkan("updateReward","Perbarui reward "+un,item["ID"],un,ud,int(up),bool(ua))
            else: st.info("Belum ada reward.")
    st.markdown("### Daftar customer")
    # Tampilkan maksimal 5 baris terlebih dahulu agar panel Admin tetap ringkas.
    customer_expanded = st.session_state.get("admin_customers_expanded", False)
    customer_rows = daftar_customer if customer_expanded else daftar_customer[:5]
    if customer_rows:
        st.dataframe(customer_rows, use_container_width=True, hide_index=True)
        if len(daftar_customer) > 5:
            label_customer = "See less" if customer_expanded else f"See more ({len(daftar_customer) - 5} lainnya)"
            if st.button(label_customer, key="toggle_admin_customers"):
                st.session_state["admin_customers_expanded"] = not customer_expanded
                st.rerun()
    else:
        st.info("Belum ada customer terdaftar.")

    st.markdown("### Semua transaksi")
    if jumlah_transaksi:
        semua_transaksi = [
            baris_transaksi(contract.functions.getTransaction(i).call())
            for i in range(jumlah_transaksi)
        ]
        transaksi_expanded = st.session_state.get("admin_transactions_expanded", False)
        transaksi_rows = semua_transaksi if transaksi_expanded else semua_transaksi[:5]
        st.dataframe(transaksi_rows, use_container_width=True, hide_index=True)
        if len(semua_transaksi) > 5:
            label_transaksi = "See less" if transaksi_expanded else f"See more ({len(semua_transaksi) - 5} lainnya)"
            if st.button(label_transaksi, key="toggle_admin_transactions"):
                st.session_state["admin_transactions_expanded"] = not transaksi_expanded
                st.rerun()
    else:
        st.info("Belum ada transaksi.")

# ---------------- MERCHANT ONLY ----------------
elif selected == "Merchant" and role == "Merchant":
    st.markdown('<div class="section-title">Panel Merchant</div>',unsafe_allow_html=True)
    a,b,c=st.columns(3)
    with a:
        with st.container(border=True):
            st.subheader("Daftarkan customer")
            with st.form("merchant_register_customer"):
                cw=st.text_input("Alamat wallet customer",placeholder="0x..."); cid=st.text_input("ID customer",placeholder="CUST-001"); cn=st.text_input("Nama")
                reg=st.form_submit_button("Daftarkan")
            if reg:
                ca=alamat_valid(cw)
                if ca: siapkan("registerCustomer","Daftarkan customer "+cid,ca,cid,cn)
    with b:
        with st.container(border=True):
            st.subheader("Ajukan poin")
            with st.form("merchant_earn"):
                eid=st.text_input("ID customer",key="merchant_eid"); ep=st.number_input("Jumlah poin",min_value=1,value=100,step=10,key="merchant_ep")
                earn=st.form_submit_button("Ajukan poin")
            if earn: siapkan("earnPoint",f"Ajukan {ep} poin untuk {eid}",eid,int(ep))
            st.caption("Status PENDING sampai disetujui Admin. Saldo belum bertambah.")
    with c:
        with st.container(border=True):
            st.subheader("Tukar poin")
            if reward_aktif:
                with st.form("merchant_redeem_catalog"):
                    rid=st.text_input("ID customer",key="merchant_rid")
                    rmap={f"{r['Nama Reward']} · {r['Harga Poin']} poin":r for r in reward_aktif}
                    chosen=st.selectbox("Pilih reward",list(rmap)); redeem=st.form_submit_button("Tukar poin")
                if redeem:
                    rr=rmap[chosen]; siapkan("redeemCatalogReward","Tukar "+rr["Nama Reward"],rid,rr["ID"])
            else: st.info("Belum ada reward aktif.")
            st.caption("Saldo berlaku di semua merchant: poin dari Merchant A dapat ditukar di Merchant B.")
    st.markdown("### Reward Catalog")
    if reward_aktif:
        cols=st.columns(3)
        for i,r in enumerate(reward_aktif):
            with cols[i%3]:
                with st.container(border=True): st.markdown(f"**{r['Nama Reward']}**"); st.write(r['Deskripsi'] or "-"); st.metric("Harga",f"{r['Harga Poin']} poin")
    else: st.info("Katalog reward kosong.")

# ---------------- CUSTOMER ONLY ----------------
elif selected == "Customer" and role == "Customer":
    st.markdown('<div class="section-title">My Rewards</div>',unsafe_allow_html=True)
    own=contract.functions.customers(address).call(); own_id=own[0]
    p1,p2=st.columns([1,1])
    with p1:
        with st.container(border=True):
            st.subheader("Cek saldo")
            st.metric("Nama",own[1]); st.metric("Saldo poin",f"{int(own[2]):,}".replace(",",".")); st.caption("ID Customer: "+own_id); st.caption("Wallet: "+address)
    with p2:
        with st.container(border=True):
            st.subheader("NFT reward")
            token_id=st.number_input("Token ID",min_value=1,value=1,step=1,key="customer_token_id")
            if st.button("Cek NFT",key="customer_check_nft"):
                try:
                    owner=contract.functions.getRewardOwner(int(token_id)).call(); asset=contract.functions.getRewardAsset(int(token_id)).call()
                    if owner.lower()!=address.lower(): st.warning("NFT ini bukan milik wallet yang sedang login.")
                    else:
                        st.write("Pemilik: "+singkat(owner)); st.write("Reward: "+asset[4]); st.write("Ditukar di: "+singkat(asset[3])); st.caption("NFT tidak dapat dipindahtangankan.")
                except Exception as e: st.error("NFT tidak ditemukan: "+alasan(e))
    st.markdown("### Points History")
    history=contract.functions.getHistory(own_id).call()
    if history: st.dataframe([baris_transaksi(t) for t in history],use_container_width=True,hide_index=True)
    else: st.info("Belum ada riwayat transaksi.")
    st.markdown("### Reward Catalog")
    if reward_aktif:
        cols=st.columns(3)
        for i,r in enumerate(reward_aktif):
            with cols[i%3]:
                with st.container(border=True): st.markdown(f"**{r['Nama Reward']}**"); st.write(r['Deskripsi'] or "-"); st.metric("Harga",f"{r['Harga Poin']} poin"); st.caption("Cukupkan saldo melalui merchant untuk menukarkan reward.")

# Catch-all role mismatch protection
elif selected != "Beranda":
    st.error("Akses ditolak. Halaman ini tidak tersedia untuk peran wallet yang sedang terhubung.")

# =========================================================
# HASIL TRANSAKSI META MASK
# =========================================================
pending=st.session_state.get("pending")
with st.container():
    last=st.session_state.get("last")
    if last:
        if last["ok"]: st.success(last["msg"])
        else: st.error(last["msg"])
        if last.get("hash"): st.caption("Hash transaksi: "+last["hash"])
    if pending:
        st.info(pending["label"]+": setujui transaksi di popup MetaMask.")
        hasil=tx_component(key="tx_"+pending["id"],data={"id":pending["id"],"from":pending["from"],"to":pending["to"],"data":pending["data"]},default={"result":None},on_result_change=lambda:None)
        result=hasil.result
        if result and result.get("id")==pending["id"]:
            if result.get("ok"):
                try:
                    receipt=w3.eth.wait_for_transaction_receipt(result["hash"],timeout=30)
                    if receipt["status"]==1:
                        msg=pending["label"]+" berhasil."
                        if pending["fn"] in ("redeemPoint","redeemCatalogReward"):
                            logs=contract.events.RewardMinted().process_receipt(receipt,errors=DISCARD)
                            if logs: msg+=f" NFT Token ID {logs[0]['args']['tokenId']} dicetak."
                        st.session_state["last"]={"ok":True,"msg":msg,"hash":result["hash"]}
                    else: st.session_state["last"]={"ok":False,"msg":pending["label"]+" gagal dieksekusi.","hash":result["hash"]}
                except Exception as error: st.session_state["last"]={"ok":False,"msg":"Transaksi terkirim, tetapi receipt gagal dibaca: "+str(error),"hash":result.get("hash","")}
            else: st.session_state["last"]={"ok":False,"msg":result.get("error") or "Transaksi dibatalkan.","hash":""}
            st.session_state["pending"]=None
            st.rerun()


# =========================================================
# STATUS JARINGAN — diletakkan paling bawah halaman
# =========================================================
st.divider()
st.markdown("### Status jaringan")
with st.container(border=True):
    net1, net2, net3 = st.columns(3)
    net1.metric("Chain ID", rpc_chain_id)
    net2.metric("Block terbaru", w3.eth.block_number)
    net3.metric("Peran terdeteksi", role)
    st.caption("RPC: 127.0.0.1:8545 · Kontrak: " + singkat(contract_address))
    if address:
        st.caption("Wallet: " + address + (" · Jaringan sesuai RPC" if can_send else " · Jaringan tidak sesuai RPC"))
    else:
        st.caption("Wallet belum terhubung")
