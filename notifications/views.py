from django.shortcuts import render, redirect, get_object_or_404
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.generic import CreateView, ListView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.db.models import Sum, Count, Q
from datetime import date
from collections import Counter
from django.utils import timezone
from datetime import date, timedelta
from .models import Notification, Alert, Plan, Subscription, User ,AdminProfile,CustomerProfile , Payment
from .forms import SignUpForm, LoginForm, NotificationForm, PlanForm


from twilio.rest import Client

def _has_field(model, field_name):
    """Return True if model has a field named field_name."""
    try:
        model._meta.get_field(field_name)
        return True
    except Exception:
        return False

# ----------------------------
# Utility: return scoped Plan queryset (or None)
# ----------------------------
def _get_scoped_plans(owner):
    """
    Return a Plan queryset that belongs to `owner` via known ownership fields.
    If owner is falsy -> return Plan.objects.all() (no scoping).
    If no owner-like field exists on Category or Plan -> return None (indicates no scoping possible).
    NOTE: This function intentionally does not try invalid lookups.
    """
    if not owner:
        return Plan.objects.all()

    # Preferred: Category.created_by -> Plan via category__created_by
    if _has_field(Category, 'created_by'):
        qs = Plan.objects.filter(category__created_by=owner)
        return qs

    # Alternative names on Category (if you used a different name)
    for alt in ('owner', 'user', 'added_by', 'author'):
        if _has_field(Category, alt):
            lookup = f"category__{alt}"
            qs = Plan.objects.filter(**{lookup: owner})
            return qs

    # Check Plan-level owner fields (only if field exists)
    for pname in ('created_by', 'owner', 'user', 'added_by', 'author'):
        if _has_field(Plan, pname):
            qs = Plan.objects.filter(**{pname: owner})
            return qs

    # No owner-like field discovered — return None to indicate "no scoping available"
    return None

# ----------------------------
# Helper wrappers
# ----------------------------
def _scoped_qs_for_owner(model_qs, owner):
    """
    Given a base queryset (e.g., Payment.objects.all() or Subscription.objects.all()),
    and an owner, attempt to scope it to owner's plans via subscription__plan__in(scoped_plans).
    Returns:
      - if owner falsy: original model_qs (no scoping)
      - if scoped_plans is a queryset: model_qs filtered to that set
      - if scoped_plans is None: None (caller should interpret as empty result / zero)
    """
    if not owner:
        return model_qs

    scoped_plans = _get_scoped_plans(owner)
    if scoped_plans is None:
        return None

    return model_qs.filter(subscription__plan__in=scoped_plans)

# ----------------------------
# 💰 Revenue & Subscription Metrics
# ----------------------------

def calculate_total_revenue(owner=None):
    """
    Total revenue from all payments (sum of Payment.amount).
    If owner is provided, scope to owner's plans (via Category.created_by or Plan owner field).
    If no scoping available, returns 0.
    """
    qs = Payment.objects.all()
    scoped_qs = _scoped_qs_for_owner(qs, owner)
    if scoped_qs is None:
        return 0.0
    total = scoped_qs.aggregate(total=Sum('amount'))['total']
    return float(total or 0.0)


def calculate_mrr(owner=None):
    """
    Monthly Recurring Revenue = sum of monthly-equivalent prices of active subscriptions.
    Yearly plans are normalized to monthly by dividing price by 12.
    If owner is provided and scoping is not possible, returns 0.
    """
    subs = Subscription.objects.filter(subscription_status='Active')
    if owner:
        scoped_plans = _get_scoped_plans(owner)
        if scoped_plans is None:
            return 0.0
        subs = subs.filter(plan__in=scoped_plans)

    total = 0.0
    for s in subs.select_related('plan'):
        price = float(s.plan.price or 0)
        if s.plan.duration == 'monthly':
            total += price
        elif s.plan.duration == 'yearly':
            total += price / 12.0
        else:
            total += price
    return round(total, 2)


