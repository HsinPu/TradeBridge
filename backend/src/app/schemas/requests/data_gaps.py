from pydantic import BaseModel, Field

from app.application.models.data_gap import DataGapRepairCommand


class DataGapRepairRequest(BaseModel):
    batch_limit: int = Field(default=1000, ge=1, le=1000)
    overlap_candles: int = Field(default=2, ge=0, le=20)
    verify_continuity: bool = True
    retry_attempts: int = Field(default=2, ge=0, le=5)
    retry_delay_seconds: float = Field(default=0.25, ge=0, le=5)

    def to_command(self, gap_id: str) -> DataGapRepairCommand:
        return DataGapRepairCommand(
            gap_id=gap_id,
            batch_limit=self.batch_limit,
            overlap_candles=self.overlap_candles,
            verify_continuity=self.verify_continuity,
            retry_attempts=self.retry_attempts,
            retry_delay_seconds=self.retry_delay_seconds,
        )
