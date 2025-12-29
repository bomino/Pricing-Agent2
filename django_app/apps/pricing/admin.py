"""
Simple admin configuration for pricing app
"""
from django.contrib import admin
from .models import (
    Category, Material, Price, PricePrediction, 
    PriceAlert, PriceBenchmark, PriceHistory, CostModel
)

# Register all models with basic admin
admin.site.register(Category)
admin.site.register(Material)
admin.site.register(Price)
admin.site.register(PricePrediction)
admin.site.register(PriceAlert)
admin.site.register(PriceBenchmark)
admin.site.register(PriceHistory)
admin.site.register(CostModel)