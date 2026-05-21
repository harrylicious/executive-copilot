"""Seed data service for populating the knowledge base with sample files on first startup.

Updated per specification v2.0 — 4 actual departments (Phase 1):
- demand_supply, accounting_tax, logistic, finance
"""

from pathlib import Path

from app.config import settings
from app.utils.department_config import DEPARTMENTS


_SEED_DATA: dict[str, list[dict[str, str]]] = {
    "demand_supply": [
        {
            "subfolder": "demand_plans",
            "filename": "demand_plan_jan2025.xlsx",
            "content": (
                "Demand Plan - January 2025\n"
                "==========================\n\n"
                "Product\tJan Forecast\tActual\tVariance\n"
                "Widget A\t5000\t4850\t-3.0%\n"
                "Widget B\t3200\t3100\t-3.1%\n"
                "Gadget Pro\t1800\t1950\t+8.3%\n"
            ),
        },
        {
            "subfolder": "supply_plans",
            "filename": "supply_plan_q1.xlsx",
            "content": (
                "Supply Plan - Q1 2025\n"
                "=====================\n\n"
                "Material\tJan\tFeb\tMar\n"
                "Raw Mat A\t1000\t1200\t1100\n"
                "Raw Mat B\t500\t550\t600\n"
            ),
        },
        {
            "subfolder": "deal_orders",
            "filename": "deal_jual_001.pdf",
            "content": (
                "DEAL JUAL - 001\n"
                "==============\n"
                "Customer: PT Maju Jaya\n"
                "Product: Widget A - 500 units\n"
                "Price: Rp 25,000,000\n"
                "Date: 2025-01-15\n"
            ),
        },
        {
            "subfolder": "forecasts",
            "filename": "forecast_2025_q2.csv",
            "content": (
                "month,product,forecast\n"
                "2025-04,Widget A,5200\n"
                "2025-04,Widget B,3300\n"
                "2025-05,Widget A,5400\n"
                "2025-05,Widget B,3400\n"
                "2025-06,Widget A,5600\n"
                "2025-06,Widget B,3500\n"
            ),
        },
        {
            "subfolder": "reference",
            "filename": "sop_demand_planning.pdf",
            "content": (
                "SOP Demand Planning\n"
                "===================\n"
                "1. Collect historical sales data\n"
                "2. Run forecast model\n"
                "3. Review with Demand Manager\n"
                "4. Finalize demand plan by 25th each month\n"
            ),
        },
    ],
    "accounting_tax": [
        {
            "subfolder": "invoices",
            "filename": "INV-2025-001.pdf",
            "content": (
                "INVOICE - INV-2025-001\n"
                "=====================\n"
                "Customer: PT Maju Jaya\n"
                "Amount: Rp 25,000,000\n"
                "Due: 2025-02-15\n"
                "Status: Unpaid\n"
            ),
        },
        {
            "subfolder": "transactions",
            "filename": "transaksi_jan2025.xlsx",
            "content": (
                "Transaction Recap - Jan 2025\n"
                "============================\n"
                "Date\tDesc\tDebit\tCredit\n"
                "2025-01-02\tSale INV-001\t0\t25,000,000\n"
                "2025-01-05\tVendor Payment\t12,000,000\t0\n"
            ),
        },
        {
            "subfolder": "tax_reports",
            "filename": "ppn_jan2025.xlsx",
            "content": (
                "PPN Report - Jan 2025\n"
                "=====================\n"
                "Output Tax: Rp 2,500,000\n"
                "Input Tax: Rp 1,200,000\n"
                "Net PPN: Rp 1,300,000\n"
            ),
        },
        {
            "subfolder": "journal_entries",
            "filename": "journal_jan2025.json",
            "content": (
                '[\n'
                '  {"date":"2025-01-02","account":"Cash","debit":25000000,"credit":0},\n'
                '  {"date":"2025-01-02","account":"Revenue","debit":0,"credit":25000000},\n'
                '  {"date":"2025-01-05","account":"Inventory","debit":12000000,"credit":0},\n'
                '  {"date":"2025-01-05","account":"Cash","debit":0,"credit":12000000}\n'
                ']\n'
            ),
        },
        {
            "subfolder": "policies",
            "filename": "coa_2025.xlsx",
            "content": (
                "Chart of Accounts 2025\n"
                "=====================\n"
                "1-1000\tCash & Bank\n"
                "1-2000\tAccounts Receivable\n"
                "2-1000\tAccounts Payable\n"
                "4-1000\tRevenue\n"
                "5-1000\tCOGS\n"
            ),
        },
    ],
    "logistic": [
        {
            "subfolder": "inbound",
            "filename": "grn_001.pdf",
            "content": (
                "GOOD RECEIPT NOTE - GRN-001\n"
                "===========================\n"
                "PO Reference: PO-2025-001\n"
                "Material: Raw Mat A - 1000 kg\n"
                "Received: 2025-01-10\n"
                "Inspected By: Budi\n"
                "Status: Accepted\n"
            ),
        },
        {
            "subfolder": "outbound",
            "filename": "sj_001.pdf",
            "content": (
                "SURAT JALAN - SJ-001\n"
                "====================\n"
                "DO Reference: DO-2025-001\n"
                "Customer: PT Maju Jaya\n"
                "Items: Widget A - 500 units\n"
                "Driver: Ahmad\n"
            ),
        },
        {
            "subfolder": "warehouse",
            "filename": "stok_jan2025.xlsx",
            "content": (
                "Stock Report - Jan 2025\n"
                "======================\n"
                "SKU\tProduct\tQty\tMin Stock\n"
                "W-001\tWidget A\t1200\t200\n"
                "W-002\tWidget B\t800\t150\n"
                "W-003\tGadget Pro\t350\t100\n"
            ),
        },
        {
            "subfolder": "shipping_docs",
            "filename": "packing_list_001.pdf",
            "content": (
                "PACKING LIST - 001\n"
                "==================\n"
                "Shipment: SH-2025-001\n"
                "Box 1: Widget A x 250 units\n"
                "Box 2: Widget A x 250 units\n"
                "Total Weight: 500 kg\n"
            ),
        },
        {
            "subfolder": "sops",
            "filename": "sop_penerimaan_barang.pdf",
            "content": (
                "SOP Penerimaan Barang\n"
                "====================\n"
                "1. Check delivery document\n"
                "2. Inspect quantity and quality\n"
                "3. Create GRN\n"
                "4. Update inventory system\n"
            ),
        },
    ],
    "finance": [
        {
            "subfolder": "cashflow",
            "filename": "cashflow_jan2025.xlsx",
            "content": (
                "Cashflow Report - Jan 2025\n"
                "==========================\n"
                "Date\tIn\tOut\tBalance\n"
                "2025-01-01\t0\t0\t500,000,000\n"
                "2025-01-02\t25,000,000\t0\t525,000,000\n"
                "2025-01-05\t0\t12,000,000\t513,000,000\n"
                "2025-01-31\t0\t15,000,000\t498,000,000\n"
            ),
        },
        {
            "subfolder": "payments",
            "filename": "bayar_vendor_001.pdf",
            "content": (
                "BUKTI PEMBAYARAN - BP-001\n"
                "=========================\n"
                "Vendor: PT Supplier Jaya\n"
                "Amount: Rp 12,000,000\n"
                "Payment Date: 2025-01-05\n"
                "Method: Bank Transfer\n"
            ),
        },
        {
            "subfolder": "receivables",
            "filename": "aging_report_jan2025.xlsx",
            "content": (
                "Aging Report - Jan 2025\n"
                "=======================\n"
                "Customer\t0-30\t31-60\t61-90\n"
                "PT Maju Jaya\t25,000,000\t0\t0\n"
                "PT Sukses Abadi\t0\t15,000,000\t0\n"
                "PT Makmur Sentosa\t0\t0\t5,000,000\n"
            ),
        },
        {
            "subfolder": "budgets",
            "filename": "rkap_2025.xlsx",
            "content": (
                "RKAP 2025\n"
                "=========\n"
                "Category\tBudget\tQ1 Actual\n"
                "Revenue\t120,000,000,000\t28,000,000,000\n"
                "COGS\t84,000,000,000\t19,600,000,000\n"
                "OPEX\t24,000,000,000\t5,800,000,000\n"
            ),
        },
        {
            "subfolder": "reports",
            "filename": "laporan_keuangan_jan2025.pdf",
            "content": (
                "LAPORAN KEUANGAN - Jan 2025\n"
                "===========================\n"
                "Revenue: Rp 28,000,000,000\n"
                "COGS: Rp 19,600,000,000\n"
                "Gross Profit: Rp 8,400,000,000\n"
                "OPEX: Rp 5,800,000,000\n"
                "Net Profit: Rp 2,600,000,000\n"
            ),
        },
    ],
}


def _department_has_files(kb_root: Path, department: str) -> bool:
    dept_path = kb_root / department
    if not dept_path.exists():
        return False
    return any(f.is_file() for f in dept_path.rglob("*"))


def seed_knowledge_base(kb_path: str | Path | None = None) -> dict[str, int]:
    if kb_path is None:
        kb_path = settings.knowledge_base_path
    kb_root = Path(kb_path)

    departments_seeded = 0
    files_created = 0

    for department, seed_files in _SEED_DATA.items():
        if _department_has_files(kb_root, department):
            continue

        for file_info in seed_files:
            subfolder = file_info["subfolder"]
            filename = file_info["filename"]
            content = file_info["content"]

            file_path = kb_root / department / subfolder / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            files_created += 1

        departments_seeded += 1

    return {"departments_seeded": departments_seeded, "files_created": files_created}
