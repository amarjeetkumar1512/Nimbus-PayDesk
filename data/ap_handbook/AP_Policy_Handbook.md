# NIMBUS RETAIL
# Accounts Payable (AP) Policy Handbook

**Document ID:** NIMBUS-AP-POL-001  
**Version:** 1.0  
**Document Type:** Project Prototype Policy Document  
**Department:** Accounts Payable  
**System:** Nimbus PayDesk – Invoice Automation  
**Status:** Prototype Reference  
**Purpose:** Policy guidance for automated invoice validation and human review

---

## 1. Purpose

This handbook defines the policy guidance used by Nimbus PayDesk to process supplier invoices safely and consistently.

The system is designed to reduce manual invoice-processing effort while ensuring that suspicious, incomplete, uncertain, or high-risk invoices are routed to authorized human reviewers.

**Core principle: The AI reads and explains. Plain, testable code decides.**

This document is a project-specific prototype policy reference, not an official corporate policy of Nimbus Retail.

## 2. Scope

This policy applies to the prototype invoice-processing workflow, including:

- Invoice intake and validation.
- Vendor and GSTIN verification.
- Purchase order verification.
- Duplicate invoice detection.
- Invoice data extraction and confidence assessment.
- Policy retrieval and exception handling.
- Human approval and rejection.
- Audit logging and decision reporting.

The prototype does not execute bank transfers, NEFT transactions, or actual supplier payments.

## 3. Invoice Intake Policy

Every invoice submitted for processing must contain the following mandatory information:

| Field | Description |
|---|---|
| invoice_id | Unique invoice reference |
| vendor | Supplier name |
| amount | Invoice amount |
| gstin | Supplier GST identification number |
| po_id | Associated purchase order reference |

### Intake requirements

1. The API must validate the incoming invoice payload.
2. An invoice with missing or invalid mandatory fields must not proceed as a valid invoice.
3. Every accepted invoice must receive a unique ticket and correlation ID (CID).
4. The system must record an invoice-received audit event.
5. The correlation ID must remain associated with all subsequent processing events.

## 4. Vendor Verification and GSTIN Policy

Vendor verification is required before an invoice can become Ready to Pay.

### Verification requirements

1. Validate the GSTIN format.
2. Check whether the GSTIN exists in the vendor database.
3. Verify that the vendor record is active.
4. Check whether the invoice vendor corresponds to the verified vendor record.

### Exception conditions

The invoice must be routed to Needs Human when:

- GSTIN format is invalid.
- GSTIN is not registered in the prototype vendor database.
- Vendor status is inactive.
- Vendor verification fails.
- The verification tool returns an error.

The system must never assume that an unverified vendor is valid.

## 5. Purchase Order Verification Policy

Every invoice must be checked against its associated purchase order.

### Verification requirements

1. Confirm that the referenced PO exists.
2. Compare the invoice vendor with the PO vendor.
3. Compare the invoice amount with the PO amount.
4. Record the verification result.

### Exception conditions

A missing purchase order, vendor mismatch, amount mismatch, or verification failure must result in Needs Human.

The system must not automatically approve an invoice with an unresolved PO discrepancy.

## 6. Duplicate Invoice Policy

Duplicate detection is mandatory to reduce the risk of repeated invoice processing.

### Verification requirements

1. Check whether the invoice reference has already been processed.
2. Identify previously registered invoice records.
3. Record the duplicate-check result.

If an invoice is identified as a duplicate, it must be routed to Needs Human for investigation.

If duplicate detection fails or produces an uncertain result, the system must fail closed and route the invoice to Needs Human.

## 7. Invoice Extraction and Confidence Policy

The extraction component converts invoice information into structured data.

### Extraction requirements

1. Extract the supplier name.
2. Extract the invoice amount.
3. Extract the GSTIN.
4. Extract the purchase order reference.
5. Provide a confidence score for extracted information.

### Confidence rule

The minimum confidence threshold is **0.80**.

- Confidence below 0.80: human verification is mandatory.
- Confidence equal to or above 0.80: the confidence condition alone does not require human review.

A confidence score does not override GSTIN, PO, duplicate, high-value, or other mandatory checks.