def calculate_new_subscriptions(owner=None, days=30):
    """
    Number of new subscriptions started in the last `days`.
    """
    since = timezone.now().date() - timedelta(days=days)
    subs = Subscription.objects.filter(start_date__gte=since)
    if owner:
        scoped_plans = _get_scoped_plans(owner)
        if scoped_plans is None:
            return 0
        subs = subs.filter(plan__in=scoped_plans)
    return subs.count()


def calculate_arpu(owner=None):
    """
    ARPU = Total Revenue / Number of Active Customers (distinct customers with active subs).
    Uses payments for revenue (calculate_total_revenue).
    """
    total_revenue = calculate_total_revenue(owner=owner)
    subs = Subscription.objects.filter(subscription_status='Active')
    if owner:
        scoped_plans = _get_scoped_plans(owner)
        if scoped_plans is None:
            return 0.0
        subs = subs.filter(plan__in=scoped_plans)

    active_customers = subs.values('customer').distinct().count()
    if active_customers == 0:
        return 0.0
    return round(total_revenue / active_customers, 2)


def calculate_churn_rate(owner=None, days=30):
    """
    Churn Rate = (Inactive subscriptions during period) / (subscriptions at start of period) × 100.
    This is a simple period-based churn estimate.
    """
    today = timezone.now().date()
    start = today - timedelta(days=days)

    subs_at_start = Subscription.objects.filter(start_date__lt=start)
    if owner:
        scoped_plans = _get_scoped_plans(owner)
        if scoped_plans is None:
            return 0.0
        subs_at_start = subs_at_start.filter(plan__in=scoped_plans)
    total_at_start = subs_at_start.count()

    inactive_during = Subscription.objects.filter(
        subscription_status='Inactive',
        end_date__gte=start,
        end_date__lte=today
    )
    if owner:
        scoped_plans = _get_scoped_plans(owner)
        if scoped_plans is None:
            return 0.0
        inactive_during = inactive_during.filter(plan__in=scoped_plans)

    inactive_count = inactive_during.count()
    if total_at_start == 0:
        return 0.0
    return round((inactive_count / total_at_start) * 100, 2)

# ----------------------------
# 💳 Payment Method Analytics
# ----------------------------

def payment_method_percentage(method, owner=None):
    """
    Percentage of payments using `method` among all payments (or owner's payments).
    Returns 0 if no payments exist or scoping not possible.
    """
    base_qs = Payment.objects.filter(payment_method=method)
    if owner:
        scoped = _scoped_qs_for_owner(base_qs, owner)
        if scoped is None:
            return 0.0
        method_count = scoped.count()
        total = _scoped_qs_for_owner(Payment.objects.all(), owner)
        if total is None:
            return 0.0
        total_count = total.count()
    else:
        method_count = base_qs.count()
        total_count = Payment.objects.count()

    if total_count == 0:
        return 0.0
    return round((method_count / total_count) * 100, 2)

def credit_total(owner=None): return payment_method_percentage('credit_card', owner)
def paypal_total(owner=None): return payment_method_percentage('paypal', owner)
def bank_total(owner=None): return payment_method_percentage('bank_transfer', owner)
def other_total(owner=None): return payment_method_percentage('other', owner)

# ----------------------------
# 👥 Customer & Location Analytics
# ----------------------------

def active_total(owner=None):
    qs = Subscription.objects.filter(subscription_status='Active')
    if owner:
        scoped_plans = _get_scoped_plans(owner)
        if scoped_plans is None:
            return 0
        qs = qs.filter(plan__in=scoped_plans)
    return qs.count()

def top_performing(owner=None, top_n=1):
    qs = Subscription.objects.all()
    if owner:
        scoped_plans = _get_scoped_plans(owner)
        if scoped_plans is None:
            return None if top_n == 1 else []
        qs = qs.filter(plan__in=scoped_plans)

    plan_counts = qs.values('plan__name').annotate(count=Count('id')).order_by('-count')
    if not plan_counts:
        return None if top_n == 1 else []
    if top_n == 1:
        return plan_counts[0]['plan__name']
    return [p['plan__name'] for p in plan_counts[:top_n]]

