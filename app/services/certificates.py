"""Certificados inmutables por huella, QR público y firma PDF opcional PAdES.

La aprobación electrónica interna NO equivale a una firma digital acreditada.
La firma criptográfica requiere PKCS#12 real de titular autorizado.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import html
import json
import os

import qrcode
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether,
)


BLUE = colors.HexColor('#071b33')
TEAL = colors.HexColor('#009d93')
MUTED = colors.HexColor('#576779')
PALE = colors.HexColor('#e8f6f4')


def load_certificate(did):
    from app.models.database import query
    row = query("""
        SELECT d.*, e.codigo equipo_codigo, e.descripcion equipo_desc,
               e.fabricante, e.modelo, e.serie, e.rango, e.resolucion, e.tolerancia,
               e.ubicacion, e.magnitud equipo_magnitud,
               c.nombre cliente_nombre, c.ruc cliente_ruc, c.email cliente_email,
               u.nombre tecnico_nombre, u.email tecnico_email,
               p.codigo patron_codigo, p.descripcion patron_desc,
               p.n_certificado patron_cert, p.trazabilidad patron_trazabilidad,
               p.incertidumbre patron_incert, p.vencimiento patron_vencimiento,
               a.nombre aprobador_nombre, a.email aprobador_email
        FROM diagnosticos d JOIN equipos e ON e.id=d.equipo_id
        LEFT JOIN clientes c ON c.id=e.cliente_id
        JOIN usuarios u ON u.id=d.tecnico_id
        LEFT JOIN patrones p ON p.id=d.patron_id
        LEFT JOIN usuarios a ON a.id=d.aprobado_por
        WHERE d.id=?
    """, (did,), one=True)
    return dict(row) if row else None


def certificate_snapshot(diag, upload_folder):
    """Incluye datos metrológicos, lecturas, fotos (bytes) y metadatos del equipo.

    No incluye campos variables de auditoría/envío/firma/aprobación para evitar
    invalidación espuria del PDF al registrar correos.
    """
    from app.models.database import query, rows_to_list
    included = (
        'id', 'n_certificado', 'equipo_id', 'patron_id', 'tecnico_id',
        'procedimiento', 'magnitud', 'unidad', 'resultado', 'dictamen',
        'estado_visual', 'observaciones', 'temp_inicio', 'temp_fin',
        'humedad_inicio', 'humedad_fin', 'presion_atm', 'fecha_inicio',
        'fecha_fin', 'prox_calibracion', 'equipo_codigo', 'equipo_desc',
        'fabricante', 'modelo', 'serie', 'rango', 'resolucion', 'tolerancia',
        'ubicacion', 'equipo_magnitud', 'cliente_nombre', 'cliente_ruc',
        'tecnico_nombre', 'tecnico_email', 'patron_codigo', 'patron_desc',
        'patron_cert', 'patron_trazabilidad', 'patron_incert',
        'patron_vencimiento',
    )
    lecturas = rows_to_list(query(
        """SELECT ciclo,punto,valor_nominal,porcentaje_rango,lectura_ebp,
                  lectura_patron,desviacion,error_pct,incertidumbre
           FROM lecturas WHERE diagnostico_id=? ORDER BY ciclo,punto,id""", (diag['id'],)))
    fotos = rows_to_list(query(
        "SELECT id,filename,label,tipo FROM fotos WHERE diagnostico_id=? ORDER BY id", (diag['id'],)))
    images = []
    for photo in fotos:
        # Si falta la foto, la comprobación deja de coincidir con la versión aprobada.
        path = os.path.join(upload_folder, os.path.basename(photo['filename']))
        if not os.path.isfile(path):
            raise ValueError('Falta una fotografía asociada al expediente.')
        with open(path, 'rb') as img_file:
            img_hash = sha256(img_file.read()).hexdigest()
        images.append({'id': photo['id'], 'label': photo['label'],
                       'tipo': photo['tipo'], 'sha256': img_hash})
    payload = {'datos': {k: diag.get(k) for k in included}, 'lecturas': lecturas, 'fotos': images}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return sha256(encoded).hexdigest(), lecturas


def status(diag, upload_folder):
    """La huella del expediente debe seguir intacta tras la aprobación."""
    if not diag or diag.get('estado_aprobacion') != 'aprobado':
        return False, 'El documento aún no está aprobado.'
    try:
        digest, _ = certificate_snapshot(diag, upload_folder)
    except (OSError, ValueError):
        return False, 'El expediente está incompleto: faltan archivos relacionados.'
    if digest != diag.get('huella_aprobada'):
        return False, 'Los datos cambiaron después de la aprobación. Documento bloqueado.'
    return True, 'Certificado aprobado; expediente sin modificaciones.'


def _clean(value):
    return html.escape('—' if value is None or value == '' else str(value), quote=True)


def build_pdf(diag, lecturas, verify_url, *, signed_label=False):
    """Genera PDF verdadero en memoria, con QR de verificación en cada certificado."""
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=17*mm, rightMargin=17*mm,
                            topMargin=14*mm, bottomMargin=12*mm, title=f"Certificado {diag['n_certificado']}",
                            author='Tatronics Perú · CalibPro')
    h1 = ParagraphStyle('Title', fontName='Helvetica-Bold', fontSize=17, leading=22, textColor=BLUE)
    body = ParagraphStyle('Body', fontName='Helvetica', fontSize=9, leading=13, textColor=BLUE)
    small = ParagraphStyle('Small', parent=body, fontSize=8, leading=11)
    muted = ParagraphStyle('Muted', parent=small, textColor=MUTED)
    section = ParagraphStyle('Section', parent=body, fontName='Helvetica-Bold', fontSize=10.2,
                             spaceBefore=10, spaceAfter=5, textColor=TEAL)
    headcell = ParagraphStyle('HeadCell', parent=small, fontName='Helvetica-Bold', textColor=colors.white)
    cell = ParagraphStyle('Cell', parent=small)
    story = []
    brand = Paragraph('<b>TATRONICS</b> <font color="#009d93">PERÚ</font><br/><font size="8">Metrología, calibración y servicios técnicos</font>', body)
    head = Table([[brand, Paragraph('CERTIFICADO DE CALIBRACIÓN', h1)]], colWidths=[75*mm, 100*mm])
    head.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'), ('LINEBELOW',(0,0),(-1,-1),2,TEAL),
                              ('BOTTOMPADDING',(0,0),(-1,-1),9)]))
    story.extend([head, Spacer(1,9), Paragraph(f"<b>N.° {_clean(diag.get('n_certificado'))}</b> &nbsp;&nbsp; | &nbsp;&nbsp; Fecha: {_clean((diag.get('fecha_fin') or diag.get('aprobado_en') or '')[:10])}", body)])

    def detail(title, items):
        story.append(Paragraph(title, section))
        rows = []
        for i in range(0, len(items), 2):
            pair = items[i:i+2]
            cells = [Paragraph(f'<font color="#576779">{_clean(k)}:</font><br/><b>{_clean(v)}</b>', body) for k,v in pair]
            if len(cells)==1: cells.append(Paragraph('',body))
            rows.append(cells)
        table = Table(rows, colWidths=[87*mm,87*mm], hAlign='LEFT')
        table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('ROWBACKGROUNDS',(0,0),(-1,-1),[colors.white,colors.HexColor('#f5f9fa')]),
                                   ('TOPPADDING',(0,0),(-1,-1),4), ('BOTTOMPADDING',(0,0),(-1,-1),4)]))
        story.append(table)

    detail('01 / IDENTIFICACIÓN DEL INSTRUMENTO', [
        ('Cliente', diag.get('cliente_nombre')), ('RUC', diag.get('cliente_ruc')),
        ('Equipo', diag.get('equipo_desc')), ('Código', diag.get('equipo_codigo')),
        ('Fabricante / modelo', f"{diag.get('fabricante') or ''} / {diag.get('modelo') or ''}"),
        ('Serie', diag.get('serie')), ('Rango',diag.get('rango')), ('Resolución',diag.get('resolucion')),
    ])
    detail('02 / TRAZABILIDAD Y CONDICIONES', [
        ('Procedimiento', diag.get('procedimiento')), ('Magnitud / unidad', f"{diag.get('magnitud') or ''} / {diag.get('unidad') or ''}"),
        ('Patrón', diag.get('patron_codigo')), ('Certificado de patrón',diag.get('patron_cert')),
        ('Temperatura inicio / fin', f"{diag.get('temp_inicio')} / {diag.get('temp_fin')} °C"),
        ('Humedad inicio / fin', f"{diag.get('humedad_inicio')} / {diag.get('humedad_fin')} %"),
    ])
    story.append(Paragraph('03 / RESULTADOS DE MEDICIÓN', section))
    headers = ['Ciclo','Punto','Nominal','EBP','Patrón','Error %','U']
    table_data = [[Paragraph(_clean(s),headcell) for s in headers]]
    def fmt(v):
        return f'{v:.6g}' if isinstance(v, float) else v
    for reading in lecturas:
        table_data.append([Paragraph(_clean(fmt(reading.get(k))),cell) for k in (
            'ciclo','punto','valor_nominal','lectura_ebp','lectura_patron','error_pct','incertidumbre')])
    if len(table_data)==1:
        table_data.append([Paragraph('Sin lecturas registradas',cell)] + ['']*6)
    tbl = Table(table_data, colWidths=[15*mm,16*mm,26*mm,27*mm,27*mm,30*mm,33*mm],repeatRows=1,hAlign='LEFT')
    tbl.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),BLUE),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f5f9fa')]),
                             ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('BOTTOMPADDING',(0,0),(-1,-1),4),('TOPPADDING',(0,0),(-1,-1),4)]))
    story.append(tbl)
    approval_section_title = Paragraph('04 / RESULTADO, REVISIÓN Y APROBACIÓN', section)
    box = Table([[Paragraph(f"<b>RESULTADO: {_clean(str(diag.get('resultado') or '').upper())}</b><br/>Dictamen: {_clean(diag.get('dictamen'))}",body)]], colWidths=[174*mm])
    box.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),PALE),('BOX',(0,0),(-1,-1),0.6,TEAL),
                             ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
    story.append(KeepTogether([approval_section_title, box, Spacer(1,7), Paragraph(f"Observaciones: {_clean(diag.get('observaciones'))}",small)]))
    qr_img = qrcode.make(verify_url).convert('RGB')
    img_io=BytesIO(); qr_img.save(img_io,format='PNG'); img_io.seek(0)
    qr=Image(img_io,width=26*mm,height=26*mm)
    qr.hAlign='CENTER'
    approve = Paragraph(
        f"<b>Responsable técnico:</b> {_clean(diag.get('tecnico_nombre'))}<br/>"
        f"<b>Aprobación electrónica:</b> {_clean(diag.get('aprobador_nombre'))}<br/>"
        f"<b>Fecha de aprobación:</b> {_clean(diag.get('aprobado_en'))} (UTC)<br/>"
        f"<b>Modalidad:</b> {('Firma criptográfica PDF incluida' if signed_label else 'Aprobación interna registrada')}<br/>"
        f"<font color=\"#576779\">El código QR permite consultar el estado del expediente aprobado.</font>",small)
    foot = Table([[approve,qr]],colWidths=[139*mm,35*mm]); foot.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),4)]))
    story.extend([Spacer(1,4),foot,Paragraph(f"Verificación pública: {_clean(verify_url)}",muted),
                  Spacer(1,10),Paragraph('Documento emitido a partir del expediente electrónico de CalibPro. '
                  'No constituye por sí solo una declaración de acreditación de laboratorio.',muted)])

    def page_footer(canvas, doc):
        canvas.setFont('Helvetica',8)
        canvas.setFillColor(MUTED)
        canvas.drawString(17*mm,11*mm,'Tatronics Perú  |  Sistema CalibPro')
        canvas.drawRightString(A4[0]-17*mm,11*mm,f'Página {doc.page}')
    doc.build(story,onFirstPage=page_footer,onLaterPages=page_footer)
    return buf.getvalue()


def sign_pdf_if_configured(pdf_bytes, *, p12_path='', p12_password=''):
    """Agrega firma CMS embebida mediante P12, sin falsificar certificado digital."""
    if not p12_path:
        return pdf_bytes
    if not os.path.isfile(p12_path):
        raise RuntimeError('No se encontró el certificado PKCS#12 configurado.')
    try:
        from pyhanko.sign import signers
        from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    except ImportError as exc:
        raise RuntimeError('Instala pyHanko para la firma digital PAdES.') from exc
    signer = signers.SimpleSigner.load_pkcs12(
        pfx_file=p12_path, passphrase=p12_password.encode('utf-8') if p12_password else None)
    if signer is None:
        raise RuntimeError('El certificado PKCS#12 no es válido.')
    writer = IncrementalPdfFileWriter(BytesIO(pdf_bytes))
    result = signers.sign_pdf(writer, signers.PdfSignatureMetadata(field_name='FirmaDigitalTatronics'), signer=signer)
    return result.getvalue()
