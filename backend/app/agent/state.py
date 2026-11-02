"""
Agent State and Pydantic Data Contracts for Conversational BI.
Defines schemas for QueryPlan, AgentResponse, and LangGraph AgentState.
"""

from typing import List, Dict, Any, Optional, Literal
from typing_extensions import TypedDict
from pydantic import BaseModel, Field


class FilterItem(BaseModel):
    field: str
    operator: str = "=" # '=', '!=', 'IN', 'LIKE', '>=', '<='
    value: Any


class QueryPlan(BaseModel):
    intent: Literal["metric_query", "ranking", "comparison", "breakdown", "trend", "anomaly", "exploratory", "llm_generated", "clarification_reply", "tiering", "out_of_scope"] = "metric_query"
    metrics: List[str] = Field(default_factory=list, description="List of metric names: gmv, revenue, cogs, margin, cancel_rate, order_count")
    dimensions: List[str] = Field(default_factory=list, description="Dimensions to group by: store_region, store_city, channel, product_category, product_name, customer_segment, order_date")
    filters: List[FilterItem] = Field(default_factory=list)
    time_window_label: str = "MTD"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    sort_by: Optional[str] = None
    sort_direction: Literal["ASC", "DESC"] = "DESC"
    limit: Optional[int] = None
    is_follow_up: bool = False
    inherited_fields: List[str] = Field(default_factory=list)
    standalone_query: Optional[str] = None
    specialist_agent: str = "AnalyticalSQLSpecialist"
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    clarification_options: List[Dict[str, str]] = Field(default_factory=list)


class KPICard(BaseModel):
    label: str
    value: Any
    format: Literal["currency_idr", "percentage", "number", "text"] = "currency_idr"
    subtitle: Optional[str] = None


class TableData(BaseModel):
    columns: List[Dict[str, str]] = Field(default_factory=list)
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    truncated: bool = False


class ChartConfig(BaseModel):
    type: Literal["bar", "line", "pie", "kpi", "none"] = "none"
    x_axis: Optional[str] = None
    y_axes: List[str] = Field(default_factory=list)
    title: Optional[str] = None


class ClarificationPayload(BaseModel):
    question: str
    options: List[Dict[str, str]] = Field(default_factory=list) # [{'label': '...', 'value': '...'}]


class AgentResponse(BaseModel):
    type: Literal["answer", "clarification", "refusal", "error"] = "answer"
    language: str = "id"
    summary: str
    kpis: List[KPICard] = Field(default_factory=list)
    table: Optional[TableData] = None
    chart: Optional[ChartConfig] = None
    insights: List[str] = Field(default_factory=list, description="2-5 analytical bullet points")
    recommendations: List[str] = Field(default_factory=list, description="Prescriptive business recommendations for leadership")
    sql: Optional[str] = None
    assumptions: List[str] = Field(default_factory=list)
    clarification: Optional[ClarificationPayload] = None
    trace: Dict[str, Any] = Field(default_factory=dict)


class AgentState(TypedDict, total=False):
    # Session identifiers
    session_id: str
    trace_id: str
    user_message: str
    language: str
    llm_provider: Optional[str]
    model_name: Optional[str]
    
    # State tracking across turns
    history: List[Dict[str, str]]
    prev_plan: Optional[Dict[str, Any]]
    prev_result_digest: Optional[Dict[str, Any]] # e.g. {"top_city": "Surabaya"}
    
    # Current turn flow
    plan: Optional[QueryPlan]
    few_shots: List[Dict[str, Any]]
    raw_sql: Optional[str]
    validated_sql: Optional[str]
    sql_errors: List[str]
    retry_count: int
    query_result: Optional[Dict[str, Any]]
    facts: Dict[str, Any] # Deterministic calculations for grounding
    final_response: Optional[AgentResponse]
    current_step: str
