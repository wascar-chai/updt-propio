# -*- coding: utf-8 -*-
{
    "name": "CHAI - Migrar Listas de Precio por Producto",
    # Version SIN prefijo de serie: Odoo le antepone la serie actual,
    # por lo que el MISMO modulo instala en 16.0 (backup) y en 18.0 (produccion).
    "version": "1.0.0",
    "author": "CHAI Consultoria y Software",
    "website": "https://chaiconsultoria.com",
    "category": "Sales/Sales",
    "summary": "Exporta las reglas de precio por producto de una lista y las "
               "importa en otra base emparejando por referencia interna, "
               "creando SOLO las faltantes (nunca sobrescribe las existentes).",
    "description": """
Migrar Listas de Precio por Producto (entre bases)
==================================================

Pensado para llevar las reglas de precio por producto de una `product.pricelist`
de una base (p. ej. un backup Odoo 16) a otra base (p. ej. produccion Odoo 18),
sin pisar lo que ya se toco en produccion.

- **Exportar** (en la base origen): vuelca a CSV las reglas por producto de la
  lista elegida, identificando el producto por su **referencia interna**
  (default_code), no por ID.
- **Importar** (en la base destino): empareja por referencia interna y **solo
  CREA** la regla para los productos que **aun no tienen regla** en la lista
  destino. Nunca modifica ni borra reglas existentes.
- **Previsualizacion (dry-run):** muestra cuantas crearia / omitiria / no
  encontro, sin escribir nada. Descarga un CSV con los no emparejados.
- Idempotente: correrlo dos veces no duplica.
    """,
    "depends": ["product"],
    "data": [
        "security/ir.model.access.csv",
        "wizards/pricelist_migration_wizard_views.xml",
    ],
    "license": "LGPL-3",
    "installable": True,
    "application": False,
}
