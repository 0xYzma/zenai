import unittest

from app.services.csv_export import build_message_csv, sanitize_csv_value


class CsvExportTests(unittest.TestCase):
    def test_spreadsheet_formula_prefixes_are_neutralized(self):
        for value in ("=1+1", "+SUM(A1:A2)", "-2+3", "@cmd", "  =HYPERLINK('x')"):
            with self.subTest(value=value):
                self.assertTrue(sanitize_csv_value(value).startswith("'"))

    def test_export_excludes_identifier_columns_and_caps_rows(self):
        content = build_message_csv({
            "content": "Product performance",
            "insights": ["Rice leads revenue"],
            "confidence": "high",
            "sources": [{"tool": "product_performance"}],
            "chart_data": [
                {"product_id": "secret-id", "product_name": "=Rice", "revenue": 10},
                {"product_id": "secret-id-2", "product_name": "Tea", "revenue": 20},
            ],
        }, max_rows=1).decode("utf-8-sig")
        self.assertNotIn("product_id", content)
        self.assertNotIn("secret-id", content)
        self.assertIn("'=Rice", content)
        self.assertNotIn("Tea", content)
        self.assertIn("answer,insights,confidence,source,created_at", content)
        self.assertIn("Product performance", content)
        self.assertIn("Rice leads revenue", content)

    def test_answer_only_export_has_useful_metadata(self):
        content = build_message_csv({
            "content": "No matching data",
            "confidence": "low",
            "sources": [{"tool": "sales_summary"}],
            "created_at": "2026-08-19T00:00:00Z",
            "chart_data": None,
        }).decode("utf-8-sig")
        self.assertIn("answer,insights,confidence,source,created_at", content)
        self.assertIn("sales_summary", content)

    def test_persisted_json_strings_export_full_table_and_metadata(self):
        content = build_message_csv({
            "content": "No stockout risk was detected",
            "insights": '["One record has sales", "Eleven records have no sales"]',
            "confidence": "medium",
            "sources": '[{"tool": "stockout_risk"}]',
            "created_at": "2026-08-24T00:00:00Z",
            "chart_data": '[{"product_name":"Coca Cola","current_stock":485}]',
        }).decode("utf-8-sig")

        self.assertIn("product_name,current_stock", content)
        self.assertIn("No stockout risk was detected", content)
        self.assertIn("One record has sales | Eleven records have no sales", content)
        self.assertIn("stockout_risk", content)
        self.assertIn("Coca Cola", content)


if __name__ == "__main__":
    unittest.main()
