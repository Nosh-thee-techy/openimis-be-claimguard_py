"""ClaimGuard URL routing."""

from django.urls import path

from claimguard.api import views

urlpatterns = [
    path("scores/", views.fraud_scores_list, name="claimguard-scores-list"),
    path("scores/<int:claim_id>/", views.claim_fraud_score, name="claimguard-score-detail"),
    path(
        "scores/<int:claim_id>/override/",
        views.override_fraud_score,
        name="claimguard-score-override",
    ),
    path("analytics/", views.fraud_analytics, name="claimguard-analytics"),
]
