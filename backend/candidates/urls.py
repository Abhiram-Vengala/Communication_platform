from rest_framework.routers import DefaultRouter

from .views import CandidateViewSet

router = DefaultRouter()
router.register("candidates", CandidateViewSet, basename="candidate")
urlpatterns = router.urls
