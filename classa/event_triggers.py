from __future__ import unicode_literals
import frappe
from frappe import auth
import datetime
import json, ast
from frappe.utils import money_in_words



################ Quotation

@frappe.whitelist()
def quot_onload(doc, method=None):
    pass
@frappe.whitelist()
def quot_before_validate(doc, method=None):
    doc.ignore_pricing_rule = 0
    
    for t in doc.items:
        allowed_uom =frappe.db.get_value('UOM Conversion Detail', {'parent': t.item_code,'uom': t.uom}, ['uom'])
        if allowed_uom != t.uom:
            frappe.throw("Row #" + str(t.idx) + ": وحدة القياس غير معرفة للصنف " + t.item_code)

    ## Make Customer Address 2 Field Mandatory If Customer Group Is Chain
    parent_group = frappe.db.get_value("Customer Group", doc.customer_group, "parent_customer_group")
    if (doc.customer_group == "مجموعة السلاسل" or parent_group == "مجموعة السلاسل") and not doc.customer_address_2:
        frappe.throw("Please Select The Customer's Address")
    if (doc.customer_group == "مجموعة السلاسل" or parent_group == "مجموعة السلاسل"):
        doc.customer_address = doc.customer_address_2
    if (doc.customer_group == "مجموعة التجزئة" or parent_group == "مجموعة التجزئة"):
        doc.customer_address_2 = doc.customer_address

    ## Fetch Branch From Territory
    doc.branch = frappe.db.get_value("Territory", doc.territory, "branch")

    ## Fetch Department From Session User
    user = frappe.session.user
    doc.department = frappe.db.get_value("Employee", {'user_id': user}, "department")

    ## Fetch Cost Center From Customer Group
    doc.cost_center = frappe.db.get_value("Customer Group", doc.customer_group, "cost_center")

    ## Fetch Accounting Dimensions In Taxes Table
    for y in doc.taxes:
        y.territory = doc.territory
        y.branch = doc.branch
        y.department = doc.department
        y.cost_center = doc.cost_center

    ## Fetch Price List Rate In Items Table
    for x in doc.items:
        x.price_list_rate = frappe.db.get_value("Item Price", {'price_list': doc.selling_price_list, 'item_code': x.item_code}, "price_list_rate")

    ## Fetch Tax Type From Customer
    default_tax_type = frappe.db.get_value("Customer", doc.party_name, "tax_type")
    if not doc.tax_type:
        doc.tax_type = default_tax_type

    ## Calculate Item Rate If Customer Tax Type Is Commercial
    if doc.tax_type == "Commercial":
        doc.set("taxes", [])
        for d in doc.items:
            if not d.margin_type:
                d.discount_percentage = 0
            if d.item_tax_template:
                item_tax_rate = float(
                    frappe.db.get_value("Item Tax Template Detail", {'parent': d.item_tax_template}, "tax_rate"))
                if item_tax_rate > 0:
                    if d.discount_percentage:
                        new_rate = (d.price_list_rate + (item_tax_rate * d.price_list_rate / 100))
                        new_discounted_rate = new_rate - ((d.discount_percentage * new_rate) / 100)
                        d.rate = new_discounted_rate
                        d.net_rate = new_discounted_rate
                        d.base_net_rate = new_discounted_rate
                        d.base_rate = new_discounted_rate
                        d.net_amount = new_discounted_rate * d.qty
                        d.base_net_amount = new_discounted_rate * d.qty
                        d.amount = new_discounted_rate * d.qty
                        d.base_amount = new_discounted_rate * d.qty
                        d.tax_rate = new_rate
                        d.discounted_amount = new_rate * d.discount_percentage / 100
                    else:
                        new_rate = (d.price_list_rate + (item_tax_rate * d.price_list_rate / 100))
                        d.rate = new_rate
                        d.base_rate = new_rate
                        d.amount = new_rate * d.qty
                        d.base_amount = new_rate * d.qty
                        d.tax_rate = new_rate
                else:
                    new_rate = (d.price_list_rate + (item_tax_rate * d.price_list_rate / 100))
                    d.tax_rate = new_rate
        totals = 0
        for x in doc.items:
            totals += x.amount
        if doc.additional_discount_percentage:
            doc.total = totals
            doc.grand_total = totals - doc.discount_amount
            doc.base_grand_total = totals - doc.discount_amount
            doc.net_total = totals - doc.discount_amount
            doc.base_net_total = totals - doc.discount_amount
            doc.base_total = totals - doc.discount_amount
            doc.outstanding_amount = totals - doc.discount_amount
            doc.total_taxes_and_charges = 0

        else:
            doc.total = totals
            doc.grand_total = totals
            doc.base_grand_total = totals
            doc.net_total = totals
            doc.base_net_total = totals
            doc.base_total = totals
            doc.outstanding_amount = totals
            doc.total_taxes_and_charges = 0

    ## Calculate Taxes Table If Customer Tax Type Is Taxable
    if doc.tax_type == "Taxable":
        doc.set("taxes", [])
        new_taxes = 0
        for d in doc.items:
            if d.item_tax_template:
                item_tax_rate = frappe.db.get_value("Item Tax Template Detail", {'parent': d.item_tax_template},
                                                    "tax_rate")
                d.tax_amount = d.net_amount * item_tax_rate / 100
                new_taxes += d.tax_amount

        taxes1 = doc.append("taxes", {})
        taxes1.charge_type = "On Net Total"
        taxes1.account_head = "2301 - ضريبة القيمة المضافة VAT - CA"
        taxes1.description = "2301 - ضريبة القيمة المضافة VAT"
        '''
        taxes1.rate = 0
        taxes1.account_currency = "EGP"
        taxes1.tax_amount = new_taxes
        taxes1.total = doc.total + new_taxes
        taxes1.base_tax_amount = new_taxes
        taxes1.base_total = doc.total + new_taxes
        taxes1.tax_amount_after_discount_amount = new_taxes
        taxes1.base_tax_amount_after_discount_amount = new_taxes
        taxes1.vehicle = doc.vehicle
        taxes1.territory = doc.territory
        taxes1.branch = doc.branch
        taxes1.department = doc.department
        taxes1.cost_center = doc.cost_center
        '''


@frappe.whitelist()
def quot_validate(doc, method=None):
    for d in doc.items:
        x = d.price_list_rate + (d.price_list_rate * 0.01)
        y = d.rate + (d.rate * 0.01)
        if (d.rate > x or d.price_list_rate > y):
            frappe.msgprint("Row #"+str(d.idx)+": Check Price List For Item Code " + d.item_code)

        if not d.price_list_rate:
            frappe.msgprint("Row #"+str(d.idx)+": Item Code " + d.item_code + " Is Not Listed For Customer " + doc.customer_name)


@frappe.whitelist()
def quot_on_submit(doc, method=None):
    for d in doc.items:
        x = d.price_list_rate + (d.price_list_rate * 0.01)
        y = d.rate + (d.rate * 0.01)
        if (d.rate > x or d.price_list_rate > y) and not doc.allow_price:
            frappe.msgprint("Row #"+str(d.idx)+": Check Price List For Item Code " + d.item_code)

        if not d.price_list_rate:
            frappe.msgprint("Row #"+str(d.idx)+": Item Code " + d.item_code + " Is Not Listed For Customer " + doc.customer_name)


@frappe.whitelist()
def quot_on_cancel(doc, method=None):
    pass
@frappe.whitelist()
def quot_on_update_after_submit(doc, method=None):
    pass
@frappe.whitelist()
def quot_before_save(doc, method=None):
    pass
@frappe.whitelist()
def quot_before_cancel(doc, method=None):
    pass
@frappe.whitelist()
def quot_on_update(doc, method=None):
    pass


################ Sales Order


@frappe.whitelist()
def so_onload(doc, method=None):
    pass
