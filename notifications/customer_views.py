from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Subscription, Plan , Category
from .forms import CustomerSubscriptionForm
from django.http import HttpResponseForbidden
from django.utils import timezone
from datetime import timedelta, date
from django.db.models import Sum


# --------------------------
# Customer Dashboard
# --------------------------
from datetime import date

@login_required
def customer_dashboard(request):
    customer = request.user
    subscriptions = customer.subscriptions.all()

    # Automatically compute days left for each subscription
    for sub in subscriptions:
        if sub.end_date:
            days_remaining = (sub.end_date - date.today()).days
            sub.days_left = max(days_remaining, 0)  # Avoid negative values
        else:
            sub.days_left = 0

    # Separate active/inactive
    active_subscriptions = [s for s in subscriptions if s.subscription_status == 'Active']
    pending_payments = [s for s in subscriptions if s.subscription_status == 'Inactive']

    context = {
        'customer': customer,
        'subscriptions': subscriptions,
        'active_subscriptions': active_subscriptions,
        'pending_payments': pending_payments,
    }

    return render(request, 'dashboard/cusindex.html', context)

@login_required
def subscribe_plan(request, plan_id):
    plan = get_object_or_404(Plan, id=plan_id, status='active')

    if request.method == 'POST':
        form = CustomerSubscriptionForm(request.POST)
        if form.is_valid():
            subscription = form.save(commit=False)
            subscription.customer = request.user
            subscription.plan = plan
            subscription.subscription_status = 'Active'
            subscription.start_date = timezone.now().date()

            # ✅ Set end_date based on plan duration
            if plan.duration == 'monthly':
                subscription.end_date = subscription.start_date + timedelta(days=30)
            elif plan.duration == 'yearly':
                subscription.end_date = subscription.start_date + timedelta(days=365)
            else:
                # Fallback if duration not defined
                subscription.end_date = subscription.start_date + timedelta(days=30)

            subscription.save()
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
@login_required


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
def customer_categories(request):
    categories = Category.objects.all()
    category_plans = {}

    # Count active plans for each category
    for category in categories:
        plans = category.plans.filter(status='active')  # use related_name "plans"
        category_plans[category.id] = plans

    return render(request, 'customers/categories_list.html', {
        'categories': categories,
        'category_plans': category_plans
    })


@login_required
def plans_by_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    plans = category.plans.filter(status='active')  # Use related_name "plans"

    return render(request, 'customers/plans_by_category.html', {
        'category': category,
        'plans': plans
    })

