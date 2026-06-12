"""Department configuration and folder initialization for the Knowledge Base Manager.

Updates per specification v2.0 — 4 actual departments (Phase 1):
- demand_supply: Demand-Supply Planning
- accounting_tax: Controller Accounting Tax
- logistic: Logistic
- finance: Finance
"""

from pathlib import Path


DEPARTMENTS: dict[str, list[str]] = {
    "master": ["barang", "outlet", "distributor"],
    "demand_supply": [
        "demand_plans",
        "supply_plans",
        "deal_orders",
        "forecasts",
        "reference",
    ],
    "accounting_tax": [
        "invoices",
        "transactions",
        "tax_reports",
        "journal_entries",
        "policies",
    ],
    "logistic": [
        "inbound",
        "outbound",
        "warehouse",
        "shipping_docs",
        "sops",
    ],
    "finance": [
        "cashflow",
        "payments",
        "receivables",
        "budgets",
        "reports",
    ],
}


DEPARTMENT_META: dict[str, dict] = {
    "master": {
        "name": "Master Data",
        "color": "blue",
        "description": "Data master: barang, outlet, distributor",
        "outputs": ["barang", "outlet", "distributor"],
    },
    "demand_supply": {
        "name": "Demand-Supply Planning",
        "color": "purple",
        "description": "Membuat rencana beli dan jual",
        "outputs": ["deal_jual", "deal_beli"],
    },
    "accounting_tax": {
        "name": "Controller Accounting Tax",
        "color": "teal",
        "description": "Mencatat deal dan transaksi",
        "outputs": ["invoice"],
    },
    "logistic": {
        "name": "Logistic",
        "color": "amber",
        "description": "Terima, kirim, dan simpan barang",
        "outputs": ["surat_jalan", "delivery_order", "good_receipt_note", "laporan_stok"],
    },
    "finance": {
        "name": "Finance",
        "color": "coral",
        "description": "Pengelolaan keuangan perusahaan",
        "outputs": ["laporan_cashflow", "bukti_pembayaran", "laporan_keuangan", "anggaran"],
    },
}


SENSITIVITY_MATRIX: dict[str, list[str]] = {
    "Confidential": ["deal_orders", "tax_reports", "reports", "budgets", "payments"],
    "Internal": [
        "invoices", "transactions", "journal_entries", "cashflow", "receivables",
        "inbound", "outbound", "warehouse", "demand_plans", "supply_plans", "forecasts",
    ],
    "Public_Internal": ["sops", "reference", "policies", "shipping_docs"],
}


def get_subfolder_sensitivity(subfolder: str) -> str:
    for level, folders in SENSITIVITY_MATRIX.items():
        if subfolder in folders:
            return level
    return "Internal"


AUTO_TAG_RULES: list[dict] = [
    {"keyword": "invoice",      "tags": ["invoice", "accounting"]},
    {"keyword": "deal_beli",    "tags": ["deal", "pembelian", "demand_supply"]},
    {"keyword": "deal_jual",    "tags": ["deal", "penjualan", "demand_supply"]},
    {"keyword": "surat_jalan",  "tags": ["pengiriman", "outbound", "logistic"]},
    {"keyword": "stok",         "tags": ["stok", "warehouse", "logistic"]},
    {"keyword": "cashflow",     "tags": ["cashflow", "keuangan", "finance"]},
    {"keyword": "forecast",     "tags": ["forecast", "perencanaan"]},
    {"keyword": "tax",          "tags": ["pajak", "tax", "accounting"]},
    {"keyword": "grn",          "tags": ["penerimaan", "inbound", "logistic"]},
]


def auto_detect_tags(filename: str) -> list[str]:
    name_lower = filename.lower()
    tags: list[str] = []
    for rule in AUTO_TAG_RULES:
        if rule["keyword"] in name_lower:
            for tag in rule["tags"]:
                if tag not in tags:
                    tags.append(tag)
    return tags


def initialize_knowledge_base(kb_path: str | Path) -> None:
    kb_root = Path(kb_path)
    kb_root.mkdir(parents=True, exist_ok=True)

    # Create master directory for master data (barang, outlet, distributor)
    master_path = kb_root / "master"
    master_path.mkdir(exist_ok=True)

    # Create departments directory with sub-department folders
    departments_path = kb_root / "departments"
    departments_path.mkdir(exist_ok=True)

    for department, subfolders in DEPARTMENTS.items():
        dept_path = departments_path / department
        dept_path.mkdir(exist_ok=True)

        for subfolder in subfolders:
            subfolder_path = dept_path / subfolder
            subfolder_path.mkdir(exist_ok=True)
