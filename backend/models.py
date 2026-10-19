from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class Evidence(BaseModel):
    model_config = ConfigDict(extra='forbid')
    value: str | None = None
    quote: str = ''
    location: str = ''

class Item(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: Evidence = Field(default_factory=Evidence)
    model: Evidence = Field(default_factory=Evidence)
    quantity: Evidence = Field(default_factory=Evidence)
    unit: Evidence = Field(default_factory=Evidence)
    price: Evidence = Field(default_factory=Evidence)
    amount: Evidence = Field(default_factory=Evidence)

class Extraction(BaseModel):
    model_config = ConfigDict(extra='forbid')
    buyer: Evidence = Field(default_factory=Evidence)
    supplier: Evidence = Field(default_factory=Evidence)
    subject: Evidence = Field(default_factory=Evidence)
    total: Evidence = Field(default_factory=Evidence)
    currency: Evidence = Field(default_factory=Evidence)
    tax: Evidence = Field(default_factory=Evidence)
    delivery: Evidence = Field(default_factory=Evidence)
    items: list[Item] = Field(default_factory=list, max_length=30)

class NewTask(BaseModel):
    name: str = Field(min_length=1, max_length=100)

class Review(BaseModel):
    status: Literal['待处理', '已确认', '误报']
    note: str = Field(default='', max_length=2000)

class AICitation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    document_id: str
    quote: str = Field(min_length=1,max_length=1200)
    location: str = Field(min_length=1,max_length=100)

class AIFinding(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1,max_length=120)
    category: Literal['交付语义','规格描述','验收要求','付款条件','范围遗漏','其他待复核']
    severity: Literal['高','中','低']
    explanation: str = Field(min_length=1,max_length=1600)
    suggestion: str = Field(min_length=1,max_length=800)
    evidence: list[AICitation] = Field(min_length=1,max_length=8)
    related_issue_ids: list[str] = Field(default_factory=list,max_length=20)

class AIAnalysis(BaseModel):
    model_config = ConfigDict(extra='forbid')
    summary: str = Field(min_length=1,max_length=1600)
    summary_evidence: list[AICitation] = Field(min_length=1,max_length=8)
    findings: list[AIFinding] = Field(max_length=12)
    limitations: list[str] = Field(min_length=1,max_length=8)
