"""
Generic OpenTelemetry monitoring framework for Lex API.

This module provides comprehensive tracking of:
- Page visits (/, /api/docs, /api/redoc)
- MCP protocol usage and connections
- REST API usage patterns
- IP addresses and user agents
- Rate limiting events
- Performance metrics

Built on OpenTelemetry with pluggable observability backends.
"""

import json
import logging
import os
import time
from contextvars import ContextVar
from typing import Any, Dict, Optional, Protocol, runtime_checkable

from fastapi import Request
from opentelemetry import context, metrics, trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.propagate import propagator
from opentelemetry.trace import Status, StatusCode

# Context variables for request tracking
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
user_ip_var: ContextVar[Optional[str]] = ContextVar("user_ip", default=None)


@runtime_checkable
class ObservabilityBackend(Protocol):
    """Protocol for observability backend implementations."""

    def configure(self) -> bool:
        """Configure the observability backend. Returns True if successful."""
        ...

    def get_tracer(self, name: str, version: str) -> Any:
        """Get a tracer instance."""
        ...

    def get_meter(self, name: str, version: str) -> Any:
        """Get a meter instance."""
        ...


class ApplicationInsightsBackend:
    """Azure Application Insights backend implementation."""

    def __init__(self):
        self.enabled = False

    def configure(self) -> bool:
        """Configure Application Insights with OpenTelemetry."""
        connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
        if not connection_string or connection_string == "":
            return False

        try:
            from azure.monitor.opentelemetry import configure_azure_monitor

            configure_azure_monitor(
                connection_string=connection_string,
                enable_live_metrics=True,
            )
            self.enabled = True
            return True
        except Exception as e:
            logging.warning(f"Failed to configure Application Insights: {e}")
            return False

    def get_tracer(self, name: str, version: str) -> Any:
        """Get OpenTelemetry tracer."""
        return trace.get_tracer(name, version)

    def get_meter(self, name: str, version: str) -> Any:
        """Get OpenTelemetry meter."""
        return metrics.get_meter(name, version)


