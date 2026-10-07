export type Role = "VIEWER" | "ANALYST" | "ADMIN";
export type Permission = "contracts:view" | "contracts:manage" | "contracts:import" | "users:manage" | "audit:read" | "alerts:manage" | "teams:manage";

export interface CurrentUser {
  id: string;
  email: string;
  name: string;
  role: Role;
  active: boolean;
  permissions?: Permission[];
}

export interface Sector {
  id: string;
  slug: string;
  name: string;
  acronym: string;
  active: boolean;
  contractCount: number;
  canEdit: boolean;
}

export type ContractCriticality = "BAIXA" | "MEDIA" | "ALTA";

export type ContractSituation = "Vigente" | "Vencido" | "Sem data" | "Finalizado";
export type RegularizationStage = "aguardando_analise" | "chamados_elos" | "analise_interna" | "fornecedor_contatado" | "em_tratativa" | "em_finalizacao";
export type ContractAlert = "Regularizacao" | "Regular" | "Atencao" | "Vencido" | "SemData" | "Finalizado";

export interface Contract {
  id: string;
  sectorId: string;
  sectorName: string;
  contractNumber: string;
  supplierId: string;
  supplier: string;
  serviceDescription: string;
  serviceValue: string | number;
  ownMaterialValue: string | number;
  thirdPartyMaterialValue: string | number;
  totalValue: string | number;
  startDate: string | null;
  endDate: string | null;
  unit: string;
  finalized: boolean;
  regularizationStage?: RegularizationStage | null;
  regularizationResponsible?: string | null;
  regularizationDeadline?: string | null;
  regularizationNotes?: string | null;
  regularizationHistory?: Array<{ date: string; user: string; previousStage: RegularizationStage | null; stage: RegularizationStage | null; responsible: string | null; deadline: string | null; notes: string | null }>;
  situation: ContractSituation;
  alert: ContractAlert;
  daysToEnd: number | null;
  source: string;
  notify: boolean;
  notifyEnabledOn: string | null;
  notificationTeamId: string | null;
  notificationTeamName: string | null;
  /** Membros ativos da equipe (cada um recebe o próprio e-mail). */
  notificationRecipients: string[];
  /** Por que não há destinatários (equipe ausente/inativa/sem membros), quando notify=true. */
  notificationProblem: string | null;
  /** Legado: não definem mais antecedência nem destinatário. */
  noticeDays: number;
  responsibleUserId: string | null;
  responsibleUserName: string | null;
  responsibleEmail: string | null;
  autoRenewal: boolean;
  criticality: ContractCriticality | null;
  canEdit: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface ContractUpdatePayload {
  regularizationStage?: RegularizationStage | null;
  regularizationResponsible?: string | null;
  regularizationDeadline?: string | null;
  regularizationNotes?: string | null;
  sectorId?: string;
  supplier?: string;
  serviceDescription?: string;
  serviceValue?: number;
  ownMaterialValue?: number;
  thirdPartyMaterialValue?: number;
  totalValue?: number;
  startDate?: string | null;
  endDate?: string | null;
  unit?: string;
  finalized?: boolean;
  notify?: boolean;
  notificationTeamId?: string | null;
  autoRenewal?: boolean;
  criticality?: ContractCriticality | null;
}

export interface ContractCreatePayload extends Omit<ContractUpdatePayload, "sectorId" | "supplier"> {
  sectorId: string;
  supplier: string;
  contractNumber: string;
}

export interface NotificationTeamMember {
  id: string;
  name: string | null;
  email: string;
  active: boolean;
}

export interface NotificationTeam {
  id: string;
  name: string;
  sectorId: string;
  sectorName: string;
  active: boolean;
  members: NotificationTeamMember[];
  activeMemberCount: number;
  contractCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface UserListItem {
  id: string;
  name: string;
  email: string;
  role: Role;
  active: boolean;
}

export interface UserSectorPermission {
  sectorId: string;
  sectorName: string;
  canView: boolean;
  canEdit: boolean;
}

export interface Responsible {
  id: string;
  name: string;
  email: string;
}

export type NotificationType = "ANTECEDENCIA" | "VENCIMENTO" | "VENCIDO";
export type NotificationStatus = "PENDING" | "SENT" | "FAILED" | "SKIPPED";

export interface ContractNotification {
  id: string;
  contractId: string;
  contractNumber: string;
  supplier: string;
  type: NotificationType;
  recipient: string;
  referenceDate: string;
  noticeDays: number;
  contractEndDate: string;
  status: NotificationStatus;
  attempts: number;
  provider: string | null;
  error: string | null;
  sentAt: string | null;
  lastAttemptAt: string | null;
  createdAt: string;
  updatedAt: string;
  canRetry: boolean;
}

export interface Pagination {
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
}

export interface ContractNotificationList {
  items: ContractNotification[];
  pagination: Pagination | null;
}

export type AlertAction = "would_send" | "would_retry" | "already_notified" | "sent" | "failed" | "skipped";

export interface AlertItem {
  action: AlertAction;
  retry: boolean;
  contractId: string;
  contractNumber: string;
  supplier: string;
  sectorName: string;
  unit: string;
  type: NotificationType;
  recipient: string | null;
  contractEndDate: string;
  referenceDate: string;
  noticeDays: number;
  daysToEnd: number;
  reason: string;
  autoRenewal: boolean;
  notificationId: string | null;
  attempts: number | null;
  error: string | null;
}

export interface AlertRun {
  today: string;
  dryRun: boolean;
  provider: string | null;
  contractsAnalyzed: number;
  eligible: number;
  sent: number;
  duplicates: number;
  retried: number;
  failed: number;
  skipped: number;
  items: AlertItem[];
}

export interface AttentionContract {
  contractId: string;
  contractNumber: string;
  supplier: string;
  sectorName: string;
  unit: string;
  alert: ContractAlert;
  endDate: string | null;
  daysToEnd: number | null;
  message: string;
  notify: boolean;
  lastNotification: { type: NotificationType; status: NotificationStatus; createdAt: string; sentAt: string | null } | null;
}

export interface AttentionList {
  items: AttentionContract[];
  total: number;
  overdue: number;
  attention: number;
  withoutDate: number;
}

export interface ApiProblem {
  detail?: string | Array<{ msg?: string }>;
  message?: string;
  error?: string;
  issues?: Array<{ msg?: string; loc?: unknown[] }>;
}

export interface SummaryGroup {
  key: string;
  label: string;
  total: number;
  regularization?: number;
  regular: number;
  atencao: number;
  vencido: number;
  finalizado: number;
  semData: number;
  totalValue: number;
}

export interface DeadlineBucket {
  key: "regularization" | "overdue" | "today" | "next7" | "next30" | "next60" | "next90" | "later" | "withoutDate";
  label: string;
  count: number;
}

export interface ContractSummary {
  today: string;
  periodStart: string | null;
  periodEnd: string | null;
  sectorId: string | null;
  unit: string | null;
  kpis: {
    regularizationWithDate?: number;
    total: number;
    regularization?: number;
  regular: number;
    atencao: number;
    vencido: number;
    finalizado: number;
    semData: number;
    active: number;
    onTime: number;
    onTimeBase: number;
    onTimePercent: number;
  };
  byStatus: Array<{ key: ContractAlert; label: string; count: number; percent: number; totalValue: number }>;
  bySector: SummaryGroup[];
  byUnit: SummaryGroup[];
  monthly: Array<{ month: string; label: string; expiring: number; overdue: number; finalized: number; regularization?: number; totalValue: number }>;
  deadlines: DeadlineBucket[];
  overdue: { count: number; averageDays: number; maxDays: number };
  values: { hasValues: boolean; total: number; active: number; overdue: number; attention: number };
}

/** Histórico real (não projetado) de `GET /contratos/vencidos-historico`, org-wide. */
export interface OverdueHistoryPoint {
  date: string;
  remaining: number;
  resolved: number;
}

export interface OverdueHistory {
  items: OverdueHistoryPoint[];
}

export interface EmailPreview {
  contractId: string;
  contractNumber: string;
  type: NotificationType;
  noticeDays: number;
  subject: string;
  html: string;
  text: string;
  teamName: string | null;
  recipients: string[];
  recipientsProblem: string | null;
  endDate: string;
  daysToEnd: number;
  illustrativeDate: boolean;
  actualDaysToEnd: number | null;
  notify: boolean;
}