@frappe.whitelist()
def so_before_validate(doc, method=None):
    doc.ignore_pricing_rule = 0
    doc.disable_rounded_total = 0
    ## Fetch Vehicle Warehouse From Vehicle
    doc.vehicle_warehouse = frappe.db.get_value("Vehicle", doc.vehicle, "warehouse")

    for t in doc.items:
        allowed_uom =frappe.db.get_value('UOM Conversion Detail', {'parent': t.item_code,'uom': t.uom}, ['uom'])
        if allowed_uom != t.uom:
            frappe.throw("Row #" + str(t.idx) + ": وحدة القياس غير معرفة للصنف " + t.item_code)

    ## Make Customer Address 2 Field Mandatory If Customer Group Is Chain
    ## Auto Set Warehouse Based On Customer Group & Territory
    parent_group = frappe.db.get_value("Customer Group", doc.customer_group, "parent_customer_group")
    parent_territory = frappe.db.get_value("Territory", doc.territory, "parent_territory")
    if (doc.customer_group == "مجموعة السلاسل" or parent_group == "مجموعة السلاسل") and not doc.customer_address_2:
        frappe.throw("Please Select The Customer's Address")
    '''
    if (doc.customer_group == "مجموعة السلاسل" or parent_group == "مجموعة السلاسل"):
        doc.customer_address = doc.customer_address_2
    if (doc.customer_group == "مجموعة التجزئة" or parent_group == "مجموعة التجزئة"):
        doc.customer_address_2 = doc.customer_address
    if (doc.customer_group == "مجموعة التجزئة" or parent_group == "مجموعة التجزئة") and (doc.territory == "القاهرة" or parent_territory == "القاهرة"):
        doc.set_warehouse = "مخزن التجمع رئيسي - CA"
    if (doc.customer_group == "مجموعة السلاسل" or parent_group == "مجموعة السلاسل") and (doc.territory == "القاهرة" or parent_territory == "القاهرة"):
        doc.set_warehouse = "مخزن بدر رئيسي - CA"
    if (doc.territory == "الاسكندرية" or parent_territory == "الاسكندرية"):
        doc.set_warehouse = "مخزن الأسكندرية رئيسي - CA"
    if (doc.territory == "الغردقة" or parent_territory == "الغردقة"):
        doc.set_warehouse = "مخزن الغردقة رئيسي - CA"
    if (doc.territory == "المنصورة" or parent_territory == "المنصورة"):
        doc.set_warehouse = "مخزن المنصورة رئيسي - CA"
    '''
    ## Fetch Sales Persons
    #doc.sales_person = frappe.db.get_value("Address", doc.customer_address, "sales_person")
    doc.sales_supervisor = frappe.db.get_value("Sales Person", doc.sales_person, "parent_sales_person")
    doc.territory_manager = frappe.db.get_value("Customer", doc.customer, "sales_person")
    doc.sales_manager = frappe.db.get_value("Customer Group", doc.customer_group, "sales_person")

    ## Fetch Branch From Territory
    doc.branch = frappe.db.get_value("Territory", doc.territory, "branch")

    ## Fetch Department From Session User
    user = frappe.session.user
    doc.department = frappe.db.get_value("Employee", {'user_id': user}, "department")

    ## Fetch Cost Center From Customer Group
    doc.cost_center = frappe.db.get_value("Customer Group", doc.customer_group, "cost_center")

    ## Fetch Vehicle Warehouse From Vehicle
    doc.vehicle_warehouse = frappe.db.get_value("Vehicle", doc.vehicle, "warehouse")

    ## Fetch Accounting Dimensions In Taxes Table
    for y in doc.taxes:
        y.vehicle = doc.vehicle
        y.territory = doc.territory
        y.branch = doc.branch
        y.department = doc.department
        y.cost_center = doc.cost_center

    ## Fetch Tax Type From Customer
    default_tax_type = frappe.db.get_value("Customer", doc.customer, "tax_type")
    if not doc.tax_type:
        doc.tax_type = default_tax_type

    ## Calculate Item Rate If Customer Tax Type Is Commercial
    if doc.tax_type == "Commercial":
        doc.set("taxes", [])
        for d in doc.items:
            if not d.margin_type:
                d.discount_percentage = 0
            if d.item_tax_template:
                item_tax_rate = float(
                    frappe.db.get_value("Item Tax Template Detail", {'parent': d.item_tax_template}, "tax_rate"))
                if item_tax_rate > 0:
                    if d.discount_percentage:
                        new_rate = (d.price_list_rate + (item_tax_rate * d.price_list_rate / 100))
                        new_discounted_rate = new_rate - ((d.discount_percentage * new_rate) / 100)
                        d.rate = new_discounted_rate
                        d.net_rate = new_discounted_rate
                        d.base_net_rate = new_discounted_rate
                        d.base_rate = new_discounted_rate
                        d.net_amount = new_discounted_rate * d.qty
                        d.base_net_amount = new_discounted_rate * d.qty
                        d.amount = new_discounted_rate * d.qty
                        d.base_amount = new_discounted_rate * d.qty
                        d.tax_rate = new_rate
                        d.discounted_amount = new_rate * d.discount_percentage / 100
                    else:
                        new_rate = (d.price_list_rate + (item_tax_rate * d.price_list_rate / 100))
                        d.rate = new_rate
                        d.base_rate = new_rate
                        d.amount = new_rate * d.qty
                        d.base_amount = new_rate * d.qty
                        d.tax_rate = new_rate
                else:
                    new_rate = (d.price_list_rate + (item_tax_rate * d.price_list_rate / 100))
                    d.tax_rate = new_rate
        totals = 0
        for x in doc.items:
            totals += x.amount
        if doc.additional_discount_percentage:
            doc.total = totals
            doc.grand_total = totals - doc.discount_amount
            doc.base_grand_total = totals - doc.discount_amount
            doc.net_total = totals - doc.discount_amount
            doc.base_net_total = totals - doc.discount_amount
            doc.base_total = totals - doc.discount_amount
            doc.outstanding_amount = totals - doc.discount_amount
            doc.total_taxes_and_charges = 0

        else:
            doc.total = totals
            doc.grand_total = totals
            doc.base_grand_total = totals
            doc.net_total = totals
            doc.base_net_total = totals
            doc.base_total = totals
            doc.outstanding_amount = totals
            doc.total_taxes_and_charges = 0

    ## Calculate Taxes Table If Customer Tax Type Is Taxable
    if doc.tax_type == "Taxable":
        doc.set("taxes", [])
        new_taxes = 0
        for d in doc.items:
            if d.item_tax_template:
                item_tax_rate = frappe.db.get_value("Item Tax Template Detail", {'parent': d.item_tax_template},"tax_rate")
                d.tax_amount = d.net_amount * item_tax_rate / 100
                new_taxes += d.tax_amount

        taxes1 = doc.append("taxes", {})
        taxes1.charge_type = "On Net Total"
        taxes1.account_head = "2301 - ضريبة القيمة المضافة VAT - CA"
        taxes1.description = "2301 - ضريبة القيمة المضافة VAT"
        '''
        taxes1.rate = 0
        taxes1.account_currency = "EGP"
        taxes1.tax_amount = new_taxes
        taxes1.total = doc.total + new_taxes
        taxes1.base_tax_amount = new_taxes
        taxes1.base_total = doc.total + new_taxes
        taxes1.tax_amount_after_discount_amount = new_taxes
        taxes1.base_tax_amount_after_discount_amount = new_taxes
        taxes1.vehicle = doc.vehicle
        taxes1.territory = doc.territory
        taxes1.branch = doc.branch
        taxes1.department = doc.department
        taxes1.cost_center = doc.cost_center
        '''

    sales_order_list = frappe.db.get_list('Sales Order', filters=[{'docstatus': ['!=', 2]}], fields=["quotation", "name"])
    for x in sales_order_list:
        if doc.quotation == x.quotation and doc.quotation is not None and doc.name != x.name:
            frappe.throw("Another Sales Order " + x.name + " Is Linked With The Same Quotation. ")

@frappe.whitelist()
def so_validate(doc, method=None):
    for d in doc.items:
        x = d.price_list_rate + (d.price_list_rate * 0.01)
        y = d.rate + (d.rate * 0.01)
        if (d.rate > x or d.price_list_rate > y) and not(doc.allow_price or d.pricing_rules):
            frappe.msgprint("Row #"+str(d.idx)+": Check Price List For Item Code " + d.item_code)

        if not d.price_list_rate:
            frappe.msgprint("Row #"+str(d.idx)+": Item Code " + d.item_code + " Is Not Listed For Customer " + doc.customer_name)

@frappe.whitelist()
def so_on_submit(doc, method=None):
    user = frappe.session.user
    lang = frappe.db.get_value("User", {'name': user}, "language")
    for d in doc.items:
        x = d.price_list_rate + (d.price_list_rate * 0.01)
        y = d.rate + (d.rate * 0.01)
        if (d.rate > x or d.price_list_rate > y) and not(doc.allow_price or d.pricing_rules):
            frappe.throw("Row #" + str(d.idx) + ": Check Price List For Item Code " + d.item_code)
        #if d.qty > d.actual_qty:
        #   frappe.throw("Row #" + str(d.idx) + ": Ordered Qty Is More Than Available Qty For Item " + d.item_code)

    ## Make Vehicle & Vehicle Warehouse Fields Mandatory On Submit
    if not doc.vehicle:
        frappe.throw("Please Select The Vehicle")
    if not doc.vehicle_warehouse:
        frappe.throw("Please Add Warehouse For The Vehicle" + doc.vehicle)


    ## Auto Create Draft Delivey Note On Submit
    new_doc = frappe.get_doc({
        "doctype": "Delivery Note",
        "customer": doc.customer,
        "customer_group": doc.customer_group,
        "territory": doc.territory,
        "sales_order": doc.name,
        "posting_date": doc.delivery_date,
        "tax_type": doc.tax_type,
        "po_no": doc.po_no,
        "po_date": doc.po_date,
        "customer_address": doc.customer_address,
        "shipping_address_name": doc.shipping_address_name,
        "dispatch_address_name": doc.dispatch_address_name,
        "company_address": doc.company_address,
        "contact_person": doc.contact_person,
        "tax_id": doc.tax_id,
        "currency": doc.currency,
        "conversion_rate": doc.conversion_rate,
        "selling_price_list": doc.selling_price_list,
        "price_list_currency": doc.price_list_currency,
        "plc_conversion_rate": doc.plc_conversion_rate,
        "ignore_pricing_rule": doc.ignore_pricing_rule,
        "set_warehouse": doc.set_warehouse,
        "tc_name": doc.tc_name,
        "terms": doc.terms,
        "apply_discount_on": doc.apply_discount_on,
        "base_discount_amount": doc.base_discount_amount,
        "additional_discount_percentage": doc.additional_discount_percentage,
        "discount_amount": doc.discount_amount,
        "driver": doc.driver,
        "project": doc.project,
        "cost_center": doc.cost_center,
        "branch": doc.branch,
        "department": doc.department,
        "vehicle": doc.vehicle,
    })
    so_items = frappe.db.sql(""" select a.name, a.idx, a.item_code, a.item_name, a.description, a.qty, a.stock_qty, a.uom, a.stock_uom, a.conversion_factor, a.rate, a.amount,
                                   a.price_list_rate, a.base_price_list_rate, a.base_rate, a.base_amount, a.net_rate, a.net_amount, a.margin_type, a.margin_rate_or_amount, a.rate_with_margin,
                                   a.discount_percentage, a.discount_amount, a.base_rate_with_margin, a.item_tax_template
                                   from `tabSales Order Item` a join `tabSales Order` b
                                   on a.parent = b.name
                                   where b.name = '{name}'
                               """.format(name=doc.name), as_dict=1)

    for c in so_items:
        items = new_doc.append("items", {})
        items.idx = c.idx
        items.item_code = c.item_code
        items.item_name = c.item_name
        items.description = c.description
        items.qty = c.qty
        items.uom = c.uom
        items.stock_uom = c.stock_uom
        items.conversion_factor = c.conversion_factor
        items.price_list_rate = c.price_list_rate
        items.base_price_list_rate = c.base_price_list_rate
        items.base_rate = c.base_rate
        items.base_amount = c.base_amount
        items.rate = c.rate
        items.net_rate = c.net_rate
        items.net_amount = c.net_amount
        items.amount = c.amount
        items.margin_type = c.margin_type
        items.margin_rate_or_amount = c.margin_rate_or_amount
        items.rate_with_margin = c.rate_with_margin
        items.discount_percentage = c.discount_percentage
        items.discount_amount = c.discount_amount
        items.base_rate_with_margin = c.base_rate_with_margin
        items.item_tax_template = c.item_tax_template
        items.so_detail = c.name
        items.against_sales_order = doc.name

    so_taxes = frappe.db.sql(""" select a.charge_type, a.row_id, a.account_head, a.description, a.included_in_print_rate, a.included_in_paid_amount, a.rate, a.account_currency, a.tax_amount,
                                a.total, a.tax_amount_after_discount_amount, a.base_tax_amount, a.base_total, a.base_tax_amount_after_discount_amount, a.item_wise_tax_detail, a.dont_recompute_tax,
                                a.vehicle, a.department, a.cost_center, a.branch
                               from `tabSales Taxes and Charges` a join `tabSales Order` b
                               on a.parent = b.name
                               where b.name = '{name}'
                           """.format(name=doc.name), as_dict=1)

    for x in so_taxes:
        taxes = new_doc.append("taxes", {})
        taxes.charge_type = x.charge_type
        taxes.row_id = x.row_id
        taxes.account_head = x.account_head
        taxes.description = x.description
        taxes.included_in_print_rate = x.included_in_print_rate
        taxes.included_in_paid_amount = x.included_in_paid_amount
        taxes.rate = x.rate
        taxes.account_currency = x.account_currency
        taxes.tax_amount = x.tax_amount
        taxes.total = x.total
        taxes.tax_amount_after_discount_amount = x.tax_amount_after_discount_amount
        taxes.base_tax_amount = x.base_tax_amount
        taxes.base_total = x.base_total
        taxes.base_tax_amount_after_discount_amount = x.base_tax_amount_after_discount_amount
        taxes.item_wise_tax_detail = x.item_wise_tax_detail
        taxes.dont_recompute_tax = x.dont_recompute_tax
        taxes.vehicle = x.vehicle
        taxes.department = x.department
        taxes.branch = x.branch
        taxes.cost_center = x.cost_center

    new_doc.insert()
    if lang == "ar":
        frappe.msgprint("  تم إنشاء إذن تسليم العميل بحالة مسودة رقم " + new_doc.name)
    else:
        frappe.msgprint(" Delivery Note record " + new_doc.name + " created ")
        # frappe.msgprint(_("Delivery Note record {0} created").format("<a href='/app/Form/Delivery Note/{0}'>{0}</a>").format(new_doc.name))

    '''
    ## Auto Create Draft Stock Entry On Submit
    new_doc = frappe.get_doc({
        "doctype": "Stock Entry",
        "posting_date": doc.transaction_date,
        "sales_order": doc.name,
        "customer": doc.customer,
        "vehicle": doc.vehicle,
        "territory": doc.territory,
        "project": doc.project,
        "stock_entry_type": "Material Transfer",
        "from_warehouse": doc.set_warehouse,
        "to_warehouse": doc.vehicle_warehouse,
    })
    so_items = frappe.db.sql(""" select a.name, a.item_code, a.item_name, a.description, a.qty, a.stock_qty, a.uom, a.stock_uom, a.conversion_factor
                                                       from `tabSales Order Item` a join `tabSales Order` b
                                                       on a.parent = b.name
                                                       where b.name = '{name}'
                                                   """.format(name=doc.name), as_dict=1)

    for c in so_items:
        items = new_doc.append("items", {})
        items.item_code = c.item_code
        items.item_name = c.item_name
        items.description = c.description
        items.qty = fc.qty
        items.transfer_qty = c.transfer_qty
        items.uom = c.uom
        items.stock_uom = c.stock_uom
        items.conversion_factor = c.conversion_factor
        items.so_item = c.name

    new_doc.insert()
    frappe.msgprint(new_doc.name + " تم إنشاء حركة مخزنية بحالة مسودة رقم ")
    #frappe.msgprint(_("Stock Entry record {0} created").format("<a href='/app/Form/Stock Entry/{0}'>{0}</a>").format(new_doc.name))
    '''
