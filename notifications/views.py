from django.shortcuts import render, redirect, get_object_or_404
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.generic import CreateView, ListView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.db.models import Sum, Count, F
from datetime import date
from collections import Counter

from .models import Notification, Alert, Plan, Subscription, User
from .forms import SignUpForm, LoginForm, NotificationForm, PlanForm


from twilio.rest import Client

# --------------------------
# Metrics Functions
# --------------------------

def calculate_total_revenue():
    total_revenue = Subscription.objects.filter(customer__role='customer').aggregate(
        total_revenue=Sum('plan__price')
    )['total_revenue']
    return total_revenue or 0

def calculate_mrr():
    current_month_revenue = Subscription.objects.filter(
        start_date__month=date.today().month,
        customer__role='customer'
    ).aggregate(mrr=Sum('plan__price'))['mrr']
    return current_month_revenue or 0

def calculate_new_subscriptions():
    current_month = date.today().month
    return Subscription.objects.filter(start_date__month=current_month, customer__role='customer').count()

def calculate_arpu():
    total_revenue = calculate_total_revenue()
    active_subscriptions = Subscription.objects.filter(subscription_status='Active', customer__role='customer').count()
    if active_subscriptions == 0:
        return 0
    return round(total_revenue / active_subscriptions, 2)

def calculate_churn_rate():
    total_subscriptions = Subscription.objects.filter(customer__role='customer').count()
    inactive_subscriptions = Subscription.objects.filter(subscription_status='Inactive', customer__role='customer').count()
    if total_subscriptions == 0:
        return 0
    return (inactive_subscriptions / total_subscriptions) * 100

def credit_total():
    total_credit = Subscription.objects.filter(payment_method='credit_card', customer__role='customer').count()
    totalnumb = Subscription.objects.filter(customer__role='customer').count()
    return round((total_credit / totalnumb) * 100) if totalnumb else 0

def paypal_total():
    total_paypal = Subscription.objects.filter(payment_method='paypal', customer__role='customer').count()
    totalnumb = Subscription.objects.filter(customer__role='customer').count()
    return round((total_paypal / totalnumb) * 100) if totalnumb else 0

def bank_total():
    total_bank = Subscription.objects.filter(payment_method='bank_transfer', customer__role='customer').count()
    totalnumb = Subscription.objects.filter(customer__role='customer').count()
    return round((total_bank / totalnumb) * 100) if totalnumb else 0

def other_total():
    total_other = Subscription.objects.filter(payment_method='other', customer__role='customer').count()
    totalnumb = Subscription.objects.filter(customer__role='customer').count()
    return round((total_other / totalnumb) * 100) if totalnumb else 0

def active_total():
    return Subscription.objects.filter(subscription_status='Active', customer__role='customer').count() or 0

def top_performing():
    plan_counts = Subscription.objects.filter(customer__role='customer').values('plan__name').annotate(count=Count('id'))
    if not plan_counts:
        return 'No subscriptions'
    plan_counts = sorted(plan_counts, key=lambda x: x['count'], reverse=True)
    return plan_counts[0]['plan__name']

def locationbased(n=1):
    subscriptions = Subscription.objects.filter(customer__role='customer')
    totalnumb = subscriptions.count()
    if totalnumb == 0:
        return None, 0
    counter = Counter(sub.address for sub in subscriptions)
    most_common = counter.most_common(n)
    if len(most_common) < n:
        return None, 0
    location, freq = most_common[n-1]
    ratio = round((freq / totalnumb) * 100)
    return location, ratio

def prem_total():
    return Subscription.objects.filter(plan__name__iexact='premium', customer__role='customer').count() * 499

def pro_total():
    return Subscription.objects.filter(plan__name__iexact='pro', customer__role='customer').count() * 199

def basic_total():
    return Subscription.objects.filter(plan__name__iexact='basic', customer__role='customer').count() * 99

def get_monthly_revenue():
    current_year = date.today().year
    return Subscription.objects.filter(customer__role='customer', start_date__year=current_year)\
        .values('start_date__month')\
        .annotate(total_revenue=Sum('plan__price'))\
        .order_by('start_date__month')

def get_monthly_subscriptions():
    current_year = date.today().year
    return Subscription.objects.filter(customer__role='customer', start_date__year=current_year)\
        .values('start_date__month')\
        .annotate(subscription_count=Count('id'))\
        .order_by('start_date__month')


# --------------------------
# Views
# --------------------------

