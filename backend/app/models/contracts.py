"""Modelos do domínio Gestão de Contratos."""

from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common import Timestamp3, utcnow, uuid_pk

if TYPE_CHECKING:
    from app.models.user import User


class ContractCriticality(str, enum.Enum):
    BAIXA = "BAIXA"
    MEDIA = "MEDIA"
    ALTA = "ALTA"


class ContractNotificationType(str, enum.Enum):
    ANTECEDENCIA = "ANTECEDENCIA"
    VENCIMENTO = "VENCIMENTO"
    VENCIDO = "VENCIDO"


class ContractNotificationStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


ContractCriticalityEnum = PGEnum(ContractCriticality, name="ContractCriticality", create_type=False)
ContractNotificationTypeEnum = PGEnum(
    ContractNotificationType, name="ContractNotificationType", create_type=False
)
ContractNotificationStatusEnum = PGEnum(
    ContractNotificationStatus, name="ContractNotificationStatus", create_type=False
)

DEFAULT_NOTICE_DAYS = 20
# `noticeDays` gravado em ContractNotification para tipos em que a antecedência
# não se aplica (VENCIMENTO, VENCIDO). Contratos só aceitam noticeDays >= 1,
# então 0 nunca colide com uma antecedência real na chave de deduplicação.
NOTICE_DAYS_NOT_APPLICABLE = 0


class Sector(Base):
    __tablename__ = "Sector"

    id: Mapped[str] = uuid_pk()
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    acronym: Mapped[str] = mapped_column(String(24), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    createdAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updatedAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow, onupdate=utcnow)

    contracts: Mapped[list[Contract]] = relationship(back_populates="sector")

    __table_args__ = (
        Index("Sector_slug_key", "slug", unique=True),
        Index("Sector_active_idx", "active"),
    )


class Supplier(Base):
    __tablename__ = "Supplier"

    id: Mapped[str] = uuid_pk()
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    createdAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updatedAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow, onupdate=utcnow)

    contracts: Mapped[list[Contract]] = relationship(back_populates="supplier")

    __table_args__ = (Index("Supplier_name_key", "name", unique=True),)