@frappe.whitelist()
def so_on_cancel(doc, method=None):
    pass
@frappe.whitelist()
def so_on_update_after_submit(doc, method=None):
    pass
@frappe.whitelist()
def so_before_save(doc, method=None):
    pass
@frappe.whitelist()
def so_before_cancel(doc, method=None):
    pass
@frappe.whitelist()
def so_on_update(doc, method=None):
    pass


@frappe.whitelist()
def delete_different_price_items(doc, method=None):
    [doc.items.remove(d) for d in doc.items if (d.rate != d.price_list_rate) or (d.rate == 0) or (d.price_list_rate == 0)]

@frappe.whitelist()
def delete_insufficient_stock_items(doc, method=None):
    [doc.items.remove(d) for d in doc.items if (d.qty > d.actual_qty)]



################ Delivery Note

@frappe.whitelist()
def dn_onload(doc, method=None):
    ## Fetch Source Warehouse From Vehicle
    #doc.set_warehouse = frappe.db.get_value("Vehicle", doc.vehicle, "warehouse")

    ## Fetch Accounting Dimensions In Items Table
    for x in doc.items:
        x.warehouse = doc.set_warehouse

@frappe.whitelist()
def dn_before_validate(doc, method=None):
    doc.ignore_pricing_rule = 0

    if doc.customer == "عميل مسحوبات عاملين" and not doc.sell_to_employees:
        frappe.throw("برجاء تحديد الموظف")


    for t in doc.items:
        allowed_uom =frappe.db.get_value('UOM Conversion Detail', {'parent': t.item_code,'uom': t.uom}, ['uom'])
        if allowed_uom != t.uom:
            frappe.throw("Row #" + str(t.idx) + ": وحدة القياس غير معرفة للصنف " + t.item_code)


    ## Fetch Driver Name and Transporter Name
    doc.driver_name = frappe.db.get_value("Driver", doc.driver, "full_name")
    doc.transporter_name = frappe.db.get_value("Supplier", doc.transporter, "name")

    ## Fetch Vehicle From Source Warehouse
    #doc.vehicle = frappe.db.get_value("Warehouse", doc.set_warehouse, "vehicle")

    ## Fetch Branch From Territory
    doc.branch = frappe.db.get_value("Territory", doc.territory, "branch")

    ## Fetch Department From Session User
    user = frappe.session.user
    doc.department = frappe.db.get_value("Employee", {'user_id': user}, "department")

    ## Fetch Cost Center From Customer Group
    customer_group = frappe.db.get_value("Customer", doc.customer, "customer_group")
    doc.cost_center = frappe.db.get_value("Customer Group", customer_group, "cost_center")

    ## Fetch Accounting Dimensions In Items Table
    for x in doc.items:
        x.vehicle = doc.vehicle
        x.territory = doc.territory
        x.branch = doc.branch
        x.department = doc.department
        x.cost_center = doc.cost_center

    ## Fetch Accounting Dimensions In Taxes Table
    for y in doc.taxes:
        y.vehicle = doc.vehicle
        y.territory = doc.territory
        y.branch = doc.branch
        y.department = doc.department
        y.cost_center = doc.cost_center

    delivery_note_list = frappe.db.get_list('Delivery Note', filters=[{'docstatus': ['!=', 2]}], fields=["sales_order", "name"])
    for x in delivery_note_list:
        if doc.sales_order == x.sales_order and doc.sales_order is not None and doc.name != x.name and doc.is_return == 0:
            frappe.throw("Another Delivery Note " + x.name + " Is Linked With The Same Sales Order. ")

    ## Fetch Tax Type From Customer
    default_tax_type = frappe.db.get_value("Customer", doc.customer, "tax_type")
    if not doc.tax_type:
        doc.tax_type = default_tax_type

    ## Calculate Item Rate If Customer Tax Type Is Commercial
    if doc.tax_type == "Commercial":
        doc.set("taxes", [])
        for d in doc.items:
            if not d.margin_type:
                d.discount_percentage = 0
            if d.item_tax_template:
                item_tax_rate = float(
                    frappe.db.get_value("Item Tax Template Detail", {'parent': d.item_tax_template}, "tax_rate"))
                if item_tax_rate > 0:
                    if d.discount_percentage:
                        new_rate = (d.price_list_rate + (item_tax_rate * d.price_list_rate / 100))
                        new_discounted_rate = new_rate - ((d.discount_percentage * new_rate) / 100)
                        d.rate = new_discounted_rate
                        d.net_rate = new_discounted_rate
                        d.base_net_rate = new_discounted_rate
                        d.base_rate = new_discounted_rate
                        d.net_amount = new_discounted_rate * d.qty
                        d.base_net_amount = new_discounted_rate * d.qty
                        d.amount = new_discounted_rate * d.qty
                        d.base_amount = new_discounted_rate * d.qty
                        d.tax_rate = new_rate
                        d.discounted_amount = new_rate * d.discount_percentage / 100
                    else:
                        new_rate = (d.price_list_rate + (item_tax_rate * d.price_list_rate / 100))
                        d.rate = new_rate
                        d.base_rate = new_rate
                        d.amount = new_rate * d.qty
                        d.base_amount = new_rate * d.qty
                        d.tax_rate = new_rate
                else:
                    new_rate = (d.price_list_rate + (item_tax_rate * d.price_list_rate / 100))
                    d.tax_rate = new_rate
        totals = 0
        for x in doc.items:
            totals += x.amount
        if doc.additional_discount_percentage:
            doc.total = totals
            doc.grand_total = totals - doc.discount_amount
            doc.base_grand_total = totals - doc.discount_amount
            doc.net_total = totals - doc.discount_amount
            doc.base_net_total = totals - doc.discount_amount
            doc.base_total = totals - doc.discount_amount
            doc.outstanding_amount = totals - doc.discount_amount
            doc.total_taxes_and_charges = 0

        else:
            doc.total = totals
            doc.grand_total = totals
            doc.base_grand_total = totals
            doc.net_total = totals
            doc.base_net_total = totals
            doc.base_total = totals
            doc.outstanding_amount = totals
            doc.total_taxes_and_charges = 0

    ## Calculate Taxes Table If Customer Tax Type Is Taxable
    if doc.tax_type == "Taxable":
        doc.set("taxes", [])
        new_taxes = 0
        for d in doc.items:
            if d.item_tax_template:
                item_tax_rate = frappe.db.get_value("Item Tax Template Detail", {'parent': d.item_tax_template},
                                                    "tax_rate")
                d.tax_amount = d.net_amount * item_tax_rate / 100
                new_taxes += d.tax_amount

        taxes1 = doc.append("taxes", {})
        taxes1.charge_type = "On Net Total"
        taxes1.account_head = "2301 - ضريبة القيمة المضافة VAT - CA"
        taxes1.description = "2301 - ضريبة القيمة المضافة VAT"
        '''
        taxes1.rate = 0
        taxes1.account_currency = "EGP"
        taxes1.tax_amount = new_taxes
        taxes1.total = doc.total + new_taxes
        taxes1.base_tax_amount = new_taxes
        taxes1.base_total = doc.total + new_taxes
        taxes1.tax_amount_after_discount_amount = new_taxes
        taxes1.base_tax_amount_after_discount_amount = new_taxes
        taxes1.vehicle = doc.vehicle
        taxes1.territory = doc.territory
        taxes1.branch = doc.branch
        taxes1.department = doc.department
        taxes1.cost_center = doc.cost_center
        '''


@frappe.whitelist()
def dn_validate(doc, method=None):
    pass
@frappe.whitelist()
def dn_on_submit(doc, method=None):
    pass
@frappe.whitelist()
def dn_on_cancel(doc, method=None):
    pass
@frappe.whitelist()
def dn_on_update_after_submit(doc, method=None):
    pass
@frappe.whitelist()
def dn_before_save(doc, method=None):
    pass
@frappe.whitelist()
def dn_before_cancel(doc, method=None):
    pass
@frappe.whitelist()
def dn_on_update(doc, method=None):
    pass

################ Sales Invoice


@frappe.whitelist()
def siv_onload(doc, method=None):
    pass
