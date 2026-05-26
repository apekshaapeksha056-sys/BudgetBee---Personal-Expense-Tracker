from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib import messages
from django.db.models import Sum, Q
from django.utils import timezone
from django.http import JsonResponse
from django.core.paginator import Paginator
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from decimal import Decimal
import json

from .models import Expense, Category, Budget
from .forms import RegisterForm, ExpenseForm, CategoryForm, BudgetForm, DateRangeFilterForm


def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Create default categories
            defaults = [
                ('Food & Dining', '🍔', '#e74c3c'),
                ('Transport', '🚗', '#3498db'),
                ('Housing', '🏠', '#2ecc71'),
                ('Healthcare', '💊', '#9b59b6'),
                ('Entertainment', '🎮', '#f39c12'),
                ('Shopping', '👕', '#1abc9c'),
                ('Education', '📚', '#34495e'),
                ('Utilities', '💡', '#e67e22'),
                ('Income', '💰', '#27ae60'),
                ('Other', '📦', '#95a5a6'),
            ]
            for name, icon, color in defaults:
                Category.objects.create(user=user, name=name, icon=icon, color=color)
            login(request, user)
            messages.success(request, f'Welcome {user.first_name or user.username}! Your account has been created.')
            return redirect('dashboard')
    else:
        form = RegisterForm()
    return render(request, 'register.html', {'form': form})


def get_date_range(period, start_date=None, end_date=None):
    today = date.today()
    if period == 'this_month':
        return today.replace(day=1), today
    elif period == 'last_month':
        first = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        last = today.replace(day=1) - timedelta(days=1)
        return first, last
    elif period == 'last_3_months':
        return today - relativedelta(months=3), today
    elif period == 'this_year':
        return today.replace(month=1, day=1), today
    elif period == 'custom' and start_date and end_date:
        return start_date, end_date
    return today.replace(day=1), today


from datetime import date, timedelta
from decimal import Decimal
import json
from django.db.models import Sum
from django.contrib.auth.decorators import login_required
from dateutil.relativedelta import relativedelta
from django.shortcuts import render

from .models import Expense, Budget


@login_required
def dashboard(request):
    today: date = date.today()
    month_start: date = today.replace(day=1)

    # ================= MONTHLY SUMMARY =================
    monthly_expenses: Decimal = (
        Expense.objects
        .filter(
            user=request.user,
            date__gte=today - relativedelta(months=1),
            type__iexact='expense'
        )
        .aggregate(total=Sum('amount'))
        .get('total') or Decimal('0')
    )

    monthly_income: Decimal = (
        Expense.objects
        .filter(
            user=request.user,
            date__gte=today - relativedelta(months=1),
            type__iexact='income'
        )
        .aggregate(total=Sum('amount'))
        .get('total') or Decimal('0')
    )

    balance: Decimal = monthly_income - monthly_expenses

    # ================= LAST 6 MONTHS =================
    months_data: list[dict] = []

    for i in range(5, -1, -1):
        d = today - relativedelta(months=i)
        m_start = d.replace(day=1)
        m_end = (m_start + relativedelta(months=1)) - timedelta(days=1)

        exp = (
            Expense.objects
            .filter(
                user=request.user,
                date__range=(m_start, m_end),
                type__iexact='expense'
            )
            .aggregate(total=Sum('amount'))
            .get('total') or 0
        )

        inc = (
            Expense.objects
            .filter(
                user=request.user,
                date__range=(m_start, m_end),
                type__iexact='income'
            )
            .aggregate(total=Sum('amount'))
            .get('total') or 0
        )

        months_data.append({
            'month': d.strftime('%b %Y'),
            'expenses': float(exp),
            'income': float(inc),
        })

    # ================= CATEGORY BREAKDOWN =================
    cat_qs = (
        Expense.objects
        .filter(
            user=request.user,
            date__gte=today - relativedelta(months=1),
            type__iexact='expense'
        )
        .exclude(category__isnull=True)
    )

    cat_data = (
        cat_qs
        .values('category__name', 'category__color', 'category__icon')
        .annotate(total=Sum('amount'))
        .order_by('-total')[:6]
    )

    cat_labels: list[str] = [
        f"{c['category__icon'] or '📦'} {c['category__name'] or 'Other'}"
        for c in cat_data
    ]

    cat_totals: list[float] = [float(c['total']) for c in cat_data]

    cat_colors: list[str] = [
        c['category__color'] or '#888888'
        for c in cat_data
    ]

    # ================= RECENT =================
    recent = (
        Expense.objects
        .filter(user=request.user)
        .select_related('category')
        .order_by('-date', '-created_at')[:8]
    )

    # ================= BUDGET =================
    budgets = (
        Budget.objects
        .filter(user=request.user)
        .select_related('category')
    )

    budget_data: list[dict] = []

    for b in budgets:

        if b.category:
            spent = (
                Expense.objects
                .filter(
                    user=request.user,
                    category=b.category,
                    date__gte=today - relativedelta(months=1),
                    type__iexact='expense'
                )
                .aggregate(total=Sum('amount'))
                .get('total') or Decimal('0')
            )
        else:
            # overall budget
            spent = (
                Expense.objects
                .filter(
                    user=request.user,
                    date__gte=today - relativedelta(months=1),
                    type__iexact='expense'
                )
                .aggregate(total=Sum('amount'))
                .get('total') or Decimal('0')
            )

        pct: int = int((spent / b.amount) * 100) if b.amount > 0 else 0
        pct = min(pct, 100)

        budget_data.append({
            'budget': b,
            'spent': spent,
            'pct': pct,
            'remaining': b.amount - spent
        })

    # ================= CONTEXT =================
    context = {
        'monthly_expenses': monthly_expenses,
        'monthly_income': monthly_income,
        'balance': balance,
        'months_data': json.dumps(months_data),
        'cat_labels': json.dumps(cat_labels),
        'cat_totals': json.dumps(cat_totals),
        'cat_colors': json.dumps(cat_colors),
        'recent': recent,
        'budget_data': budget_data,
        'today': today,
    }

    return render(request, 'dashboard.html', context)

