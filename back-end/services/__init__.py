"""Service layer (P1.4).

Plain-Python business logic extracted from the route handlers: functions take
plain args (ids, bytes, a DB session) and return plain data, so they're testable
without Flask. Handlers stay thin — parse the request, call a service, map the
result (or a raised ServiceError) to an HTTP response. Celery tasks and the
*_ops data-access modules are called from here, not from the routes.
"""
