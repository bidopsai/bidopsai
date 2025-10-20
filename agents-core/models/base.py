"""
Base Pydantic models for the agent system.

Provides reusable base classes with common functionality:
- Timestamped models with created_at/updated_at
- Identified models with UUID
- JSON serialization helpers
"""

import uuid
from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, Field, ConfigDict


class TimestampedModel(BaseModel):
    """
    Base model with automatic timestamp fields.
    
    Attributes:
        created_at: Creation timestamp (auto-generated)
        updated_at: Last update timestamp (optional)
    """
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        },
        use_enum_values=True,
        populate_by_name=True,
        validate_assignment=True
    )
    
    def mark_updated(self) -> None:
        """Update the updated_at timestamp to current time."""
        self.updated_at = datetime.now()


class IdentifiedModel(TimestampedModel):
    """
    Base model with UUID identifier and timestamps.
    
    Attributes:
        id: Unique identifier (auto-generated UUID4)
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    
    def __hash__(self) -> int:
        """Make model hashable by ID for use in sets/dicts."""
        return hash(self.id)
    
    def __eq__(self, other: Any) -> bool:
        """Compare models by ID."""
        if not isinstance(other, IdentifiedModel):
            return False
        return self.id == other.id


class ConfigurableModel(BaseModel):
    """
    Base model for configurable components (agents, tools, etc.).
    
    Attributes:
        enabled: Whether component is enabled
        config: Additional configuration as dict
    """
    enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)
    
    model_config = ConfigDict(
        extra="allow",  # Allow extra fields for flexibility
        use_enum_values=True
    )


class PaginatedResponse(BaseModel):
    """
    Standard paginated response wrapper.
    
    Attributes:
        items: List of items
        total: Total count of items
        page: Current page number (1-indexed)
        page_size: Number of items per page
        has_more: Whether more pages exist
    """
    items: list[Any]
    total: int
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    
    @property
    def has_more(self) -> bool:
        """Check if more pages exist."""
        return (self.page * self.page_size) < self.total
    
    @property
    def total_pages(self) -> int:
        """Calculate total number of pages."""
        return (self.total + self.page_size - 1) // self.page_size


class ErrorResponse(BaseModel):
    """
    Standard error response model.
    
    Attributes:
        error_code: Standardized error code
        message: Human-readable error message
        details: Additional error details
        timestamp: When error occurred
    """
    error_code: str
    message: str
    details: Optional[dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    
    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat()
        }
    )


class SuccessResponse(BaseModel):
    """
    Standard success response model.
    
    Attributes:
        success: Always true
        message: Success message
        data: Response data
        timestamp: When response was created
    """
    success: bool = True
    message: str
    data: Optional[Any] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    
    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat()
        }
    )


# Type aliases for common patterns
JSON = dict[str, Any]
JSONList = list[dict[str, Any]]