from django.urls import path
from . import views , customer_views
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
    path('password_reset/', auth_views.PasswordResetView.as_view(template_name='password_reset.html'), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='password_reset_complete.html'), name='password_reset_complete'),

    # -----------------------------
    # Dashboards
    # -----------------------------
    path('dashboard/', views.LKJH_view, name='LKJH'),  # optional duplicate
    

    # -----------------------------
    # Notifications (Admin only)
    # -----------------------------
    path('notifications/', views.notifications_view, name='notifications'),
    path('notifications/new/', views.new_notification_view, name='new_notification'),
    path('notifications/update/<int:pk>/', views.update_notification_view, name='update_notification'),
    path('notifications/all/', views.all_notifications_view, name='notifications_list'),
    path('notifications/detail/<int:pk>/', views.notification_detail, name='detail'),
    path('notifications/search/', views.search_noti, name='search_noti'),

    # -----------------------------
    # Customers / Payments
    # -----------------------------
    # path('payments/add/', views.add_customer, name='add_customer'),
    path('payments/', views.payments_list, name='payments_list'),
    


    # -----------------------------
    # Plans (Admin only)
    # -----------------------------
    path('plans/', views.plan_list, name='plan_list'),
    path('plans/create/', views.create_plan, name='plan_create'),
    path('plans/edit/<int:plan_id>/', views.edit_plan, name='plan_edit'),
    path('plans/delete/<int:plan_id>/', views.plan_delete, name='plan_delete'),
    path('plans/<int:plan_id>/', views.plan_detail, name='plan_detail'),

    # -----------------------------
    # Subscriptions
    # -----------------------------
    
    
    path('categories/', views.category_manage, name='category_manage'),
    
    
    # -----------------------------
    # Customer
    # -----------------------------
    path("cusdashboard/", customer_views.customer_dashboard, name="customer_dashboard"),
    path("plans/<int:plan_id>/subscribe/", customer_views.subscribe_plan, name="subscribe_plan"),
    path("subscriptions/", customer_views.customer_subscriptions, name="customer_subscriptions"),
    
    path("subscriptions/<int:subscription_id>/cancel/", customer_views.cancel_subscription, name="cancel_subscription"),
    path('cuscategories/', customer_views.customer_categories, name='customer_categories'),
    path('customer/category/<int:category_id>/plans/', customer_views.plans_by_category, name='plans_by_category'),
    path('customer/subscribe/<int:plan_id>/', customer_views.subscribe_plan, name='subscribe_plan'),
]