@login_required
def expense_list(request):
    filter_form = DateRangeFilterForm(user=request.user, data=request.GET or None)
    period = request.GET.get('period', 'this_month')
    start_date_raw = request.GET.get('start_date')
    end_date_raw = request.GET.get('end_date')

    start_date = datetime.strptime(start_date_raw, '%Y-%m-%d').date() if start_date_raw else None
    end_date = datetime.strptime(end_date_raw, '%Y-%m-%d').date() if end_date_raw else None
    start, end = get_date_range(period, start_date, end_date)

    qs = Expense.objects.filter(user=request.user, date__gte=start, date__lte=end).select_related('category')

    category_id = request.GET.get('category')
    if category_id:
        qs = qs.filter(category_id=category_id)

    tx_type = request.GET.get('type')
    if tx_type:
        qs = qs.filter(type=tx_type)

    search = request.GET.get('search', '').strip()
    if search:
        qs = qs.filter(Q(title__icontains=search) | Q(description__icontains=search))

    total_expenses = qs.filter(type='expense').aggregate(total=Sum('amount'))['total'] or 0
    total_income = qs.filter(type='income').aggregate(total=Sum('amount'))['total'] or 0

    paginator = Paginator(qs, 15)
    page = request.GET.get('page', 1)
    expenses = paginator.get_page(page)

    context = {
        'expenses': expenses,
        'filter_form': filter_form,
        'total_expenses': total_expenses,
        'total_income': total_income,
        'start': start,
        'end': end,
        'search': search,
    }
    return render(request, 'expense_list.html', context)


