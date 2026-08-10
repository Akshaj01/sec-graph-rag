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
    id: str = Field(..., description="Unique identifier for the entity, typically the name normalized to uppercase without spaces.")
    type: EntityType = Field(..., description="The strict category of this entity.")
    name: str = Field(..., description="The canonical name of the entity.")
    description: Optional[str] = Field(default=None, description="A brief description or context about the entity.")

class Relationship(BaseModel):
    source_entity_id: str = Field(..., description="The ID of the source entity (must match an extracted Entity ID).")
    target_entity_id: str = Field(..., description="The ID of the target entity (must match an extracted Entity ID).")
    type: RelationshipType = Field(..., description="The nature of the relationship.")
    context: Optional[str] = Field(default=None, description="The textual context from the document justifying this relationship.")

class KnowledgeGraphExtraction(BaseModel):
    """
    This is the master schema that we will pass to Instructor/OpenAI/Claude 
    to force them to return a strictly typed Knowledge Graph.
    """
    entities: List[Entity] = Field(..., description="List of all entities extracted from the text.")
    relationships: List[Relationship] = Field(..., description="List of all relationships connecting the extracted entities.")
