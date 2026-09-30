import type { AlertAction, ContractCriticality, NotificationStatus, NotificationType } from "~/types/api";

export const NOTIFICATION_TYPE_LABEL: Record<NotificationType, string> = {
  ANTECEDENCIA: "Antecedência",
  VENCIMENTO: "Vencimento",
  VENCIDO: "Vencido",
};

export const NOTIFICATION_STATUS_LABEL: Record<NotificationStatus, string> = {
  PENDING: "Enviando",
  SENT: "Enviado",
  FAILED: "Falhou",
  SKIPPED: "Ignorado",
};

export const ALERT_ACTION_LABEL: Record<AlertAction, string> = {
  would_send: "Seria enviado",
  would_retry: "Seria reenviado",
  already_notified: "Já notificado",
  sent: "Enviado",
  failed: "Falhou",
  skipped: "Ignorado",
};

export const CRITICALITY_LABEL: Record<ContractCriticality, string> = {
  BAIXA: "Baixa",
  MEDIA: "Média",
  ALTA: "Alta",
};

export const PROVIDER_LABEL: Record<string, string> = {
  graph: "E-mail (Microsoft Graph)",
  mailpit: "Homologação local (Mailpit, não entregue)",
  log: "Somente registro (sem e-mail)",
};

/** Classe CSS do selo de status de envio. */
export function notificationStatusTone(status: NotificationStatus): string {
  return {
    PENDING: "tone-info",
    SENT: "tone-success",
    FAILED: "tone-danger",
    SKIPPED: "tone-muted",
  }[status];
}

export function alertActionTone(action: AlertAction): string {
  return {
    would_send: "tone-info",
    would_retry: "tone-warning",
    already_notified: "tone-muted",
    sent: "tone-success",
    failed: "tone-danger",
    skipped: "tone-muted",
  }[action];
}

export const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

/** Régua fixa de lembretes (backend: eligibility.MILESTONES). */
export const REMINDER_SCHEDULE = ["45 dias antes", "20 dias antes", "1 dia antes", "No dia do vencimento"] as const;

/** Rótulo do marco: "45 dias antes", "1 dia antes", "Vencimento", "Vencido". */
export function milestoneLabel(type: NotificationType, noticeDays: number): string {
  if (type === "ANTECEDENCIA") return noticeDays === 1 ? "1 dia antes" : `${noticeDays} dias antes`;
  return NOTIFICATION_TYPE_LABEL[type];
}
