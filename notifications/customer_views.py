from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Subscription, Plan , Category , Payment
from .forms import CustomerSubscriptionForm
from django.http import HttpResponseForbidden
from django.utils import timezone
from datetime import timedelta, date
from django.db.models import Sum


# --------------------------
# Customer Dashboard
# --------------------------
from datetime import date

from datetime import date
from collections import Counter

from collections import Counter
from datetime import date

@login_required
def customer_dashboard(request):
    customer = request.user
    subscriptions = customer.subscriptions.all()

    # Calculate days left
    for sub in subscriptions:
        if sub.end_date:
            sub.days_left = max((sub.end_date - date.today()).days, 0)
        else:
            sub.days_left = 0

    active_subscriptions = [s for s in subscriptions if s.subscription_status == 'Active']
    pending_payments = [s for s in subscriptions if s.subscription_status != 'Active']

    # Subscription chart: count per month
    months = [sub.start_date.strftime("%b %Y") for sub in subscriptions]
    month_counts = Counter(months)
    subscription_labels = list(month_counts.keys())
    subscription_data = list(month_counts.values())

    # Payment chart: sum of amounts per month (only pending payments)
    payment_months = [sub.start_date.strftime("%b %Y") for sub in pending_payments]
    payment_counter = Counter()
    for sub, month in zip(pending_payments, payment_months):
        payment_counter[month] += sub.plan.final_price
    payment_labels = list(payment_counter.keys())
    payment_data = list(payment_counter.values())

    context = {
        'customer': customer,
        'subscriptions': subscriptions,
        'active_subscriptions': active_subscriptions,
        'pending_payments': pending_payments,
        'subscription_labels': subscription_labels,
        'subscription_data': subscription_data,
        'payment_labels': payment_labels,
        'payment_data': payment_data,
    }

    return render(request, 'dashboard/cusindex.html', context)

@login_required
def subscribe_plan(request, plan_id):
    plan = get_object_or_404(Plan, id=plan_id, status='active')

    if request.method == 'POST':
        form = CustomerSubscriptionForm(request.POST)
        if form.is_valid():
            # ✅ Create subscription
            subscription = form.save(commit=False)
            subscription.customer = request.user
            subscription.plan = plan
            subscription.subscription_status = 'Active'
            subscription.start_date = timezone.now().date()

            # Set end date based on plan duration
            if plan.duration == 'monthly':
                subscription.end_date = subscription.start_date + timedelta(days=30)
            elif plan.duration == 'yearly':
                subscription.end_date = subscription.start_date + timedelta(days=365)
            else:
                subscription.end_date = subscription.start_date + timedelta(days=30)

            subscription.save()

            # ✅ Create a corresponding Payment record
            Payment.objects.create(
                subscription=subscription,
                transaction_id=f"TXN-{timezone.now().strftime('%Y%m%d%H%M%S')}",  # unique transaction id
                amount=plan.price,
                payment_method=request.POST.get('payment_method', 'credit_card'),  # optional form field
                status='completed',  # can be changed later if using payment gateway
                payment_date=timezone.now(),
                notes=f"Initial payment for {plan.name} plan."
            )

            return redirect('customer_subscriptions')
    else:
        form = CustomerSubscriptionForm()

    return render(request, 'customers/subscribe.html', {'form': form, 'plan': plan})


# ✅ List (All subscriptions of logged-in customer)
@login_required
def customer_subscriptions(request):
    subscriptions = request.user.subscriptions.all()
    return render(request, 'customers/subscription_list.html', {'subscriptions': subscriptions})


# ✅ Update (Edit subscription details like address, phone, payment)


# ✅ Delete (Cancel subscription)
@login_required
def cancel_subscription(request, subscription_id):
    subscription = get_object_or_404(Subscription, id=subscription_id)

    # Ensure the logged-in customer owns this subscription
    if subscription.customer != request.user:
        return HttpResponseForbidden("You are not allowed to cancel this subscription.")

    if request.method == 'POST':
        subscription.delete()
        return redirect('customer_subscriptions')

    return render(request, 'customers/subscription_confirm_delete.html', {'subscription': subscription})


@login_required
def customer_category_types(request):
    """
    Show only category types that have at least one category.
    """
    # Get distinct category types that have categories
    category_types = Category.objects.values_list('category', flat=True).distinct()
    category_types_with_data = [ct for ct in category_types if Category.objects.filter(category=ct).exists()]

    return render(request, 'customers/category_types.html', {
        'category_types': category_types_with_data
    })


@login_required
def categories_by_type(request, category_type):
    """
    Show all categories of a given category type in card format.
    """
    categories = Category.objects.filter(category=category_type)
    return render(request, 'customers/categories_by_type.html', {
        'categories': categories,
        'category_type': category_type
    })


@login_required
def plans_by_category(request, category_id):
    """
    Show all active plans for a specific category.
    """
    category = get_object_or_404(Category, id=category_id)
    plans = category.plans.filter(status='active')  # related_name 'plans'
    return render(request, 'customers/plans_by_category.html', {
        'category': category,
        'plans': plans
    })