@frappe.whitelist()
def siv_before_validate(doc, method=None):

    #doc.ignore_pricing_rule = 0
    #doc.update_stock = 1
    #if doc.tax_type == "Taxable":
    #    doc.set_warehouse = frappe.db.get_value("Vehicle", doc.vehicle, "warehouse")

    ## Fetch Sales Persons
    #doc.sales_person = frappe.db.get_value("Address", doc.customer_address, "sales_person")
    if not doc.delivery_note and not doc.update_stock and not doc.not_stock:
        frappe.throw("برجاء تحديد المخزن المسحوب منه حيث ان الفاتورة غير مربوطة باذن تسليم للعميل")

    if doc.customer == "عميل مسحوبات عاملين" and not doc.sell_to_employees:
        frappe.throw("برجاء تحديد الموظف")

    for t in doc.items:
        allowed_uom =frappe.db.get_value('UOM Conversion Detail', {'parent': t.item_code,'uom': t.uom}, ['uom'])
        if allowed_uom != t.uom:
            frappe.throw("Row #" + str(t.idx) + ": وحدة القياس غير معرفة للصنف " + t.item_code)

    doc.sales_supervisor = frappe.db.get_value("Sales Person", doc.sales_person, "parent_sales_person")
    doc.territory_manager = frappe.db.get_value("Customer", doc.customer, "sales_person")
    doc.sales_manager = frappe.db.get_value("Customer Group", doc.customer_group, "sales_person")

    ## Fetch Branch From Territory
    doc.branch = frappe.db.get_value("Territory", doc.territory, "branch")

    ## Fetch Department From Session User
    user = frappe.session.user
    doc.department = frappe.db.get_value("Employee", {'user_id': user}, "department")

    ## Fetch Cost Center From Customer Group
    doc.cost_center = frappe.db.get_value("Customer Group", doc.customer_group, "cost_center")

    ## Fetch Accounting Dimensions In Items Table
    for x in doc.items:
        x.vehicle = doc.vehicle
        x.territory = doc.territory
        x.branch = doc.branch
        x.department = doc.department
        x.cost_center = doc.cost_center
        x.warehouse = doc.set_warehouse

    ## Fetch Accounting Dimensions In Taxes Table
    for y in doc.taxes:
        y.vehicle = doc.vehicle
        y.territory = doc.territory
        y.branch = doc.branch
        y.department = doc.department
        y.cost_center = doc.cost_center

    sales_invoice_list = frappe.db.get_list('Sales Invoice', filters=[{'docstatus': ['!=', 2]}], fields=["delivery_note", "name"])
    for x in sales_invoice_list:
        if doc.delivery_note == x.delivery_note and doc.delivery_note is not None and doc.name != x.name and doc.is_return == 0:
            frappe.throw("Another Sales Invoice " + x.name + " Is Linked With The Same Delivery Note. ")

    ## Fetch Tax Type From Customer
    default_tax_type = frappe.db.get_value("Customer", doc.customer, "tax_type")
    if not doc.tax_type:
        doc.tax_type = default_tax_type

    ## Calculate Item Rate If Customer Tax Type Is Commercial
    if doc.tax_type == "Commercial":
        doc.set("taxes", [])
        for d in doc.items:
            if d.item_tax_template:
                item_tax_rate = float(frappe.db.get_value("Item Tax Template Detail", {'parent': d.item_tax_template},
                                                    "tax_rate"))
                if item_tax_rate > 0:
                    if d.discount_percentage:
                        new_rate = (d.price_list_rate + (item_tax_rate * d.price_list_rate / 100))
                        new_discounted_rate = new_rate - ((d.discount_percentage * new_rate )/ 100)
                        d.rate = new_discounted_rate
                        d.net_rate = new_discounted_rate
                        d.base_net_rate = new_discounted_rate
                        d.base_rate = new_discounted_rate
                        d.net_amount = new_discounted_rate * d.qty
                        d.base_net_amount = new_discounted_rate * d.qty
                        d.amount = new_discounted_rate * d.qty
                        d.base_amount = new_discounted_rate * d.qty
                        d.tax_rate = new_rate
                        d.total_with_tax_before_discount_ = new_rate * d.qty
                        d.discounted_amount = new_rate * d.discount_percentage/100
                    else:
                        new_rate = (d.price_list_rate + (item_tax_rate * d.price_list_rate / 100))
                        d.rate = new_rate
                        d.base_rate = new_rate
                        d.amount = new_rate * d.qty
                        d.base_amount = new_rate * d.qty
                        d.total_with_tax_before_discount_ = new_rate * d.qty
                        d.tax_rate = new_rate
                else:
                    new_rate = (d.price_list_rate + (item_tax_rate * d.price_list_rate / 100))
                    d.total_with_tax_before_discount_ = new_rate * d.qty
                    d.tax_rate = new_rate
        totals = 0
        for x in doc.items:
            totals += x.amount
        if doc.additional_discount_percentage:
            doc.total = totals
            doc.grand_total = totals - doc.discount_amount
            doc.rounded_total = totals - doc.discount_amount
            doc.base_rounded_total = totals - doc.discount_amount
            doc.in_words = money_in_words(doc.disable_rounded_total and abs(doc.grand_total) or abs(doc.rounded_total),doc.currency)
            doc.base_in_words = money_in_words(doc.disable_rounded_total and abs(doc.grand_total) or abs(doc.rounded_total), doc.currency)
            doc.base_grand_total = totals - doc.discount_amount
            doc.net_total = totals - doc.discount_amount
            doc.base_net_total = totals - doc.discount_amount
            doc.base_total = totals - doc.discount_amount
            doc.outstanding_amount = totals - doc.discount_amount
            doc.total_taxes_and_charges = 0

        else:
            doc.total = totals
            doc.grand_total = totals
            doc.rounded_total = totals
            doc.base_rounded_total = totals
            doc.in_words = money_in_words(doc.disable_rounded_total and abs(doc.grand_total) or abs(doc.rounded_total),doc.currency)
            doc.base_in_words = money_in_words(doc.disable_rounded_total and abs(doc.grand_total) or abs(doc.rounded_total), doc.currency)
            doc.base_grand_total = totals
            doc.net_total = totals
            doc.base_net_total = totals
            doc.base_total = totals
            doc.outstanding_amount = totals
            doc.total_taxes_and_charges = 0

    ## Calculate Taxes Table If Customer Tax Type Is Taxable
    if doc.tax_type == "Taxable":
        doc.set("taxes", [])
        new_taxes = 0
        for d in doc.items:
            if d.item_tax_template:
                item_tax_rate = frappe.db.get_value("Item Tax Template Detail", {'parent': d.item_tax_template},
                                                    "tax_rate")
                d.tax_amount = d.net_amount * item_tax_rate / 100
                new_taxes += d.tax_amount

        taxes1 = doc.append("taxes", {})
        taxes1.charge_type = "On Net Total"
        taxes1.account_head = "2301 - ضريبة القيمة المضافة VAT - CA"
        taxes1.description = "2301 - ضريبة القيمة المضافة VAT"
        '''
        taxes1.rate = 0
        taxes1.account_currency = "EGP"
        taxes1.tax_amount = new_taxes
        taxes1.total = doc.total + new_taxes
        taxes1.base_tax_amount = new_taxes
        taxes1.base_total = doc.total + new_taxes
        taxes1.tax_amount_after_discount_amount = new_taxes
        taxes1.base_tax_amount_after_discount_amount = new_taxes
        taxes1.vehicle = doc.vehicle
        taxes1.territory = doc.territory
        taxes1.branch = doc.branch
        taxes1.department = doc.department
        taxes1.cost_center = doc.cost_center
        '''




    '''
    ## validate sales invoice items with stock entry items

    for c in doc.items:
        update_qty = frappe.db.sql(""" select qty as qty from `tabStock Entry Detail` where so_item = '{so_item1}' and docstatus = 1""".format(so_item1=c.so_detail),as_dict=1)
        if update_qty:
            for d in update_qty:
                c.qty = d.qty
        
    [doc.items.remove(d) for d in doc.items if not d.st_item]

    '''


    """
    def removeSingleRow(master, detailName):
        theDetail = None
        for detail in master.details:
            if detail.name == detailName:
                theDetail = detail

    
    master.remove(theDetail)
    #master.save()
    #frappe.db.commit()
    """


@frappe.whitelist()
def siv_validate(doc, method=None):
    ## Remove Returned Qty From Sales Invoice
    for p in doc.items:
        if p.dn_detail:
            qty_del = frappe.db.get_value("Delivery Note Item", {'name': p.dn_detail}, "qty")
            qty = frappe.db.get_value("Delivery Note Item", {'name': p.dn_detail}, "returned_qty")
            convert_factor = frappe.db.get_value("Delivery Note Item", {'name': p.dn_detail}, "conversion_factor")
            if qty > 0:
                returned_qty = qty / convert_factor
                new_qty = qty_del - returned_qty
                p.qty = new_qty

    #doc.ignore_pricing_rule = 0

    if not doc.sales_person:
        frappe.throw("مندوب البيع الزامي")

    ## Calculate Item Rate If Customer Tax Type Is Commercial
    if doc.tax_type == "Commercial":
        doc.set("taxes", [])
        #if doc.edit_items_rate_discount:
        for d in doc.items:
            if d.item_tax_template:
                item_tax_rate = float(frappe.db.get_value("Item Tax Template Detail", {'parent': d.item_tax_template}, "tax_rate"))
                if item_tax_rate > 0:
                    if d.discount_percentage:
                        new_rate = (d.price_list_rate + (item_tax_rate * d.price_list_rate / 100))
                        new_discounted_rate = new_rate - ((d.discount_percentage * new_rate) / 100)
                        d.rate = new_discounted_rate
                        d.net_rate = new_discounted_rate
                        d.base_net_rate = new_discounted_rate
                        d.base_rate = new_discounted_rate
                        d.net_amount = new_discounted_rate * d.qty
                        d.base_net_amount = new_discounted_rate * d.qty
                        d.amount = new_discounted_rate * d.qty
                        d.base_amount = new_discounted_rate * d.qty
                        d.tax_rate = new_rate
                        d.total_with_tax_before_discount_ = new_rate * d.qty
                        d.discounted_amount = new_rate * d.discount_percentage / 100
                    else:
                        new_rate = (d.price_list_rate + (item_tax_rate * d.price_list_rate / 100))
                        d.rate = new_rate
                        d.base_rate = new_rate
                        d.amount = new_rate * d.qty
                        d.base_amount = new_rate * d.qty
                        d.total_with_tax_before_discount_ = new_rate * d.qty
                        d.tax_rate = new_rate
                else:
                    new_rate = (d.price_list_rate + (item_tax_rate * d.price_list_rate / 100))
                    d.total_with_tax_before_discount_ = new_rate * d.qty
                    d.tax_rate = new_rate

        totals = 0
        for x in doc.items:
            totals += x.amount
        if doc.additional_discount_percentage:
            doc.total = totals
            doc.grand_total = totals - doc.discount_amount
            doc.rounded_total = totals - doc.discount_amount
            doc.base_rounded_total = totals - doc.discount_amount
            doc.in_words = money_in_words(doc.disable_rounded_total and abs(doc.grand_total) or abs(doc.rounded_total),doc.currency)
            doc.base_in_words = money_in_words(doc.disable_rounded_total and abs(doc.grand_total) or abs(doc.rounded_total), doc.currency)
            doc.base_grand_total = totals - doc.discount_amount
            doc.net_total = totals - doc.discount_amount
            doc.base_net_total = totals - doc.discount_amount
            doc.base_total = totals - doc.discount_amount
            doc.outstanding_amount = totals - doc.discount_amount
            doc.total_taxes_and_charges = 0

        else:
            doc.total = totals
            doc.grand_total = totals
            doc.rounded_total = totals
            doc.base_rounded_total = totals
            doc.in_words = money_in_words(doc.disable_rounded_total and abs(doc.grand_total) or abs(doc.rounded_total),doc.currency)
            doc.base_in_words = money_in_words(doc.disable_rounded_total and abs(doc.grand_total) or abs(doc.rounded_total), doc.currency)
            doc.base_grand_total = totals
            doc.net_total = totals
            doc.base_net_total = totals
            doc.base_total = totals
            doc.outstanding_amount = totals
            doc.total_taxes_and_charges = 0


