from fastapi import FastAPI

from apps.invoicing.schemas import InvoiceCreate, InvoiceRead

app = FastAPI(title="Invoicing Service", version="0.1.0")

INVOICES = {}


@app.get("/")
def root() -> dict:
    return {"service": "invoicing", "message": "Invoicing service is ready"}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "invoicing"}


@app.post("/invoices", response_model=InvoiceRead)
def create_invoice(invoice: InvoiceCreate) -> InvoiceRead:
    INVOICES[invoice.invoice_id] = invoice.model_dump()
    return InvoiceRead(**invoice.model_dump())