@login_required
def LKJH_view(request):
    total_revenue = calculate_total_revenue()
    total_customers = active_total()
    total_plans = Plan.objects.count()
    new_subscriptions = calculate_new_subscriptions()
    churn_rate = calculate_churn_rate()
    arpu = calculate_arpu()
    mrr = calculate_mrr()
    monthly_revenue = get_monthly_revenue()
    monthly_subscriptions = get_monthly_subscriptions()
    location, location_ratio = locationbased()

    months = range(1, 13)
    revenue_data = [0] * 12
    subscription_data = [0] * 12

    for entry in monthly_revenue:
        revenue_data[entry['start_date__month']-1] = float(entry['total_revenue'])

    for entry in monthly_subscriptions:
        subscription_data[entry['start_date__month']-1] = float(entry['subscription_count'])

    recent_transactions = Subscription.objects.filter(customer__role='customer').order_by('-start_date')[:5]

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
def signup_view(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
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


def new_notification_view(request):
    if request.method == 'POST':
        form = NotificationForm(request.POST)
        if form.is_valid():
            phone_number = form.cleaned_data['recipient']
            message_body = form.cleaned_data['details']

            # Twilio SMS sending
            try:
                client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                client.messages.create(
                    body=message_body,
                    from_=settings.TWILIO_PHONE_NUMBER,
                    to=phone_number
                )
                messages.success(request, "SMS sent successfully!")
                form.save()
            except Exception as e:
                messages.error(request, f"Failed to send SMS: {str(e)}")
            
            return redirect('notifications')
    else:
        form = NotificationForm()

    return render(request, 'notifications/new_notification.html', {'form': form})


def update_notification_view(request, pk):
    record = get_object_or_404(Notification, pk=pk)
    if request.method == 'POST':
        form = NotificationForm(request.POST, instance=record)
        if form.is_valid():
            email = form.cleaned_data['recipient']
            subject = form.cleaned_data['title']
            message = form.cleaned_data['details']
            # Send email
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)
            form.save()
            return redirect('notifications')
    else:
        form = NotificationForm(instance=record)
    
    return render(request, 'notifications/update_notification.html', {'form': form})


def all_notifications_view(request):
    notifications = Notification.objects.all()
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
    else:  # default
        notifications = notifications.order_by('-date_sent')
    
    context = {
        'notifications': notifications,
        'myFilter': myFilter,
        'sort_by': sort_by,
    }
    return render(request, 'notifications/notifications_list.html', context)


def notification_detail(request, pk):
    notification = get_object_or_404(Notification, id=pk)
    return render(request, 'notifications/details_noti.html', {'notification': notification})


def search_noti(request):
    notifications = []
    searched = ''
    if request.method == "POST":
        searched = request.POST.get('searched', '')
        notifications = Notification.objects.filter(title__icontains=searched)
    
    context = {'searched': searched, 'notifications': notifications}
    return render(request, 'notifications/search_noti.html', context)



# --------------------------
# Plan Views
# --------------------------



def plan_list(request):
    sort_by = request.GET.get('sort_by', 'name')
    search_query = request.GET.get('search', '')
    category_id = request.GET.get('category', '')

    plans = Plan.objects.all()

    if search_query:
        plans = plans.filter(name__icontains=search_query)

    if category_id:
        plans = plans.filter(category__id=category_id)

    if sort_by == 'price':
        plans = plans.order_by('price')
    elif sort_by == 'created_date':
        plans = plans.order_by('created_date')
    elif sort_by == 'final_price':
        plans = sorted(plans, key=lambda x: x.final_price)
    else:
        plans = plans.order_by('name')

    categories = Category.objects.all()  # to populate sidebar or dropdown

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
    if request.method == 'POST':
        form = PlanForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('plan_list')
    else:
        form = PlanForm()
    categories = Category.objects.all()
    return render(request, 'plans/plan_form.html', {'form': form, 'categories': categories})


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



def payments_list(request):
    query = request.GET.get('q', '')

    # Only subscriptions for plans whose category belongs to this admin
    payments = Subscription.objects.select_related('customer', 'plan', 'plan__category').filter(plan__category__created_by=request.user)

    if query:
        payments = payments.filter(
            Q(customer__username__icontains=query) |
            Q(plan__name__icontains=query)
        )

    context = {
        'payments': payments,
        'query': query,
    }
    return render(request, 'payments/payments_list.html', context)


# --------------------------
# Category Views
# --------------------------
from django.shortcuts import render, redirect, get_object_or_404
from .models import Category
from .forms import CategoryForm

from django.shortcuts import render, redirect, get_object_or_404
from .models import Category
from .forms import CategoryForm

def category_manage(request):
    # Only show categories created by the logged-in user
    categories = Category.objects.filter(created_by=request.user)
    category = None

    # Edit category
    edit_id = request.GET.get("edit")
    if edit_id:
        category = get_object_or_404(Category, id=edit_id, created_by=request.user)

    # Delete category
    delete_id = request.GET.get("delete")
    if delete_id:
        obj = get_object_or_404(Category, id=delete_id, created_by=request.user)
        obj.delete()
        return redirect("category_manage")

    # Add or update category form
    if category:
        form = CategoryForm(request.POST or None, instance=category)
    else:
        form = CategoryForm(request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            category_instance = form.save(commit=False)
            # Set the creator if new
            if not category_instance.pk:
                category_instance.created_by = request.user
            category_instance.save()
            return redirect("category_manage")

    return render(request, "category/category_manage.html", {
        "form": form,
        "categories": categories
    })