def locationbased(owner=None, n=1):
    qs = Subscription.objects.all()
    if owner:
        scoped_plans = _get_scoped_plans(owner)
        if scoped_plans is None:
            return None, 0
        qs = qs.filter(plan__in=scoped_plans)
    total = qs.count()
    if total == 0:
        return None, 0
    counter = Counter(sub.address for sub in qs if sub.address)
    common = counter.most_common(n)
    if not common:
        return None, 0
    loc, freq = common[n-1]
    return loc, round((freq / total) * 100, 2)

# ----------------------------
# 📊 Revenue by Plan Type
# ----------------------------

def prem_total(owner=None):
    price_obj = Plan.objects.filter(name__iexact='premium').first()
    if not price_obj:
        return 0.0
    qs = Subscription.objects.filter(plan__name__iexact='premium')
    if owner:
        scoped_plans = _get_scoped_plans(owner)
        if scoped_plans is None:
            return 0.0
        qs = qs.filter(plan__in=scoped_plans)
    return round(qs.count() * float(price_obj.price), 2)

def pro_total(owner=None):
    price_obj = Plan.objects.filter(name__iexact='pro').first()
    if not price_obj:
        return 0.0
    qs = Subscription.objects.filter(plan__name__iexact='pro')
    if owner:
        scoped_plans = _get_scoped_plans(owner)
        if scoped_plans is None:
            return 0.0
        qs = qs.filter(plan__in=scoped_plans)
    return round(qs.count() * float(price_obj.price), 2)

def basic_total(owner=None):
    price_obj = Plan.objects.filter(name__iexact='basic').first()
    if not price_obj:
        return 0.0
    qs = Subscription.objects.filter(plan__name__iexact='basic')
    if owner:
        scoped_plans = _get_scoped_plans(owner)
        if scoped_plans is None:
            return 0.0
        qs = qs.filter(plan__in=scoped_plans)
    return round(qs.count() * float(price_obj.price), 2)

# ----------------------------
# 📅 Monthly Aggregations
# ----------------------------

def get_monthly_revenue(owner=None):
    current_year = date.today().year
    qs = Payment.objects.filter(payment_date__year=current_year)
    if owner:
        scoped = _scoped_qs_for_owner(qs, owner)
        if scoped is None:
            return []
        qs = scoped
    return qs.values('payment_date__month').annotate(total_revenue=Sum('amount')).order_by('payment_date__month')

def get_monthly_subscriptions(owner=None):
    current_year = date.today().year
    qs = Subscription.objects.filter(start_date__year=current_year)
    if owner:
        scoped_plans = _get_scoped_plans(owner)
        if scoped_plans is None:
            return []
        qs = qs.filter(plan__in=scoped_plans)
    return qs.values('start_date__month').annotate(subscription_count=Count('id')).order_by('start_date__month')


def _admin_plan_queryset(user):
    """
    Return Plan queryset for an admin user by using category__created_by.
    Do NOT try to filter Plan.created_by (that field doesn't exist).
    """
    if not user:
        return Plan.objects.none()
    return Plan.objects.filter(category__created_by=user)


