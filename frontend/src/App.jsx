
import { useEffect, useMemo, useState } from 'react'
import './App.css'

const DEFAULT_API_URL = '/api'
const PAGE_SIZE = 10

const EMPTY_INVOICE = {
  invoice_id: '',
  vendor: '',
  gstin: '',
  po_id: '',
  amount: '',
}

const EMPTY_REVIEW = {
  reviewer: '',
  decision: '',
  comment: '',
}

function getTicketId(data) {
  return data?.ticket_id || data?.ticket?.ticket_id || data?.data?.ticket_id || ''
}

function getStatus(data) {
  return (
    data?.status ||
    data?.ticket_status ||
    data?.decision ||
    data?.ticket?.status ||
    data?.data?.status ||
    'Received'
  )
}

function getInvoiceId(data) {
  return (
    data?.invoice_id ||
    data?.invoice_number ||
    data?.ticket?.invoice_id ||
    data?.invoice?.invoice_number ||
    '—'
  )
}

function getReason(data) {
  return data?.reason || data?.ticket?.reason || ''
}

function getDate(data) {
  return data?.updated_at || data?.created_at || data?.timestamp || ''
}

function formatDate(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)

  return date.toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function isReviewRequired(ticket) {
  const status = getStatus(ticket).toLowerCase()
  return (
    status.includes('human') ||
    status.includes('review') ||
    status.includes('hold') ||
    status.includes('reject')
  )
}

function isReady(ticket) {
  const status = getStatus(ticket).toLowerCase()
  return (
    status.includes('ready') ||
    status.includes('approved') ||
    status.includes('pay')
  )
}

function canApproveTicket(ticket) {
  return (
    getStatus(ticket).toLowerCase() === 'needs_human' &&
    getReason(ticket).trim() === 'amount>=50000'
  )
}

function extractTicketList(data) {
  if (Array.isArray(data)) return data
  if (Array.isArray(data?.tickets)) return data.tickets
  if (Array.isArray(data?.data?.tickets)) return data.data.tickets
  if (Array.isArray(data?.items)) return data.items
  if (Array.isArray(data?.records)) return data.records
  if (data?.ticket && typeof data.ticket === 'object') return [data]
  if (data?.ticket_id || data?.data?.ticket_id) return [data]
  return []
}

function normalizeTicketRecord(record) {
  if (!record || typeof record !== 'object') return null

  if (record.ticket && typeof record.ticket === 'object') {
    return {
      ...record,
      ...record.ticket,
      ticket_id: getTicketId(record.ticket) || record.ticket_id || '',
      audit_events:
        record.audit_events ||
        record.audit_trail ||
        record.events ||
        record.ticket.audit_events ||
        record.ticket.events ||
        [],
      report: record.report || record.ticket.report || '',
    }
  }

  return record
}

function sortTicketsByDate(ticketList) {
  return [...ticketList].sort((a, b) => {
    const dateA = new Date(getDate(a)).getTime() || 0
    const dateB = new Date(getDate(b)).getTime() || 0
    return dateB - dateA
  })
}

