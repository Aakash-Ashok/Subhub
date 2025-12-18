from django.urls import path
from . import views, customer_views
from django.contrib.auth import views as auth_views

urlpatterns = [
    # -----------------------------
    # Authentication
    # -----------------------------
    path('login/', views.login_view, name='login'),
    path('', views.signup_view, name='signup'),
    path('logout/', views.logout_view, name='logout'),

    # -----------------------------
    # Password reset
    # -----------------------------
    path("password-reset/",
         auth_views.PasswordResetView.as_view(
             template_name="login/password_reset.html"
         ),
         name="password_reset"),

    path("password-reset/done/",
         auth_views.PasswordResetDoneView.as_view(
             template_name="login/password_reset_done.html"
         ),
         name="password_reset_done"),

    path("reset/<uidb64>/<token>/",
         auth_views.PasswordResetConfirmView.as_view(
             template_name="login/password_reset_confirm.html"
         ),
         name="password_reset_confirm"),

    path("reset/done/",
         auth_views.PasswordResetCompleteView.as_view(
             template_name="login/password_reset_complete.html"
         ),
         name="password_reset_complete"),
    # -----------------------------
    # Dashboard
    # -----------------------------
    path('dashboard/', views.LKJH_view, name='LKJH'),

    # -----------------------------
    # Notifications (Admin)
    # -----------------------------
    path('notifications/', views.notifications_view, name='notifications'),
    path('notifications/new/', views.new_notification_view, name='new_notification'),
    path('notifications/update/<int:pk>/', views.update_notification_view, name='update_notification'),
    path('notifications/all/', views.all_notifications_view, name='notifications_list'),
    path('notifications/detail/<int:pk>/', views.notification_detail, name='detail'),
    path('notifications/search/', views.search_noti, name='search_noti'),

    # -----------------------------
    # Payments (Admin)
    # -----------------------------
    path('payments/', views.payments_list, name='payments_list'),

    # -----------------------------
    # Plans (Admin)
    # -----------------------------
    path('plans/', views.plan_list, name='plan_list'),
    path('plans/create/', views.create_plan, name='plan_create'),
    path('plans/edit/<int:plan_id>/', views.edit_plan, name='plan_edit'),
    path('plans/delete/<int:plan_id>/', views.plan_delete, name='plan_delete'),
    path('plans/<int:plan_id>/', views.plan_detail, name='plan_detail'),

    # -----------------------------
    # Categories
    # -----------------------------
    path('categories/', views.category_manage, name='category_manage'),

    # -----------------------------
    # Customer
    # -----------------------------
    path('cusdashboard/', customer_views.customer_dashboard, name='customer_dashboard'),

    # ✅ ONE subscribe URL ONLY
    path('plans/<int:plan_id>/subscribe/', customer_views.subscribe_plan, name='subscribe_plan'),

    path('subscriptions/', customer_views.customer_subscriptions, name='customer_subscriptions'),
    path(
        'subscriptions/<int:subscription_id>/cancel/',
        customer_views.cancel_subscription,
        name='cancel_subscription'
    ),

    # -----------------------------
    # Customer Categories & Plans
    # -----------------------------
    path('cuscategories/', customer_views.customer_category_types, name='customer_category_types'),
    path('categories/<str:category_type>/', customer_views.categories_by_type, name='categories_by_type'),
    path(
        'categories/plans/<int:category_id>/',
        customer_views.plans_by_category,
        name='plans_by_category'
    ),

    # -----------------------------
    # 🔐 PAYMENT FLOW (IMPORTANT)
    # -----------------------------
    path(
        'payment/start/<int:subscription_id>/',
        customer_views.start_payment,
        name='start_payment'
    ),
    path(
        'payment/success/',
        customer_views.payment_success,
        name='payment_success'
    ),

    # -----------------------------
    # Customer Notifications
    # -----------------------------
    path('Cnotifications/read/<int:pk>/', customer_views.mark_notification_read, name='notif_read'),
    path('Cnotifications/unread/<int:pk>/', customer_views.mark_notification_unread, name='notif_unread'),
]