@frappe.whitelist()
def siv_on_submit(doc, method=None):
    #doc.ignore_pricing_rule = 0

    if doc.tax_type == "Commercial":
        doc.set("taxes", [])
        #if doc.edit_items_rate_discount:
        for d in doc.items:
            if d.item_tax_template:
                item_tax_rate = int(frappe.db.get_value("Item Tax Template Detail", {'parent': d.item_tax_template},"tax_rate"))
                if item_tax_rate > 0 and d.rate <= d.price_list_rate :
                    if d.discount_percentage:
                        new_rate = ( d.price_list_rate + (item_tax_rate * d.price_list_rate / 100) )
                        new_discounted_rate = new_rate - (d.discount_percentage* new_rate / 100)
                        d.rate = new_discounted_rate
                        d.net_rate = new_discounted_rate
                        d.base_net_rate = new_discounted_rate
                        d.base_rate = new_discounted_rate
                        d.net_amount = new_discounted_rate * d.qty
                        d.base_net_amount = new_discounted_rate * d.qty
                        d.amount = new_discounted_rate * d.qty
                        d.base_amount = new_discounted_rate * d.qty
                        d.tax_rate = new_rate
                    else:
                        new_rate = (d.price_list_rate + (item_tax_rate * d.price_list_rate / 100))
                        d.rate = new_rate
                        d.base_rate = new_rate
                        d.amount = new_rate * d.qty
                        d.base_amount = new_rate * d.qty
                        d.tax_rate = new_rate
                else:
                    new_rate = ( d.price_list_rate + (item_tax_rate * d.price_list_rate / 100) )
                    d.tax_rate = new_rate
            else:
                item_tax_rate = frappe.db.get_value("Item Tax Template Detail", {'parent': d.item_tax_template},"tax_rate")
                new_rate = ( d.price_list_rate + (item_tax_rate * d.price_list_rate / 100) )
                d.tax_rate = new_rate

        totals = 0
        for x in doc.items:
            totals += x.amount
        if doc.additional_discount_percentage:
            doc.total = totals 
            doc.grand_total = totals - doc.discount_amount
            doc.rounded_total = totals - doc.discount_amount
            doc.base_rounded_total = totals - doc.discount_amount
            doc.in_words = money_in_words(doc.disable_rounded_total and abs(doc.grand_total) or abs(doc.rounded_total),doc.currency)
            doc.base_in_words = money_in_words(doc.disable_rounded_total and abs(doc.grand_total) or abs(doc.rounded_total), doc.currency)
            doc.base_grand_total = totals - doc.discount_amount
            doc.net_total = totals - doc.discount_amount
            doc.base_net_total = totals - doc.discount_amount
            doc.base_total = totals - doc.discount_amount
            doc.outstanding_amount = totals - doc.discount_amount
            doc.total_taxes_and_charges = 0

        else:
            doc.total = totals
            doc.grand_total = totals
            doc.rounded_total = totals
            doc.base_rounded_total = totals
            doc.in_words = money_in_words(doc.disable_rounded_total and abs(doc.grand_total) or abs(doc.rounded_total), doc.currency)
            doc.base_in_words = money_in_words(doc.disable_rounded_total and abs(doc.grand_total) or abs(doc.rounded_total), doc.currency)
            doc.base_grand_total = totals
            doc.net_total = totals
            doc.base_net_total = totals
            doc.base_total = totals
            doc.outstanding_amount = totals
            doc.total_taxes_and_charges = 0

    if doc.sell_to_employees and doc.is_return == 0:
        references = [
            {
                "doctype": "Payment Entry Reference",
                "reference_doctype": "Sales Invoice",
                "reference_name": doc.name,
                "due_date": doc.posting_date,
                "allocated_amount": doc.grand_total,
                "outstanding_amount": doc.grand_total
            }
        ]
        pe_doc = frappe.get_doc({
            "doctype": "Payment Entry",
            "posting_date": doc.posting_date,
            "payment_type": "Receive",
            "mode_of_payment": "مشتريات عاملين",
            "paid_to": "1321 - تسوية مشتريات عاملين - CA",
            "party_type": "Customer",
            "party": doc.customer,
            "paid_amount": doc.net_total,
            "received_amount": doc.net_total,
            "reference_date": doc.posting_date,
            "source_exchange_rate": 1,
            "target_exchange_rate": 1,
            "references": references
        })
        pe_doc.insert(ignore_permissions=True)
        pe_doc.submit()

        new_doc = frappe.new_doc('Loan')
        new_doc.applicant_type = 'Employee'
        new_doc.applicant = doc.employee_code
        new_doc.applicant_name = doc.employee_name
        new_doc.repay_from_salary = 1
        new_doc.repayment_start_date = doc.posting_date
        new_doc.loan_type = 'مشتريات'
        new_doc.loan_amount = doc.net_total
        new_doc.repayment_method = 'Repay Fixed Amount per Period'
        new_doc.invoice = doc.name
        new_doc.monthly_repayment_amount = doc.net_total
        new_doc.insert(ignore_permissions=True)
        new_doc.submit()

        '''
        for x in doc.sell_to_employee_table:
            new_doc = frappe.new_doc('Loan')
            new_doc.applicant_type = 'Employee'
            new_doc.applicant = x.employee_code
            new_doc.applicant_name = x.employee_name
            new_doc.repay_from_salary = 1
            new_doc.repayment_start_date = doc.posting_date
            new_doc.loan_type = 'مشتريات'
            new_doc.loan_amount = x.amount
            new_doc.repayment_method = 'Repay Fixed Amount per Period'
            new_doc.monthly_repayment_amount = x.amount
            new_doc.insert()
            new_doc.submit()
        '''

    if doc.sell_to_employees and doc.is_return == 1 and doc.return_against:
        loan = frappe.get_doc('Loan', {'invoice': doc.return_against})
        repayment = frappe.new_doc('Loan Repayment')
        repayment.against_loan = loan.name
        repayment.applicant_type = "Employee"
        repayment.applicant = loan.applicant
        repayment.posting_date = doc.posting_date
        repayment.amount_paid = -1 * doc.grand_total
        repayment.insert(ignore_permissions=True)
        repayment.submit()


@frappe.whitelist()
def siv_on_cancel(doc, method=None):
    pass
    #if doc.sell_to_employees:
        #pe_name = frappe.db.sql(""" select parent as parent from `tabPayment Entry Reference` where reference_name = '{invoice}' """.format(invoice=doc.name),as_dict=1)
        #for g in pe_name :
        #    pe = frappe.get_doc('Payment Entry', g.parent)
        #    frappe.throw(pe)
        #loan = frappe.db.get_value('Loan', {'invoice': doc.name}, ['name'])
        #loan1 = frappe.get_doc('Loan', loan) 
        #loan1.cancel()  

@frappe.whitelist()
def siv_on_update_after_submit(doc, method=None):
    pass
@frappe.whitelist()
def siv_before_save(doc, method=None):
    pass
@frappe.whitelist()
def siv_before_cancel(doc, method=None):
    pass
@frappe.whitelist()
def siv_on_update(doc, method=None):
    pass



################ Payment Entry

@frappe.whitelist()
def pe_before_insert(doc, method=None):
    if doc.payment_type == "Internal Transfer":
        doc.paid_to = frappe.db.get_value("Mode of Payment Account", {'parent': doc.mode_of_payment_2},
                                          'default_account')

@frappe.whitelist()
def pe_onload(doc, method=None):
    if doc.payment_type == "Internal Transfer":
        doc.paid_to = frappe.db.get_value("Mode of Payment Account", {'parent': doc.mode_of_payment_2},
                                          'default_account')
@frappe.whitelist()
def pe_before_validate(doc, method=None):
    ## Fetch Sales Persons
    if doc.party_type == "Customer":
        user = frappe.session.user
        employee = frappe.db.get_value("Employee", {'user_id': user}, "name")
        customer_group = frappe.db.get_value("Customer", doc.party, "customer_group")
        current_sales_person = frappe.db.get_value("Sales Person", {'employee': employee}, "name")
        #if current_sales_person:
            #doc.sales_person = current_sales_person
        if not current_sales_person and not doc.sales_person and doc.mode_of_payment != "مشتريات عاملين":
            #frappe.throw(" قم باختيار مندوب البيع")
            pass
        doc.sales_supervisor = frappe.db.get_value("Sales Person", doc.sales_person, "parent_sales_person")
        doc.territory_manager = frappe.db.get_value("Customer", doc.party, "sales_person")
        doc.sales_manager = frappe.db.get_value("Customer Group", customer_group, "sales_person")

    ## Fetch Territory From Customer
    doc.territory = frappe.db.get_value("Customer", doc.party, "territory")

    ## Fetch Branch From Territory
    doc.branch = frappe.db.get_value("Territory", doc.territory, "branch")

    ## Fetch Department From Session User
    user = frappe.session.user
    doc.department = frappe.db.get_value("Employee", {'user_id': user}, "department")

    ## Fetch Cost Center From Customer Group
    customer_group = frappe.db.get_value("Customer", doc.party, "customer_group")
    doc.cost_center = frappe.db.get_value("Customer Group", customer_group, "cost_center")

    ## Fetch Accounting Dimensions In Taxes Table
    for x in doc.taxes:
        x.cost_center = doc.cost_center

    ## Fetch Accounting Dimensions In Taxes Table
    for y in doc.deductions:
        y.territory = doc.territory
        y.branch = doc.branch
        y.department = doc.department
        y.cost_center = doc.cost_center

    if doc.payment_type == "Internal Transfer":
        doc.paid_to = frappe.db.get_value("Mode of Payment Account", {'parent': doc.mode_of_payment_2}, 'default_account')

