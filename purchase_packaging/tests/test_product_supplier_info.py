# Copyright 2015-2017 ACSONE SA/NV (<http://acsone.eu>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import odoo.tests.common as common


class TestProductSupplierInfo(common.TransactionCase):

    def setUp(self):
        """ Create the UOMs, product, packaging, and product_supplierinfo required to
            test the _compute_product_uom method
        """
        super(TestProductSupplierInfo, self).setUp()

        # Create UOMs and a parent category
        self.uom_categ = self.env['product.uom.categ'].create(
            {'name': 'Product UOM Test Category'})
        self.uom_Packaging = self.env['product.uom'].create({
            'name': 'Test UOM Packaging',
            'category_id': self.uom_categ.id,
            'uom_type': 'reference',
            'rounding': 1.0,
        })
        # the _compute_product_uom method may use the product's uom_po_id. By default,
        # this is the same as the product's uom_id; therefore, we need to assign
        # different values to the uom_id & uom_po_id fields to ensure the method
        # uses the correct one. We create those UOMs here.
        self.uom_Product_uom = self.env['product.uom'].create({
            'name': 'Test UOM Product - uom',
            'category_id': self.uom_categ.id,
            'uom_type': 'reference',
            'rounding': 1.0,
        })
        self.uom_Product_uom_po = self.env['product.uom'].create({
            'name': 'Test UOM Product - uom_po',
            'category_id': self.uom_categ.id,
            'uom_type': 'reference',
            'rounding': 1.0,
        })

        # Create a product with the UOMs created for Products.
        self.product_obj = self.env['product.product']
        vals = {
            'name': 'Test Product',
            'categ_id': self.env.ref('product.product_category_all').id,
            'list_price': 30.0,
            'standard_price': 20.0,
            'type': 'product',
            'uom_id': self.uom_Product_uom.id,
            'uom_po_id': self.uom_Product_uom_po.id,
        }
        self.product_test = self.product_obj.create(vals)

        # Create a packaging that initially uses uom_Packaging
        self.product_packaging_test = self.env['product.packaging'].create({
            'product_id': self.product_test.id,
            'uom_id': self.uom_Packaging.id,
            'name': 'Packaging Test'
        })

        # Create a vendor and a supplierinfo
        self.vendor1 = self.env['res.partner'].create({'name': 'vendor1'})
        self.seller1 = self.env['product.supplierinfo'].create({
            'name': self.vendor1.id,
            'price': 15,
            'product_id': self.product_test.id,
            'product_tmpl_id': self.product_test.product_tmpl_id.id,
            'packaging_id': self.product_packaging_test.id,
        })

    def test_supplierinfo_product_uom(self):
        """ Test the _compute_product_uom method, which searches product_supplierinfo:
            if packaging_id found, use that package's uom_id,
            else if product_id found, use that product's uom_po_id,
            else if product_tmpl_id found, use that template's uom_po_id (same as prev)
        """
        # product_supplierinfo has a packaging_id - it should be used
        self.assertEqual(self.seller1.product_uom.id,
                         self.uom_Packaging.id)

        # remove the packaging_id from product_supplierinfo
        # the uom_po_id of the product should be used (different from uom_id)
        self.seller1.write({'packaging_id': ''})
        self.assertEqual(self.seller1.product_uom.id,
                         self.uom_Product_uom_po.id)

        # remove the product_id from product_supplierinfo
        # the uom_po_id of the product template should be used (diff from uom_id)
        # the result should be the same as the previous assertEqual
        self.seller1.write({'product_id': ''})
        self.assertEqual(self.seller1.product_uom.id,
                         self.uom_Product_uom_po.id)
