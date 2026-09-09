# -*- coding: utf-8 -*-
import base64
import csv
import io

from odoo import _, fields, models
from odoo.exceptions import UserError

# Solo migramos reglas por producto (no categoria/global).
PRODUCT_APPLIED = ("1_product", "0_product_variant")

COLUMNS = [
    "default_code", "product_name", "applied_on", "compute_price",
    "fixed_price", "percent_price", "price_discount", "price_surcharge",
    "base", "min_quantity", "date_start", "date_end",
    "source_pricelist", "source_currency",
]


def _f(v):
    """CSV -> float tolerante (admite coma decimal y vacio)."""
    v = (v or "").strip().replace(",", ".")
    try:
        return float(v) if v else 0.0
    except ValueError:
        return 0.0


def _date(v):
    v = (v or "").strip()
    return v or False


class PricelistMigrationWizard(models.TransientModel):
    _name = "chai.pricelist.migration.wizard"
    _description = "Migrar Listas de Precio por Producto (entre bases)"

    mode = fields.Selection(
        [("export", "Exportar (base origen)"), ("import", "Importar (base destino)")],
        default="export", required=True, string="Operacion",
    )
    pricelist_id = fields.Many2one(
        "product.pricelist", required=True,
        string="Lista de precios",
        help="Al exportar: lista de la que se sacan las reglas. "
             "Al importar: lista destino donde se crearan las faltantes.",
    )
    dry_run = fields.Boolean(
        string="Solo previsualizar (no escribe)", default=True,
        help="Muestra cuantas reglas crearia/omitiria/no encontro, sin tocar la "
             "base. Desactivalo para aplicar de verdad.",
    )

    export_file = fields.Binary(string="Archivo exportado", readonly=True)
    export_filename = fields.Char(readonly=True)
    import_file = fields.Binary(string="Archivo a importar (CSV exportado)")
    import_filename = fields.Char()

    result_html = fields.Html(string="Resultado", readonly=True, sanitize=False)
    report_file = fields.Binary(string="Reporte de no emparejados", readonly=True)
    report_filename = fields.Char(readonly=True)

    # ------------------------------------------------------------------
    def _reopen(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": self.env.context,
        }

    @staticmethod
    def _item_code(item):
        """Referencia interna del producto de la regla."""
        if item.applied_on == "0_product_variant" and item.product_id:
            return item.product_id.default_code or ""
        tmpl = item.product_tmpl_id
        if tmpl:
            variants = tmpl.with_context(active_test=False).product_variant_ids
            if len(variants) == 1 and variants.default_code:
                return variants.default_code
            return tmpl.default_code or ""
        return ""

    # ------------------------------------------------------------------
    # EXPORTAR
    # ------------------------------------------------------------------
    def action_export(self):
        self.ensure_one()
        pl = self.pricelist_id
        items = self.env["product.pricelist.item"].with_context(
            active_test=False).search([
                ("pricelist_id", "=", pl.id),
                ("applied_on", "in", list(PRODUCT_APPLIED)),
            ])
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";")
        w.writerow(COLUMNS)
        exported = no_code = 0
        cur = pl.currency_id.name or ""
        for it in items:
            code = self._item_code(it)
            if not code:
                no_code += 1
            name = (it.product_id.display_name if it.product_id
                    else it.product_tmpl_id.display_name)
            w.writerow([
                code, name, it.applied_on, it.compute_price,
                it.fixed_price, it.percent_price, it.price_discount,
                it.price_surcharge, it.base or "", it.min_quantity,
                it.date_start or "", it.date_end or "",
                pl.name, cur,
            ])
            exported += 1
        self.export_file = base64.b64encode(buf.getvalue().encode("utf-8-sig"))
        self.export_filename = "listaprecios_%s.csv" % (pl.name or pl.id)
        warn = ("<p style='color:#b30000'>%s regla(s) sin referencia interna: "
                "no podran emparejarse en destino.</p>" % no_code) if no_code else ""
        self.result_html = (
            "<h4>Exportacion lista</h4>"
            "<p>Lista <b>%s</b> (moneda %s): <b>%s</b> reglas por producto "
            "exportadas.</p>%s"
            "<p>Descarga el archivo y subelo en la base destino con Operacion = "
            "<b>Importar</b>.</p>" % (pl.name, cur or "-", exported, warn))
        return self._reopen()

    # ------------------------------------------------------------------
    # IMPORTAR
    # ------------------------------------------------------------------
    def action_import(self):
        self.ensure_one()
        if not self.import_file:
            raise UserError(_("Sube primero el archivo CSV exportado."))
        target = self.pricelist_id
        Product = self.env["product.product"].with_context(active_test=False)
        Item = self.env["product.pricelist.item"]

        content = base64.b64decode(self.import_file).decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(content), delimiter=";")

        to_create = []
        n_create = n_skip = n_unmatched = n_dup = n_unsupported = n_curmix = 0
        issues = []  # (default_code, nombre, motivo)
        queued_tmpls = set()  # plantillas ya en el lote (evita duplicar por variantes)
        tgt_cur = target.currency_id.name or ""

        for row in reader:
            code = (row.get("default_code") or "").strip()
            name = (row.get("product_name") or "").strip()
            if not code:
                n_unmatched += 1
                issues.append((code, name, "fila sin referencia interna"))
                continue
            prods = Product.search([("default_code", "=", code)])
            tmpls = prods.product_tmpl_id
            if not prods:
                n_unmatched += 1
                issues.append((code, name, "no existe en destino"))
                continue
            if len(prods) > 1 or len(tmpls) > 1:
                n_dup += 1
                issues.append((code, name,
                               "referencia duplicada en destino (%s productos)" % len(prods)))
                continue
            prod, tmpl = prods, tmpls

            # ¿ya tiene CUALQUIER regla en la lista destino? -> se respeta y omite
            already = Item.with_context(active_test=False).search_count([
                ("pricelist_id", "=", target.id),
                "|",
                ("product_tmpl_id", "=", tmpl.id),
                ("product_id", "in", tmpl.with_context(
                    active_test=False).product_variant_ids.ids),
            ])
            if already:
                n_skip += 1
                continue

            # El usuario indico que aunque en el backup algunas quedaron como
            # "variante", en realidad son PRODUCTOS. Normalizamos TODO a regla
            # por producto (1_product), emparejando por referencia interna.
            if tmpl.id in queued_tmpls:
                n_dup += 1
                issues.append((code, name,
                               "otra fila ya apunta a este mismo producto (variante duplicada)"))
                continue

            compute = (row.get("compute_price") or "fixed").strip() or "fixed"
            vals = {
                "pricelist_id": target.id,
                "compute_price": compute,
                "min_quantity": _f(row.get("min_quantity")),
                "date_start": _date(row.get("date_start")),
                "date_end": _date(row.get("date_end")),
            }
            # Siempre como regla por producto (aunque el backup la tuviera como variante)
            vals["applied_on"] = "1_product"
            vals["product_tmpl_id"] = tmpl.id
            queued_tmpls.add(tmpl.id)

            if compute == "fixed":
                vals["fixed_price"] = _f(row.get("fixed_price"))
            elif compute == "percentage":
                vals["percent_price"] = _f(row.get("percent_price"))
            elif compute == "formula":
                base = (row.get("base") or "list_price").strip() or "list_price"
                if base == "pricelist":
                    # base = otra lista: no es portable entre bases -> se omite
                    n_unsupported += 1
                    issues.append((code, name,
                                   "regla 'formula' basada en otra lista (no portable)"))
                    continue
                vals["base"] = base
                vals["price_discount"] = _f(row.get("price_discount"))
                vals["price_surcharge"] = _f(row.get("price_surcharge"))

            src_cur = (row.get("source_currency") or "").strip()
            if src_cur and tgt_cur and src_cur != tgt_cur:
                n_curmix += 1

            to_create.append(vals)

        applied = False
        if not self.dry_run and to_create:
            Item.create(to_create)
            applied = True
        n_create = len(to_create)

        # Reporte descargable de problemas
        if issues:
            b = io.StringIO()
            ww = csv.writer(b, delimiter=";")
            ww.writerow(["default_code", "producto", "motivo"])
            for r in issues:
                ww.writerow(list(r))
            self.report_file = base64.b64encode(b.getvalue().encode("utf-8-sig"))
            self.report_filename = "no_emparejados.csv"
        else:
            self.report_file = False
            self.report_filename = False

        estado = ("<b style='color:#0a7d33'>APLICADO</b>" if applied
                  else "<b style='color:#b58900'>PREVISUALIZACION (no se escribio nada)</b>")
        cur_warn = ("<p style='color:#b30000'>ATENCION: %s regla(s) vienen en moneda "
                    "distinta a la lista destino (%s). Revisa antes de aplicar.</p>"
                    % (n_curmix, tgt_cur or "-")) if n_curmix else ""
        self.result_html = (
            "<h4>Importacion a la lista: %s</h4>"
            "<p>%s</p>"
            "<ul>"
            "<li><b>%s</b> regla(s) %s por productos SIN regla previa</li>"
            "<li><b>%s</b> omitida(s): el producto YA tiene regla en esta lista "
            "(se respeta, no se toca)</li>"
            "<li><b>%s</b> no encontrada(s) por referencia interna</li>"
            "<li><b>%s</b> con referencia duplicada en destino (omitidas)</li>"
            "<li><b>%s</b> formula basada en otra lista (omitidas, no portable)</li>"
            "</ul>%s"
            "%s"
            % (target.name, estado,
               n_create, "creadas" if applied else "a crear",
               n_skip, n_unmatched, n_dup, n_unsupported, cur_warn,
               ("<p>Descarga <b>no_emparejados.csv</b> para revisar los pendientes.</p>"
                if issues else "")))
        return self._reopen()
