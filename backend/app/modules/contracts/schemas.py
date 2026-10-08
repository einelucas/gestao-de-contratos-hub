from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.models.contracts import ContractCriticality
from app.shared.schema import CamelModel

AuditStage = Literal[
    "AGUARDANDO_ANALISE",
    "CHAMADO_ELES",
    "ANALISE_INTERNA_INPASA",
    "FORNECEDOR_CONTATADO",
    "EM_TRATATIVA",
    "EM_FINALIZACAO",
    "FINALIZADO",
]


class SectorOut(CamelModel):
    id: str
    slug: str
    name: str
    acronym: str
    active: bool
    contract_count: int = 0
    can_edit: bool = False


class SectorListOut(CamelModel):
    items: list[SectorOut]


class SupplierOut(CamelModel):
    id: str
    name: str
    active: bool


class ContractOut(CamelModel):
    id: str
    sector_id: str
    sector_name: str
    contract_number: str
    supplier_id: str
    supplier: str
    service_description: str
    service_value: Decimal
    own_material_value: Decimal
    third_party_material_value: Decimal
    total_value: Decimal
    start_date: date | None
    end_date: date | None
    unit: str
    finalized: bool
    audit_stage: AuditStage | None
    situation: str
    alert: str
    days_to_end: int | None
    source: str
    notify: bool
    notify_enabled_on: date | None
    notification_team_id: str | None
    notification_team_name: str | None
    # Destinatários efetivos: membros ativos da equipe (vazio se não houver).
    notification_recipients: list[str]
    # Motivo de não haver destinatários (equipe ausente, inativa ou sem membros ativos).
    notification_problem: str | None
    # LEGADO (não definem mais antecedência nem destinatário dos alertas).
    notice_days: int
    responsible_user_id: str | None
    responsible_user_name: str | None
    responsible_email: str | None
    auto_renewal: bool
    criticality: ContractCriticality | None
    can_edit: bool
    created_at: datetime
    updated_at: datetime


class ContractListOut(CamelModel):
    items: list[ContractOut]
    total: int


class AuditBoardMoveIn(CamelModel):
    stage: AuditStage


class AuditBoardOut(CamelModel):
    items: list[ContractOut]
    units: list[str]


class SummaryKpisOut(CamelModel):
    total: int
    regular: int
    atencao: int
    vencido: int
    finalizado: int
    sem_data: int
    active: int
    on_time: int
    on_time_base: int
    on_time_percent: float


class StatusCountOut(CamelModel):
    key: str
    label: str
    count: int
    percent: float
    total_value: float


class SummaryGroupOut(CamelModel):
    key: str
    label: str
    total: int
    regular: int
    atencao: int
    vencido: int
    finalizado: int
    sem_data: int
    total_value: float


class SummaryMonthOut(CamelModel):
    month: str
    label: str
    expiring: int
    overdue: int
    finalized: int
    total_value: float


class DeadlineBucketOut(CamelModel):
    key: str
    label: str
    count: int


class OverdueStatsOut(CamelModel):
    count: int
    average_days: float
    max_days: int


class SummaryValuesOut(CamelModel):
    has_values: bool
    total: float
    active: float
    overdue: float
    attention: float


class ContractSummaryOut(CamelModel):
    today: date
    period_start: date | None
    period_end: date | None
    sector_id: str | None
    unit: str | None
    kpis: SummaryKpisOut
    by_status: list[StatusCountOut]
    by_sector: list[SummaryGroupOut]
    by_unit: list[SummaryGroupOut]
    monthly: list[SummaryMonthOut]
    deadlines: list[DeadlineBucketOut]
    overdue: OverdueStatsOut
    values: SummaryValuesOut


class OverdueHistoryPointOut(CamelModel):
    date: date
    remaining: int
    resolved: int


class OverdueHistoryOut(CamelModel):
    """Histórico real (não projetado) para o gráfico "Evolução da Regularização"
    do Dashboard — org-wide, igual para todo mundo com acesso ao Hub."""

    items: list[OverdueHistoryPointOut]


class ResponsibleOut(CamelModel):
    id: str
    name: str
    email: str


class ResponsibleListOut(CamelModel):
    items: list[ResponsibleOut]


class ContractCreateIn(CamelModel):
    sector_id: str
    supplier: str = Field(min_length=1)
    contract_number: str = Field(min_length=1)
    service_description: str = ""
    service_value: Decimal = Decimal("0")
    own_material_value: Decimal = Decimal("0")
    third_party_material_value: Decimal = Decimal("0")
    total_value: Decimal | None = None
    start_date: date | None = None
    end_date: date | None = None
    unit: str = ""
    finalized: bool = False
    notify: bool = False
    # Equipe de notificação do mesmo setor; obrigatória (com membros ativos) quando notify=true.
    notification_team_id: str | None = None
    auto_renewal: bool = False
    criticality: ContractCriticality | None = None

    @field_validator("contract_number", "supplier")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Campo obrigatório")
        return value


# Campos que não aceitam `null` explícito no PATCH (colunas NOT NULL).
_NON_NULLABLE_UPDATE_FIELDS = frozenset({"finalized", "notify", "auto_renewal", "sector_id", "supplier"})


class ContractUpdateIn(CamelModel):
    # Mudar o setor exige permissão de edição nos dois setores e uma equipe do novo setor.
    sector_id: str | None = None
    supplier: str | None = None
    service_description: str | None = None
    service_value: Decimal | None = None
    own_material_value: Decimal | None = None
    third_party_material_value: Decimal | None = None
    total_value: Decimal | None = None
    start_date: date | None = None
    end_date: date | None = None
    unit: str | None = None
    finalized: bool | None = None
    notify: bool | None = None
    # `null` explícito remove a equipe; campo ausente mantém a atual.
    notification_team_id: str | None = None
    auto_renewal: bool | None = None
    criticality: ContractCriticality | None = None

    @model_validator(mode="after")
    def _no_null_on_required(self) -> ContractUpdateIn:
        for name in _NON_NULLABLE_UPDATE_FIELDS & self.model_fields_set:
            if getattr(self, name) is None:
                raise ValueError(f"'{name}' não pode ser nulo")
        return self


class UserSectorPermissionIn(CamelModel):
    sector_id: str
    can_view: bool = True
    can_edit: bool = False


class UserSectorPermissionsIn(CamelModel):
    """Substitui o conjunto completo de setores do usuário."""

    items: list[UserSectorPermissionIn]

    @model_validator(mode="after")
    def _unique_sectors(self) -> UserSectorPermissionsIn:
        ids = [item.sector_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("Setor repetido na lista de permissões")
        return self


class UserSectorPermissionOut(CamelModel):
    sector_id: str
    sector_name: str
    can_view: bool
    can_edit: bool


class UserSectorPermissionsOut(CamelModel):
    user_id: str
    items: list[UserSectorPermissionOut]