class LexMonitoring:
    """Generic OpenTelemetry monitoring for Lex API with pluggable backends."""

    def __init__(self, backend: Optional[ObservabilityBackend] = None):
        self.enabled = False
        self.tracer = None
        self.meter = None
        self.logger = logging.getLogger("lex.monitoring")
        self.backend = backend or ApplicationInsightsBackend()

        # Configure the observability backend
        if self.backend.configure():
            try:
                self.tracer = self.backend.get_tracer("lex.api", version="2.0.0")
                self.meter = self.backend.get_meter("lex.api", version="2.0.0")
                self.enabled = True

                # Create custom metrics for analytics
                self.page_view_counter = self.meter.create_counter(
                    name="lex_page_views",
                    description="Number of page views for documentation",
                    unit="1",
                )

                self.api_request_counter = self.meter.create_counter(
                    name="lex_api_requests", description="Number of API endpoint requests", unit="1"
                )

                self.mcp_event_counter = self.meter.create_counter(
                    name="lex_mcp_events",
                    description="MCP protocol events and connections",
                    unit="1",
                )

                self.rate_limit_counter = self.meter.create_counter(
                    name="lex_rate_limit_events",
                    description="Rate limiting events and violations",
                    unit="1",
                )

                # Performance metrics
                self.request_duration = self.meter.create_histogram(
                    name="lex_request_duration",
                    description="Request duration in milliseconds",
                    unit="ms",
                )

                # MCP-specific metrics
                self.mcp_tool_invocation_counter = self.meter.create_counter(
                    name="lex_mcp_tool_invocations",
                    description="Total number of MCP tool invocations",
                    unit="1",
                )

                self.mcp_tool_duration = self.meter.create_histogram(
                    name="lex_mcp_tool_duration",
                    description="Duration of MCP tool executions",
                    unit="ms",
                )

                self.mcp_session_counter = self.meter.create_counter(
                    name="lex_mcp_sessions", description="MCP client session events", unit="1"
                )

                self.logger.info(
                    f"OpenTelemetry monitoring configured successfully with {type(self.backend).__name__}"
                )

            except Exception as e:
                self.logger.warning(f"Failed to configure monitoring metrics: {e}")
                self.enabled = False
        else:
            self.logger.info("No observability backend configured - monitoring disabled")

    def instrument_fastapi(self, app):
        """Instrument FastAPI application with OpenTelemetry."""
        if self.enabled:
            try:
                FastAPIInstrumentor.instrument_app(app, tracer_provider=trace.get_tracer_provider())
                HTTPXClientInstrumentor().instrument()
                RequestsInstrumentor().instrument()
                RedisInstrumentor().instrument()
                self.logger.info("FastAPI instrumented with OpenTelemetry")
            except Exception as e:
                self.logger.error(f"Failed to instrument FastAPI: {e}")

    def track_page_view(self, request: Request, page_name: str):
        """Track page view with detailed metadata for analytics."""
        if not self.enabled:
            return

        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("User-Agent", "unknown")

        # Create custom span for page view with rich attributes
        with self.tracer.start_as_current_span(f"page_view_{page_name}") as span:
            span.set_attributes(
                {
                    "page.name": page_name,
                    "page.url": str(request.url),
                    "page.path": request.url.path,
                    "user.ip": client_ip,
                    "user.agent": user_agent,
                    "user.agent.category": self._categorise_user_agent(user_agent),
                    "http.method": request.method,
                    "http.scheme": request.url.scheme,
                    "net.host.name": request.url.hostname,
                    "request.timestamp": time.time(),
                }
            )

            # Increment page view counter with dimensions
            self.page_view_counter.add(
                1,
                {
                    "page_name": page_name,
                    "source_ip_region": self._anonymise_ip(client_ip),
                    "user_agent_category": self._categorise_user_agent(user_agent),
                },
            )

            span.set_status(Status(StatusCode.OK))

        # Structured log for additional analytics
        self.logger.info(
            f"Page view: {page_name}",
            extra={
                "custom_dimensions": {
                    "event_type": "page_view",
                    "page_name": page_name,
                    "client_ip": self._anonymise_ip(client_ip),
                    "user_agent": user_agent,
                    "url": str(request.url),
                }
            },
        )

    def track_api_usage(
        self,
        request: Request,
        endpoint: str,
        duration: float,
        status_code: int,
        query_params: Dict[str, Any] = None,
    ):
        """Track API endpoint usage with performance and query analytics."""
        if not self.enabled:
            return

        client_ip = self._get_client_ip(request)
        content_length = int(request.headers.get("Content-Length", 0))

        with self.tracer.start_as_current_span(f"api_call_{endpoint.replace('/', '_')}") as span:
            span.set_attributes(
                {
                    "api.endpoint": endpoint,
                    "api.method": request.method,
                    "api.duration_ms": duration * 1000,
                    "api.status_code": status_code,
                    "api.success": status_code < 400,
                    "user.ip": client_ip,
                    "request.content_length": content_length,
                    "request.has_query_params": bool(query_params),
                    "request.timestamp": time.time(),
                }
            )

            # Add query parameter analytics (anonymised)
            if query_params:
                span.set_attributes(
                    {
                        "query.has_search": "query" in query_params,
                        "query.has_filters": any(
                            k in query_params for k in ["year_from", "year_to", "court", "types"]
                        ),
                        "query.limit": query_params.get("limit", 0)
                        if query_params.get("limit")
                        else 0,
                    }
                )

            # Increment API request counter
            self.api_request_counter.add(
                1,
                {
                    "endpoint": endpoint,
                    "method": request.method,
                    "status_code": str(status_code),
                    "source_ip_region": self._anonymise_ip(client_ip),
                    "endpoint_category": self._categorise_endpoint(endpoint),
                },
            )

            # Record request duration
            self.request_duration.record(
                duration * 1000,
                {"endpoint": endpoint, "method": request.method, "status_code": str(status_code)},
            )

            span.set_status(
                Status(StatusCode.OK) if status_code < 400 else Status(StatusCode.ERROR)
            )

    def track_mcp_event(
        self,
        event_type: str,
        client_info: Dict[str, Any] = None,
        session_data: Dict[str, Any] = None,
    ):
        """Track MCP protocol events and AI agent connections."""
        if not self.enabled:
            return

        with self.tracer.start_as_current_span(f"mcp_{event_type}") as span:
            span.set_attributes(
                {
                    "mcp.event_type": event_type,
                    "mcp.client_name": client_info.get("name", "unknown")
                    if client_info
                    else "unknown",
                    "mcp.client_version": client_info.get("version", "unknown")
                    if client_info
                    else "unknown",
                    "mcp.protocol_version": client_info.get("protocolVersion", "unknown")
                    if client_info
                    else "unknown",
                    "mcp.timestamp": time.time(),
                }
            )

            # Add session-specific data
            if session_data:
                span.set_attributes(
                    {
                        "mcp.session_id": session_data.get("session_id", "unknown"),
                        "mcp.tools_available": session_data.get("tools_count", 0),
                        "mcp.session_duration": session_data.get("duration", 0),
                    }
                )

            # Increment MCP event counter
            self.mcp_event_counter.add(
                1,
                {
                    "event_type": event_type,
                    "client_name": client_info.get("name", "unknown") if client_info else "unknown",
                    "protocol_version": client_info.get("protocolVersion", "unknown")
                    if client_info
                    else "unknown",
                },
            )

            span.set_status(Status(StatusCode.OK))

        # Structured logging for MCP analytics
        self.logger.info(
            f"MCP event: {event_type}",
            extra={
                "custom_dimensions": {
                    "event_type": "mcp_event",
                    "mcp_event_type": event_type,
                    "client_info": client_info,
                    "session_data": session_data,
                }
            },
        )

    def track_mcp_tool_execution(
        self,
        tool_name: str,
        duration: float,
        success: bool,
        client_info: Dict[str, Any] = None,
        error_type: str = None,
        meta: Dict[str, Any] = None,
    ):
        """Track MCP tool execution with comprehensive metrics and context propagation."""
        if not self.enabled:
            return

        # Extract trace context from MCP _meta field if provided
        parent_context = self._extract_context_from_meta(meta) if meta else context.get_current()

        with self.tracer.start_as_current_span(
            f"mcp_tool_{tool_name}", context=parent_context, kind=trace.SpanKind.SERVER
        ) as span:
            span.set_attributes(
                {
                    "mcp.tool.name": tool_name,
                    "mcp.tool.duration_ms": duration * 1000,
                    "mcp.tool.success": success,
                    "mcp.client.name": client_info.get("name") if client_info else "unknown",
                    "mcp.client.version": client_info.get("version") if client_info else "unknown",
                    "mcp.has_context": bool(meta),
                }
            )

            if error_type:
                span.set_attributes({"mcp.tool.error_type": error_type})
                span.set_status(Status(StatusCode.ERROR))
            else:
                span.set_status(Status(StatusCode.OK))

        # Record metrics
        self.mcp_tool_invocation_counter.add(
            1,
            {
                "tool_name": tool_name,
                "success": str(success),
                "client_type": client_info.get("name", "unknown") if client_info else "unknown",
            },
        )

        self.mcp_tool_duration.record(
            duration * 1000, {"tool_name": tool_name, "success": str(success)}
        )

    def track_mcp_session_lifecycle(self, event: str, session_id: str, client_info: Dict[str, Any]):
        """Track MCP session lifecycle events (initialize, shutdown, etc.)."""
        if not self.enabled:
            return

        with self.tracer.start_as_current_span(f"mcp_session_{event}") as span:
            span.set_attributes(
                {
                    "mcp.session.id": session_id,
                    "mcp.session.event": event,
                    "mcp.client.name": client_info.get("name", "unknown"),
                    "mcp.client.version": client_info.get("version", "unknown"),
                    "mcp.protocol.version": client_info.get("protocolVersion", "unknown"),
                }
            )

        # Record session metrics
        self.mcp_session_counter.add(
            1, {"event": event, "client_name": client_info.get("name", "unknown")}
        )

        self.logger.info(
            f"MCP session {event}: {session_id}",
            extra={
                "custom_dimensions": {
                    "event_type": "mcp_session",
                    "session_event": event,
                    "session_id": session_id,
                    "client_info": client_info,
                }
            },
        )

    def _extract_context_from_meta(self, meta: Dict[str, Any]) -> Any:
        """Extract OpenTelemetry context from MCP _meta field."""
        if not meta:
            return context.get_current()

        try:
            # Extract W3C trace context from _meta field
            carrier = {}
            if "traceparent" in meta:
                carrier["traceparent"] = meta["traceparent"]
            if "tracestate" in meta:
                carrier["tracestate"] = meta["tracestate"]
            if "baggage" in meta:
                carrier["baggage"] = meta["baggage"]

            if carrier:
                return propagator.extract(carrier)
        except Exception as e:
            self.logger.warning(f"Failed to extract context from MCP _meta: {e}")

        return context.get_current()

    def inject_context_to_meta(self) -> Dict[str, Any]:
        """Inject current OpenTelemetry context into MCP _meta field format."""
        if not self.enabled:
            return {}

        try:
            carrier = {}
            propagator.inject(carrier, context=context.get_current())
            return carrier
        except Exception as e:
            self.logger.warning(f"Failed to inject context to MCP _meta: {e}")
            return {}

    def track_rate_limit_event(
        self,
        request: Request,
        limit_type: str,
        current_count: int,
        limit_value: int,
        exceeded: bool = False,
    ):
        """Track rate limiting events and near-limit warnings."""
        if not self.enabled:
            return

        client_ip = self._get_client_ip(request)

        with self.tracer.start_as_current_span(f"rate_limit_{limit_type}") as span:
            span.set_attributes(
                {
                    "rate_limit.type": limit_type,
                    "rate_limit.current_count": current_count,
                    "rate_limit.limit_value": limit_value,
                    "rate_limit.exceeded": exceeded,
                    "rate_limit.usage_percentage": (current_count / limit_value) * 100,
                    "user.ip": client_ip,
                    "request.endpoint": request.url.path,
                    "request.timestamp": time.time(),
                }
            )

            # Increment rate limit counter
            self.rate_limit_counter.add(
                1,
                {
                    "limit_type": limit_type,
                    "exceeded": str(exceeded),
                    "usage_tier": self._get_usage_tier(current_count, limit_value),
                    "source_ip_region": self._anonymise_ip(client_ip),
                },
            )

            span.set_status(Status(StatusCode.ERROR) if exceeded else Status(StatusCode.OK))

        # Log rate limit events for security monitoring
        log_level = "warning" if exceeded else "info"
        self.logger.log(
            getattr(logging, log_level.upper()),
            f"Rate limit {limit_type}: {current_count}/{limit_value} ({'exceeded' if exceeded else 'within limits'})",
            extra={
                "custom_dimensions": {
                    "event_type": "rate_limit",
                    "limit_type": limit_type,
                    "client_ip": self._anonymise_ip(client_ip),
                    "exceeded": exceeded,
                    "current_count": current_count,
                    "limit_value": limit_value,
                }
            },
        )

    def track_error(self, request: Request, error: Exception, endpoint: str):
        """Track application errors and exceptions."""
        if not self.enabled:
            return

        client_ip = self._get_client_ip(request)

        with self.tracer.start_as_current_span("error") as span:
            span.set_attributes(
                {
                    "error.type": type(error).__name__,
                    "error.message": str(error),
                    "error.endpoint": endpoint,
                    "user.ip": client_ip,
                    "request.method": request.method,
                    "request.timestamp": time.time(),
                }
            )

            span.record_exception(error)
            span.set_status(Status(StatusCode.ERROR, str(error)))

        # Log structured error for debugging
        self.logger.error(
            f"Application error in {endpoint}: {error}",
            extra={
                "custom_dimensions": {
                    "event_type": "error",
                    "error_type": type(error).__name__,
                    "endpoint": endpoint,
                    "client_ip": self._anonymise_ip(client_ip),
                    "error_message": str(error),
                }
            },
            exc_info=True,
        )

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address considering Azure proxies."""
        # Check Azure Front Door headers first
        forwarded_for = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        if forwarded_for:
            return forwarded_for

        # Check other common proxy headers
        real_ip = request.headers.get("X-Real-IP", "")
        if real_ip:
            return real_ip

        client_ip = request.headers.get("X-Client-IP", "")
        if client_ip:
            return client_ip

        # Fallback to direct client host
        return getattr(request.client, "host", "unknown") if request.client else "unknown"

    def _anonymise_ip(self, ip: str) -> str:
        """Anonymise IP address for privacy compliance (keep first 3 octets for regional analytics)."""
        if not ip or ip == "unknown":
            return "unknown"

        try:
            # For IPv4, keep first 3 octets
            parts = ip.split(".")
            if len(parts) == 4:
                return f"{parts[0]}.{parts[1]}.{parts[2]}.xxx"

            # For IPv6, keep first 4 groups
            if ":" in ip:
                parts = ip.split(":")
                if len(parts) >= 4:
                    return f"{':'.join(parts[:4])}::xxxx"

        except Exception:
            pass

        return "unknown"

    def _categorise_user_agent(self, user_agent: str) -> str:
        """Categorise user agent for analytics."""
        if not user_agent or user_agent == "unknown":
            return "unknown"

        ua_lower = user_agent.lower()

        if "curl" in ua_lower:
            return "curl"
        elif "postman" in ua_lower:
            return "postman"
        elif "insomnia" in ua_lower:
            return "insomnia"
        elif "python" in ua_lower:
            return "python_client"
        elif "node" in ua_lower or "javascript" in ua_lower:
            return "javascript_client"
        elif any(browser in ua_lower for browser in ["chrome", "firefox", "safari", "edge"]):
            return "web_browser"
        elif "bot" in ua_lower or "crawler" in ua_lower:
            return "bot"
        elif "mcp" in ua_lower or "claude" in ua_lower:
            return "ai_agent"
        else:
            return "other"

    def _categorise_endpoint(self, endpoint: str) -> str:
        """Categorise API endpoint for analytics."""
        if endpoint.startswith("/legislation"):
            return "legislation"
        elif endpoint.startswith("/caselaw"):
            return "caselaw"
        elif endpoint.startswith("/mcp"):
            return "mcp"
        elif endpoint in ["/", "/api/docs", "/api/redoc"]:
            return "documentation"
        elif endpoint == "/healthcheck":
            return "health"
        else:
            return "other"

    def _get_usage_tier(self, current: int, limit: int) -> str:
        """Get usage tier for rate limiting analytics."""
        percentage = (current / limit) * 100

        if percentage >= 100:
            return "exceeded"
        elif percentage >= 90:
            return "high"
        elif percentage >= 70:
            return "medium"
        elif percentage >= 50:
            return "moderate"
        else:
            return "low"

    def parse_mcp_request(self, body: bytes) -> Dict[str, Any]:
        """Parse MCP JSON-RPC request body safely."""
        try:
            return json.loads(body.decode("utf-8"))
        except Exception as e:
            self.logger.warning(f"Failed to parse MCP request body: {e}")
            return {}


# Global instance with default Application Insights backend
monitoring = LexMonitoring()
