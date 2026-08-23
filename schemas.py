from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Optional


class EntityType(str, Enum):
    COMPANY = "Company"
    SUBSIDIARY = "Subsidiary"
    SUPPLIER = "Supplier"
    PRODUCT_LINE = "ProductLine"
    RISK_FACTOR = "RiskFactor"
    EXECUTIVE = "Executive"


class RelationshipType(str, Enum):
    OWNS_SUBSIDIARY = "OWNS_SUBSIDIARY"
    SUPPLIED_BY = "SUPPLIED_BY"
    COMPETES_WITH = "COMPETES_WITH"
    EXPOSED_TO_RISK = "EXPOSED_TO_RISK"
    PRODUCES_PRODUCT = "PRODUCES_PRODUCT"
    DEPENDS_ON = "DEPENDS_ON"
    LED_BY = "LED_BY"
    OPERATES_IN_SEGMENT = "OPERATES_IN_SEGMENT"


class Entity(BaseModel):
    id: str = Field(
        ...,
        description="Unique identifier for the entity, typically the name normalized to uppercase without spaces.",
    )
    type: EntityType = Field(..., description="The strict category of this entity.")
    name: str = Field(..., description="The canonical name of the entity.")
    description: Optional[str] = Field(
        default=None,
        description="A brief description or context about the entity.",
    )
    source_chunk_id: str = Field(
        ...,
        description="ID of the document chunk that justified this entity.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Model confidence that this entity is correctly typed and grounded in the chunk (0-1).",
    )


class Relationship(BaseModel):
    source_entity_id: str = Field(
        ...,
        description="The ID of the source entity (must match an extracted Entity ID).",
    )
    target_entity_id: str = Field(
        ...,
        description="The ID of the target entity (must match an extracted Entity ID).",
    )
    type: RelationshipType = Field(..., description="The nature of the relationship.")
    context: Optional[str] = Field(
        default=None,
        description="The textual context from the document justifying this relationship.",
    )
    source_chunk_id: str = Field(
        ...,
        description="ID of the document chunk that justified this relationship.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Model confidence that this relationship is correctly typed and grounded in the chunk (0-1).",
    )


class KnowledgeGraphExtraction(BaseModel):
    """
    Master schema passed to Instructor/Claude so extraction returns a strictly typed graph.
    Closed-world: only EntityType and RelationshipType enum values are allowed.
    """

    entities: List[Entity] = Field(
        ...,
        description="List of all entities extracted from the text.",
    )
    relationships: List[Relationship] = Field(
        ...,
        description="List of all relationships connecting the extracted entities.",
    )