@login_required
def expense_add(request):
    if request.method == 'POST':
        form = ExpenseForm(user=request.user, data=request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.user = request.user
            expense.save()
            messages.success(request, f'{"Income" if expense.type == "income" else "Expense"} "{expense.title}" added successfully!')
            return redirect('expense_list')
    else:
        form = ExpenseForm(user=request.user, initial={'date': date.today()})
    return render(request, 'expense_form.html', {'form': form, 'title': 'Add Transaction', 'action': 'Add'})


@login_required
def expense_edit(request, pk):
    expense = get_object_or_404(Expense, pk=pk, user=request.user)
    if request.method == 'POST':
        form = ExpenseForm(user=request.user, data=request.POST, instance=expense)
        if form.is_valid():
            form.save()
            messages.success(request, 'Transaction updated successfully!')
            return redirect('expense_list')
    else:
        form = ExpenseForm(user=request.user, instance=expense)
    return render(request, 'expense_form.html', {'form': form, 'title': 'Edit Transaction', 'action': 'Update', 'expense': expense})


@login_required
def expense_delete(request, pk):
    expense = get_object_or_404(Expense, pk=pk, user=request.user)
    if request.method == 'POST':
        name = expense.title
        expense.delete()
        messages.success(request, f'Transaction "{name}" deleted.')
        return redirect('expense_list')
    return render(request, 'confirm_delete.html', {'object': expense, 'type': 'transaction'})


@login_required
def category_list(request):
    categories = Category.objects.filter(user=request.user).annotate(
        total_expenses=Sum('expenses__amount', filter=Q(expenses__type='expense'))
    )
    return render(request, 'category_list.html', {'categories': categories})


@login_required
def category_add(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            cat = form.save(commit=False)
            cat.user = request.user
            cat.save()
            messages.success(request, f'Category "{cat.name}" created!')
            return redirect('category_list')
    else:
        form = CategoryForm()
    return render(request, 'category_form.html', {'form': form, 'title': 'Add Category', 'action': 'Add'})


@login_required
def category_edit(request, pk):
    cat = get_object_or_404(Category, pk=pk, user=request.user)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=cat)
        if form.is_valid():
            form.save()
            messages.success(request, f'Category "{cat.name}" updated!')
            return redirect('category_list')
    else:
        form = CategoryForm(instance=cat)
    return render(request, 'category_form.html', {'form': form, 'title': 'Edit Category', 'action': 'Update'})


@login_required
def category_delete(request, pk):
    cat = get_object_or_404(Category, pk=pk, user=request.user)
    if request.method == 'POST':
        name = cat.name
        cat.delete()
        messages.success(request, f'Category "{name}" deleted.')
        return redirect('category_list')
    return render(request, 'confirm_delete.html', {'object': cat, 'type': 'category'})


from datetime import date, timedelta
from decimal import Decimal
from django.db.models import Sum
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from dateutil.relativedelta import relativedelta

from .models import Expense, Budget


@login_required
def budget_list(request):
    today: date = date.today()

    # ================= AUTO-DETECT MONTH (BEST UX) =================
    latest_expense = (
        Expense.objects
        .filter(user=request.user)
        .order_by('-date')
        .first()
    )

    if latest_expense:
        default_month: int = latest_expense.date.month
        default_year: int = latest_expense.date.year
    else:
        default_month = today.month
        default_year = today.year

    # ================= SAFE INPUT =================
    try:
        month: int = int(request.GET.get("month", default_month))
        year: int = int(request.GET.get("year", default_year))
    except (TypeError, ValueError):
        month = default_month
        year = default_year

    # ================= DATE RANGE =================
    month_start: date = date(year, month, 1)
    month_end: date = (month_start + relativedelta(months=1)) - timedelta(days=1)

    # ================= FETCH BUDGETS =================
    budgets = (
        Budget.objects
        .filter(user=request.user, month=month, year=year)
        .select_related("category")
    )

    budget_data: list[dict] = []

    for b in budgets:

        filters = {
            "user": request.user,
            "date__range": (month_start, month_end),
            "type__iexact": "expense",
        }

        if b.category:
            filters["category"] = b.category

        spent: Decimal = (
            Expense.objects
            .filter(**filters)
            .aggregate(total=Sum("amount"))
            .get("total") or Decimal("0")
        )

        # ================= CALCULATIONS =================
        pct: int = int((spent / b.amount) * 100) if b.amount > 0 else 0
        pct = min(pct, 100)

        if pct >= 90:
            status = "danger"
        elif pct >= 70:
            status = "warning"
        else:
            status = "success"

        budget_data.append({
            "budget": b,
            "spent": spent,
            "pct": pct,
            "remaining": b.amount - spent,
            "status": status,
        })

    # ================= CONTEXT =================
    context = {
        "budget_data": budget_data,
        "month": date(year, month, 1), 
        "year": year,
        "months": [date(year, m, 1) for m in range(1, 13)],
        "years": range(2020, today.year + 2),
    }

    return render(request, "budget_list.html", context)



@login_required
def budget_add(request):
    today = date.today()
    if request.method == 'POST':
        form = BudgetForm(user=request.user, data=request.POST)
        if form.is_valid():
            budget = form.save(commit=False)
            budget.user = request.user
            budget.save()
            messages.success(request, 'Budget set successfully!')
            return redirect('budget_list')
    else:
        form = BudgetForm(user=request.user, initial={'month': today.month, 'year': today.year})
    return render(request, 'budget_form.html', {'form': form, 'title': 'Set Budget'})


@login_required
def budget_delete(request, pk):
    budget = get_object_or_404(Budget, pk=pk, user=request.user)
    if request.method == 'POST':
        budget.delete()
        messages.success(request, 'Budget removed.')
        return redirect('budget_list')
    return render(request, 'confirm_delete.html', {'object': budget, 'type': 'budget'})


@login_required
def reports(request):
    today = date.today()
    year = int(request.GET.get('year', today.year))

    # Monthly breakdown for the year
    monthly = []
    for m in range(1, 13):
        m_start = date(year, m, 1)
        m_end = (m_start + relativedelta(months=1)) - timedelta(days=1)
        exp = Expense.objects.filter(user=request.user, date__gte=m_start, date__lte=m_end, type='expense'
                                     ).aggregate(total=Sum('amount'))['total'] or 0
        inc = Expense.objects.filter(user=request.user, date__gte=m_start, date__lte=m_end, type='income'
                                     ).aggregate(total=Sum('amount'))['total'] or 0
        monthly.append({'month': datetime(year, m, 1).strftime('%b'), 'expenses': float(exp), 'income': float(inc), 'net': float(inc) - float(exp)})

    # Category breakdown for year
    cat_data = Expense.objects.filter(
        user=request.user, date__year=year, type='expense', category__isnull=False
    ).values('category__name', 'category__color', 'category__icon').annotate(total=Sum('amount')).order_by('-total')

    yearly_income = Expense.objects.filter(user=request.user, date__year=year, type='income').aggregate(total=Sum('amount'))['total'] or 0
    yearly_expense = Expense.objects.filter(user=request.user, date__year=year, type='expense').aggregate(total=Sum('amount'))['total'] or 0

    context = {
        'year': year,
        'years': range(2020, today.year + 1),
        'monthly_data': monthly,
        'monthly_data_json': json.dumps(monthly),
        'cat_data': json.dumps([{'name': f"{c['category__icon']} {c['category__name']}", 'total': float(c['total']), 'color': c['category__color']} for c in cat_data]),
        'yearly_income': yearly_income,
        'yearly_expense': yearly_expense,
        'yearly_net': float(yearly_income) - float(yearly_expense),
    }
    return render(request, 'reports.html', context)