@login_required
def LKJH_view(request):
    user = request.user
    is_admin = getattr(user, 'role', None) == 'admin'
    owner = user if is_admin else None

    # Use helper functions (they must accept owner=None|User)
    total_revenue = calculate_total_revenue(owner=owner)
    total_customers = active_total(owner=owner)
    new_subscriptions = calculate_new_subscriptions(owner=owner)
    churn_rate = calculate_churn_rate(owner=owner)
    arpu = calculate_arpu(owner=owner)
    mrr = calculate_mrr(owner=owner)

    # Total plans: if admin scope by categories created by this admin
    if is_admin:
        plans_qs = _admin_plan_queryset(user)
        total_plans = plans_qs.count()
    else:
        total_plans = Plan.objects.count()

    # Monthly aggregations
    monthly_revenue_qs = get_monthly_revenue(owner=owner)
    monthly_subscriptions_qs = get_monthly_subscriptions(owner=owner)

    months = range(1, 13)
    revenue_data = [0.0] * 12
    subscription_data = [0.0] * 12

    # defensive extraction of month keys
    for entry in monthly_revenue_qs:
        month = entry.get('payment_date__month') or entry.get('start_date__month') or entry.get('month')
        if month:
            revenue_data[int(month) - 1] = float(entry.get('total_revenue') or 0)

    for entry in monthly_subscriptions_qs:
        month = entry.get('start_date__month') or entry.get('payment_date__month') or entry.get('month')
        if month:
            subscription_data[int(month) - 1] = float(entry.get('subscription_count') or 0)

    # Recent transactions: scoped to admin's plans via plan.category.created_by
    if is_admin:
        plan_ids = list(_admin_plan_queryset(user).values_list('id', flat=True))
        recent_transactions = Subscription.objects.filter(
            plan__id__in=plan_ids,
            customer__role='customer'
        ).order_by('-start_date')[:5]
    else:
        recent_transactions = Subscription.objects.filter(customer__role='customer').order_by('-start_date')[:5]

    # Location-based (helper accepts owner)
    location, location_ratio = locationbased(owner=owner)

    context = {
        'total_revenue': total_revenue,
        'total_customers': total_customers,
        'new_subscriptions': new_subscriptions,
        'churn_rate': churn_rate,
        'arpu': arpu,
        'mrr': mrr,
        'revenue_labels': list(months),
        'revenue_data': revenue_data,
        'subscription_labels': list(months),
        'subscription_data': subscription_data,
        'recent_transactions': recent_transactions,
        'total_plans': total_plans,
        'location': location,
        'location_ratio': location_ratio,
    }
    return render(request, 'dashboard/index.html', context)



    

