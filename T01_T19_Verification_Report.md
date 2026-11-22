# Nimbus PayDesk
# T-01 to T-19 Verification Report

## 1. Project Information

**Project:** Nimbus PayDesk  
**Project Type:** Invoice Automation with Human-in-the-Loop Controls  
**Python Version:** 3.11.0  
**Testing Framework:** Pytest  
**Test Date:** 22 November 2026

## 2. Overall Test Results

| Metric | Result |
|---|---:|
| Total automated tests | 70 |
| Passed tests | 70 |
| Failed tests | 0 |
| Warnings | 2 |
| Risk scenarios in safety suite | 24 |

**Latest full test command:**

```powershell
python -m pytest -v
```

**Recorded result:** 70 passed, 2 warnings in 13.30 seconds.

## 3. T-01 to T-19 Verification Matrix

| Test ID | Test Scenario | Evidence | Status |
|---|---|---|---|
| T-01 | Clean invoice ₹12,000 | Real tools integration test | PASS |
| T-02 | High-value invoice ₹75,000 | Human approval and safety tests | PASS |
| T-03 | Exact threshold ₹50,000 | Router boundary test | PASS |
| T-04 | Invoice ₹49,999 | Router boundary test | PASS |
| T-05 | Invalid GSTIN | Safety gate test | PASS |
| T-06 | Inactive GSTIN | Real tools integration test | PASS |
| T-07 | PO mismatch | Real tools integration test | PASS |
| T-08 | Duplicate invoice | Real tools integration test | PASS |
| T-09 | Confidence 0.79 | Safety gate test | PASS |
| T-10 | Confidence 0.80 | Router boundary test | PASS |
| T-11 | GST tool failure | GST failure test | PASS |
| T-12 | Extraction failure | Extraction failure tests | PASS |
| T-13 | Missing amount | API acceptance test | PASS |
| T-14 | Missing API key | API security test | PASS |
| T-15 | Incorrect API path | HTTP 404 verification | PASS |
| T-16 | Named human approval and audit | API acceptance test | PASS |
| T-17 | Missing reviewer rejected | API security test | PASS |
| T-18 | Audit events and CID traceability | API audit test and database inspection | PASS |
| T-19 | Risky invoice safety scenarios | 24 simulated scenarios | PASS - SIMULATED |

## 4. Safety Gate Verification

The safety suite tested 24 simulated risky scenarios.

Covered conditions:

- High-value invoices.
- Low extraction confidence.
- Invalid, inactive and unknown GSTIN.
- GST verification failure.
- Missing and mismatched purchase orders.
- Duplicate invoices.
- Policy retrieval failures.
- Invalid tool responses.
- Combined risk conditions.

All 24 simulated risky scenarios resulted in `needs_human`.

A clean control invoice successfully reached `ready_to_pay`.

**Important:** These are controlled simulated test cases, not 24 independently processed real invoices. A production-scale Missed-Gate Rate has not been established.

## 5. Audit Trail Verification

A complete invoice processing journey produced nine audit events:

1. INTAKE - invoice_received
2. EXTRACTOR - extraction_completed
3. POLICY_CHECKER - gst_check_completed
4. POLICY_CHECKER - po_check_completed
5. POLICY_CHECKER - duplicate_check_completed
6. POLICY_CHECKER - policy_retrieval_completed
7. EXCEPTION_ROUTER - decision_completed
8. EXCEPTION_ROUTER - status_assigned
9. REPORTER - decision_report_generated

All nine records shared the same correlation ID.

Human approval and status-change events were also verified through API acceptance tests.

## 6. API Security Verification

The following checks passed:

- Missing API key returns HTTP 401.
- Invalid API key returns HTTP 401.
- Missing required invoice amount returns HTTP 422.
- Missing reviewer is rejected with HTTP 422.
- Unknown ticket returns HTTP 404.
- Duplicate human stamping is rejected.
- Approval cannot override an inactive GSTIN or extraction failure.

## 7. Known Limitations

1. PDF extraction is tailored to the supplied specimen invoice format.
2. Scanned PDF OCR is not implemented.
3. Extraction confidence is provisional and not statistically calibrated.
4. Structured invoice ingestion and PDF extraction are separate workflows.
5. n8n integration requires separate implementation and verification evidence.
6. No real bank or NEFT payment is executed.
7. The two FastAPI deprecation warnings remain.

## 8. Final Assessment

The latest automated regression suite completed successfully with 70 passing tests and zero failures.

The T-01 to T-19 matrix records the available verification evidence. T-19 is verified through 24 controlled simulated risky scenarios; it is not a production-scale safety certification.

This project is an academic prototype and requires further validation before production deployment.

---

**Report prepared:** 22 November 2026  
**Project:** Nimbus PayDesk