@frappe.whitelist()
def pe_validate(doc, method=None):
    customer_tax_type = frappe.db.get_value("Customer", doc.party, "tax_type")
    supplier_tax_type = frappe.db.get_value("Supplier", doc.party, "tax_type")
    if not doc.tax_type and doc.party_type == "Customer":
        doc.tax_type = customer_tax_type

    if not doc.tax_type and doc.party_type == "Supplier":
        doc.tax_type = supplier_tax_type

    else:
        pass


@frappe.whitelist()
def pe_on_submit(doc, method=None):
    pass
@frappe.whitelist()
def pe_on_cancel(doc, method=None):
    pass
@frappe.whitelist()
def pe_on_update_after_submit(doc, method=None):
    pass
@frappe.whitelist()
def pe_before_save(doc, method=None):
    pass
@frappe.whitelist()
def pe_before_cancel(doc, method=None):
    pass
@frappe.whitelist()
def pe_on_update(doc, method=None):
    pass

################ Material Request

@frappe.whitelist()
def mr_onload(doc, method=None):
    pass
@frappe.whitelist()
def mr_before_validate(doc, method=None):
    ## Fetch Accounting Dimensions In Taxes Table
    for y in doc.items:
        y.from_warehouse = doc.set_from_warehouse
        y.warehouse = doc.set_warehouse
@frappe.whitelist()
def mr_validate(doc, method=None):
    pass
@frappe.whitelist()
def mr_on_submit(doc, method=None):
    user = frappe.session.user
    lang = frappe.db.get_value("User", {'name': user}, "language")

    ## Auto Create Draft Stock Entry On Submit
    if doc.material_request_type == "Material Transfer":
        new_doc = frappe.get_doc({
            "doctype": "Stock Entry",
            "stock_entry_type": "Material Transfer",
            "posting_date": doc.transaction_date,
            "from_warehouse": doc.set_from_warehouse,
            "to_warehouse": doc.set_warehouse,
        })
        mr_items = frappe.db.sql(""" select a.name, a.idx, a.item_code, a.item_name, a.description, a.qty, a.stock_qty, a.uom, a.stock_uom, a.conversion_factor
                                                               from `tabMaterial Request Item` a join `tabMaterial Request` b
                                                               on a.parent = b.name
                                                               where b.name = '{name}'
                                                           """.format(name=doc.name), as_dict=1)

        for c in mr_items:
            items = new_doc.append("items", {})
            items.idx = c.idx
            items.item_code = c.item_code
            items.item_name = c.item_name
            items.description = c.description
            items.qty = c.qty
            items.transfer_qty = c.transfer_qty
            items.uom = c.uom
            items.stock_uom = c.stock_uom
            items.conversion_factor = c.conversion_factor
            items.material_request = doc.name
            items.material_request_item = c.name

        new_doc.insert()
        if lang == "ar":
            frappe.msgprint(" تم إنشاء حركة مخزنية بحالة مسودة رقم " + new_doc.name)
        else:
            frappe.msgprint(" Stock Entry record " + new_doc.name + " created ")
            #frappe.msgprint(_("Stock Entry record {0} created").format("<a href='https://erp.classatrading.com/app/stock-entry/{0}'>{0}</a>").format(x))

@frappe.whitelist()
def mr_on_cancel(doc, method=None):
    pass
@frappe.whitelist()
def mr_on_update_after_submit(doc, method=None):
    pass
@frappe.whitelist()
def mr_before_save(doc, method=None):
    pass
@frappe.whitelist()
def mr_before_cancel(doc, method=None):
    pass
@frappe.whitelist()
def mr_on_update(doc, method=None):
    pass

################ Purchase Order

@frappe.whitelist()
def po_onload(doc, method=None):
    pass
@frappe.whitelist()
def po_before_validate(doc, method=None):
    ## Fetch Cost Center From Supplier Group
    supplier_group = frappe.db.get_value("Supplier", doc.supplier, "supplier_group")
    cost_center = frappe.db.get_value("Supplier Group", supplier_group, "cost_center")

    ## Fetch Department From Session User
    user = frappe.session.user
    department = frappe.db.get_value("Employee", {'user_id': user}, "department")

    ## Fetch Accounting Dimensions In Items Table
    for y in doc.items:
        y.department = department
        y.cost_center = cost_center

    ##fetch_tax_type_from_Supplier
    default_tax_type = frappe.db.get_value("Supplier", doc.supplier, "tax_type")
    if not doc.tax_type:
        doc.tax_type = default_tax_type

    ## Calculate Item Rate If Supplier Tax Type Is Commercial
    if doc.tax_type == "Commercial":
        doc.set("taxes", [])
        for d in doc.items:
            if d.item_tax_template:
                item_tax_rate = float(
                    frappe.db.get_value("Item Tax Template Detail", {'parent': d.item_tax_template},
                                        "tax_rate"))
                if item_tax_rate > 0:
                    if d.discount_percentage:
                        new_rate = (d.price_list_rate + (item_tax_rate * d.price_list_rate / 100))
                        new_discounted_rate = new_rate - ((d.discount_percentage * new_rate) / 100)
                        d.rate = new_discounted_rate
                        d.net_rate = new_discounted_rate
                        d.base_net_rate = new_discounted_rate
                        d.base_rate = new_discounted_rate
                        d.net_amount = new_discounted_rate * d.qty
                        d.base_net_amount = new_discounted_rate * d.qty
                        d.amount = new_discounted_rate * d.qty
                        d.base_amount = new_discounted_rate * d.qty
                        d.tax_rate = new_rate
                        d.discounted_amount = new_rate * d.discount_percentage / 100
                    else:
                        new_rate = (d.price_list_rate + (item_tax_rate * d.price_list_rate / 100))
                        d.rate = new_rate
                        d.base_rate = new_rate
                        d.amount = new_rate * d.qty
                        d.base_amount = new_rate * d.qty
                        d.tax_rate = new_rate
                else:
                    new_rate = (d.price_list_rate + (item_tax_rate * d.price_list_rate / 100))
                    d.tax_rate = new_rate
        totals = 0
        for x in doc.items:
            totals += x.amount
        if doc.additional_discount_percentage:
            doc.total = totals
            doc.grand_total = totals - doc.discount_amount
            doc.base_grand_total = totals - doc.discount_amount
            doc.net_total = totals - doc.discount_amount
            doc.base_net_total = totals - doc.discount_amount
            doc.base_total = totals - doc.discount_amount
            doc.outstanding_amount = totals - doc.discount_amount
            doc.total_taxes_and_charges = 0

        else:
            doc.total = totals
            doc.grand_total = totals
            doc.base_grand_total = totals
            doc.net_total = totals
            doc.base_net_total = totals
            doc.base_total = totals
            doc.outstanding_amount = totals
            doc.total_taxes_and_charges = 0


    ## Remove Taxes Table
    for d in doc.taxes:
        account_type = frappe.db.get_value("Account", d.account_head, "account_type")
        if doc.tax_type == "Taxable" and doc.purchase_request_type == "Imported" and account_type == "Tax":
            doc.set("taxes", [])

    ## Calculate Taxes Table
    if doc.tax_type == "Taxable" and (doc.purchase_request_type == "Local" or doc.purchase_request_type == "Spare Parts"):
        doc.set("taxes", [])
        new_taxes = 0
        for d in doc.items:
            if d.item_tax_template:
                item_tax_rate = frappe.db.get_value("Item Tax Template Detail", {'parent': d.item_tax_template}, "tax_rate")
                d.tax_amount = d.net_amount * item_tax_rate / 100
                new_taxes += d.tax_amount

        taxes1 = doc.append("taxes", {})
        taxes1.category = "Total"
        taxes1.add_deduct_tax = "Add"
        taxes1.charge_type = "On Net Total"
        taxes1.account_head = "2301 - ضريبة القيمة المضافة VAT - CA"
        taxes1.description = "2301 - ضريبة القيمة المضافة VAT"


        if doc.ci_profits == "1%":
            taxes2 = doc.append("taxes", {})
            taxes2.category = "Total"
            taxes2.add_deduct_tax = "Deduct"
            taxes2.charge_type = "On Net Total"
            taxes2.rate = 1
            taxes2.account_head = "2302 - ارباح تجارية وصناعية - موردين - CA"
            taxes2.description = "2302 - ارباح تجارية وصناعية - موردين"

        if doc.ci_profits == "3%":
            taxes2 = doc.append("taxes", {})
            taxes2.category = "Total"
            taxes2.add_deduct_tax = "Deduct"
            taxes2.charge_type = "On Net Total"
            taxes2.rate = 3
            taxes2.account_head = "2302 - ارباح تجارية وصناعية - موردين - CA"
            taxes2.description = "2302 - ارباح تجارية وصناعية - موردين"

        if doc.ci_profits == "5%":
            taxes2 = doc.append("taxes", {})
            taxes2.category = "Total"
            taxes2.add_deduct_tax = "Deduct"
            taxes2.charge_type = "On Net Total"
            taxes2.rate = 5
            taxes2.account_head = "2302 - ارباح تجارية وصناعية - موردين - CA"
            taxes2.description = "2302 - ارباح تجارية وصناعية - موردين"

@frappe.whitelist()
def po_validate(doc, method=None):
    pass
@frappe.whitelist()
def po_on_submit(doc, method=None):
    pass
@frappe.whitelist()
def po_on_cancel(doc, method=None):
    pass
@frappe.whitelist()
def po_on_update_after_submit(doc, method=None):
    pass
@frappe.whitelist()
def po_before_save(doc, method=None):
    pass
@frappe.whitelist()
def po_before_cancel(doc, method=None):
    pass
@frappe.whitelist()
def po_on_update(doc, method=None):
    pass

################ Purchase Receipt

@frappe.whitelist()
def pr_onload(doc, method=None):
    pass
