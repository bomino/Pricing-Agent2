"""
Simple admin configuration for procurement app
"""
from django.contrib import admin
from .models import (
    Supplier, RFQ, Quote, RFQItem, QuoteItem,
    Contract, SupplierContact, SupplierDocument
)

# Register all models with basic admin
admin.site.register(Supplier)
admin.site.register(RFQ)
admin.site.register(Quote)
admin.site.register(RFQItem)
admin.site.register(QuoteItem)
admin.site.register(Contract)
admin.site.register(SupplierContact)
admin.site.register(SupplierDocument)