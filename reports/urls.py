from django.urls import path

from .views import ConsumptionReportViewSet, SummaryViewSet

urlpatterns = [
    path('consumption/', ConsumptionReportViewSet.as_view({'get': 'list'}), name='consumption-report'),
    path('summary/', SummaryViewSet.as_view({'get': 'list'}), name='summary'),
]