@frappe.whitelist()
def pr_before_validate(doc, method=None):
    ##fetch_tax_type_from_Supplier
    default_tax_type = frappe.db.get_value("Supplier", doc.supplier, "tax_type")
    if not doc.tax_type:
        doc.tax_type = default_tax_type

    ## Calculate Item Rate If Supplier Tax Type Is Commercial
    if doc.tax_type == "Commercial":
        doc.set("taxes", [])
        for d in doc.items:
            if d.item_tax_template:
                item_tax_rate = float(
                    frappe.db.get_value("Item Tax Template Detail", {'parent': d.item_tax_template},
                                        "tax_rate"))
                if item_tax_rate > 0:
                    if d.discount_percentage:
                        new_rate = (d.price_list_rate + (item_tax_rate * d.price_list_rate / 100))
                        new_discounted_rate = new_rate - ((d.discount_percentage * new_rate) / 100)
                        d.rate = new_discounted_rate
                        d.net_rate = new_discounted_rate
                        d.base_net_rate = new_discounted_rate
                        d.base_rate = new_discounted_rate
                        d.net_amount = new_discounted_rate * d.qty
                        d.base_net_amount = new_discounted_rate * d.qty
                        d.amount = new_discounted_rate * d.qty
                        d.base_amount = new_discounted_rate * d.qty
                        d.tax_rate = new_rate
                        d.discounted_amount = new_rate * d.discount_percentage / 100
                    else:
                        new_rate = (d.price_list_rate + (item_tax_rate * d.price_list_rate / 100))
                        d.rate = new_rate
                        d.base_rate = new_rate
                        d.amount = new_rate * d.qty
                        d.base_amount = new_rate * d.qty
                        d.tax_rate = new_rate
                else:
                    new_rate = (d.price_list_rate + (item_tax_rate * d.price_list_rate / 100))
                    d.tax_rate = new_rate
        totals = 0
        for x in doc.items:
            totals += x.amount
        if doc.additional_discount_percentage:
            doc.total = totals
            doc.grand_total = totals - doc.discount_amount
            doc.base_grand_total = totals - doc.discount_amount
            doc.net_total = totals - doc.discount_amount
            doc.base_net_total = totals - doc.discount_amount
            doc.base_total = totals - doc.discount_amount
            doc.outstanding_amount = totals - doc.discount_amount
            doc.total_taxes_and_charges = 0

        else:
            doc.total = totals
            doc.grand_total = totals
            doc.base_grand_total = totals
            doc.net_total = totals
            doc.base_net_total = totals
            doc.base_total = totals
            doc.outstanding_amount = totals
            doc.total_taxes_and_charges = 0

    ## Remove Taxes Table
    for d in doc.taxes:
        account_type = frappe.db.get_value("Account", d.account_head, "account_type")
        if doc.tax_type == "Taxable" and doc.purchase_request_type == "Imported" and account_type == "Tax":
            doc.set("taxes", [])

    ## Calculate Taxes Table
    if doc.tax_type == "Taxable" and (
            doc.purchase_request_type == "Local" or doc.purchase_request_type == "Spare Parts"):
        doc.set("taxes", [])
        new_taxes = 0
        for d in doc.items:
            if d.item_tax_template:
                item_tax_rate = frappe.db.get_value("Item Tax Template Detail", {'parent': d.item_tax_template},
                                                    "tax_rate")
                d.tax_amount = d.net_amount * item_tax_rate / 100
                new_taxes += d.tax_amount

        taxes1 = doc.append("taxes", {})
        taxes1.category = "Total"
        taxes1.add_deduct_tax = "Add"
        taxes1.charge_type = "On Net Total"
        taxes1.account_head = "2301 - ضريبة القيمة المضافة VAT - CA"
        taxes1.description = "2301 - ضريبة القيمة المضافة VAT"


        if doc.ci_profits == "1%":
            taxes2 = doc.append("taxes", {})
            taxes2.category = "Total"
            taxes2.add_deduct_tax = "Deduct"
            taxes2.charge_type = "On Net Total"
            taxes2.rate = 1
            taxes2.account_head = "2302 - ارباح تجارية وصناعية - موردين - CA"
            taxes2.description = "2302 - ارباح تجارية وصناعية - موردين"

        if doc.ci_profits == "3%":
            taxes2 = doc.append("taxes", {})
            taxes2.category = "Total"
            taxes2.add_deduct_tax = "Deduct"
            taxes2.charge_type = "On Net Total"
            taxes2.rate = 3
            taxes2.account_head = "2302 - ارباح تجارية وصناعية - موردين - CA"
            taxes2.description = "2302 - ارباح تجارية وصناعية - موردين"

        if doc.ci_profits == "5%":
            taxes2 = doc.append("taxes", {})
            taxes2.category = "Total"
            taxes2.add_deduct_tax = "Deduct"
            taxes2.charge_type = "On Net Total"
            taxes2.rate = 5
            taxes2.account_head = "2302 - ارباح تجارية وصناعية - موردين - CA"
            taxes2.description = "2302 - ارباح تجارية وصناعية - موردين"
            
@frappe.whitelist()
def pr_validate(doc, method=None):
    pass
@frappe.whitelist()
def pr_on_submit(doc, method=None):
    pass
@frappe.whitelist()
def pr_on_cancel(doc, method=None):
    pass
@frappe.whitelist()
def pr_on_update_after_submit(doc, method=None):
    pass
@frappe.whitelist()
def pr_before_save(doc, method=None):
    pass
@frappe.whitelist()
def pr_before_cancel(doc, method=None):
    pass
@frappe.whitelist()
def pr_on_update(doc, method=None):
    pass


################ Purchase Invoice

@frappe.whitelist()
def piv_onload(doc, method=None):
    pass
@frappe.whitelist()
def piv_before_validate(doc, method=None):
    '''
    ## Calculate Item Rate If Supplier Tax Type Is Taxable
    if doc.tax_type == "Commercial":
        doc.set("taxes", [])
        for d in doc.items:
            if d.item_tax_template:
                item_tax_rate = frappe.db.get_value("Item Tax Template Detail", {'parent': d.item_tax_template},
                                                    "tax_rate")
                if item_tax_rate > 0 and d.rate <= d.price_list_rate:
                    new_rate = d.rate + (item_tax_rate * d.rate / 100)
                    d.rate = new_rate

                else:
                    pass
            else:
                pass
    '''

    ##fetch_tax_type_from_Supplier
    default_tax_type = frappe.db.get_value("Supplier", doc.supplier, "tax_type")
    if not doc.tax_type:
        doc.tax_type = default_tax_type

    ## Calculate Item Rate If Supplier Tax Type Is Commercial
    if doc.tax_type == "Commercial":
        doc.set("taxes", [])
        for d in doc.items:
            if d.item_tax_template:
                item_tax_rate = float(
                    frappe.db.get_value("Item Tax Template Detail", {'parent': d.item_tax_template},
                                        "tax_rate"))
                if item_tax_rate > 0:
                    if d.discount_percentage:
                        new_rate = (d.price_list_rate + (item_tax_rate * d.price_list_rate / 100))
                        new_discounted_rate = new_rate - ((d.discount_percentage * new_rate) / 100)
                        d.rate = new_discounted_rate
                        d.net_rate = new_discounted_rate
                        d.base_net_rate = new_discounted_rate
                        d.base_rate = new_discounted_rate
                        d.net_amount = new_discounted_rate * d.qty
                        d.base_net_amount = new_discounted_rate * d.qty
                        d.amount = new_discounted_rate * d.qty
                        d.base_amount = new_discounted_rate * d.qty
                        d.tax_rate = new_rate
                        d.discounted_amount = new_rate * d.discount_percentage / 100
                    else:
                        new_rate = (d.price_list_rate + (item_tax_rate * d.price_list_rate / 100))
                        d.rate = new_rate
                        d.base_rate = new_rate
                        d.amount = new_rate * d.qty
                        d.base_amount = new_rate * d.qty
                        d.tax_rate = new_rate
                else:
                    new_rate = (d.price_list_rate + (item_tax_rate * d.price_list_rate / 100))
                    d.tax_rate = new_rate
        totals = 0
        for x in doc.items:
            totals += x.amount
        if doc.additional_discount_percentage:
            doc.total = totals
            doc.grand_total = totals - doc.discount_amount
            doc.base_grand_total = totals - doc.discount_amount
            doc.net_total = totals - doc.discount_amount
            doc.base_net_total = totals - doc.discount_amount
            doc.base_total = totals - doc.discount_amount
            doc.outstanding_amount = totals - doc.discount_amount
            doc.total_taxes_and_charges = 0

        else:
            doc.total = totals
            doc.grand_total = totals
            doc.base_grand_total = totals
            doc.net_total = totals
            doc.base_net_total = totals
            doc.base_total = totals
            doc.outstanding_amount = totals
            doc.total_taxes_and_charges = 0

    ## Remove Taxes Table
    for d in doc.taxes:
        account_type = frappe.db.get_value("Account", d.account_head, "account_type")
        if doc.tax_type == "Taxable" and doc.purchase_request_type == "Imported" and account_type == "Tax":
            doc.set("taxes", [])

    ## Calculate Taxes Table
    if doc.tax_type == "Taxable" and (doc.purchase_request_type == "Local" or doc.purchase_request_type == "Spare Parts"):
        doc.set("taxes", [])
        new_taxes = 0
        for d in doc.items:
            if d.item_tax_template:
                item_tax_rate = frappe.db.get_value("Item Tax Template Detail",
                                                    {'parent': d.item_tax_template},
                                                    "tax_rate")
                d.tax_amount = d.net_amount * item_tax_rate / 100
                new_taxes += d.tax_amount

        taxes1 = doc.append("taxes", {})
        taxes1.category = "Total"
        taxes1.add_deduct_tax = "Add"
        taxes1.charge_type = "On Net Total"
        taxes1.account_head = "2301 - ضريبة القيمة المضافة VAT - CA"
        taxes1.description = "2301 - ضريبة القيمة المضافة VAT"

        if doc.ci_profits == "1%":
            taxes2 = doc.append("taxes", {})
            taxes2.category = "Total"
            taxes2.add_deduct_tax = "Deduct"
            taxes2.charge_type = "On Net Total"
            taxes2.rate = 1
            taxes2.account_head = "2302 - ارباح تجارية وصناعية - موردين - CA"
            taxes2.description = "2302 - ارباح تجارية وصناعية - موردين"

        if doc.ci_profits == "3%":
            taxes2 = doc.append("taxes", {})
            taxes2.category = "Total"
            taxes2.add_deduct_tax = "Deduct"
            taxes2.charge_type = "On Net Total"
            taxes2.rate = 3
            taxes2.account_head = "2302 - ارباح تجارية وصناعية - موردين - CA"
            taxes2.description = "2302 - ارباح تجارية وصناعية - موردين"

        if doc.ci_profits == "5%":
            taxes2 = doc.append("taxes", {})
            taxes2.category = "Total"
            taxes2.add_deduct_tax = "Deduct"
            taxes2.charge_type = "On Net Total"
            taxes2.rate = 5
            taxes2.account_head = "2302 - ارباح تجارية وصناعية - موردين - CA"
            taxes2.description = "2302 - ارباح تجارية وصناعية - موردين"


    ## Fetch Cost Center From Supplier Group
    supplier_group = frappe.db.get_value("Supplier", doc.supplier, "supplier_group")
    doc.cost_center = frappe.db.get_value("Supplier Group", supplier_group, "cost_center")

    ## Fetch Department From Session User
    user = frappe.session.user
    doc.department = frappe.db.get_value("Employee", {'user_id': user}, "department")

    ## Fetch Accounting Dimensions In Items Table
    for y in doc.items:
        y.department = doc.department
        y.cost_center = doc.cost_center

