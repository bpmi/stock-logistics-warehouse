# Copyright 2015-2017 ACSONE SA/NV (<http://acsone.eu>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, models
from odoo.tools import float_compare


class ProcurementRule(models.Model):
    _inherit = 'procurement.rule'

    @api.multi
    def _prepare_purchase_order_line(self, product_id, product_qty, product_uom, values,
                                     po, supplier):
        res = super(ProcurementRule, self)._prepare_purchase_order_line(product_id,
                                                                        product_qty,
                                                                        product_uom,
                                                                        values, po,
                                                                        supplier)
        seller = product_id._select_seller(
            partner_id=supplier.name,
            quantity=res['product_qty'],
            date=po.date_order and po.date_order[:10],
            uom_id=product_id.uom_po_id)
        if seller.packaging_id:
            res['packaging_id'] = seller.packaging_id.id
            new_uom_id = seller.product_uom
            if new_uom_id.id != res['product_uom']:
                res['product_uom'] = new_uom_id
                qty = product_uom._compute_quantity(
                    product_qty, new_uom_id)
                res['product_qty'] = max(qty, seller.min_qty)
        return res


class Orderpoint(models.Model):
    _inherit = 'stock.warehouse.orderpoint'

    @api.multi
    def subtract_procurements_from_orderpoints(self):
        # In this method we need to access the purchase order line quantity
        # to correctly evaluate the forecast.
        # Imagine a product with a minimum rule of 4 units and a purchase
        # multiple of 12. The first run will generate a procurement for 4 Pc
        # but a purchase for 12 units.
        # Let's change the minimum rule to 5 units.
        # The standard subtract_procurements_from_orderpoints will return 4
        # and Odoo will create a procurement for 1 unit which will trigger a
        # purchase of 12 due to the multiple. So the original purchase will
        # be increased to 24 units which is wrong.
        # This override will return 12 and no additionnal procurement will be
        # created
        res = super(Orderpoint, self).subtract_procurements_from_orderpoints()
        procurements = self.env['procurement.order'].search([
            ('orderpoint_id', 'in', self.ids),
            ('state', 'not in', ['cancel', 'done']),
            ('purchase_line_id.state', 'in', ['draft', 'sent', 'to approve'])
        ])
        procurements.mapped('product_uom.rounding')
        procurements.mapped('purchase_line_id.state')
        procs_by_orderpoint = dict.fromkeys(
            self.ids, self.env['procurement.order'])
        for proc in procurements:
            procs_by_orderpoint[proc.orderpoint_id.id] |= proc
        for orderpoint in self:
            procs = procs_by_orderpoint.get(orderpoint.id)
            if procs:
                po_lines = procs.mapped('purchase_line_id').filtered(
                    lambda x: x.state in ['draft', 'sent', 'to approve'])
                if po_lines:
                    qty = sum([line.product_qty for line in po_lines])
                    precision = orderpoint.product_uom.rounding
                    if float_compare(qty, res[orderpoint.id],
                                     precision_rounding=precision) >= 0:
                        res[orderpoint.id] = qty
        return res
