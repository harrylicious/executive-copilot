"""Deep testing script for questions-answers2.json against the /api/chat endpoint.

Sends each question to the backend, checks response against expected_keywords,
reports pass/fail, and optionally updates ground_truth for mismatches.
"""

import json
import sys
import time
from pathlib import Path

import httpx

BASE_URL = "http://localhost:8000/api/chat"
QA_FILE = Path(__file__).parent.parent / "json" / "questions-answers2.json"

# Load questions
with open(QA_FILE, "r", encoding="utf-8") as f:
    questions = json.load(f)

results = []
updated = False

print(f"{'='*80}")
print(f"DEEP TEST: Running {len(questions)} questions against /api/chat")
print(f"{'='*80}\n")

for qa in questions:
    qid = qa["id"]
    question = qa["question"]
    expected_keywords = qa["expected_keywords"]
    ground_truth = qa["ground_truth"]

    print(f"[Q{qid:02d}] {question}")
    print(f"  Category: {qa['category']} | Difficulty: {qa['difficulty']}")

    payload = {
        "query": question,
        "retrieval_mode": "combined",
        "language": "id",
    }

    try:
        start = time.time()
        with httpx.Client(timeout=90.0) as client:
            resp = client.post(BASE_URL, json=payload)
        elapsed = time.time() - start

        if resp.status_code != 200:
            print(f"  ❌ HTTP {resp.status_code}: {resp.text[:200]}")
            results.append({
                "id": qid,
                "status": "ERROR",
                "http_status": resp.status_code,
                "error": resp.text[:200],
            })
            print()
            continue

        data = resp.json()
        answer = data.get("answer", "")
        response_type = data.get("response_type", "")
        docs_retrieved = data.get("retrieval_metadata", {}).get("documents_retrieved", 0)

        # Check keywords
        matched = []
        missed = []
        for kw in expected_keywords:
            if kw.lower() in answer.lower():
                matched.append(kw)
            else:
                missed.append(kw)

        match_ratio = len(matched) / len(expected_keywords) if expected_keywords else 1.0
        passed = match_ratio >= 0.5  # At least 50% keywords matched

        status = "PASS" if passed else "FAIL"
        icon = "✅" if passed else "❌"

        print(f"  {icon} {status} ({len(matched)}/{len(expected_keywords)} keywords matched) | {elapsed:.1f}s | {docs_retrieved} docs")
        if matched:
            print(f"     Matched: {matched}")
        if missed:
            print(f"     Missed:  {missed}")
        print(f"     Answer (first 200): {answer[:200]}")

        result_entry = {
            "id": qid,
            "status": status,
            "match_ratio": match_ratio,
            "matched_keywords": matched,
            "missed_keywords": missed,
            "elapsed_s": round(elapsed, 2),
            "docs_retrieved": docs_retrieved,
            "response_type": response_type,
            "answer_preview": answer[:300],
        }
        results.append(result_entry)

        # Update _test_status and _test_actual fields (preserving ground_truth)
        qa["_test_status"] = status
        qa["_test_actual"] = answer[:500] if answer.strip() else ""
        if not passed:
            qa["_test_note"] = f"Matched {len(matched)}/{len(expected_keywords)} keywords. Missed: {missed}"
        updated = True

    except httpx.TimeoutException:
        print(f"  ❌ TIMEOUT (90s)")
        results.append({"id": qid, "status": "TIMEOUT"})
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        results.append({"id": qid, "status": "ERROR", "error": str(e)})

    print()

# Summary
print(f"\n{'='*80}")
print("SUMMARY")
print(f"{'='*80}")
passed_count = sum(1 for r in results if r.get("status") == "PASS")
failed_count = sum(1 for r in results if r.get("status") == "FAIL")
error_count = sum(1 for r in results if r.get("status") in ("ERROR", "TIMEOUT"))
print(f"  Total:  {len(results)}")
print(f"  Passed: {passed_count}")
print(f"  Failed: {failed_count}")
print(f"  Errors: {error_count}")
print(f"  Pass Rate: {passed_count/len(results)*100:.1f}%")

# Save updated JSON if there were failures
if updated:
    with open(QA_FILE, "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)
    print(f"\n  📝 Updated {QA_FILE} with actual responses for failed questions.")

# Save detailed report
report_file = Path(__file__).parent.parent / "_qa2_test_report.json"
with open(report_file, "w", encoding="utf-8") as f:
    json.dump({
        "summary": {
            "total": len(results),
            "passed": passed_count,
            "failed": failed_count,
            "errors": error_count,
            "pass_rate": f"{passed_count/len(results)*100:.1f}%",
        },
        "results": results,
    }, f, ensure_ascii=False, indent=2)
print(f"  📊 Detailed report saved to {report_file}")
