from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Category(models.Model):
    CATEGORY_ICONS = [
        ('🍔', 'Food & Dining'),
        ('🚗', 'Transport'),
        ('🏠', 'Housing'),
        ('💊', 'Healthcare'),
        ('🎮', 'Entertainment'),
        ('👕', 'Shopping'),
        ('📚', 'Education'),
        ('✈️', 'Travel'),
        ('💡', 'Utilities'),
        ('💰', 'Income'),
        ('🎁', 'Gifts'),
        ('📱', 'Technology'),
        ('🏋️', 'Fitness'),
        ('🐾', 'Pets'),
        ('📦', 'Other'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=10, choices=[(i, i) for i, _ in CATEGORY_ICONS], default='📦')
    color = models.CharField(max_length=7, default='#6c757d')  # hex color
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def __str__(self):
        return f"{self.icon} {self.name}"


class Budget(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='budgets')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='budgets', null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    month = models.IntegerField()  # 1-12
    year = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'category', 'month', 'year']

    def __str__(self):
        cat = self.category.name if self.category else 'Overall'
        return f"{cat} budget - {self.month}/{self.year}: ₹{self.amount}"

from datetime import date

class Expense(models.Model):
    TYPE_CHOICES = [
        ('expense', 'Expense'),
        ('income', 'Income'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='expenses')
    title = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='expense')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='expenses')
    date = models.DateField(default=date.today)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.title} - ₹{self.amount} ({self.date})"