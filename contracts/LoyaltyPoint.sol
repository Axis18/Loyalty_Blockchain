// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";

contract LoyaltyPoint is ERC721 {
    address public admin;

    // CONSTRUCTOR <>

    constructor()
        ERC721("Loyalty Reward", "LRWD")
    {
        admin = msg.sender;
    }

    // STATUS TRANSAKSI <>

    enum Status {
        PENDING,
        EARNED,
        REDEEMED,
        REJECTED
    }

    // DATA <>

    // Data katalog reward yang disimpan langsung di blockchain
    struct RewardCatalog {
        uint256 id;
        string nama;
        string deskripsi;
        uint256 hargaPoin;
        bool aktif;
    }

    // Data customer <>
    struct Customer {
        string id;
        string nama;
        uint256 saldo;
        bool terdaftar;
        address registeredBy; // merchant tempat customer mendaftar
    }

    // Data transaksi <>
    // earn   -> merchant = merchant yang mengajukan poin
    // redeem -> merchant = merchant tempat poin ditukar
    struct Transaction {
        uint256 id;
        string customerId;
        address merchant;
        uint256 poin;
        Status status;
        string reward;
        uint256 timestamp;
    }

    // Data aset NFT (reward hasil redeem) <>
    struct RewardAsset {
        uint256 tokenId;
        uint256 transactionId;
        string customerId;
        address merchant; // merchant tempat reward ditukar
        string reward;
        uint256 poin;
        uint256 redeemedAt;
    }

    // VARIABLE <>

    mapping(address => Customer) public customers;
    mapping(string => address) public customerById;
    mapping(address => bool) public merchants;

    // Array wallet diperlukan agar daftar customer dapat dibaca oleh aplikasi.
    address[] private customerWallets;

    // Katalog reward on-chain. Reward dinonaktifkan dengan aktif=false,
    // bukan dihapus, agar data katalog tetap dapat diaudit.
    mapping(uint256 => RewardCatalog) public rewardCatalog;
    uint256[] private rewardIds;
    uint256 public nextRewardId = 1;

    Transaction[] private transactions;
    mapping(string => uint256[]) private customerHistory;

    uint256 public nextTransactionId;

    // Token ID otomatis: mint pertama = 1, kedua = 2, dst
    uint256 private nextTokenId = 1;

    // Token ID -> Data reward <>
    mapping(uint256 => RewardAsset) public rewards;

    // EVENTS <>

    event CustomerRegistered(address indexed wallet, string id, address indexed merchant);
    event MerchantUpdated(address indexed merchant, bool active);
    event EarnRequested(uint256 indexed transactionId, string customerId, uint256 poin);
    event TransactionApproved(uint256 indexed transactionId);
    event TransactionRejected(uint256 indexed transactionId);
    event PointRedeemed(uint256 indexed transactionId, string customerId, uint256 poin, address indexed merchant);
    event RewardMinted(uint256 indexed tokenId, address indexed owner, string reward);
    event RewardAdded(uint256 indexed rewardId, string nama, uint256 hargaPoin);
    event RewardUpdated(uint256 indexed rewardId, uint256 hargaPoin, bool aktif);

    // MODIFIER <>

    modifier onlyAdmin() {
        require(msg.sender == admin, "Hanya admin");
        _;
    }

    modifier onlyMerchant() {
        require(merchants[msg.sender], "Merchant tidak terdaftar");
        _;
    }

    // 1. ADMIN SET MERCHANT <>

    function setMerchant(
        address merchant,
        bool active
    ) external onlyAdmin {
        require(merchant != address(0), "Alamat tidak valid");

        merchants[merchant] = active;

        emit MerchantUpdated(merchant, active);
    }

    // 2. MERCHANT MENDAFTARKAN CUSTOMER (DI KASIR) <>

    function registerCustomer(
        address wallet,
        string calldata id,
        string calldata nama
    ) external onlyMerchant {
        require(wallet != address(0), "Alamat wallet tidak valid");
        require(bytes(id).length > 0, "ID kosong");
        require(bytes(nama).length > 0, "Nama kosong");
        require(!customers[wallet].terdaftar, "Wallet sudah terdaftar");
        require(customerById[id] == address(0), "ID sudah digunakan");

        customers[wallet] = Customer({
            id: id,
            nama: nama,
            saldo: 0,
            terdaftar: true,
            registeredBy: msg.sender
        });

        customerById[id] = wallet;
        customerWallets.push(wallet);

        emit CustomerRegistered(wallet, id, msg.sender);
    }

    // 3. MERCHANT MENGAJUKAN EARN POINT <>

    function earnPoint(
        string calldata customerId,
        uint256 poin
    ) external onlyMerchant returns (uint256) {
        require(poin > 0, "Poin harus lebih dari 0");

        address wallet = customerById[customerId];
        require(wallet != address(0), "Customer tidak ditemukan");

        uint256 txId = nextTransactionId++;

        transactions.push(Transaction({
            id: txId,
            customerId: customerId,
            merchant: msg.sender,
            poin: poin,
            status: Status.PENDING,
            reward: "",
            timestamp: block.timestamp
        }));

        customerHistory[customerId].push(txId);

        emit EarnRequested(txId, customerId, poin);

        return txId;
    }
    
    // 4. ADMIN MENYETUJUI EARN POINT <>

    function approveEarn(
        uint256 txId
    ) external onlyAdmin {
        require(txId < transactions.length, "Transaksi tidak ditemukan");

        Transaction storage txn = transactions[txId];

        require(txn.status == Status.PENDING, "Status tidak valid");

        address wallet = customerById[txn.customerId];
        require(wallet != address(0), "Customer tidak ditemukan");

        customers[wallet].saldo += txn.poin;
        txn.status = Status.EARNED;

        emit TransactionApproved(txId);
    }

    // 5. ADMIN MENOLAK EARN POINT <>

    function rejectEarn(
        uint256 txId
    ) external onlyAdmin {
        require(txId < transactions.length, "Transaksi tidak ditemukan");

        Transaction storage txn = transactions[txId];

        require(txn.status == Status.PENDING, "Status tidak valid");

        txn.status = Status.REJECTED;

        emit TransactionRejected(txId);
    }

    // 6. MERCHANT MENUKAR POIN CUSTOMER + MINT NFT <>
    // Poin bisa ditukar di merchant mana pun (saldo berlaku lintas merchant)

    function redeemPoint(
        string memory customerId,
        uint256 poin,
        string memory reward
    ) external onlyMerchant returns (uint256 txId, uint256 tokenId) {
        address wallet = customerById[customerId];

        require(wallet != address(0), "Customer tidak ditemukan");
        require(poin > 0, "Poin harus lebih dari 0");
        require(customers[wallet].saldo >= poin, "Saldo poin tidak cukup");
        require(bytes(reward).length > 0, "Reward kosong");

        // Kurangi saldo sebelum mencatat reward
        customers[wallet].saldo -= poin;

        txId = _recordRedeem(customerId, poin, reward);
        tokenId = _mintReward(wallet, customerId, txId, poin, reward);

        emit PointRedeemed(txId, customerId, poin, msg.sender);
        emit RewardMinted(tokenId, wallet, reward);
    }

    // Menukar reward berdasarkan item yang dipilih dari katalog on-chain.
    function redeemCatalogReward(
        string calldata customerId,
        uint256 rewardId
    ) external onlyMerchant returns (uint256 txId, uint256 tokenId) {
        address wallet = customerById[customerId];
        require(wallet != address(0), "Customer tidak ditemukan");
        require(rewardId > 0 && rewardId < nextRewardId, "Reward tidak ditemukan");

        RewardCatalog storage item = rewardCatalog[rewardId];
        require(item.aktif, "Reward tidak aktif");
        require(customers[wallet].saldo >= item.hargaPoin, "Saldo poin tidak cukup");

        customers[wallet].saldo -= item.hargaPoin;
        txId = _recordRedeem(customerId, item.hargaPoin, item.nama);
        tokenId = _mintReward(wallet, customerId, txId, item.hargaPoin, item.nama);

        emit PointRedeemed(txId, customerId, item.hargaPoin, msg.sender);
        emit RewardMinted(tokenId, wallet, item.nama);
    }

    // Mencatat transaksi redeem
    function _recordRedeem(
        string memory customerId,
        uint256 poin,
        string memory reward
    ) private returns (uint256 txId) {
        txId = nextTransactionId++;

        transactions.push(Transaction({
            id: txId,
            customerId: customerId,
            merchant: msg.sender,
            poin: poin,
            status: Status.REDEEMED,
            reward: reward,
            timestamp: block.timestamp
        }));

        customerHistory[customerId].push(txId);
    }

    // Mencetak NFT reward ke wallet customer
    function _mintReward(
        address wallet,
        string memory customerId,
        uint256 txId,
        uint256 poin,
        string memory reward
    ) private returns (uint256 tokenId) {
        // Ambil Token ID, lalu siapkan Token ID berikutnya
        tokenId = nextTokenId;
        nextTokenId++;

        // Simpan data aset yang terhubung ke Token ID
        RewardAsset storage asset = rewards[tokenId];
        asset.tokenId = tokenId;
        asset.transactionId = txId;
        asset.customerId = customerId;
        asset.merchant = msg.sender;
        asset.reward = reward;
        asset.poin = poin;
        asset.redeemedAt = block.timestamp;

        // Mint NFT ke wallet customer
        _safeMint(wallet, tokenId);
    }

    // 7. ADMIN MENGELOLA KATALOG REWARD ON-CHAIN

    function addReward(
        string calldata nama,
        string calldata deskripsi,
        uint256 hargaPoin
    ) external onlyAdmin returns (uint256 rewardId) {
        require(bytes(nama).length > 0, "Nama reward kosong");
        require(hargaPoin > 0, "Harga poin harus lebih dari 0");

        rewardId = nextRewardId++;
        rewardCatalog[rewardId] = RewardCatalog({
            id: rewardId,
            nama: nama,
            deskripsi: deskripsi,
            hargaPoin: hargaPoin,
            aktif: true
        });
        rewardIds.push(rewardId);

        emit RewardAdded(rewardId, nama, hargaPoin);
    }

    function updateReward(
        uint256 rewardId,
        string calldata nama,
        string calldata deskripsi,
        uint256 hargaPoin,
        bool aktif
    ) external onlyAdmin {
        require(rewardId > 0 && rewardId < nextRewardId, "Reward tidak ditemukan");
        require(bytes(nama).length > 0, "Nama reward kosong");
        require(hargaPoin > 0, "Harga poin harus lebih dari 0");

        RewardCatalog storage item = rewardCatalog[rewardId];
        item.nama = nama;
        item.deskripsi = deskripsi;
        item.hargaPoin = hargaPoin;
        item.aktif = aktif;

        emit RewardUpdated(rewardId, hargaPoin, aktif);
    }

    function getRewardCount() external view returns (uint256) {
        return rewardIds.length;
    }

    function getAllRewards() external view returns (RewardCatalog[] memory) {
        RewardCatalog[] memory result = new RewardCatalog[](rewardIds.length);
        for (uint256 i = 0; i < rewardIds.length; i++) {
            result[i] = rewardCatalog[rewardIds[i]];
        }
        return result;
    }

    // 8. MEMBACA DAFTAR CUSTOMER ON-CHAIN

    function getCustomerCount() external view returns (uint256) {
        return customerWallets.length;
    }

    function getCustomerAt(uint256 index) external view returns (address) {
        require(index < customerWallets.length, "Index customer tidak valid");
        return customerWallets[index];
    }

    function getCustomer(address wallet) external view returns (Customer memory) {
        require(customers[wallet].terdaftar, "Customer tidak ditemukan");
        return customers[wallet];
    }

    // 9. MELIHAT SALDO CUSTOMER <>

    function getBalance(
        string calldata customerId
    ) external view returns (
        string memory nama,
        uint256 saldo
    ) {
        address wallet = customerById[customerId];

        require(wallet != address(0), "Customer tidak ditemukan");

        Customer storage customer = customers[wallet];

        return (customer.nama, customer.saldo);
    }

    // 10. MELIHAT JUMLAH TRANSAKSI <>

    function getTransactionCount()
        external
        view
        returns (uint256)
    {
        return transactions.length;
    }

    // 11. MELIHAT DETAIL TRANSAKSI <>

    function getTransaction(
        uint256 txId
    ) external view returns (Transaction memory) {
        require(txId < transactions.length, "Transaksi tidak ditemukan");

        return transactions[txId];
    }

    // 12. MELIHAT RIWAYAT CUSTOMER <>

    function getHistory(
        string calldata customerId
    ) external view returns (Transaction[] memory) {
        require(
            customerById[customerId] != address(0),
            "Customer tidak ditemukan"
        );

        uint256[] storage ids = customerHistory[customerId];
        Transaction[] memory result = new Transaction[](ids.length);

        for (uint256 i = 0; i < ids.length; i++) {
            result[i] = transactions[ids[i]];
        }

        return result;
    }

    // 13. MELIHAT PEMILIK NFT REWARD <>

    function getRewardOwner(
        uint256 tokenId
    ) public view returns (address) {
        require(
            _ownerOf(tokenId) != address(0),
            "NFT tidak ditemukan"
        );

        return ownerOf(tokenId);
    }

    // 14. MELIHAT DATA ASET YANG TERHUBUNG KE TOKEN <>

    function getRewardAsset(
        uint256 tokenId
    ) external view returns (RewardAsset memory) {
        require(
            _ownerOf(tokenId) != address(0),
            "NFT tidak ditemukan"
        );

        return rewards[tokenId];
    }

    function _update(
        address to,
        uint256 tokenId,
        address auth
    ) internal override returns (address) {
        require(
            _ownerOf(tokenId) == address(0),
            "NFT tidak dapat dipindahtangankan"
        );

        return super._update(to, tokenId, auth);
    }
}