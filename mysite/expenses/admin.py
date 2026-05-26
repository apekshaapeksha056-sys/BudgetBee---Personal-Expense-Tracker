from django.contrib import admin
from .models import Expense, Category, Budget


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['title', 'amount', 'type', 'category', 'date', 'user']
    list_filter = ['type', 'category', 'date']
    search_fields = ['title', 'description']
    date_hierarchy = 'date'


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['icon', 'name', 'user', 'color']
    list_filter = ['user']


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ['user', 'category', 'amount', 'month', 'year']
    list_filter = ['month', 'year']