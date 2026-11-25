# -*- coding: utf-8 -*-
"""Tests for REPORT_TYPE=table and REPORT_ZH_VARIANT."""

import unittest
from unittest import mock

from src.analyzer import AnalysisResult
from src.config import Config
from src.enums import ReportType
from src.notification import NotificationService
from src.table_report import generate_table_markdown
from src.zh_variant import to_report_variant


def _result(code, name, score, advice, decision_type):
    return AnalysisResult(
        code=code,
        name=name,
        sentiment_score=score,
        trend_prediction="震荡",
        operation_advice=advice,
        decision_type=decision_type,
        dashboard={
            "core_conclusion": {"one_sentence": "等待回踩确认"},
            "intelligence": {"risk_alerts": ["估值偏高"]},
            "data_perspective": {"price_position": {"current_price": 100, "ma5": 99, "ma20": 95,
                                                    "support_level": 94, "resistance_level": 108}},
            "battle_plan": {"sniper_points": {"ideal_buy": "理想买入点：96", "stop_loss": "止损位：90",
                                              "take_profit": "目标位：110"},
                            "position_strategy": {"suggested_position": "3 成"}},
        },
    )


class TableReportTestCase(unittest.TestCase):
    def test_report_type_table_is_accepted(self):
        self.assertEqual(ReportType.from_str("table"), ReportType.TABLE)
        self.assertEqual(Config._parse_report_type("table"), "table")

    def test_markdown_table_contains_key_levels(self):
        notifier = NotificationService()
        with mock.patch.dict("os.environ", {"REPORT_ZH_VARIANT": ""}):
            md = generate_table_markdown(notifier, [_result("AAPL", "Apple", 42, "观望", "hold")])
        self.assertIn("| **理想买点** | 96 |", md)
        self.assertIn("| **止损** | 90 |", md)
        self.assertIn("| **目标** | 110 |", md)
        self.assertIn("估值偏高", md)

    def test_aggregate_report_routes_table_type(self):
        notifier = NotificationService()
        md = notifier.generate_aggregate_report([_result("AAPL", "Apple", 42, "观望", "hold")], "table")
        self.assertIn("|", md)
        self.assertIn("AAPL", md)

    def test_zh_variant_conversion(self):
        with mock.patch.dict("os.environ", {"REPORT_ZH_VARIANT": "tw"}):
            self.assertEqual(to_report_variant("台积电 软件 观望"), "台積電 軟體 觀望")
        with mock.patch.dict("os.environ", {"REPORT_ZH_VARIANT": ""}):
            self.assertEqual(to_report_variant("观望"), "观望")


if __name__ == "__main__":
    unittest.main()
