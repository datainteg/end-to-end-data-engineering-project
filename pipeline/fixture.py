"""Small synthetic fixture shared by the local reference and source seed tool."""
from copy import deepcopy

T0 = "2026-01-01T00:00:00Z"
BASELINE_UPPER = "2026-01-02T00:00:00Z"
DATASETS = ("orders", "order_items", "payments", "products", "customers")
KEYS = {"orders": ("order_id",), "order_items": ("order_id", "line_id"),
        "payments": ("payment_id",), "products": ("product_id",), "customers": ("customer_id",)}


def baseline():
    data = {
        "orders": [dict(order_id=f"O{100+i}", customer_id=c, ordered_at=T0,
                        status=s, currency="INR")
                   for i, (c, s) in enumerate([("C001", "paid"), ("C002", "paid"), ("C001", "cancelled")])],
        "order_items": [dict(order_id=f"O{100+i}", line_id="1", product_id=f"SKU{i+1}",
                             quantity=q, unit_price=p, discount_amount=d)
                        for i, (q, p, d) in enumerate([(2, "500.00", "100.00"), (1, "300.00", "0.00"), (1, "200.00", "0.00")])],
        "payments": [dict(payment_id=f"P{100+i}", order_id=o, amount=a, status=s, attempted_at=T0)
                     for i, (o, a, s) in enumerate([("O100", "900.00", "SUCCESS"), ("O101", "300.00", "FAILED"), ("O101", "300.00", "SUCCESS"), ("O102", "200.00", "FAILED")])],
        "products": [dict(product_id=f"SKU{i+1}", product_name=n, category="Learning")
                     for i, n in enumerate(["SQL workbook", "Python workbook", "Spark workbook"])],
        "customers": [dict(customer_id="C001", profile=dict(city="Pune", loyalty_tier="Silver")),
                      dict(customer_id="C002", profile=dict(city="Mumbai", loyalty_tier="Bronze"))],
    }
    for rows in data.values():
        for row in rows:
            row.update(updated_at=T0, is_deleted=False)
    return data


def changed(data, at="2026-01-02T12:00:00Z"):
    data = deepcopy(data)
    data["customers"][0]["profile"]["loyalty_tier"] = "Gold"
    data["customers"][0]["updated_at"] = at
    return data
