from abc import ABC, abstractmethod
from pathlib import Path

from app.schemas.meeting import MeetingAnalysisResponse


class ProtocolExportService(ABC):
    """Future local DOCX/PDF export contract."""

    @abstractmethod
    def export(self, meeting: MeetingAnalysisResponse, output_dir: Path) -> Path:
        """Create a protocol file in the requested local format."""
