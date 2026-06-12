/**
 * Tested questions sourced from backend/json/questions-answers.json
 * and backend/json/questions-answers2.json.
 *
 * These are loaded in the Copilot Chat welcome screen so users can
 * quickly try real tested queries against the knowledge base.
 */

export interface TestedQuestion {
  id: number;
  category: string;
  difficulty: "easy" | "medium" | "hard";
  question: string;
  ground_truth: string;
}

const QUESTIONS_ANSWERS_1: TestedQuestion[] = [
  {
    id: 1,
    category: "Factual Lookup",
    difficulty: "easy",
    question: "Berapa harga jual Olivoila Olive Oil 500c?",
    ground_truth: "Harga jual Olivoila Olive Oil 500c adalah Rp 111.000",
  },
  {
    id: 2,
    category: "Factual Lookup",
    difficulty: "easy",
    question: "Berapa isi per CS untuk produk Sania Botol 1l?",
    ground_truth: "1 CS Sania Botol 1l berisi 12 BTL (botol)",
  },
  {
    id: 3,
    category: "Factual Lookup",
    difficulty: "easy",
    question: "Apa satuan terkecil (SatK) untuk produk Sania Jerigen 5l?",
    ground_truth: "Satuan terkecil untuk Sania Jerigen 5l adalah JRG (jerigen)",
  },
  {
    id: 4,
    category: "Factual Lookup",
    difficulty: "easy",
    question: "Berapa berat produk Blue Band Pastry Fat 15k dalam kg?",
    ground_truth: "Berat Blue Band Pastry Fat 15k adalah 15,52 kg",
  },
  {
    id: 5,
    category: "Factual Lookup",
    difficulty: "easy",
    question: "Siapa vendor untuk produk Fortune Margarine 15k?",
    ground_truth: "Vendor untuk Fortune Margarine 15k adalah PD-0109 (SARI AGROTAMA PERSADA D)",
  },
  {
    id: 6,
    category: "Filtering",
    difficulty: "medium",
    question: "Produk apa saja yang disupply oleh vendor PD-0110?",
    ground_truth: "Produk dari vendor PD-0110 (UPFIELD DISTRIBUTION INDONESIA PT) antara lain: Blue Band Mst Cake Marg Box 15k, Blue Band C&C Sachet 200g, Blue Band Serbaguna 200g, Blue Band Rice Mix Barbeque 45g, Blue Band White Cream Fat 15k, Blue Band Pastry Fat 15k, Blue Band Gold Margarine 15k, Minyak Samin Cap Onta 2k, Frytol Minyak Goreng Padat 15k, Blue Band Coklat Compound Butir 10k, dan masih banyak lagi.",
  },
  {
    id: 7,
    category: "Filtering",
    difficulty: "medium",
    question: "Produk mana yang memiliki harga jual paling mahal?",
    ground_truth: "Produk dengan harga jual paling mahal adalah Blue Band Pastry Fat 15k dengan harga Rp 683.871",
  },
  {
    id: 8,
    category: "Filtering",
    difficulty: "medium",
    question: "Produk mana yang memiliki harga jual paling murah?",
    ground_truth: "Produk dengan harga jual paling murah adalah Kecap Manis Bango 18c dengan harga Rp 800,10",
  },
  {
    id: 9,
    category: "Filtering",
    difficulty: "medium",
    question: "Produk apa saja yang satuan terkecilnya (SatK) adalah BTL?",
    ground_truth: "Produk dengan satuan terkecil BTL (botol) adalah: Olivoila Olive Oil 500c, Sania Botol 1l, dan Sania Botol 2l",
  },
  {
    id: 10,
    category: "Filtering",
    difficulty: "medium",
    question: "Berapa jumlah outlet dengan tipe 'Wholesale' yang berada di area Mataram?",
    ground_truth: "Terdapat beberapa outlet bertipe Wholesale di area Mataram, termasuk ABDULLAH SUNGKAR dan ADI TOPAN.",
  },
  {
    id: 11,
    category: "Cross-Sheet",
    difficulty: "medium",
    question: "Nama lengkap dan alamat vendor PD-0109 itu apa?",
    ground_truth: "Vendor PD-0109 adalah SARI AGROTAMA PERSADA D, beralamat di JL. PULO KAMBING RAYA KAV. IIE/7",
  },
  {
    id: 12,
    category: "Cross-Sheet",
    difficulty: "hard",
    question: "Produk dari vendor UPFIELD DISTRIBUTION INDONESIA PT yang harganya di bawah Rp 10.000 apa saja?",
    ground_truth: "Produk dari vendor PD-0110 (UPFIELD) dengan harga di bawah Rp 10.000 adalah: Blue Band Rice Mix Barbeque 45g (Rp 4.040), Blue Band Rice Mix Ayam 45g (Rp 4.040), Blue Band Serbaguna 100g (Rp 4.029,90), Blue Band 5In1 Serbaguna 190g (Rp 5.760,15), Blue Band Kuliner Ayam Bawang 40g (Rp 3.345,10), Blue Band Kuliner Sapi BBQ 40g (Rp 3.345,10), Blue Band Coconut Cream 65c (Rp 4.141), Blue Band Serbaguna 200g (Rp 8.599,13)",
  },
  {
    id: 13,
    category: "Cross-Sheet",
    difficulty: "medium",
    question: "Customer dengan kode JBD0628 berlokasi di mana dan tipe outletnya apa?",
    ground_truth: "Customer JBD0628 adalah ADI TOPAN, berlokasi di JLN. ADI SUCIPTO KEBON ROEK-AMPENAN, KODYA MATARAM, area Ampenan. Tipe outletnya adalah Wholesale Pasar.",
  },
  {
    id: 14,
    category: "Calculation",
    difficulty: "hard",
    question: "Jika 1 CS Sania Botol 2l berisi 6 BTL, berapa harga per botol-nya?",
    ground_truth: "Harga jual Sania Botol 2l per CS adalah Rp 46.842. Karena 1 CS berisi 6 BTL, maka harga per botol adalah Rp 46.842 / 6 = Rp 7.807",
  },
  {
    id: 15,
    category: "Calculation",
    difficulty: "hard",
    question: "Produk Blue Band mana yang memiliki volume terbesar berdasarkan dimensi panjang × lebar × tinggi?",
    ground_truth: "Produk Blue Band dengan volume terbesar adalah Blue Band Mst Cake Marg Box 15k (22 × 32 × 27 = 19.008 cm³)",
  },
  {
    id: 16,
    category: "Out-of-scope",
    difficulty: "easy",
    question: "Berapa stok saat ini untuk Sania Botol 1l?",
    ground_truth: "Data stok tidak tersedia/tidak ditemukan dalam dokumen yang tersedia.",
  },
  {
    id: 17,
    category: "Out-of-scope",
    difficulty: "easy",
    question: "Apakah ada produk merek Indomie dalam data ini?",
    ground_truth: "Tidak ada produk merek Indomie dalam data ini. Data tidak ditemukan.",
  },
];