The system must not guess missing or uncertain invoice information.

## 8. Invoice Approval Policy

The prototype uses two final processing outcomes:

- Ready to Pay
- Needs Human

### High-value approval rule

An invoice with an amount equal to or greater than **₹50,000** requires human approval.

| Invoice amount | Approval requirement |
|---|---|
| Below ₹50,000 | Subject to all other validation and policy checks |
| Equal to ₹50,000 | Human approval required |
| Above ₹50,000 | Human approval required |

An invoice below ₹50,000 is not automatically approved merely because it is low value. All mandatory checks must pass.

## 9. Exception Management Policy

The following conditions require human intervention:

| Exception | Required handling |
|---|---|
| Invalid GSTIN | Needs Human |
| Unknown GSTIN | Needs Human |
| Inactive vendor | Needs Human |
| PO not found | Needs Human |
| PO vendor mismatch | Needs Human |
| PO amount mismatch | Needs Human |
| Duplicate invoice | Needs Human |
| Confidence below 0.80 | Needs Human |
| Amount ≥ ₹50,000 | Needs Human |
| Extraction failure | Needs Human |
| Tool or database failure | Needs Human |

### Fail-Closed Requirement

If any mandatory verification tool fails, the system must not approve the invoice.

Unknown, incomplete, or uncertain verification results must be treated as exceptions.

## 10. Human-in-the-Loop Approval Policy

Human review is required for invoices that meet one or more exception conditions.

### Reviewer requirements

1. A reviewer must be identified by name.
2. The reviewer must explicitly approve or reject the invoice.
3. The decision must be recorded through the stamp endpoint.
4. The system must record the reviewer and decision.
5. The status change must generate an audit event.

A human decision must not be represented as an automated approval.

## 11. Audit and Traceability Policy

Every invoice must have an identifiable processing history.

### Audit requirements

The system must record:

- Correlation ID.
- Invoice ID.
- Processing stage.
- Event name.
- Event details.
- Event timestamp.
- Relevant status changes.

Every status change must generate an audit event.

The invoice journey must be reconstructable using its correlation ID.

## 12. Security and Data Handling Policy

The prototype must follow basic application security practices.

1. API requests must use API-key authentication.
2. Missing or invalid API keys must be rejected.
3. Secrets must be stored in environment variables.
4. Sensitive configuration must not be hard-coded.
5. The `.env` file must not be committed to GitHub.
6. API errors must not be reported as successful processing.

## 13. Automation Boundaries

Nimbus PayDesk automates invoice validation, decision routing, and reporting.

The prototype may produce a Ready to Pay status after all mandatory checks pass.

However:

- It does not execute bank payments.
- It does not execute NEFT transfers.
- It does not independently bypass human approval.
- It does not approve uncertain or failed verification results.

Ready to Pay is a workflow status, not confirmation that money has been transferred.

## 14. Policy Retrieval and Knowledge Base

This handbook is the reference document for the prototype's AP policy knowledge base.

The document will be processed into text chunks and indexed in ChromaDB.

The policy retrieval component will:

1. Receive a policy-related query.
2. Retrieve relevant handbook sections.
3. Return supporting policy text to the processing workflow.
4. Make the retrieved information available for explanation and reporting.

Policy retrieval provides context and guidance. It does not replace deterministic validation or routing rules.

## 15. Final Decision Control Matrix

| Control | Mandatory rule | Failure outcome |
|---|---|---|
| GSTIN verification | Valid and active vendor | Needs Human |
| PO verification | Existing and matching PO | Needs Human |
| Duplicate detection | No duplicate | Needs Human |
| Extraction confidence | At least 0.80 | Needs Human |
| High-value invoice | Amount ≥ ₹50,000 | Needs Human |
| Tool execution | Successful verification | Needs Human |
| Audit logging | Record every status change | Processing must not silently succeed |

### Final Routing Principle

An invoice may reach Ready to Pay only when all mandatory validation and policy checks pass and no human-approval condition exists.

Otherwise, the invoice must be routed to Needs Human.

**Safety Target: Missed-Gate Rate = 0**

---

**End of Document**

**Nimbus PayDesk | Accounts Payable Policy Reference | Version 1.0**