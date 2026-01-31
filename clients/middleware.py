import logging
from django.conf import settings


class ActionAuditMiddleware:
    """Audit manager/admin actions for downstream troubleshooting."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger("audit")

    def __call__(self, request):
        response = self.get_response(request)
        try:
            user = getattr(request, "user", None)
            if not user or not user.is_authenticated:
                return response
            if not self._is_manager_or_admin(user):
                return response

            path = request.path or "/"
            if self._skip_path(path):
                return response

            self.logger.info(
                "actor=%s role=%s method=%s path=%s status=%s ip=%s",
                user.username,
                self._resolve_role(user),
                request.method,
                path,
                getattr(response, "status_code", "unknown"),
                self._get_client_ip(request),
            )
        except Exception:
            self.logger.exception("Failed to write audit log")
        return response

    def _is_manager_or_admin(self, user):
        if user.is_superuser:
            return True
        if user.is_staff:
            return True
        return user.groups.filter(name="Client Managers").exists()

    def _skip_path(self, path):
        static_url = getattr(settings, "STATIC_URL", "/static/")
        media_url = getattr(settings, "MEDIA_URL", "/media/")
        return path.startswith(static_url) or path.startswith(media_url)

    def _resolve_role(self, user):
        if user.is_superuser:
            return "admin"
        if user.groups.filter(name="Client Managers").exists():
            return "manager"
        if user.is_staff:
            return "staff"
        return "user"

    def _get_client_ip(self, request):
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")