const QUESTIONS_ANSWERS_2: TestedQuestion[] = [
  {
    id: 18,
    category: "Aggregation",
    difficulty: "easy",
    question: "Berapa banyak outlet yang ada di master data?",
    ground_truth: "Total outlet yang terdaftar dalam master data (sheet MOutlet) adalah 760 outlet.",
  },
  {
    id: 19,
    category: "Aggregation",
    difficulty: "easy",
    question: "Berapa total jumlah produk yang ada di master data barang?",
    ground_truth: "Total produk yang terdaftar dalam master data barang (sheet MBarang) adalah 45 produk.",
  },
  {
    id: 20,
    category: "Aggregation",
    difficulty: "medium",
    question: "Tipe outlet apa yang paling banyak dalam master data?",
    ground_truth: "Tipe outlet terbanyak adalah Groceries Store dengan 349 outlet, diikuti Kiosk Pasar dengan 202 outlet.",
  },
  {
    id: 21,
    category: "Aggregation",
    difficulty: "medium",
    question: "Area mana yang memiliki jumlah outlet terbanyak?",
    ground_truth: "Area dengan jumlah outlet terbanyak adalah Mataram dengan 79 outlet, diikuti Cakranegara dengan 69 outlet dan Praya dengan 66 outlet.",
  },
  {
    id: 22,
    category: "Aggregation",
    difficulty: "medium",
    question: "Berapa jumlah outlet bertipe Wholesale (semua varian) dalam master data?",
    ground_truth: "Jumlah outlet bertipe Wholesale adalah 65, Wholesale Pasar 24, dan Modern Wholesale KA 1, sehingga total seluruh varian Wholesale adalah 90 outlet.",
  },
  {
    id: 23,
    category: "Aggregation",
    difficulty: "medium",
    question: "Berapa jumlah produk yang disupply oleh vendor PD-0109?",
    ground_truth: "Vendor PD-0109 (SARI AGROTAMA PERSADA D) menyupply 11 produk, antara lain Fortune Margarine 15k, Olivoila Olive Oil 500c, Sania Botol 1l, Sania Pouch 1l, Sania Botol 2l, Sania Pouch 2l, Sania Jerigen 5l, Sania Botol 500c, Mahkota 900c, Sania Pouch 800c, dan Sania Pouch 1.8l.",
  },
  {
    id: 24,
    category: "Aggregation",
    difficulty: "medium",
    question: "Berapa jumlah produk yang disupply oleh vendor PD-0110?",
    ground_truth: "Vendor PD-0110 (UPFIELD DISTRIBUTION INDONESIA PT) menyupply 34 produk, mencakup berbagai varian Blue Band, Minyak Samin Cap Onta, Frytol, dan Kecap Manis Bango.",
  },
  {
    id: 25,
    category: "Filtering",
    difficulty: "medium",
    question: "Produk apa saja yang harga jualnya berada di antara Rp 10.000 dan Rp 50.000?",
    ground_truth: "Produk dengan harga jual antara Rp 10.000–50.000 adalah: Sania Botol 1l (Rp 24.009), Sania Pouch 1l (Rp 22.566), Sania Botol 2l (Rp 46.842), Sania Pouch 2l (Rp 44.400), Sania Botol 500c (Rp 13.120), Mahkota 900c (Rp 19.369), Sania Pouch 800c (Rp 18.648), Sania Pouch 1.8l (Rp 40.404), Blue Band C&C Sachet 200g (Rp 11.778), dan lainnya.",
  },
  {
    id: 26,
    category: "Filtering",
    difficulty: "medium",
    question: "Produk apa saja yang satuan tengah (SatT)-nya bukan CS?",
    ground_truth: "Produk yang satuan tengahnya bukan CS adalah: Blue Band Rice Mix Barbeque 45g (BOX), Blue Band Rice Mix Ayam 45g (BOX), Blue Band Kuliner Ayam Bawang 40g (PACK), dan Blue Band Kuliner Sapi BBQ 40g (PACK).",
  },
  {
    id: 27,
    category: "Filtering",
    difficulty: "medium",
    question: "Berapa jumlah outlet di area Sandubaya?",
    ground_truth: "Terdapat 40 outlet di area Sandubaya.",
  },
  {
    id: 28,
    category: "Filtering",
    difficulty: "medium",
    question: "Produk mana saja yang memiliki berat di atas 10 kg?",
    ground_truth: "Produk dengan berat di atas 10 kg adalah: Fortune Margarine 15k (15,20 kg), Blue Band Mst Cake Marg Box 15k (15,52 kg), Blue Band White Cream Fat 15k (15,52 kg), Blue Band Pastry Fat 15k (15,52 kg), Blue Band Gold Margarine 15k (15,52 kg), Frytol Minyak Goreng Padat 15k (15,52 kg), Blue Band Croma 15k (15,05 kg).",
  },
  {
    id: 29,
    category: "Filtering",
    difficulty: "medium",
    question: "Outlet mana saja yang bertipe Minimarket Local di area Mataram?",
    ground_truth: "Outlet Minimarket Local di area Mataram antara lain: DEWA PUTU MEKI SURYANA (JBD0043), EDELWEIS MITRA ABADI (JBD12001), dan EDWARD CHRISTIADI SE (JBD27286).",
  },
  {
    id: 30,
    category: "Comparison",
    difficulty: "medium",
    question: "Dari semua produk berukuran 15k, mana yang paling murah dan paling mahal?",
    ground_truth: "Dari produk 15k, yang paling murah adalah Fortune Margarine 15k (Rp 182.680,77) dan yang paling mahal adalah Blue Band Pastry Fat 15k (Rp 683.871).",
  },
  {
    id: 31,
    category: "Comparison",
    difficulty: "medium",
    question: "Mana yang lebih ringan: Sania Pouch 1l atau Sania Botol 1l?",
    ground_truth: "Sania Pouch 1l lebih ringan dengan berat 1,00 kg dibandingkan Sania Botol 1l yang beratnya 1,01 kg.",
  },
  {
    id: 32,
    category: "Comparison",
    difficulty: "medium",
    question: "Produk Sania mana yang paling murah harga jualnya?",
    ground_truth: "Produk Sania dengan harga jual paling murah adalah Sania Botol 500c dengan harga Rp 13.120,21.",
  },
  {
    id: 33,
    category: "Comparison",
    difficulty: "hard",
    question: "Antara Blue Band Rice Mix Chicken 6s 45g dan Blue Band Rice Mix Chicken Box 12s 45g, mana yang lebih murah per EA-nya?",
    ground_truth: "Blue Band Rice Mix Chicken 6s 45g: Rp 24.240 / 10 EA = Rp 2.424 per EA. Blue Band Rice Mix Chicken Box 12s 45g: Rp 33.905,7 / 8 EA = Rp 4.238 per EA. Jadi Blue Band Rice Mix Chicken 6s 45g lebih murah per EA-nya.",
  },
  {
    id: 34,
    category: "Calculation",
    difficulty: "hard",
    question: "Berapa harga per EA untuk Blue Band Mst Cake Marg Box 15k jika satuan terkecilnya adalah CS?",
    ground_truth: "Blue Band Mst Cake Marg Box 15k memiliki satuan terkecil CS dengan Berisi_T = 1 CS, sehingga harga per CS sama dengan harga jualnya yaitu Rp 501.970.",
  },
  {
    id: 35,
    category: "Calculation",
    difficulty: "hard",
    question: "Berapa total harga jika membeli 2 CS Blue Band Gold Margarine 15k?",
    ground_truth: "Harga 1 CS Blue Band Gold Margarine 15k adalah Rp 556.211,92, sehingga 2 CS = Rp 556.211,92 × 2 = Rp 1.112.423,84.",
  },
  {
    id: 36,
    category: "Cross-Sheet",
    difficulty: "medium",
    question: "Apakah vendor yang menyupply Fortune Margarine 15k statusnya blocked?",
    ground_truth: "Vendor Fortune Margarine 15k adalah PD-0109 (SARI AGROTAMA PERSADA D). Status blocked vendor PD-0109 adalah False, artinya tidak diblokir.",
  },
  {
    id: 37,
    category: "Cross-Sheet",
    difficulty: "medium",
    question: "Berapa jumlah vendor yang terdaftar di master data supplier?",
    ground_truth: "Terdapat 2 vendor yang terdaftar di master data supplier (sheet MPD), yaitu PD-0109 (SARI AGROTAMA PERSADA D) dan PD-0110 (UPFIELD DISTRIBUTION INDONESIA PT).",
  },
  {
    id: 38,
    category: "Out-of-scope",
    difficulty: "easy",
    question: "Berapa harga beli (HPP) untuk produk Blue Band Serbaguna 1k?",
    ground_truth: "Data harga beli (HPP) tidak tersedia dalam file ini. File hanya menyimpan harga jual, bukan harga pokok pembelian.",
  },
];

/** All 38 tested questions merged from both JSON files. */
export const ALL_TESTED_QUESTIONS: TestedQuestion[] = [...QUESTIONS_ANSWERS_1, ...QUESTIONS_ANSWERS_2];

/** Questions suitable for any role (non-cross-dept / general factual lookups). */
export const GENERAL_SUGGESTIONS: TestedQuestion[] = ALL_TESTED_QUESTIONS.filter(
  (q) => q.category !== "Cross-Sheet" && q.category !== "Out-of-scope"
);

/** Cross-department / out-of-scope questions used to test blocking behavior. */
export const CROSS_DEPT_SUGGESTIONS: TestedQuestion[] = ALL_TESTED_QUESTIONS.filter(
  (q) => q.category === "Cross-Sheet" || q.category === "Out-of-scope"
);