@frappe.whitelist()
def piv_validate(doc, method=None):
    ##fetch_tax_type_from_Supplier
    default_tax_type = frappe.db.get_value("Supplier", doc.supplier, "tax_type")
    if not doc.tax_type:
        doc.tax_type = default_tax_type

    else:
        pass

@frappe.whitelist()
def piv_on_submit(doc, method=None):
    ## Calculate Item Rate If Supplier Tax Type Is Commercial
    if doc.tax_type == "Commercial":
        doc.set("taxes", [])
        for d in doc.items:
            if d.item_tax_template:
                item_tax_rate = float(
                    frappe.db.get_value("Item Tax Template Detail", {'parent': d.item_tax_template},
                                        "tax_rate"))
                if item_tax_rate > 0:
                    if d.discount_percentage:
                        new_rate = (d.price_list_rate + (item_tax_rate * d.price_list_rate / 100))
                        new_discounted_rate = new_rate - ((d.discount_percentage * new_rate) / 100)
                        d.rate = new_discounted_rate
                        d.net_rate = new_discounted_rate
                        d.base_net_rate = new_discounted_rate
                        d.base_rate = new_discounted_rate
                        d.net_amount = new_discounted_rate * d.qty
                        d.base_net_amount = new_discounted_rate * d.qty
                        d.amount = new_discounted_rate * d.qty
                        d.base_amount = new_discounted_rate * d.qty
                        d.tax_rate = new_rate
                        d.discounted_amount = new_rate * d.discount_percentage / 100
                    else:
                        new_rate = (d.price_list_rate + (item_tax_rate * d.price_list_rate / 100))
                        d.rate = new_rate
                        d.base_rate = new_rate
                        d.amount = new_rate * d.qty
                        d.base_amount = new_rate * d.qty
                        d.tax_rate = new_rate
                else:
                    new_rate = (d.price_list_rate + (item_tax_rate * d.price_list_rate / 100))
                    d.tax_rate = new_rate
        totals = 0
        for x in doc.items:
            totals += x.amount
        if doc.additional_discount_percentage:
            doc.total = totals
            doc.grand_total = totals - doc.discount_amount
            doc.base_grand_total = totals - doc.discount_amount
            doc.net_total = totals - doc.discount_amount
            doc.base_net_total = totals - doc.discount_amount
            doc.base_total = totals - doc.discount_amount
            doc.outstanding_amount = totals - doc.discount_amount
            doc.total_taxes_and_charges = 0

        else:
            doc.total = totals
            doc.grand_total = totals
            doc.base_grand_total = totals
            doc.net_total = totals
            doc.base_net_total = totals
            doc.base_total = totals
            doc.outstanding_amount = totals
            doc.total_taxes_and_charges = 0

@frappe.whitelist()
def piv_on_cancel(doc, method=None):
    pass
@frappe.whitelist()
def piv_on_update_after_submit(doc, method=None):
    pass
@frappe.whitelist()
def piv_before_save(doc, method=None):
    pass

@frappe.whitelist()
def piv_before_cancel(doc, method=None):
    pass
@frappe.whitelist()
def piv_on_update(doc, method=None):
    pass

################ Employee Advance

@frappe.whitelist()
def emad_onload(doc, method=None):
    pass
@frappe.whitelist()
def emad_before_validate(doc, method=None):
    pass
@frappe.whitelist()
def emad_validate(doc, method=None):
    pass
@frappe.whitelist()
def emad_on_submit(doc, method=None):
    pass
@frappe.whitelist()
def emad_on_cancel(doc, method=None):
    pass
@frappe.whitelist()
def emad_on_update_after_submit(doc, method=None):
    pass
@frappe.whitelist()
def emad_before_save(doc, method=None):
    pass
@frappe.whitelist()
def emad_before_cancel(doc, method=None):
    pass
@frappe.whitelist()
def emad_on_update(doc, method=None):
    pass

################ Expense Claim

@frappe.whitelist()
def excl_onload(doc, method=None):
    pass
@frappe.whitelist()
def excl_before_validate(doc, method=None):
    ## Fetch Vehicle From Vehicle Log
    doc.vehicle = frappe.db.get_value("Vehicle Log", doc.vehicle_log, "license_plate")

    ## Fetch Cost Center From Department
    #doc.cost_center = frappe.db.get_value("Department", doc.department, "payroll_cost_center")

    ## Fetch Accounting Dimensions In Expenses Table
    for x in doc.expenses:
        x.vehicle = doc.vehicle
        x.territory = doc.territory
        x.branch = doc.branch
        x.department = doc.department

    ## Fetch Accounting Dimensions In Taxes Table
    for y in doc.taxes:
        y.vehicle = doc.vehicle
        y.territory = doc.territory
        y.branch = doc.branch
        y.department = doc.department


@frappe.whitelist()
def excl_validate(doc, method=None):
    pass
@frappe.whitelist()
def excl_on_submit(doc, method=None):
    if doc.workflow_state == "Accounts Manager Approved" and doc.grand_total == 0:
        frappe.throw(" من فضلك اعتمد المبلغ ")
@frappe.whitelist()
def excl_on_cancel(doc, method=None):
    pass
@frappe.whitelist()
def excl_on_update_after_submit(doc, method=None):
    pass
@frappe.whitelist()
def excl_before_save(doc, method=None):
    pass
@frappe.whitelist()
def excl_before_cancel(doc, method=None):
    pass
@frappe.whitelist()
def excl_on_update(doc, method=None):
    pass

################ Stock Entry

@frappe.whitelist()
def ste_onload(doc, method=None):
    pass
@frappe.whitelist()
def ste_before_validate(doc, method=None):
    for t in doc.items:
        allowed_uom =frappe.db.get_value('UOM Conversion Detail', {'parent': t.item_code,'uom': t.uom}, ['uom'])
        if allowed_uom != t.uom:
            frappe.throw("Row #" + str(t.idx) + ": وحدة القياس غير معرفة للصنف " + t.item_code)

    if doc.sales_order:
        so = frappe.get_doc("Sales Order", doc.sales_order)
        doc.customer = so.customer
        doc.customer_address = so.customer_address
        #doc.save()

    ## Fetch Vehcile From Target Warehouse
    doc.vehicle = frappe.db.get_value("Warehouse", doc.to_warehouse, "vehicle")

    ## Fetch Branch From Territory
    doc.branch = frappe.db.get_value("Territory", doc.territory, "branch")

    ## Fetch Department From Session User
    user = frappe.session.user
    doc.department = frappe.db.get_value("Employee", {'user_id': user}, "department")

    ## Fetch Cost Center From Customer Group
    if doc.customer:
        customer_group = frappe.db.get_value("Customer", doc.customer, "customer_group")
        doc.cost_center = frappe.db.get_value("Customer Group", customer_group, "cost_center")

    ## Fetch Accounting Dimensions In Items Table
    for x in doc.items:
        x.vehicle = doc.vehicle
        x.territory = doc.territory
        x.branch = doc.branch
        x.department = doc.department
        x.cost_center = doc.cost_center

@frappe.whitelist()
def ste_validate(doc, method=None):
    pass
@frappe.whitelist()
def ste_on_submit(doc, method=None):
    for d in doc.items:
        so_ite = d.so_item
        #so_qt = d.qty
        frappe.db.sql(""" update `tabSales Order Item` set st_item = '{st_item}' where name = '{so_ite}'""".format(st_item=d.name,so_ite=so_ite))
        frappe.db.sql(""" update `tabSales Order Item` set st_qty = '{st_qty}' where name = '{so_ite}'""".format(st_qty=d.qty,so_ite=so_ite))
    #if doc.sales_order:
    #    frappe.db_set_value('Sales Order', doc.sales_order, 'se_submitted', 1)
@frappe.whitelist()
def ste_on_cancel(doc, method=None):
    for d in doc.items:
        so_ite = d.so_item
        frappe.db.sql(""" update `tabSales Order Item` set st_item = '' where name = '{so_ite}'""".format(st_item=d.name,so_ite=so_ite))
    pass
@frappe.whitelist()
def ste_on_update_after_submit(doc, method=None):
    pass
@frappe.whitelist()
def ste_before_save(doc, method=None):
    pass
@frappe.whitelist()
def ste_before_cancel(doc, method=None):
    pass
@frappe.whitelist()
def ste_on_update(doc, method=None):
    pass

################ Blanket Order

@frappe.whitelist()
def blank_onload(doc, method=None):
    pass
@frappe.whitelist()
def blank_before_validate(doc, method=None):
    pass
@frappe.whitelist()
def blank_validate(doc, method=None):
    pass
@frappe.whitelist()
def blank_on_submit(doc, method=None):
    pass
@frappe.whitelist()
def blank_on_cancel(doc, method=None):
    pass
@frappe.whitelist()
def blank_on_update_after_submit(doc, method=None):
    pass
@frappe.whitelist()
def blank_before_save(doc, method=None):
    pass
@frappe.whitelist()
def blank_before_cancel(doc, method=None):
    pass
@frappe.whitelist()
def blank_on_update(doc, method=None):
    pass


################ Loan

@frappe.whitelist()
def loan_onload(doc, method=None):
    pass
@frappe.whitelist()
def loan_before_validate(doc, method=None):
    pass
@frappe.whitelist()
def loan_validate(doc, method=None):
    pass
@frappe.whitelist()
def loan_on_submit(doc, method=None):
    if doc.loan_type == "مشتريات":
        dis = frappe.new_doc('Loan Disbursement')
        dis.against_loan = doc.name
        dis.applicant_type = "Employee"
        dis.company = doc.company
        dis.applicant = doc.applicant
        dis.disbursed_amount = doc.loan_amount
        dis.insert(ignore_permissions=True)
        dis.submit()
    pass
@frappe.whitelist()
def loan_on_cancel(doc, method=None):
    #ld =  frappe.db.get_value('Loan Disbursement', {'against_loan': doc.name}, ['name'])    
    #ld1 = frappe.get_doc('Loan Disbursement',ld)
    #ld1.cancel()  
    pass
     
@frappe.whitelist()
def loan_on_update_after_submit(doc, method=None):
    pass
@frappe.whitelist()
def loan_before_save(doc, method=None):
    pass
@frappe.whitelist()
def loan_before_cancel(doc, method=None):
    pass
@frappe.whitelist()
def loan_on_update(doc, method=None):
    pass
