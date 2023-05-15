# Copyright 2015-2017 ACSONE SA/NV (<http://acsone.eu>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, fields, models
import odoo.addons.decimal_precision as dp


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    @api.model
    def _default_product_purchase_uom_id(self):
        return self.env.ref('product.product_uom_unit')

    # product_tmpl_id = fields.Many2one(
    #     related='product_id.product_tmpl_id',
    #     comodel_name='product.template',
    #     readonly=True
    # )
    packaging_id = fields.Many2one(
        'product.packaging',
        'Packaging'
    )
    product_purchase_qty = fields.Float(
        'Purchase quantity',
        digits=dp.get_precision('Product Unit of Measure'),
        required=True, default=lambda *a: 1.0
    )
    product_purchase_uom_id = fields.Many2one(
        'product.uom',
        'Purchase Unit of Measure',
        required=True,
        default=_default_product_purchase_uom_id
    )
    product_qty = fields.Float(
        compute="_compute_product_qty",
        string='Quantity',
        inverse='_inverse_product_qty',
        store=True,
    )

    @api.multi
    def _get_product_seller(self):
        self.ensure_one()
        return self.product_id._select_seller(
            partner_id=self.order_id.partner_id,
            quantity=self.product_qty,
            date=self.order_id.date_order and fields.Date.to_string(
                fields.Date.from_string(self.order_id.date_order)) or None,
            uom_id=self.product_uom)

    @api.multi
    @api.depends('product_purchase_uom_id',
                 'product_purchase_qty',
                 'product_purchase_uom_id.category_id')
    def _compute_product_qty(self):
        """
        Compute the total quantity
        """
        uom_categories = self.mapped("product_purchase_uom_id.category_id")
        uom_obj = self.env['product.uom']
        to_uoms = uom_obj.search(
            [('category_id',
              'in',
              uom_categories.ids),
             ('uom_type', '=', 'reference')])
        uom_by_category = {to_uom.category_id: to_uom for to_uom in to_uoms}
        for line in self:
            line.product_qty = line.product_purchase_uom_id._compute_quantity(
                line.product_purchase_qty,
                uom_by_category.get(line.product_purchase_uom_id.category_id))

    @api.multi
    def _inverse_product_qty(self):
        """ If product_quantity is set compute the purchase_qty
        """
        uom_categories = self.mapped("product_purchase_uom_id.category_id")
        uom_obj = self.env['product.uom']
        from_uoms = uom_obj.search(
            [('category_id',
              'in',
              uom_categories.ids),
             ('uom_type', '=', 'reference')])
        uom_by_category = {
            from_uom.category_id: from_uom for from_uom in from_uoms}
        for line in self:
            purchase_qty = line.product_qty
            if line.product_id:
                supplier = line._get_product_seller()
                if supplier:
                    product_purchase_uom = supplier.min_qty_uom_id
                    from_uom = uom_by_category.get(
                        line.product_purchase_uom_id.category_id)
                    purchase_qty = from_uom._compute_quantity(
                        line.product_qty,
                        product_purchase_uom)
                    line.product_purchase_uom_id = product_purchase_uom.id
            line.product_purchase_qty = purchase_qty

    @api.onchange("packaging_id")
    def _onchange_packaging_id(self):
        """When Packaging field changes:
        1. Update the Product Unit of Measure.
        2. If a Partner has been selected, look for any packaging/price combinations that match this supplier
           """
        if self.packaging_id:
            self.product_uom = self.packaging_id.uom_id
            # If Supplier is selected, look for Packagings that match this product and

    @api.onchange('product_id')
    def onchange_product_id(self):
        """ set domain on product_purchase_uom_id and packaging_id
            set the first packaging, purchase_uom and purchase_qty
        """
        domain = {}
        # call default implementation
        # restore default values
        defaults = self.default_get(
            ['packaging_id', 'product_purchase_uom_id'])
        self.packaging_id = self.packaging_id.browse(
            defaults.get('packaging_id', []))
        self.product_purchase_uom_id = self.product_purchase_uom_id.browse(
            defaults.get('product_purchase_uom_id', []))
        # add default domains
        if self.product_id:
            if self.partner_id:
                # search() for a recordset from product_supplierinfo with entries that match the current product and
                # supplier, and then use the mapped() method to create a list of the packaging_ids
                packaging_ids = self.env['product.supplierinfo'].search(
                    ['&', ('product_id', '=', self.product_id.id), ('name', '=', self.partner_id.id)]
                ).mapped('packaging_id.id')



                # product_supplierinfo_ids = self.env['product.supplierinfo'].search(
                #     [('product_id', '=', self.product_id.id)])
                # packaging_ids = product_supplierinfo_ids.mapped('packaging_id')
                #
                # packaging_ids = self.env['product.supplierinfo'].search(
                #     [('product_id', '=', self.product_id.id)]).mapped(
                #     'packaging_id')

                # supplierinfo_ids = [supplierinfo.id for supplierinfo in product_supplierinfo_ids]
                # supplierinfo_ids = product_supplierinfo_ids.mapped('id')

                # supplierinfo_ids = self.env['product.supplierinfo'].search(
                #     ['&', ('product_id', '=', self.product_id.id), ('name', '=', self.partner_id.id)]).mapped('id')


            else:
                # there is no partner set for this purchase order, so return all packages related to this product
                packaging_ids = self.env['product.packaging'].search(
                    [('product_id', '=', self.product_id.id)]
                ).mapped('id')

            domain['packaging_id'] = [('id', 'in', packaging_ids)]
            domain['product_purchase_uom_id'] = \
                [('id', 'in', self.product_id.mapped(
                    'seller_ids.min_qty_uom_id.id'))]

        res = super(PurchaseOrderLine, self).onchange_product_id()
        if self.product_id:
            supplier = self._get_product_seller()
        else:
            supplier = self.product_id.seller_ids.browse([]) # why would this ever amount to anything? We've already determined that there's no self.product_id? Currently returns and empty set.
        if supplier.product_uom:
            # use the uom from the supplier
            # yes, but there can also be UoMs that do not have a packaging_id (e.g. min qty: 1 uom: Dozen(s) and then a price (no packaging_id). Why should we set it to the one that has a packaging_id vs. the one that doesn't? Well, b/c this is the purchase_packaging
            # model, and the idea is to make it easier to purchase things in packages, and therefore we can assume that either the user has everything purchased in packages or at least places heavy emphasis on purchasing by package.

            # we do however need to make sure that the uom from the supplier matches the Packaging (packaging_id) that has been set in this order line.
            self.product_uom = supplier.product_uom
        if supplier.min_qty_uom_id:
            # if the supplier requires some min qty/uom,
            self.product_purchase_qty = supplier.min_qty
            self.product_purchase_uom_id = supplier.min_qty_uom_id
            domain['product_purchase_uom_id'] = \
                [('id', '=', supplier.min_qty_uom_id.id)]
            to_uom = self.env['product.uom'].search([
                ('category_id', '=',
                 supplier.min_qty_uom_id.category_id.id),
                ('uom_type', '=', 'reference')], limit=1)
            to_uom = to_uom and to_uom[0]
            self.product_qty = supplier.min_qty_uom_id._compute_quantity(
                supplier.min_qty, to_uom
            )
        self.packaging_id = supplier.packaging_id
        if domain:
            if res.get('domain'):
                res['domain'].update(domain)
            else:
                res['domain'] = domain  # pragma: no cover not aware of super
        return res

    @api.multi
    def _prepare_stock_moves(self, picking):
        self.ensure_one()
        val = super(PurchaseOrderLine, self)._prepare_stock_moves(picking)
        for v in val:
            v['product_packaging'] = self.packaging_id.id
        return val

    @api.model
    def update_vals(self, vals):
        """
        When packaging_id is set, uom_id is readonly,
        so we need to reset the uom value in the vals dict
        """
        if vals.get('packaging_id'):
            vals['product_uom'] = self.env['product.packaging'].browse(
                vals['packaging_id']).uom_id.id
        return vals

    @api.model
    @api.returns('self', lambda rec: rec.id)
    def create(self, vals):
        if 'product_qty' not in vals and 'product_purchase_qty' in vals:
            # compute product_qty to avoid inverse computation and reset to 1
            uom_obj = self.env['product.uom']
            product_purchase_uom = uom_obj.browse(
                vals['product_purchase_uom_id'])
            to_uom = uom_obj.search(
                [('category_id', '=', product_purchase_uom.category_id.id),
                 ('uom_type', '=', 'reference')], limit=1)
            vals['product_qty'] = to_uom._compute_quantity(
                vals['product_purchase_qty'],
                to_uom)
        res = super(PurchaseOrderLine, self).create(self.update_vals(vals))
        if 'product_qty' in vals and not \
                self.env.context.get('recomputing_product_qty'):
            # Mandatory as we always want product_qty be computed
            res.with_context(
                recomputing_product_qty=True)._compute_product_qty()
        return res

    @api.multi
    def write(self, vals):
        res = super(PurchaseOrderLine, self).write(self.update_vals(vals))
        # Required if we want to avoid recursion as there is nothing in
        # environment that would help distinguish write call from a
        # compute
        if 'product_qty' in vals and not \
                self.env.context.get('recomputing_product_qty'):
            self.with_context(
                recomputing_product_qty=True)._compute_product_qty()
        return res