# --------------------------
# Authentication Views
# --------------------------
# notifications/views.py (signup_view)
def signup_view(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()  # save handles set_password()
            # Create profile
            if user.role == 'customer':
                CustomerProfile.objects.create(
                    user=user,
                    state=form.cleaned_data.get('state', ''),
                    district=form.cleaned_data.get('district', ''),
                    city=form.cleaned_data.get('city', ''),
                    pin_code=form.cleaned_data.get('pin_code', '')
                )
            else:
                AdminProfile.objects.create(user=user)
            return redirect('login')
    else:
        form = SignUpForm()
    return render(request, 'sign_up/signup.html', {'form': form})




def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data['user']
            login(request, user)

            if user.role == 'admin':
                return redirect('LKJH')  # Admin dashboard
            else:
                return redirect('customer_dashboard')
    else:
        form = LoginForm()

    return render(request, 'login/login.html', {'form': form})





@login_required
def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect('login')




# --------------------------
# Notifications
# --------------------------

from .filters import OrderFilter

def notifications_view(request):
    notifications = Notification.objects.all()
    alerts = Alert.objects.all()
    myFilter = OrderFilter(request.GET, queryset=notifications)
    notifications = myFilter.qs
    sort_by = request.GET.get('sort_by', 'date_sent_desc')
    
    if sort_by == 'type':
        notifications = notifications.order_by('type')
    elif sort_by == 'title':
        notifications = notifications.order_by('title')
    elif sort_by == 'recipient':
        notifications = notifications.order_by('recipient')
    elif sort_by == 'date_sent_asc':
        notifications = notifications.order_by('date_sent')
    else:  # default is 'date_sent_desc'
        notifications = notifications.order_by('-date_sent')
    
    context = {
        'notifications': notifications,
        'alerts': alerts,
        'myFilter': myFilter,
        'sort_by': sort_by,
    }
    return render(request, 'notifications/notifications.html', context)


import requests
from django.conf import settings

def send_sms_via_msg91(phone, message):
    """Send SMS using MSG91 transactional API"""
    url = "https://api.msg91.com/api/v2/sendsms"
    headers = {
        'authkey': settings.MSG91_AUTH_KEY,
        'Content-Type': 'application/json'
    }
    payload = {
        "sender": settings.MSG91_SENDER_ID,
        "route": settings.MSG91_ROUTE,
        "country": settings.MSG91_COUNTRY,
        "sms": [
            {"message": message, "to": [phone]}
        ]
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"MSG91 error: {e}")
        return False



# notifications/views.py (snippet)
from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import NotificationForm
from .models import Notification, User
from .utils import send_and_update_notification

# notifications/views.py
from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import NotificationForm
from .models import Notification, User
from .utils import send_and_update_notification
from django.db import transaction

def new_notification_view(request):
    """
    Admin view to send a notification. This implementation avoids creating a
    'template' Notification row that duplicates per-user notifications.
    - For single recipient: create one Notification and send it.
    - For broadcast: create per-user Notification rows only.
    """
    if request.method == 'POST':
        form = NotificationForm(request.POST)
        send_to_all = request.POST.get('send_to_all') == 'yes'  # adapt to your form field

        if form.is_valid():
            # Do NOT save the form as a template row to avoid duplicates.
            cleaned = form.cleaned_data

            title = cleaned['title']
            notif_type = cleaned['type']
            details = cleaned['details']
            recipient_value = cleaned.get('recipient')  # can be email for single send

            if send_to_all:
                # Broadcast: create per-user notification rows and send synchronously
                users = User.objects.filter(role='customer').only('id', 'email')
                sent = 0
                failed = 0

                # Use a DB transaction to avoid partial states if you want
                with transaction.atomic():
                    for user in users.iterator():
                        # Skip creating a per-user notification if one already exists very recently
                        exists = Notification.objects.filter(
                            recipient_user=user,
                            title=title,
                            details=details
                        ).exists()
                        if exists:
                            continue

                        per_notif = Notification.objects.create(
                            title=title,
                            type=notif_type,
                            recipient_user=user,
                            recipient=user.email,
                            details=details,
                            status='pending'
                        )

                        res = send_and_update_notification(per_notif, pause_seconds=0.2)
                        if res.get('success'):
                            sent += 1
                        else:
                            failed += 1

                messages.success(request, f'Broadcast completed. Sent: {sent}. Failed: {failed}.')
                return redirect('notifications')

            else:
                # Single recipient email send: create exactly one Notification and send it.
                # If recipient matches a user, link it; otherwise leave recipient_user blank.
                recipient_email = recipient_value.strip()
                recipient_user = User.objects.filter(email__iexact=recipient_email).first()

                # Prevent duplicate if same user already has same notification recently
                existing = Notification.objects.filter(
                    recipient__iexact=recipient_email,
                    title=title,
                    details=details
                ).first()
                if existing and existing.recipient_user == recipient_user:
                    messages.info(request, "An identical notification already exists; resent that instead.")
                    # resend existing
                    send_and_update_notification(existing, pause_seconds=0)
                    return redirect('notifications')

                n = Notification.objects.create(
                    title=title,
                    type=notif_type,
                    recipient=recipient_email,
                    recipient_user=recipient_user,
                    details=details,
                    status='pending'
                )
                res = send_and_update_notification(n, pause_seconds=0)
                if res.get('success'):
                    messages.success(request, "Email sent successfully.")
                else:
                    messages.error(request, f"Send failed: {res.get('error')}")
                return redirect('notifications')

    else:
        form = NotificationForm()

    return render(request, 'notifications/new_notification.html', {'form': form})







# notifications/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import NotificationForm
from .models import Notification
from .utils import send_and_update_notification

@login_required
def update_notification_view(request, pk):
    notif = get_object_or_404(Notification, pk=pk)

    if request.method == 'POST':
        form = NotificationForm(request.POST, instance=notif)
        if form.is_valid():
            notif = form.save(commit=False)
            # If AJAX request, perform send and return JSON
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                # synchronous send (safe for small tests / admin)
                result = send_and_update_notification(notif, pause_seconds=0)
                if result.get('success'):
                    return JsonResponse({'ok': True, 'message': 'Email resent successfully.'})
                else:
                    return JsonResponse({'ok': False, 'message': result.get('error', 'Unknown error')} , status=500)
            else:
                # non-AJAX fallback: send and redirect with messages
                result = send_and_update_notification(notif, pause_seconds=0)
                if result.get('success'):
                    messages.success(request, "Email resent successfully!")
                else:
                    messages.error(request, f"Failed to resend email: {result.get('error')}")
                return redirect('notifications')
        else:
            # If AJAX and invalid form send validation errors
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                errors = {k: v.get_json_data() for k, v in form.errors.items()}
                return JsonResponse({'ok': False, 'errors': form.errors}, status=400)
    else:
        form = NotificationForm(instance=notif)

    return render(request, 'notifications/update_notification.html', {'form': form, 'notification': notif})



# ✅ List all notifications
@login_required
def all_notifications_view(request):
    notifications = Notification.objects.all().order_by('-date_sent')
    myFilter = OrderFilter(request.GET, queryset=notifications)
    notifications = myFilter.qs

    sort_by = request.GET.get('sort_by', 'date_sent_desc')
    if sort_by == 'type':
        notifications = notifications.order_by('type')
    elif sort_by == 'title':
        notifications = notifications.order_by('title')
    elif sort_by == 'recipient':
        notifications = notifications.order_by('recipient')
    elif sort_by == 'date_sent_asc':
        notifications = notifications.order_by('date_sent')
    else:
        notifications = notifications.order_by('-date_sent')

    paginator = Paginator(notifications, 15)
    page = request.GET.get('page')
    notifications_page = paginator.get_page(page)

    context = {
        'notifications': notifications_page,
        'myFilter': myFilter,
        'sort_by': sort_by,
    }
    return render(request, 'notifications/notifications_list.html', context)


# ✅ Notification detail view
@login_required
def notification_detail(request, pk):
    notification = get_object_or_404(Notification, id=pk)
    return render(request, 'notifications/details_noti.html', {'notification': notification})


# ✅ Search notifications by title
@login_required
def search_noti(request):
    # Accept either GET param 'q' or POST 'searched'
    query = ''
    if request.method == 'POST':
        query = request.POST.get('searched', '').strip()
    else:
        query = request.GET.get('q', '').strip()

    if query:
        notifications = Notification.objects.filter(
            Q(title__icontains=query) | Q(details__icontains=query)
        ).order_by('-date_sent')
    else:
        notifications = Notification.objects.none()

    return render(request, 'notifications/search_noti.html', {'searched': query, 'notifications': notifications})

# --------------------------
# Plan Views
# --------------------------



@login_required
def plan_list(request):
    sort_by = request.GET.get('sort_by', 'name')
    search_query = request.GET.get('search', '')
    category_id = request.GET.get('category', '')

    # Base queryset
    plans = Plan.objects.all()

    # ✅ Restrict admin to only their own plans
    if request.user.role == 'admin':
        plans = plans.filter(category__created_by=request.user)

    # Search filter
    if search_query:
        plans = plans.filter(name__icontains=search_query)

    # Category filter
    if category_id:
        plans = plans.filter(category__id=category_id)

    # Sorting options
    if sort_by == 'price':
        plans = plans.order_by('price')
    elif sort_by == 'created_date':
        plans = plans.order_by('created_date')
    elif sort_by == 'final_price':
        plans = sorted(plans, key=lambda x: x.final_price)
    else:
        plans = plans.order_by('name')

    categories = Category.objects.all()

    context = {
        'plans': plans,
        'categories': categories,
        'search_query': search_query,
        'sort_by': sort_by,
        'selected_category': int(category_id) if category_id else None,
    }
    return render(request, 'plans/plans_list.html', context)


def plan_detail(request, plan_id):
    plan = get_object_or_404(Plan, pk=plan_id)
    context = {'plan': plan}
    return render(request, 'plans/plan_detail.html', context)


def create_plan(request):
    # initialize form (bind POST data when available)
    if request.method == 'POST':
        form = PlanForm(request.POST)
        # restrict category choices to categories created by current user
        form.fields['category'].queryset = Category.objects.filter(created_by=request.user)
        if form.is_valid():
            form.save()
            return redirect('plan_list')
    else:
        form = PlanForm()
        # restrict category choices for the empty form
        form.fields['category'].queryset = Category.objects.filter(created_by=request.user)

    # you can still pass categories separately if your template expects them,
    # but it's better to use form.category in the template after this change.
    return render(request, 'plans/plan_form.html', {'form': form})

def edit_plan(request, plan_id):
    plan = get_object_or_404(Plan, pk=plan_id)
    if request.method == 'POST':
        form = PlanForm(request.POST, instance=plan)
        if form.is_valid():
            form.save()
            return redirect('plan_list')
    else:
        form = PlanForm(instance=plan)
    categories = Category.objects.all()
    return render(request, 'plans/plan_form.html', {'form': form, 'categories': categories})


def plan_delete(request, plan_id):
    plan = get_object_or_404(Plan, id=plan_id)
    subscriptions_exist = Subscription.objects.filter(plan=plan).exists()

    if request.method == 'POST' and not subscriptions_exist:
        plan.delete()
        messages.success(request, "Plan deleted successfully.")
        return redirect('plan_list')

    return render(request, 'plans/plan_confirm_delete.html', {'plan': plan, 'subscriptions_exist': subscriptions_exist})


# --------------------------
# Subscription CRUD
# --------------------------




def customer_list(request):
    query = request.GET.get('q', '')

    # Get subscriptions of plans owned by this admin
    subscriptions = Subscription.objects.filter(plan__admin=request.user)
    
    # Get distinct customers from these subscriptions
    customers = User.objects.filter(
        id__in=subscriptions.values_list('customer_id', flat=True)
    )

    if query:
        customers = customers.filter(username__icontains=query)

    return render(request, 'payments/customer_list.html', {'customers': customers})



@login_required

def payments_list(request):
    query = request.GET.get('q', '').strip()

    # only payments related to plans whose category.created_by == current admin
    payments = Payment.objects.select_related(
        'subscription__customer', 'subscription__plan', 'subscription__plan__category'
    ).filter(subscription__plan__category__created_by=request.user)

    if query:
        payments = payments.filter(
            Q(subscription__customer__username__icontains=query) |
            Q(subscription__plan__name__icontains=query) |
            Q(transaction_id__icontains=query)
        )

    return render(request, 'payments/payments_list.html', {'payments': payments, 'query': query})


# --------------------------
# Category Views
# --------------------------
from django.shortcuts import render, redirect, get_object_or_404
from .models import Category
from .forms import CategoryForm

from django.shortcuts import render, redirect, get_object_or_404
from .models import Category
from .forms import CategoryForm

# notifications/views.py -> category_manage
from django.shortcuts import get_object_or_404

def category_manage(request):
    categories = Category.objects.filter(created_by=request.user)
    category = None
    edit_id = request.GET.get("edit")
    if edit_id:
        category = get_object_or_404(Category, id=edit_id, created_by=request.user)

    delete_id = request.GET.get("delete")
    if delete_id:
        obj = get_object_or_404(Category, id=delete_id, created_by=request.user)
        obj.delete()
        return redirect("category_manage")

    if category:
        form = CategoryForm(request.POST or None, instance=category)
    else:
        form = CategoryForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        category_instance = form.save(commit=False)
        if not category_instance.pk:
            category_instance.created_by = request.user
        else:
            # enforce that created_by remains original owner
            category_instance.created_by = get_object_or_404(Category, pk=category_instance.pk).created_by
        category_instance.save()
        return redirect("category_manage")

    return render(request, "category/category_manage.html", {"form": form, "categories": categories})
