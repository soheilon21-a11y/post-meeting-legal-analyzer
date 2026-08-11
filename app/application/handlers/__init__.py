from app.application.handlers.document_handlers import DocumentCommandHandler
from app.application.handlers.document_handlers import DocumentQueryHandler
from app.application.handlers.matter_handlers import MatterCommandHandler
from app.application.handlers.matter_handlers import MatterQueryHandler
from app.application.handlers.meeting_handlers import MeetingCommandHandler
from app.application.handlers.meeting_handlers import MeetingQueryHandler
from app.application.handlers.organization_handlers import OrganizationCommandHandler
from app.application.handlers.organization_handlers import OrganizationQueryHandler

__all__ = [
    "AnalysisCommandHandler",
    "AnalysisQueryHandler",
    "DocumentCommandHandler",
    "DocumentQueryHandler",
    "MatterCommandHandler",
    "MatterQueryHandler",
    "MeetingCommandHandler",
    "MeetingQueryHandler",
    "OrganizationCommandHandler",
    "OrganizationQueryHandler",
    "RedlineCommandHandler",
    "RedlineQueryHandler",
    "ReportCommandHandler",
    "ReportQueryHandler",
]
from app.application.handlers.analysis_handlers import AnalysisCommandHandler
from app.application.handlers.analysis_handlers import AnalysisQueryHandler
from app.application.handlers.redline_handlers import RedlineCommandHandler
from app.application.handlers.redline_handlers import RedlineQueryHandler
from app.application.handlers.report_handlers import ReportCommandHandler
from app.application.handlers.report_handlers import ReportQueryHandler