function App() {
  const [apiUrl] = useState(DEFAULT_API_URL)
  const [activePage, setActivePage] = useState('Dashboard')

  const [tickets, setTickets] = useState([])
  const [totalTickets, setTotalTickets] = useState(0)
  const [selectedTicket, setSelectedTicket] = useState(null)

  const [ticketId, setTicketId] = useState('')
  const [search, setSearch] = useState('')
  const [visibleLimit, setVisibleLimit] = useState(PAGE_SIZE)

  const [invoiceForm, setInvoiceForm] = useState(EMPTY_INVOICE)
  const [invoiceStep, setInvoiceStep] = useState(1)
  const [reviewForm, setReviewForm] = useState(EMPTY_REVIEW)

  const [showSubmitPanel, setShowSubmitPanel] = useState(false)
  const [showStampPanel, setShowStampPanel] = useState(false)

  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const apiRoot = apiUrl.trim().replace(/\/+$/, '')

  const sortedTickets = useMemo(
    () => sortTicketsByDate(tickets),
    [tickets],
  )

  const reviewTickets = useMemo(
    () => sortedTickets.filter(isReviewRequired),
    [sortedTickets],
  )

  const readyTickets = useMemo(
    () => sortedTickets.filter(isReady),
    [sortedTickets],
  )

  const otherTickets = useMemo(
    () => sortedTickets.filter(
      (ticket) => !isReviewRequired(ticket) && !isReady(ticket),
    ),
    [sortedTickets],
  )

  const visibleTickets = useMemo(() => {
    let result = sortedTickets

    if (activePage === 'Human Review') {
      result = reviewTickets
    }

    const query = search.trim().toLowerCase()
    if (!query) return result

    return result.filter((ticket) => {
      const searchable = [
        getTicketId(ticket),
        getStatus(ticket),
        getInvoiceId(ticket),
        ticket?.vendor_name,
        ticket?.vendor,
        ticket?.supplier_name,
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()

      return searchable.includes(query)
    })
  }, [sortedTickets, reviewTickets, activePage, search])

  const displayedTickets = useMemo(
    () => visibleTickets.slice(0, visibleLimit),
    [visibleTickets, visibleLimit],
  )

  const auditRecords = useMemo(() => {
    const records = []

    sortedTickets.forEach((ticket) => {
      const events =
        ticket?.audit_events ||
        ticket?.audit_trail ||
        ticket?.audit_logs ||
        ticket?.events

      if (Array.isArray(events)) {
        events.forEach((event, index) => {
          records.push({
            ...event,
            ticket_id: getTicketId(ticket),
            event_key: `${getTicketId(ticket)}-${index}`,
          })
        })
      }
    })

    return records.sort((a, b) => {
      const dateA = new Date(a.ts || a.timestamp || a.created_at || 0).getTime() || 0
      const dateB = new Date(b.ts || b.timestamp || b.created_at || 0).getTime() || 0
      return dateB - dateA
    })
  }, [sortedTickets])

  async function requestApi(path, options = {}) {
    const response = await fetch(`${apiRoot}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
      },
    })

    const responseText = await response.text()
    let data

    try {
      data = responseText ? JSON.parse(responseText) : {}
    } catch {
      data = { message: responseText }
    }

    if (!response.ok) {
      const detail = data?.detail
      throw new Error(
        typeof detail === 'string'
          ? detail
          : detail
            ? JSON.stringify(detail)
            : data?.message || `Request failed (${response.status})`,
      )
    }

    return data
  }

  useEffect(() => {
    let cancelled = false

    async function loadTickets() {
      try {
        const data = await requestApi('/tickets')

        const ticketList = extractTicketList(data)
          .map(normalizeTicketRecord)
          .filter(Boolean)

        const sortedList = sortTicketsByDate(ticketList)

        if (!cancelled) {
          setTickets(sortedList)
          setTotalTickets(
            Number.isFinite(Number(data?.total))
              ? Number(data.total)
              : sortedList.length,
          )
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || 'Could not load saved tickets.')
        }
      }
    }

    loadTickets()

    return () => {
      cancelled = true
    }
  }, [apiRoot])

  function addTicket(data) {
    const id = getTicketId(data)

    setTickets((current) => {
      if (!id) return sortTicketsByDate([data, ...current])

      return sortTicketsByDate([
        data,
        ...current.filter((item) => getTicketId(item) !== id),
      ])
    })

    setTotalTickets((current) => {
      const alreadyExists = tickets.some((item) => getTicketId(item) === id)
      return id && !alreadyExists ? current + 1 : current
    })

    setSelectedTicket(data)
    if (id) setTicketId(id)
  }

  function changePage(page) {
    setActivePage(page)
    setSearch('')
    setVisibleLimit(PAGE_SIZE)
    setMessage('')
    setError('')
    setSelectedTicket(null)
  }

  function openSubmitPanel() {
    setInvoiceForm(EMPTY_INVOICE)
    setInvoiceStep(1)
    setShowSubmitPanel(true)
    setError('')
    setMessage('')
  }

  function closeSubmitPanel() {
    if (loading) return
    setShowSubmitPanel(false)
    setInvoiceStep(1)
    setInvoiceForm(EMPTY_INVOICE)
    setError('')
  }

  function openReviewPanel() {
    setReviewForm(EMPTY_REVIEW)
    setShowStampPanel(true)
    setError('')
    setMessage('')
  }

  function closeReviewPanel() {
    if (loading) return
    setShowStampPanel(false)
    setReviewForm(EMPTY_REVIEW)
    setError('')
  }

  function updateInvoiceField(field, value) {
    setInvoiceForm((current) => ({
      ...current,
      [field]: value,
    }))
  }

  function updateReviewField(field, value) {
    setReviewForm((current) => ({
      ...current,
      [field]: value,
    }))
  }

  function validateInvoiceStep(step) {
    if (step === 1) {
      if (!invoiceForm.invoice_id.trim()) {
        setError('Invoice ID enter karo.')
        return false
      }

      if (!invoiceForm.vendor.trim()) {
        setError('Vendor name enter karo.')
        return false
      }

      if (!invoiceForm.gstin.trim()) {
        setError('GSTIN enter karo.')
        return false
      }
    }

    if (step === 2) {
      if (!invoiceForm.po_id.trim()) {
        setError('PO ID enter karo.')
        return false
      }

      const amount = Number(invoiceForm.amount)

      if (!invoiceForm.amount.trim() || !Number.isFinite(amount) || amount <= 0) {
        setError('Valid invoice amount enter karo. Amount zero se greater hona chahiye.')
        return false
      }
    }

    setError('')
    return true
  }

  function goToNextInvoiceStep() {
    if (!validateInvoiceStep(invoiceStep)) return
    setInvoiceStep((current) => Math.min(current + 1, 3))
  }

  function goToPreviousInvoiceStep() {
    setError('')
    setInvoiceStep((current) => Math.max(current - 1, 1))
  }

  async function submitInvoice(event) {
    event.preventDefault()
    setError('')
    setMessage('')

    if (!validateInvoiceStep(1) || !validateInvoiceStep(2)) {
      setInvoiceStep(
        !invoiceForm.invoice_id.trim() ||
        !invoiceForm.vendor.trim() ||
        !invoiceForm.gstin.trim()
          ? 1
          : 2,
      )
      return
    }

    const payload = {
      invoice_id: invoiceForm.invoice_id.trim(),
      vendor: invoiceForm.vendor.trim(),
      amount: Number(invoiceForm.amount),
      gstin: invoiceForm.gstin.trim(),
      po_id: invoiceForm.po_id.trim(),
    }

    setLoading(true)

    try {
      const data = await requestApi('/ingest', {
        method: 'POST',
        body: JSON.stringify(payload),
      })

      const ticket = {
        ...payload,
        ...data,
        invoice_id: payload.invoice_id,
        vendor: payload.vendor,
        amount: payload.amount,
        gstin: payload.gstin,
        po_id: payload.po_id,
      }

      addTicket(ticket)
      setMessage('Invoice successfully submitted.')
      setShowSubmitPanel(false)
      setInvoiceForm(EMPTY_INVOICE)
      setInvoiceStep(1)
      setActivePage('Invoices')
      setVisibleLimit(PAGE_SIZE)
    } catch (err) {
      setError(err.message || 'Invoice submission failed.')
    } finally {
      setLoading(false)
    }
  }

  async function lookupTicket(event) {
    event.preventDefault()
    setError('')
    setMessage('')

    if (!ticketId.trim()) {
      setError('Ticket ID enter karo.')
      return
    }

    setLoading(true)

    try {
      const data = await requestApi(
        `/tickets/${encodeURIComponent(ticketId.trim())}`,
      )

      const normalized = normalizeTicketRecord({
        ...data,
        ticket_id: getTicketId(data) || ticketId.trim(),
      })

      addTicket(normalized)
      setMessage('Ticket details loaded successfully.')
      setActivePage('Invoices')
      setVisibleLimit(PAGE_SIZE)
    } catch (err) {
      setError(err.message || 'Ticket lookup failed.')
    } finally {
      setLoading(false)
    }
  }

  async function submitReview(event) {
    event.preventDefault()
    setError('')
    setMessage('')

    const id = getTicketId(selectedTicket) || ticketId.trim()

    if (!id) {
      setError('Pehle ticket select karo.')
      return
    }

    if (!reviewForm.reviewer.trim()) {
      setError('Reviewer name enter karo.')
      return
    }

    if (!['approve', 'reject'].includes(reviewForm.decision)) {
      setError('Please select Approve or Reject.')
      return
    }

    if (
      reviewForm.decision === 'approve' &&
      !canApproveTicket(selectedTicket)
    ) {
      setError(
        'Approval is allowed only for eligible high-value invoices without other validation failures.',
      )
      return
    }

    const payload = {
      reviewer: reviewForm.reviewer.trim(),
      decision: reviewForm.decision,
      comment: reviewForm.comment.trim(),
    }

    setLoading(true)

    try {
      const data = await requestApi(
        `/tickets/${encodeURIComponent(id)}/stamp`,
        {
          method: 'POST',
          body: JSON.stringify(payload),
        },
      )

      const updatedTicket = {
        ...(selectedTicket || {}),
        ...data,
        ticket_id: getTicketId(data) || id,
      }

      addTicket(updatedTicket)

      setMessage(
        `Review action successfully submitted. Ticket status: ${data.status || getStatus(data)}.`,
      )
      setShowStampPanel(false)
      setReviewForm(EMPTY_REVIEW)
    } catch (err) {
      setError(err.message || 'Review action failed.')
    } finally {
      setLoading(false)
    }
  }

  function openTicket(ticket) {
    setSelectedTicket(ticket)
    setTicketId(getTicketId(ticket))
  }

  function loadMoreTickets() {
    setVisibleLimit((current) => current + PAGE_SIZE)
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">N</div>
          <div className="brand-copy">
            <strong>NIMBUS</strong>
            <span>PAYDESK</span>
          </div>
        </div>

        <div className="workspace-label">WORKSPACE</div>

        <nav className="side-nav">
          <NavItem icon="▦" label="Dashboard" activePage={activePage} onClick={changePage} />
          <NavItem icon="▤" label="Invoices" activePage={activePage} onClick={changePage} />
          <NavItem
            icon="◎"
            label="Human Review"
            activePage={activePage}
            onClick={changePage}
            count={reviewTickets.length}
          />
          <NavItem icon="◷" label="Audit Trail" activePage={activePage} onClick={changePage} />
        </nav>

        <div className="sidebar-bottom">
          <div className="workspace-label">PREFERENCES</div>
          <NavItem icon="⚙" label="Settings" activePage={activePage} onClick={changePage} />

          <div className="sidebar-help">
            <div className="help-icon">?</div>
            <div>
              <strong>Need help?</strong>
              <span>Contact your administrator</span>
            </div>
          </div>

          <div className="profile">
            <div className="profile-avatar">NR</div>
            <div className="profile-info">
              <strong>Nimbus Retail</strong>
              <span>Accounts Payable</span>
            </div>
            <span className="profile-menu">•••</span>
          </div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumb">
            <span>Workspace</span>
            <span className="breadcrumb-divider">/</span>
            <strong>{activePage}</strong>
          </div>

          <div className="topbar-actions">
            <div className="system-status">
              <span className="status-dot" />
              Nimbus PayDesk
            </div>
            <div className="top-avatar">NR</div>
          </div>
        </header>

        <div className="page-content">
          <section className="page-heading">
            <div>
              <p className="eyebrow">NIMBUS RETAIL · ACCOUNTS PAYABLE</p>
              <h1>{pageTitle(activePage)}</h1>
              <p className="page-subtitle">{pageDescription(activePage)}</p>
            </div>

            {activePage !== 'Settings' && activePage !== 'Audit Trail' && (
              <button
                className="primary-button"
                onClick={openSubmitPanel}
              >
                ＋ Submit invoice
              </button>
            )}
          </section>

          {message && <div className="notice success-notice">{message}</div>}
          {error && <div className="notice error-notice">{error}</div>}

          {activePage === 'Dashboard' && (
            <Dashboard
              tickets={sortedTickets}
              totalTickets={totalTickets}
              reviewCount={reviewTickets.length}
              readyCount={readyTickets.length}
              otherCount={otherTickets.length}
              onNavigate={changePage}
            />
          )}

          {activePage === 'Invoices' && (
            <RecordSection
              title="All invoices"
              description={`Showing ${displayedTickets.length} of ${visibleTickets.length} matching tickets · ${totalTickets} total records in database`}
              tickets={displayedTickets}
              search={search}
              setSearch={(value) => {
                setSearch(value)
                setVisibleLimit(PAGE_SIZE)
              }}
              onSelect={openTicket}
              emptyTitle="No invoice records found"
              emptyDescription="Submit an invoice or retrieve an existing ticket using its ticket ID."
              canLoadMore={displayedTickets.length < visibleTickets.length}
              onLoadMore={loadMoreTickets}
            />
          )}

          {activePage === 'Human Review' && (
            <RecordSection
              title="Human review queue"
              description={`Showing ${displayedTickets.length} of ${visibleTickets.length} matching review tickets`}
              tickets={displayedTickets}
              search={search}
              setSearch={(value) => {
                setSearch(value)
                setVisibleLimit(PAGE_SIZE)
              }}
              onSelect={openTicket}
              emptyTitle="No review-required tickets found"
              emptyDescription="Tickets will appear here when their loaded status indicates human review is required."
              canLoadMore={displayedTickets.length < visibleTickets.length}
              onLoadMore={loadMoreTickets}
            />
          )}

          {activePage === 'Audit Trail' && (
            <AuditSection records={auditRecords} />
          )}

          {activePage === 'Settings' && (
            <section className="content-card settings-card">
              <div className="section-heading">
                <div>
                  <h2>Backend connection</h2>
                  <p>Secure connection to your Nimbus PayDesk backend.</p>
                </div>
              </div>

              <label className="field-label" htmlFor="api-url">
                Backend API route
              </label>
              <input
                id="api-url"
                className="text-input"
                value="/api"
                readOnly
              />

              <p className="field-help">
                API authentication is handled by the backend proxy using the
                server-side API_KEY environment variable. You do not need to
                enter or save an API key in this browser.
              </p>
            </section>
          )}

          {selectedTicket && activePage !== 'Settings' && (
            <section className="content-card ticket-details">
              <div className="section-heading">
                <div>
                  <h2>Ticket details</h2>
                  <p>{getTicketId(selectedTicket) || 'Selected ticket'}</p>
                </div>
                <div className="detail-actions">
                  <StatusPill status={getStatus(selectedTicket)} />
                  {getStatus(selectedTicket).toLowerCase() === 'needs_human' && (
                    <button
                      className="primary-button"
                      onClick={openReviewPanel}
                    >
                      Human review action
                    </button>
                  )}
                  <button
                    className="secondary-button"
                    onClick={() => setSelectedTicket(null)}
                  >
                    Close details
                  </button>
                </div>
              </div>

              <pre className="json-view">
                {JSON.stringify(selectedTicket, null, 2)}
              </pre>
            </section>
          )}

          {activePage !== 'Settings' && (
            <section className="lookup-strip">
              <div>
                <div className="lookup-icon">⌕</div>
                <div>
                  <strong>Find an existing ticket</strong>
                  <span>Retrieve ticket details using its ticket ID.</span>
                </div>
              </div>
              <form className="lookup-form" onSubmit={lookupTicket}>
                <input
                  value={ticketId}
                  onChange={(event) => setTicketId(event.target.value)}
                  placeholder="Enter ticket ID"
                  aria-label="Ticket ID"
                />
                <button className="primary-button" disabled={loading}>
                  {loading ? 'Loading...' : 'Search ticket'}
                </button>
              </form>
            </section>
          )}

          <footer className="page-footer">
            <span>© 2026 Nimbus Retail · Nimbus PayDesk</span>
            <span>Invoice automation with human-in-the-loop controls</span>
          </footer>
        </div>
      </main>

      {showSubmitPanel && (
        <Modal
          title="Submit invoice"
          subtitle="Enter the invoice details to start processing."
          onClose={closeSubmitPanel}
        >
          <form onSubmit={invoiceStep === 3 ? submitInvoice : (event) => {
            event.preventDefault()
            goToNextInvoiceStep()
          }}>
            {invoiceStep === 1 && (
              <div className="invoice-form-step">
                <h3>Invoice information</h3>
                <p className="field-help">Enter the invoice and vendor details.</p>

                <label className="field-label" htmlFor="invoice-id">Invoice ID *</label>
                <input
                  id="invoice-id"
                  className="text-input"
                  value={invoiceForm.invoice_id}
                  onChange={(event) => updateInvoiceField('invoice_id', event.target.value)}
                  placeholder="Enter invoice ID"
                  required
                  autoFocus
                />

                <label className="field-label" htmlFor="vendor-name">Vendor name *</label>
                <input
                  id="vendor-name"
                  className="text-input"
                  value={invoiceForm.vendor}
                  onChange={(event) => updateInvoiceField('vendor', event.target.value)}
                  placeholder="Enter vendor name"
                  required
                />

                <label className="field-label" htmlFor="gstin">GSTIN *</label>
                <input
                  id="gstin"
                  className="text-input"
                  value={invoiceForm.gstin}
                  onChange={(event) => updateInvoiceField('gstin', event.target.value)}
                  placeholder="Enter vendor GSTIN"
                  required
                />
              </div>
            )}

            {invoiceStep === 2 && (
              <div className="invoice-form-step">
                <h3>Purchase order & amount</h3>
                <p className="field-help">Enter the purchase order reference and invoice amount.</p>

                <label className="field-label" htmlFor="po-id">Purchase Order ID *</label>
                <input
                  id="po-id"
                  className="text-input"
                  value={invoiceForm.po_id}
                  onChange={(event) => updateInvoiceField('po_id', event.target.value)}
                  placeholder="Enter PO ID"
                  required
                  autoFocus
                />

                <label className="field-label" htmlFor="invoice-amount">Invoice amount *</label>
                <input
                  id="invoice-amount"
                  className="text-input"
                  type="number"
                  min="0.01"
                  step="any"
                  value={invoiceForm.amount}
                  onChange={(event) => updateInvoiceField('amount', event.target.value)}
                  placeholder="Enter invoice amount"
                  required
                />
                <p className="field-help">Amount must be greater than zero.</p>
              </div>
            )}

            {invoiceStep === 3 && (
              <div className="invoice-form-step">
                <h3>Review invoice details</h3>
                <p className="field-help">Check the information before submitting it to Nimbus PayDesk.</p>

                <div className="invoice-review-list">
                  <ReviewRow label="Invoice ID" value={invoiceForm.invoice_id} />
                  <ReviewRow label="Vendor name" value={invoiceForm.vendor} />
                  <ReviewRow label="GSTIN" value={invoiceForm.gstin} />
                  <ReviewRow label="Purchase Order ID" value={invoiceForm.po_id} />
                  <ReviewRow
                    label="Invoice amount"
                    value={Number(invoiceForm.amount).toLocaleString('en-IN', {
                      maximumFractionDigits: 2,
                    })}
                  />
                </div>

                <p className="field-help">
                  The five fields above will be submitted to the backend.
                </p>
              </div>
            )}

            {error && <div className="notice error-notice">{error}</div>}

            <div className="modal-actions">
              <button
                type="button"
                className="secondary-button"
                onClick={invoiceStep === 1 ? closeSubmitPanel : goToPreviousInvoiceStep}
                disabled={loading}
              >
                {invoiceStep === 1 ? 'Cancel' : 'Back'}
              </button>

              {invoiceStep < 3 ? (
                <button
                  type="submit"
                  className="primary-button"
                  disabled={loading}
                >
                  Continue →
                </button>
              ) : (
                <button
                  type="submit"
                  className="primary-button"
                  disabled={loading}
                >
                  {loading ? 'Submitting...' : 'Submit invoice'}
                </button>
              )}
            </div>
          </form>
        </Modal>
      )}

      {showStampPanel && (
        <Modal
          title="Human review action"
          subtitle={`Review ticket ${getTicketId(selectedTicket)}.`}
          onClose={closeReviewPanel}
        >
          <form onSubmit={submitReview}>
            <div className="invoice-form-step">
              <label className="field-label" htmlFor="reviewer-name">
                Reviewer name *
              </label>
              <input
                id="reviewer-name"
                className="text-input"
                value={reviewForm.reviewer}
                onChange={(event) => updateReviewField('reviewer', event.target.value)}
                placeholder="Enter reviewer name"
                required
                autoFocus
              />

              <label className="field-label">Decision *</label>

              <div className="review-decision-group">
                <button
                  type="button"
                  className={`review-decision-button reject-choice ${
                    reviewForm.decision === 'reject' ? 'selected' : ''
                  }`}
                  onClick={() => updateReviewField('decision', 'reject')}
                  aria-pressed={reviewForm.decision === 'reject'}
                >
                  <span>✕</span>
                  Reject
                </button>

                <button
                  type="button"
                  className={`review-decision-button approve-choice ${
                    reviewForm.decision === 'approve' ? 'selected' : ''
                  }`}
                  onClick={() => updateReviewField('decision', 'approve')}
                  disabled={!canApproveTicket(selectedTicket)}
                  aria-pressed={reviewForm.decision === 'approve'}
                >
                  <span>✓</span>
                  Approve
                </button>
              </div>

              {!canApproveTicket(selectedTicket) && (
                <p className="field-help">
                  Approval is available only for eligible high-value invoices
                  without other validation failures. Rejection is available.
                </p>
              )}

              <label className="field-label" htmlFor="review-comment">
                Comment
              </label>
              <textarea
                id="review-comment"
                className="json-input"
                value={reviewForm.comment}
                onChange={(event) => updateReviewField('comment', event.target.value)}
                placeholder="Enter the review reason or comment"
                rows={5}
              />

              <p className="field-help">
                The decision and reviewer details will be recorded in the audit trail.
              </p>
            </div>

            {error && <div className="notice error-notice">{error}</div>}

            <div className="modal-actions">
              <button
                type="button"
                className="secondary-button"
                onClick={closeReviewPanel}
                disabled={loading}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="primary-button"
                disabled={loading || !reviewForm.decision}
              >
                {loading
                  ? 'Submitting...'
                  : `Confirm ${reviewForm.decision === 'approve' ? 'approval' : 'rejection'}`}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}

function pageTitle(page) {
  const titles = {
    Dashboard: 'Dashboard Overview',
    Invoices: 'Invoice Management',
    'Human Review': 'Human Review Queue',
    'Audit Trail': 'Audit Trail',
    Settings: 'Settings',
  }
  return titles[page] || page
}

function pageDescription(page) {
  const descriptions = {
    Dashboard: 'Monitor invoice processing and current ticket status.',
    Invoices: 'Search, retrieve and inspect invoice records.',
    'Human Review': 'Inspect tickets requiring human attention.',
    'Audit Trail': 'Review audit events returned with loaded ticket records.',
    Settings: 'Configure the connection to your Nimbus PayDesk backend.',
  }
  return descriptions[page] || ''
}

function NavItem({ icon, label, activePage, onClick, count }) {
  return (
    <button
      className={`nav-item ${activePage === label ? 'active' : ''}`}
      onClick={() => onClick(label)}
    >
      <span className="nav-icon">{icon}</span>
      <span>{label}</span>
      {count > 0 && <span className="nav-count">{count}</span>}
    </button>
  )
}

function Dashboard({
  tickets,
  totalTickets,
  reviewCount,
  readyCount,
  otherCount,
  onNavigate,
}) {
  return (
    <>
      <section className="overview-grid">
        <div className="overview-card overview-primary">
          <div className="overview-card-top">
            <span className="overview-label">INVOICE CONTROL CENTER</span>
            <span className="overview-symbol">↗</span>
          </div>
          <h2>Accounts payable,<br />under control.</h2>
          <p>
            Submit invoices, inspect decisions and maintain a traceable review process.
          </p>
          <button className="light-button" onClick={() => onNavigate('Invoices')}>
            View invoice activity →
          </button>
          <div className="primary-decoration decoration-one" />
          <div className="primary-decoration decoration-two" />
        </div>

        <div className="overview-card chart-card">
          <div className="card-heading">
            <div>
              <h3>Processing activity</h3>
              <p>Latest tickets in the database</p>
            </div>
            <span className="mini-icon">▥</span>
          </div>
          {tickets.length ? (
            <div className="activity-chart">
              {tickets.slice(0, 7).reverse().map((ticket, index) => (
                <div className="activity-column" key={getTicketId(ticket) || index}>
                  <div
                    className="activity-bar"
                    style={{ height: `${Math.max(24, 35 + (index * 13) % 55)}%` }}
                  />
                  <span>{index + 1}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="chart-empty">
              <div className="empty-chart-icon">▥</div>
              <strong>No activity loaded yet</strong>
              <span>Submit an invoice or look up a ticket to begin.</span>
            </div>
          )}
        </div>

        <div className="overview-card distribution-card">
          <div className="card-heading">
            <div>
              <h3>Ticket overview</h3>
              <p>All database records</p>
            </div>
            <span className="mini-icon">◉</span>
          </div>
          <div className="donut-wrap">
            <div
              className="donut-chart"
              style={{
                '--review': tickets.length ? `${reviewCount / tickets.length * 100}%` : '0%',
                '--ready': tickets.length ? `${readyCount / tickets.length * 100}%` : '0%',
              }}
            >
              <div className="donut-center">
                <strong>{totalTickets}</strong>
                <span>Total tickets</span>
              </div>
            </div>
            <div className="donut-legend">
              <span><i className="legend-orange" /> Review: {reviewCount}</span>
              <span><i className="legend-green" /> Ready: {readyCount}</span>
              <span><i className="legend-blue" /> Other: {otherCount}</span>
            </div>
          </div>
        </div>
      </section>

      <section className="metrics-grid">
        <MetricCard
          label="Total tickets"
          value={totalTickets}
          note="All database records"
          icon="▤"
          tone="blue"
        />
        <MetricCard
          label="Needs review"
          value={reviewCount}
          note="Based on loaded ticket status"
          icon="◎"
          tone="orange"
        />
        <MetricCard
          label="Ready / approved"
          value={readyCount}
          note="Based on loaded ticket status"
          icon="✓"
          tone="green"
        />
        <MetricCard
          label="Other statuses"
          value={otherCount}
          note="Based on loaded ticket status"
          icon="◷"
          tone="purple"
        />
      </section>

      <section className="content-card">
        <div className="section-heading">
          <div>
            <h2>Recent invoice activity</h2>
            <p>Latest 5 tickets from the database.</p>
          </div>
          <button className="secondary-button" onClick={() => onNavigate('Invoices')}>
            View all invoices →
          </button>
        </div>
        <TicketTable
          tickets={tickets.slice(0, 5)}
          onSelect={() => onNavigate('Invoices')}
          compact
        />
      </section>
    </>
  )
}

function RecordSection({
  title,
  description,
  tickets,
  search,
  setSearch,
  onSelect,
  emptyTitle,
  emptyDescription,
  canLoadMore,
  onLoadMore,
}) {
  return (
    <section className="content-card">
      <div className="section-heading table-heading">
        <div>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
        <div className="table-actions">
          <div className="search-box">
            <span>⌕</span>
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search tickets..."
            />
          </div>
        </div>
      </div>

      {tickets.length ? (
        <>
          <TicketTable tickets={tickets} onSelect={onSelect} />
          {canLoadMore && (
            <div className="load-more-wrap">
              <button className="secondary-button" onClick={onLoadMore}>
                Load 10 more tickets
              </button>
            </div>
          )}
        </>
      ) : (
        <div className="table-empty">
          <div className="empty-icon">▤</div>
          <strong>{emptyTitle}</strong>
          <span>{emptyDescription}</span>
        </div>
      )}
    </section>
  )
}

function TicketTable({ tickets, onSelect, compact = false }) {
  if (!tickets.length) {
    return (
      <div className="table-empty">
        <div className="empty-icon">▤</div>
        <strong>No invoice records loaded</strong>
        <span>Submit an invoice or retrieve an existing ticket to display records.</span>
      </div>
    )
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Ticket ID</th>
            <th>Invoice reference</th>
            <th>Status</th>
            <th>Updated</th>
            <th className="align-right">Action</th>
          </tr>
        </thead>
        <tbody>
          {tickets.map((ticket, index) => (
            <tr key={getTicketId(ticket) || index}>
              <td>
                <span className="ticket-link">
                  {getTicketId(ticket) || '—'}
                </span>
              </td>
              <td>{getInvoiceId(ticket)}</td>
              <td><StatusPill status={getStatus(ticket)} /></td>
              <td>{formatDate(getDate(ticket))}</td>
              <td className="align-right">
                <button className="row-action" onClick={() => onSelect(ticket)}>
                  Details →
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function AuditSection({ records }) {
  return (
    <section className="content-card">
      <div className="section-heading">
        <div>
          <h2>Audit events</h2>
          <p>Events found inside ticket records loaded during this browser session.</p>
        </div>
      </div>

      {records.length ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Ticket ID</th>
                <th>Event</th>
                <th>Actor</th>
                <th>Timestamp</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {records.map((record, index) => (
                <tr key={record.event_key || index}>
                  <td>{record.ticket_id || '—'}</td>
                  <td>{record.event_type || record.event || record.action || '—'}</td>
                  <td>{record.actor || record.user || '—'}</td>
                  <td>{formatDate(record.timestamp || record.created_at || record.event_time || record.ts)}</td>
                  <td>{record.description || record.details || record.reason || record.detail || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="table-empty">
          <div className="empty-icon">◷</div>
          <strong>No audit events available in loaded records</strong>
          <span>
            Load a ticket that includes audit events. This screen does not generate
            sample audit entries or claim to show the complete database audit history.
          </span>
        </div>
      )}
    </section>
  )
}

function MetricCard({ label, value, note, icon, tone }) {
  return (
    <div className="metric-card">
      <div className={`metric-icon ${tone}`}>{icon}</div>
      <div className="metric-copy">
        <span>{label}</span>
        <strong>{value}</strong>
        <small>{note}</small>
      </div>
    </div>
  )
}

function StatusPill({ status }) {
  const value = String(status || 'Unknown')
  const lower = value.toLowerCase()

  let tone = 'neutral'

  if (
    lower.includes('human') ||
    lower.includes('review') ||
    lower.includes('hold') ||
    lower.includes('reject')
  ) {
    tone = 'warning'
  } else if (
    lower.includes('ready') ||
    lower.includes('approved') ||
    lower.includes('pay')
  ) {
    tone = 'success'
  } else if (lower.includes('fail') || lower.includes('error')) {
    tone = 'danger'
  }

  return <span className={`status-pill ${tone}`}>{value}</span>
}

function ReviewRow({ label, value }) {
  return (
    <div className="invoice-review-row">
      <span>{label}</span>
      <strong>{value || '—'}</strong>
    </div>
  )
}

function Modal({ title, subtitle, onClose, children }) {
  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <section className="modal-card" onMouseDown={(event) => event.stopPropagation()}>
        <div className="modal-heading">
          <div>
            <h2>{title}</h2>
            <p>{subtitle}</p>
          </div>
          <button className="modal-close" onClick={onClose} aria-label="Close">×</button>
        </div>
        {children}
      </section>
    </div>
  )
}

export default App
