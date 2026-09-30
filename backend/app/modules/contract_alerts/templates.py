"""Assunto, texto simples e HTML corporativo dos alertas de vencimento.

HTML em tabelas com CSS inline (o que o Outlook renderiza de forma confiável),
na paleta do Hub. Todo valor vindo do banco passa por `html.escape`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from html import escape

_NAVY = "#213758"
_MUTED = "#6b7688"
_BORDER = "#e3e8f0"

# tipo -> (rótulo, cor do selo, fundo do selo)
_TYPE_STYLE = {
    "ANTECEDENCIA": ("Vencimento próximo", "#1f5fa8", "#e8f1fb"),
    "VENCIMENTO": ("Vence hoje", "#9a5b00", "#fff4e0"),
    "VENCIDO": ("Contrato vencido", "#b42318", "#fdecea"),
}
_CRITICALITY_LABEL = {"BAIXA": "Baixa", "MEDIA": "Média", "ALTA": "Alta"}


@dataclass(frozen=True, slots=True)
class RenderedAlert:
    subject: str
    text: str
    html: str


def headline(alert_type: str, days: int) -> str:
    if alert_type == "ANTECEDENCIA":
        return "vence amanhã" if days == 1 else f"vence em {days} dias"
    if alert_type == "VENCIMENTO":
        return "vence hoje"
    return "está vencido há 1 dia" if days == -1 else f"está vencido há {abs(days)} dias"


def render_alert(
    *,
    alert_type: str,
    contract_number: str,
    supplier: str,
    service_description: str,
    sector: str,
    unit: str,
    end_date: date,
    days: int,
    auto_renewal: bool,
    criticality: str | None,
    contract_url: str | None,
) -> RenderedAlert:
    title = headline(alert_type, days)
    # Assunto por marco: "vence em 45/20 dias", "vence amanhã", "vence hoje", "está vencido há N dias".
    subject = f"Contrato {contract_number} {title}"
    end_br = end_date.strftime("%d/%m/%Y")
    criticality_label = _CRITICALITY_LABEL.get(criticality or "", "")

    rows = [
        ("Contrato", contract_number),
        ("Fornecedor", supplier),
        ("Objeto", service_description or "—"),
        ("Setor", sector),
        ("Unidade", unit or "—"),
        ("Fim da vigência", end_br),
    ]
    if criticality_label:
        rows.append(("Criticidade", criticality_label))

    text_lines = [f"O contrato {contract_number} ({supplier}) {title}.", ""]
    text_lines += [f"{label}: {value}" for label, value in rows]
    if auto_renewal:
        text_lines += ["", "Este contrato possui renovação automática."]
    if contract_url:
        text_lines += ["", f"Abrir no Hub: {contract_url}"]
    text_lines += [
        "",
        "Você recebe este aviso por fazer parte da equipe de notificação deste contrato no Hub.",
        "Mensagem automática — não responda.",
    ]

    label, color, background = _TYPE_STYLE.get(alert_type, ("Alerta de contrato", _NAVY, "#eef2f7"))
    detail_rows = "".join(
        f'<tr><td style="padding:8px 0;color:{_MUTED};font-size:13px;width:150px;vertical-align:top">'
        f"{escape(row_label)}</td>"
        f'<td style="padding:8px 0;color:{_NAVY};font-size:14px;font-weight:600">{escape(value)}</td></tr>'
        for row_label, value in rows
    )
    renewal_box = (
        '<tr><td style="padding:0 32px 8px">'
        '<div style="background:#eef7ea;border-left:4px solid #609346;padding:12px 14px;'
        'color:#2f5a1f;font-size:14px;font-weight:600">'
        "Este contrato possui renovação automática."
        "</div></td></tr>"
        if auto_renewal
        else ""
    )
    button = (
        '<tr><td style="padding:8px 32px 24px">'
        f'<a href="{escape(contract_url, quote=True)}" '
        f'style="display:inline-block;background:{_NAVY};color:#ffffff;text-decoration:none;'
        'padding:11px 20px;border-radius:8px;font-size:14px;font-weight:700">Abrir no Hub</a>'
        "</td></tr>"
        if contract_url
        else ""
    )

    html = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><title>{escape(subject)}</title></head>
<body style="margin:0;padding:0;background:#f4f5f7;font-family:Segoe UI,Arial,sans-serif">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
 style="background:#f4f5f7;padding:24px 0">
<tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0"
 style="max-width:600px;width:100%;background:#ffffff;border:1px solid {_BORDER};border-radius:12px">
<tr><td style="background:{_NAVY};padding:18px 32px;border-radius:12px 12px 0 0;color:#ffffff;
 font-size:13px;font-weight:700;letter-spacing:.08em;text-transform:uppercase">
Gestão de Contratos · Hub</td></tr>
<tr><td style="padding:28px 32px 8px">
<span style="display:inline-block;background:{background};color:{color};font-size:12px;font-weight:700;
 padding:5px 10px;border-radius:999px">{escape(label)}</span>
<h1 style="margin:14px 0 4px;color:{_NAVY};font-size:22px;line-height:1.3">
Contrato {escape(contract_number)} {escape(title)}</h1>
<p style="margin:0;color:{_MUTED};font-size:14px">{escape(supplier)}</p>
</td></tr>
<tr><td style="padding:16px 32px 16px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
 style="border-top:1px solid {_BORDER};border-bottom:1px solid {_BORDER}">{detail_rows}</table>
</td></tr>
{renewal_box}
{button}
<tr><td style="padding:16px 32px 24px;color:{_MUTED};font-size:12px;line-height:1.5;
 border-top:1px solid {_BORDER}">
Você recebe este aviso por fazer parte da equipe de notificação deste contrato no Hub.<br>
Mensagem automática — não responda.</td></tr>
</table></td></tr></table></body></html>"""

    return RenderedAlert(subject=subject, text="\n".join(text_lines), html=html)