class Contract(Base):
    __tablename__ = "Contract"

    id: Mapped[str] = uuid_pk()
    sectorId: Mapped[str] = mapped_column(
        String, ForeignKey("Sector.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False
    )
    supplierId: Mapped[str] = mapped_column(
        String, ForeignKey("Supplier.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False
    )
    contractNumber: Mapped[str] = mapped_column(String(80), nullable=False)
    serviceDescription: Mapped[str] = mapped_column(Text, nullable=False, default="")
    serviceValue: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, default=Decimal("0"))
    ownMaterialValue: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, default=Decimal("0"))
    thirdPartyMaterialValue: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), nullable=False, default=Decimal("0")
    )
    totalValue: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, default=Decimal("0"))
    startDate: Mapped[date | None] = mapped_column(Date, nullable=True)
    endDate: Mapped[date | None] = mapped_column(Date, nullable=True)
    unit: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    finalized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False, default="manual")
    # Alertas de vencimento por e-mail: régua fixa 45/20/1/0 dias enviada aos
    # membros ativos da equipe `notificationTeamId`. O status visual (Atenção)
    # segue ATTENTION_DAYS, independente dos e-mails.
    notify: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notificationTeamId: Mapped[str | None] = mapped_column(
        String, ForeignKey("NotificationTeam.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True
    )
    # Dia (America/Sao_Paulo) em que `notify` foi ligado: marcos anteriores a ele
    # não são recuperados (ativação tardia ≠ job fora do ar).
    notifyEnabledOn: Mapped[date | None] = mapped_column(Date, nullable=True)
    # LEGADO (Etapas 1–5): não definem mais antecedência nem destinatário dos alertas.
    noticeDays: Mapped[int] = mapped_column(Integer, nullable=False, default=DEFAULT_NOTICE_DAYS)
    responsibleUserId: Mapped[str | None] = mapped_column(
        String, ForeignKey("User.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True
    )
    responsibleEmail: Mapped[str | None] = mapped_column(String(320), nullable=True)
    autoRenewal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    criticality: Mapped[ContractCriticality | None] = mapped_column(ContractCriticalityEnum, nullable=True)
    createdAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updatedAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow, onupdate=utcnow)

    sector: Mapped[Sector] = relationship(back_populates="contracts")
    supplier: Mapped[Supplier] = relationship(back_populates="contracts")
    responsibleUser: Mapped[User | None] = relationship("User")
    notificationTeam: Mapped[NotificationTeam | None] = relationship("NotificationTeam")

    __table_args__ = (
        UniqueConstraint("sectorId", "contractNumber", name="Contract_sectorId_contractNumber_key"),
        CheckConstraint('"noticeDays" BETWEEN 1 AND 365', name="Contract_noticeDays_check"),
        Index("Contract_sectorId_idx", "sectorId"),
        Index("Contract_supplierId_idx", "supplierId"),
        Index("Contract_endDate_idx", "endDate"),
        Index("Contract_unit_idx", "unit"),
        Index("Contract_responsibleUserId_idx", "responsibleUserId"),
        Index("Contract_notify_endDate_idx", "notify", "endDate"),
        Index("Contract_notificationTeamId_idx", "notificationTeamId"),
    )


class NotificationTeam(Base):
    """Equipe de notificação de um setor: destinatários dos alertas dos contratos.

    Equipes não são excluídas (o histórico de envios as referencia); desative-as.
    """

    __tablename__ = "NotificationTeam"

    id: Mapped[str] = uuid_pk()
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    sectorId: Mapped[str] = mapped_column(
        String, ForeignKey("Sector.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    createdAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updatedAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow, onupdate=utcnow)

    sector: Mapped[Sector] = relationship("Sector")
    members: Mapped[list[NotificationTeamMember]] = relationship(
        back_populates="team", cascade="all, delete-orphan", order_by="NotificationTeamMember.email"
    )

    __table_args__ = (
        Index("NotificationTeam_sectorId_name_key", "sectorId", "name", unique=True),
        Index("NotificationTeam_sectorId_idx", "sectorId"),
    )


class NotificationTeamMember(Base):
    __tablename__ = "NotificationTeamMember"

    id: Mapped[str] = uuid_pk()
    teamId: Mapped[str] = mapped_column(
        String, ForeignKey("NotificationTeam.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    # Sempre normalizado (minúsculas, sem espaços) pela aplicação.
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    createdAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updatedAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow, onupdate=utcnow)

    team: Mapped[NotificationTeam] = relationship(back_populates="members")

    __table_args__ = (
        Index("NotificationTeamMember_teamId_email_key", "teamId", "email", unique=True),
        Index("NotificationTeamMember_teamId_idx", "teamId"),
    )


class ContractNotification(Base):
    """Histórico e deduplicação dos alertas de vencimento por e-mail.

    Uma linha por (contrato, tipo, data de referência, antecedência,
    destinatário). O índice único é o que garante que o mesmo alerta nunca
    seja enviado duas vezes, mesmo que o job rode de novo no mesmo dia.
    `referenceDate` é o fim de vigência para ANTECEDENCIA/VENCIMENTO e a data
    do marco semanal para VENCIDO; como deriva do fim de vigência, uma
    renovação (novo `endDate`) abre um ciclo novo de alertas sozinha.
    """

    __tablename__ = "ContractNotification"

    id: Mapped[str] = uuid_pk()
    contractId: Mapped[str] = mapped_column(
        String, ForeignKey("Contract.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    type: Mapped[ContractNotificationType] = mapped_column(ContractNotificationTypeEnum, nullable=False)
    recipient: Mapped[str] = mapped_column(String(320), nullable=False)
    referenceDate: Mapped[date] = mapped_column(Date, nullable=False)
    noticeDays: Mapped[int] = mapped_column(Integer, nullable=False, default=NOTICE_DAYS_NOT_APPLICABLE)
    # Fim de vigência no momento em que o alerta foi gerado (retrato do ciclo).
    contractEndDate: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[ContractNotificationStatus] = mapped_column(
        ContractNotificationStatusEnum, nullable=False, default=ContractNotificationStatus.PENDING
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Adapter da última tentativa ("log" não envia e-mail de verdade; "graph" envia).
    provider: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Equipe de onde veio o destinatário (retrato do envio; a equipe do contrato pode mudar depois).
    notificationTeamId: Mapped[str | None] = mapped_column(
        String, ForeignKey("NotificationTeam.id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sentAt: Mapped[datetime | None] = mapped_column(Timestamp3, nullable=True)
    lastAttemptAt: Mapped[datetime | None] = mapped_column(Timestamp3, nullable=True)
    createdAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updatedAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow, onupdate=utcnow)

    contract: Mapped[Contract] = relationship("Contract")

    __table_args__ = (
        Index(
            "ContractNotification_dedup_key",
            "contractId",
            "type",
            "referenceDate",
            "noticeDays",
            "recipient",
            unique=True,
        ),
        Index("ContractNotification_contractId_idx", "contractId"),
        Index("ContractNotification_status_attempts_idx", "status", "attempts"),
        Index("ContractNotification_createdAt_idx", "createdAt"),
    )


class UserSectorPermission(Base):
    """Acesso por setor para VIEWER/ANALYST (ADMIN consulta e edita todos).

    `canView` libera consulta; `canEdit` libera criação/edição para quem tem
    perfil de edição (ANALYST) e também implica consulta.
    """

    __tablename__ = "UserSectorPermission"

    id: Mapped[str] = uuid_pk()
    userId: Mapped[str] = mapped_column(
        String, ForeignKey("User.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    sectorId: Mapped[str] = mapped_column(
        String, ForeignKey("Sector.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    canView: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    canEdit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    createdAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updatedAt: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        UniqueConstraint("userId", "sectorId", name="UserSectorPermission_userId_sectorId_key"),
        Index("UserSectorPermission_userId_idx", "userId"),
        Index("UserSectorPermission_sectorId_idx", "sectorId"),
    )
