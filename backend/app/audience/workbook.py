"""Bounded OOXML reader/writer for the application's tabular planning contract.

No formulas from uploaded files are executed. Exports use typed cells, so untrusted
text beginning with '=' remains text. Formula cells generated here have caches.
"""
from io import BytesIO
import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
MAX_ROWS = 20000


def col_index(ref):
    value = 0
    for char in re.match(r'[A-Z]+', ref.upper()).group():
        value = value * 26 + ord(char) - 64
    return value - 1


def col_name(n):
    result = ''
    while n:
        n, digit = divmod(n - 1, 26)
        result = chr(65 + digit) + result
    return result


def read_workbook(data):
    try:
        archive = zipfile.ZipFile(BytesIO(data))
        if len(archive.infolist()) > 3000 or sum(i.file_size for i in archive.infolist()) > 150_000_000:
            raise ValueError('工作簿解压后过大')
        def xml(path):
            raw = archive.read(path)
            if b'<!DOCTYPE' in raw or b'<!ENTITY' in raw:
                raise ValueError('不支持 XML 实体')
            return ET.fromstring(raw)
        strings = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            strings = [''.join(t.text or '' for t in si.findall('.//m:t', NS)) for si in xml('xl/sharedStrings.xml')]
        rels = {r.get('Id'): r.get('Target') for r in xml('xl/_rels/workbook.xml.rels') if r.get('TargetMode') != 'External'}
        sheets = {}
        for sheet in xml('xl/workbook.xml').find('m:sheets', NS):
            target = rels.get(sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'))
            if not target:
                continue
            path = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/' + target)
            rows = []
            for row in xml(path).findall('m:sheetData/m:row', NS):
                if len(rows) >= MAX_ROWS + 30:
                    raise ValueError(f'每表最多 {MAX_ROWS} 条数据')
                values = []
                for cell in row.findall('m:c', NS):
                    index = col_index(cell.get('r', 'A1'))
                    if index > 255:
                        continue
                    values.extend([None] * max(0, index + 1 - len(values)))
                    kind = cell.get('t')
                    node = cell.find('m:v', NS)
                    value = node.text if node is not None else None
                    if kind == 's' and value is not None:
                        value = strings[int(value)]
                    elif kind == 'inlineStr':
                        value = ''.join(t.text or '' for t in cell.findall('.//m:t', NS))
                    elif kind == 'b':
                        value = value == '1'
                    elif kind not in ('str', 'e') and value is not None:
                        try:
                            value = float(value)
                        except ValueError:
                            pass
                    values[index] = value
                if any(v is not None and v != '' for v in values):
                    rows.append(values)
            sheets[sheet.get('name')] = rows
        return sheets
    except (zipfile.BadZipFile, KeyError, ET.ParseError, IndexError, AttributeError) as exc:
        raise ValueError('无法读取 XLSX 工作簿，请上传有效且未加密的 .xlsx 文件') from exc


def headers_and_records(rows, required=None):
    for index, row in enumerate(rows[:30]):
        keys = [str(x or '').strip() for x in row]
        semantic = [re.sub(r'[^A-Z0-9]', '', x.upper()) for x in keys]
        if required and required not in semantic:
            continue
        if not any(keys):
            continue
        # Preserve duplicate source columns using explicit suffixes.
        used, headers = {}, []
        for i, key in enumerate(keys):
            key = key or f'Unnamed_{i+1}'
            used[key] = used.get(key, 0) + 1
            headers.append(key if used[key] == 1 else f'{key}__{used[key]}')
        records = [dict(zip(headers, list(r) + [None] * max(0, len(headers) - len(r)))) for r in rows[index + 1:]]
        return headers, records
    raise ValueError('找不到原始屏幕表头（需要 VIOOH_ID 或 Screen ID）')


def text(value):
    # XML 1.0 cannot encode control characters.
    return escape(re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', str(value))[:32767])


def write_workbook(sheets, images=None):
    """sheets: [(name, headers, rows)]. Formula values: {'formula': ..., 'value': ...}."""
    images = images or []
    out = BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        base = 'http://schemas.openxmlformats.org/'
        types = ['<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>', '<Default Extension="xml" ContentType="application/xml"/>', '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>', '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>']
        refs, rels = [], []
        for ext, mime in [('png','image/png'),('jpg','image/jpeg'),('webp','image/webp')]:
            types.append(f'<Default Extension="{ext}" ContentType="{mime}"/>')
        for sid, (name, headers, rows) in enumerate(sheets, 1):
            types.append(f'<Override PartName="/xl/worksheets/sheet{sid}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
            refs.append(f'<sheet name="{text(name)}" sheetId="{sid}" r:id="rId{sid}"/>')
            rels.append(f'<Relationship Id="rId{sid}" Type="{base}officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{sid}.xml"/>')
            sheet_images = [image for image in images if image['sheet'] == name]
            rendered = []
            for ri, row in enumerate([headers] + rows, 1):
                cells = []
                for ci, value in enumerate(row, 1):
                    ref = f'{col_name(ci)}{ri}'
                    style = '1' if ri == 1 else '2'
                    if value is None:
                        continue
                    if isinstance(value, dict) and 'formula' in value:
                        cells.append(f'<c r="{ref}" s="2"><f>{text(value["formula"])}</f><v>{value["value"]}</v></c>')
                    elif isinstance(value, (int, float)) and not isinstance(value, bool):
                        cells.append(f'<c r="{ref}" s="{style}"><v>{value}</v></c>')
                    else:
                        cells.append(f'<c r="{ref}" s="{style}" t="inlineStr"><is><t xml:space="preserve">{text(value)}</t></is></c>')
                rendered.append(f'<row r="{ri}" ht="{42 if ri == 1 else 130 if sheet_images else 32}" customHeight="1">{"".join(cells)}</row>')
            cols = ''.join(f'<col min="{i}" max="{i}" width="{min(48, max(18, len(str(h)) * 1.3))}" customWidth="1"/>' for i, h in enumerate(headers, 1))
            drawing = ''
            if sheet_images:
                drawing = '<drawing r:id="rIdDrawing"/>'
                types.append(f'<Override PartName="/xl/drawings/drawing{sid}.xml" ContentType="application/vnd.openxmlformats-officedocument.drawing+xml"/>')
                z.writestr(f'xl/worksheets/_rels/sheet{sid}.xml.rels', f'<Relationships xmlns="{base}package/2006/relationships"><Relationship Id="rIdDrawing" Type="{base}officeDocument/2006/relationships/drawing" Target="../drawings/drawing{sid}.xml"/></Relationships>')
                anchors, image_rels = [], []
                for ii, image in enumerate(sheet_images, 1):
                    ext = {'image/png':'png','image/jpeg':'jpg','image/webp':'webp'}[image['mime']]
                    filename = f'image{sid}_{ii}.{ext}'
                    z.writestr('xl/media/' + filename, image['data'])
                    image_rels.append(f'<Relationship Id="rId{ii}" Type="{base}officeDocument/2006/relationships/image" Target="../media/{filename}"/>')
                    import fitz
                    bitmap=fitz.Pixmap(image['data'])
                    scale=min(1524000/bitmap.width,1524000/bitmap.height)
                    width,height=int(bitmap.width*scale),int(bitmap.height*scale)
                    anchors.append(f'<xdr:oneCellAnchor><xdr:from><xdr:col>{image["column"]-1}</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>{image["row"]-1}</xdr:row><xdr:rowOff>19050</xdr:rowOff></xdr:from><xdr:ext cx="{width}" cy="{height}"/><xdr:pic><xdr:nvPicPr><xdr:cNvPr id="{ii}" name="Screen photo {ii}"/><xdr:cNvPicPr><a:picLocks noChangeAspect="1"/></xdr:cNvPicPr></xdr:nvPicPr><xdr:blipFill><a:blip r:embed="rId{ii}"/><a:stretch><a:fillRect/></a:stretch></xdr:blipFill><xdr:spPr><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></xdr:spPr></xdr:pic><xdr:clientData/></xdr:oneCellAnchor>')
                z.writestr(f'xl/drawings/drawing{sid}.xml', f'<xdr:wsDr xmlns:xdr="{base}drawingml/2006/spreadsheetDrawing" xmlns:a="{base}drawingml/2006/main" xmlns:r="{base}officeDocument/2006/relationships">{"".join(anchors)}</xdr:wsDr>')
                z.writestr(f'xl/drawings/_rels/drawing{sid}.xml.rels', f'<Relationships xmlns="{base}package/2006/relationships">{"".join(image_rels)}</Relationships>')
            z.writestr(f'xl/worksheets/sheet{sid}.xml', f'<worksheet xmlns="{base}spreadsheetml/2006/main" xmlns:r="{base}officeDocument/2006/relationships"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols>{cols}</cols><sheetData>{"".join(rendered)}</sheetData><autoFilter ref="A1:{col_name(len(headers))}{len(rows)+1}"/>{drawing}</worksheet>')
        rels.append(f'<Relationship Id="rIdStyles" Type="{base}officeDocument/2006/relationships/styles" Target="styles.xml"/>')
        z.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">' + ''.join(types) + '</Types>')
        z.writestr('_rels/.rels', f'<Relationships xmlns="{base}package/2006/relationships"><Relationship Id="rId1" Type="{base}officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr('xl/workbook.xml', f'<workbook xmlns="{base}spreadsheetml/2006/main" xmlns:r="{base}officeDocument/2006/relationships"><sheets>{"".join(refs)}</sheets><calcPr calcMode="auto"/></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels', f'<Relationships xmlns="{base}package/2006/relationships">{"".join(rels)}</Relationships>')
        z.writestr('xl/styles.xml', f'<styleSheet xmlns="{base}spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF194F3E"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyAlignment="1"><alignment wrapText="1" vertical="center"/></xf><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')
    return out.getvalue()
