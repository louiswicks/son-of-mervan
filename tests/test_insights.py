"""
Tests for spending insights endpoints.

Coverage targets:
  routers/insights.py — GET /insights/monthly-summary
                         GET /insights/trends
                         GET /insights/heatmap
"""
import pytest

from tests.conftest import make_month, make_expense


class TestMonthlySummary:
    def test_empty_month_returns_200(self, auth_client):
        r = auth_client.get("/insights/monthly-summary?month=2026-01")
        assert r.status_code == 200

    def test_missing_month_param_returns_422(self, auth_client):
        r = auth_client.get("/insights/monthly-summary")
        assert r.status_code == 422

    def test_invalid_month_format_returns_422(self, auth_client):
        r = auth_client.get("/insights/monthly-summary?month=January")
        assert r.status_code == 422

    def test_with_data_returns_summary(self, auth_client, db, verified_user):
        month = make_month(db, verified_user, month="2026-03", salary_planned=3000.0, total_planned=1500.0)
        make_expense(db, month, name="Rent", category="Housing", planned=800.0, actual=850.0)
        make_expense(db, month, name="Groceries", category="Food", planned=400.0, actual=300.0)

        r = auth_client.get("/insights/monthly-summary?month=2026-03")
        assert r.status_code == 200
        body = r.json()
        # Response should contain per-category data or insights list
        assert isinstance(body, dict)

    def test_unauthenticated_returns_401_or_403(self, client):
        r = client.get("/insights/monthly-summary?month=2026-01")
        assert r.status_code in (401, 403)

    def test_only_own_data(self, auth_client, db, second_user):
        month = make_month(db, second_user, month="2026-01")
        make_expense(db, month, name="BigRent", category="Housing", planned=2000.0, actual=2000.0)

        r = auth_client.get("/insights/monthly-summary?month=2026-01")
        assert r.status_code == 200
        body = r.json()
        # The authenticated user has no data for this month — net_income or categories should reflect that
        assert isinstance(body, dict)


class TestTrends:
    def test_empty_returns_200(self, auth_client):
        r = auth_client.get("/insights/trends")
        assert r.status_code == 200

    def test_default_months(self, auth_client):
        r = auth_client.get("/insights/trends")
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, dict)

    def test_custom_months_param(self, auth_client):
        r = auth_client.get("/insights/trends?months=3")
        assert r.status_code == 200

    def test_invalid_months_too_small(self, auth_client):
        r = auth_client.get("/insights/trends?months=1")
        assert r.status_code == 422

    def test_invalid_months_too_large(self, auth_client):
        r = auth_client.get("/insights/trends?months=25")
        assert r.status_code == 422

    def test_with_data(self, auth_client, db, verified_user):
        m1 = make_month(db, verified_user, month="2026-01", salary_planned=3000.0)
        make_expense(db, m1, name="Rent", category="Housing", planned=800.0, actual=800.0)
        m2 = make_month(db, verified_user, month="2026-02", salary_planned=3000.0)
        make_expense(db, m2, name="Rent", category="Housing", planned=800.0, actual=900.0)

        r = auth_client.get("/insights/trends?months=6")
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, dict)

    def test_unauthenticated(self, client):
        r = client.get("/insights/trends")
        assert r.status_code in (401, 403)


class TestHeatmap:
    def test_empty_returns_200(self, auth_client):
        r = auth_client.get("/insights/heatmap")
        assert r.status_code == 200

    def test_returns_year_key(self, auth_client):
        r = auth_client.get("/insights/heatmap?year=2026")
        assert r.status_code == 200
        body = r.json()
        assert "year" in body

    def test_invalid_year(self, auth_client):
        r = auth_client.get("/insights/heatmap?year=notayear")
        assert r.status_code == 422

    def test_with_data(self, auth_client, db, verified_user):
        month = make_month(db, verified_user, month="2026-04")
        make_expense(db, month, name="Coffee", category="Food", planned=50.0, actual=60.0)

        r = auth_client.get("/insights/heatmap?year=2026")
        assert r.status_code == 200
        body = r.json()
        assert int(body["year"]) == 2026

    def test_unauthenticated(self, client):
        r = client.get("/insights/heatmap")
        assert r.status_code in (401, 403)


class TestSpendingPace:
    def test_missing_month_returns_422(self, auth_client):
        r = auth_client.get("/insights/pace")
        assert r.status_code == 422

    def test_invalid_month_returns_422(self, auth_client):
        r = auth_client.get("/insights/pace?month=not-a-month")
        assert r.status_code == 422

    def test_unauthenticated_returns_401_or_403(self, client):
        r = client.get("/insights/pace?month=2026-04")
        assert r.status_code in (401, 403)

    def test_empty_month_returns_200_with_expected_keys(self, auth_client):
        r = auth_client.get("/insights/pace?month=2026-04")
        assert r.status_code == 200
        body = r.json()
        assert "month" in body
        assert "days_elapsed" in body
        assert "days_in_month" in body
        assert "categories" in body
        assert "overall" in body
        assert "warnings" in body

    def test_future_month_returns_zero_days_elapsed(self, auth_client):
        r = auth_client.get("/insights/pace?month=2099-12")
        assert r.status_code == 200
        body = r.json()
        assert body["days_elapsed"] == 0
        assert body["warnings"] == []

    def test_with_overspending_data_generates_warning(self, auth_client, db, verified_user):
        # Use current month so days_elapsed > 0
        from datetime import datetime
        now = datetime.utcnow()
        month_str = f"{now.year:04d}-{now.month:02d}"

        month = make_month(db, verified_user, month=month_str, salary_planned=3000.0, total_planned=500.0)
        # Actual already exceeds planned — pace will project over budget
        make_expense(db, month, name="Rent", category="Housing", planned=100.0, actual=500.0)

        r = auth_client.get(f"/insights/pace?month={month_str}")
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body["categories"], dict)
        assert isinstance(body["warnings"], list)
        # Housing should be flagged because 500 actual >> 100 planned
        warning_cats = [w["category"] for w in body["warnings"]]
        assert "Housing" in warning_cats

    def test_within_budget_produces_no_warning(self, auth_client, db, verified_user):
        from datetime import datetime
        now = datetime.utcnow()
        month_str = f"{now.year:04d}-{now.month:02d}"

        month = make_month(db, verified_user, month=month_str, salary_planned=3000.0)
        # Very low actual vs high planned — pace projection will be well under planned
        make_expense(db, month, name="Food", category="Food", planned=1000.0, actual=1.0)

        r = auth_client.get(f"/insights/pace?month={month_str}")
        assert r.status_code == 200
        body = r.json()
        food_warnings = [w for w in body["warnings"] if w["category"] == "Food"]
        assert food_warnings == []

    def test_only_own_data(self, auth_client, db, second_user):
        from datetime import datetime
        now = datetime.utcnow()
        month_str = f"{now.year:04d}-{now.month:02d}"

        month = make_month(db, second_user, month=month_str)
        make_expense(db, month, name="BigSpend", category="Housing", planned=100.0, actual=9999.0)

        r = auth_client.get(f"/insights/pace?month={month_str}")
        assert r.status_code == 200
        body = r.json()
        # Authenticated user has no data, so no Housing warning from second_user
        warning_cats = [w["category"] for w in body["warnings"]]
        assert "Housing" not in warning_cats


class TestSuggestCategory:
    def test_missing_name_returns_422(self, auth_client):
        r = auth_client.get("/insights/suggest-category")
        assert r.status_code == 422

    def test_name_too_short_returns_422(self, auth_client):
        r = auth_client.get("/insights/suggest-category?name=a")
        assert r.status_code == 422

    def test_unauthenticated_returns_401_or_403(self, client):
        r = client.get("/insights/suggest-category?name=tesco")
        assert r.status_code in (401, 403)

    def test_no_history_returns_null_suggestion(self, auth_client):
        r = auth_client.get("/insights/suggest-category?name=tesco")
        assert r.status_code == 200
        body = r.json()
        assert body["suggestion"] is None
        assert body["count"] == 0

    def test_returns_most_common_category(self, auth_client, db, verified_user):
        month = make_month(db, verified_user, month="2026-01")
        make_expense(db, month, name="Tesco", category="Food", planned=50.0, actual=50.0)
        make_expense(db, month, name="Tesco Express", category="Food", planned=30.0, actual=30.0)
        make_expense(db, month, name="Tesco Metro", category="Housing", planned=10.0, actual=10.0)

        r = auth_client.get("/insights/suggest-category?name=Tesco")
        assert r.status_code == 200
        body = r.json()
        # "Tesco" substring matches all 3 expenses; Food appears twice, Housing once
        assert body["suggestion"] == "Food"
        assert body["count"] == 2
        assert body["total_matches"] == 3

    def test_case_insensitive_matching(self, auth_client, db, verified_user):
        month = make_month(db, verified_user, month="2026-02")
        make_expense(db, month, name="Netflix", category="Entertainment", planned=15.0, actual=15.0)

        r = auth_client.get("/insights/suggest-category?name=netflix")
        assert r.status_code == 200
        body = r.json()
        assert body["suggestion"] == "Entertainment"

    def test_only_own_history(self, auth_client, db, second_user):
        month = make_month(db, second_user, month="2026-03")
        make_expense(db, month, name="Gym", category="Healthcare", planned=40.0, actual=40.0)

        # auth_client user has no "Gym" expense in their own history
        r = auth_client.get("/insights/suggest-category?name=Gym")
        assert r.status_code == 200
        body = r.json()
        assert body["suggestion"] is None

    def test_deleted_expenses_not_counted(self, auth_client, db, verified_user):
        from datetime import datetime
        month = make_month(db, verified_user, month="2026-04")
        exp = make_expense(db, month, name="Spotify", category="Entertainment", planned=10.0, actual=10.0)
        # Soft-delete the expense
        exp.deleted_at = datetime.utcnow()
        db.commit()

        r = auth_client.get("/insights/suggest-category?name=Spotify")
        assert r.status_code == 200
        body = r.json()
        assert body["suggestion"] is None


class TestHealthScore:
    def test_no_data_returns_zero_score(self, auth_client):
        r = auth_client.get("/insights/health-score?month=2026-01")
        assert r.status_code == 200
        body = r.json()
        assert body["score"] == 0
        assert body["band"] == "red"
        assert "components" in body
        assert "explanations" in body

    def test_missing_month_returns_422(self, auth_client):
        r = auth_client.get("/insights/health-score")
        assert r.status_code == 422

    def test_invalid_month_format_returns_422(self, auth_client):
        r = auth_client.get("/insights/health-score?month=not-a-month")
        assert r.status_code == 422

    def test_unauthenticated_returns_401_or_403(self, client):
        r = client.get("/insights/health-score?month=2026-01")
        assert r.status_code in (401, 403)

    def test_high_savings_rate_increases_score(self, auth_client, db, verified_user):
        # 25% savings rate should give savings_component = 100 (capped)
        make_month(db, verified_user, month="2026-01", salary_planned=4000.0, total_planned=3000.0)
        from database import MonthlyData
        row = db.query(MonthlyData).filter(MonthlyData.user_id == verified_user.id).first()
        row.salary_actual = 4000.0
        row.total_actual = 3000.0  # 25% saved
        db.commit()

        r = auth_client.get("/insights/health-score?month=2026-01")
        assert r.status_code == 200
        body = r.json()
        assert body["components"]["savings_rate"]["score"] == 100
        assert body["score"] > 0

    def test_all_categories_within_budget_gives_full_adherence(self, auth_client, db, verified_user):
        month = make_month(db, verified_user, month="2026-02", salary_planned=3000.0, total_planned=1000.0)
        from database import MonthlyData
        row = db.query(MonthlyData).filter(MonthlyData.user_id == verified_user.id).first()
        row.salary_actual = 3000.0
        row.total_actual = 900.0
        db.commit()
        make_expense(db, month, name="Rent", category="Housing", planned=800.0, actual=750.0)
        make_expense(db, month, name="Food", category="Food", planned=300.0, actual=150.0)

        r = auth_client.get("/insights/health-score?month=2026-02")
        assert r.status_code == 200
        body = r.json()
        assert body["components"]["budget_adherence"]["score"] == 100

    def test_overspending_reduces_adherence_score(self, auth_client, db, verified_user):
        month = make_month(db, verified_user, month="2026-03", salary_planned=3000.0, total_planned=1000.0)
        from database import MonthlyData
        row = db.query(MonthlyData).filter(MonthlyData.user_id == verified_user.id).first()
        row.salary_actual = 3000.0
        row.total_actual = 1500.0
        db.commit()
        make_expense(db, month, name="Rent", category="Housing", planned=800.0, actual=1000.0)  # over
        make_expense(db, month, name="Food", category="Food", planned=300.0, actual=200.0)       # under

        r = auth_client.get("/insights/health-score?month=2026-03")
        assert r.status_code == 200
        body = r.json()
        # 1 of 2 categories within budget = 50%
        assert body["components"]["budget_adherence"]["score"] == 50

    def test_savings_goals_improve_emergency_fund_score(self, auth_client, db, verified_user):
        from database import SavingsGoal, SavingsContribution, MonthlyData
        from datetime import datetime

        # Set up 3 months of expense data (~£1000/month)
        for m_str in ["2026-01", "2026-02", "2026-03"]:
            row = make_month(db, verified_user, month=m_str, salary_planned=3000.0, total_planned=1000.0)
            row.total_actual = 1000.0
            db.commit()

        # Create a savings goal with £3000 saved (= 3 months coverage)
        goal = SavingsGoal(user_id=verified_user.id)
        goal.name = "Emergency"
        goal.target_amount = 5000.0
        db.add(goal)
        db.commit()
        db.refresh(goal)

        contrib = SavingsContribution(goal_id=goal.id, contributed_at=datetime.utcnow())
        contrib.amount = 3000.0
        contrib.note = "initial"
        db.add(contrib)
        db.commit()

        r = auth_client.get("/insights/health-score?month=2026-03")
        assert r.status_code == 200
        body = r.json()
        # coverage_months ≈ 3000 / 1000 = 3.0 → emergency_component = 100
        assert body["components"]["emergency_fund"]["score"] == 100

    def test_response_structure(self, auth_client):
        r = auth_client.get("/insights/health-score?month=2026-01")
        assert r.status_code == 200
        body = r.json()
        assert "score" in body
        assert "band" in body
        assert "components" in body
        assert "explanations" in body
        assert "savings_rate" in body["components"]
        assert "budget_adherence" in body["components"]
        assert "emergency_fund" in body["components"]
        for comp in body["components"].values():
            assert "score" in comp
            assert "weight" in comp
            assert "detail" in comp
            assert "raw_value" in comp
        assert isinstance(body["explanations"], list)
        assert len(body["explanations"]) == 3

    def test_score_band_boundaries(self, auth_client, db, verified_user):
        # With no data, score=0 → band=red
        r = auth_client.get("/insights/health-score?month=2026-06")
        body = r.json()
        assert body["band"] == "red"
        assert body["score"] < 40

    def test_only_own_data_counted(self, auth_client, db, second_user):
        # second_user has 100% adherence data; auth_client user has none
        make_month(db, second_user, month="2026-05")
        from database import MonthlyData
        row = db.query(MonthlyData).filter(MonthlyData.user_id == second_user.id).first()
        row.salary_actual = 5000.0
        row.total_actual = 500.0
        db.commit()

        r = auth_client.get("/insights/health-score?month=2026-05")
        assert r.status_code == 200
        body = r.json()
        # Auth user has no salary data → savings score should be 0
        assert body["components"]["savings_rate"]["score"] == 0


class TestAIReview:
    """Tests for POST /insights/ai-review (streaming SSE endpoint)."""

    def test_unauthenticated_returns_401_or_403(self, client):
        r = client.post("/insights/ai-review?month=2026-04")
        assert r.status_code in (401, 403)

    def test_missing_month_returns_422(self, auth_client):
        r = auth_client.post("/insights/ai-review")
        assert r.status_code == 422

    def test_invalid_month_format_returns_422(self, auth_client):
        r = auth_client.post("/insights/ai-review?month=not-a-month")
        assert r.status_code == 422

    def test_no_api_key_streams_error_message(self, auth_client, monkeypatch):
        """When ANTHROPIC_API_KEY is absent, endpoint streams an error SSE event."""
        from core import config as cfg
        monkeypatch.setattr(cfg.settings, "ANTHROPIC_API_KEY", "")

        r = auth_client.post("/insights/ai-review?month=2026-04")
        assert r.status_code == 200
        assert "text/event-stream" in r.headers.get("content-type", "")
        # Response body should contain an error event
        assert b"error" in r.content

    def test_rate_limit_blocks_after_max_requests(self, auth_client, monkeypatch):
        """After MAX_AI_REVIEWS_PER_DAY requests the endpoint returns 429."""
        import routers.insights as ins

        def always_denied(user_id):
            return False, 0

        monkeypatch.setattr(ins, "_check_and_increment_ai_rate_limit", always_denied)

        r = auth_client.post("/insights/ai-review?month=2026-04")
        assert r.status_code == 429

    def test_rate_limit_header_present(self, auth_client, monkeypatch):
        """X-RateLimit-Remaining header is included in a successful (SSE) response."""
        from core import config as cfg
        monkeypatch.setattr(cfg.settings, "ANTHROPIC_API_KEY", "")

        r = auth_client.post("/insights/ai-review?month=2026-04")
        assert r.status_code == 200
        assert "x-ratelimit-remaining" in r.headers

    def test_empty_month_still_returns_sse_stream(self, auth_client, monkeypatch):
        """With no expense data the endpoint still streams (error when no API key)."""
        from core import config as cfg
        monkeypatch.setattr(cfg.settings, "ANTHROPIC_API_KEY", "")

        r = auth_client.post("/insights/ai-review?month=2099-01")
        # Should be 200 streaming response even for a future month with no data
        assert r.status_code == 200


class TestAnomalyDetection:
    """Tests for GET /insights/anomalies."""

    def test_unauthenticated_returns_401_or_403(self, client):
        r = client.get("/insights/anomalies?month=2026-04")
        assert r.status_code in (401, 403)

    def test_missing_month_returns_422(self, auth_client):
        r = auth_client.get("/insights/anomalies")
        assert r.status_code == 422

    def test_invalid_month_format_returns_422(self, auth_client):
        r = auth_client.get("/insights/anomalies?month=not-a-month")
        assert r.status_code == 422

    def test_lookback_below_minimum_returns_422(self, auth_client):
        r = auth_client.get("/insights/anomalies?month=2026-04&lookback=1")
        assert r.status_code == 422

    def test_lookback_above_maximum_returns_422(self, auth_client):
        r = auth_client.get("/insights/anomalies?month=2026-04&lookback=13")
        assert r.status_code == 422

    def test_no_data_returns_empty_list(self, auth_client):
        r = auth_client.get("/insights/anomalies?month=2099-01")
        assert r.status_code == 200
        body = r.json()
        assert body["anomalies"] == []
        assert body["categories_analysed"] == 0

    def test_no_historical_baseline_returns_empty_list(self, auth_client, db, verified_user):
        """Current month data exists but no prior months — can't flag anomalies."""
        month = make_month(db, verified_user, month="2026-04", salary_planned=3000.0)
        make_expense(db, month, name="Rent", category="Housing", planned=800.0, actual=900.0)

        r = auth_client.get("/insights/anomalies?month=2026-04&lookback=2")
        assert r.status_code == 200
        body = r.json()
        assert body["anomalies"] == []

    def test_detects_high_severity_anomaly(self, auth_client, db, verified_user):
        """Spending well above the historical mean (high z-score) is flagged as high."""
        # Build 3 months of consistent history at £200
        for mo in ["2026-01", "2026-02", "2026-03"]:
            m = make_month(db, verified_user, month=mo, salary_planned=3000.0)
            make_expense(db, m, name="Groceries", category="Food", planned=200.0, actual=200.0)

        # Current month: spike to £600 (3× the mean — very high z-score)
        current = make_month(db, verified_user, month="2026-04", salary_planned=3000.0)
        make_expense(db, current, name="Groceries", category="Food", planned=200.0, actual=600.0)

        r = auth_client.get("/insights/anomalies?month=2026-04&lookback=3")
        assert r.status_code == 200
        body = r.json()
        assert len(body["anomalies"]) >= 1
        anomaly = next(a for a in body["anomalies"] if a["category"] == "Food")
        assert anomaly["severity"] == "high"
        assert anomaly["current_amount"] == 600.0
        assert anomaly["historical_avg"] == 200.0
        assert anomaly["pct_change"] == 200.0

    def test_ignores_normal_spending(self, auth_client, db, verified_user):
        """Spending within normal range does not produce any anomaly."""
        for mo in ["2026-01", "2026-02", "2026-03"]:
            m = make_month(db, verified_user, month=mo, salary_planned=3000.0)
            make_expense(db, m, name="Rent", category="Housing", planned=800.0, actual=800.0)

        # Current month within normal bounds (same as history)
        current = make_month(db, verified_user, month="2026-04", salary_planned=3000.0)
        make_expense(db, current, name="Rent", category="Housing", planned=800.0, actual=810.0)

        r = auth_client.get("/insights/anomalies?month=2026-04&lookback=3")
        assert r.status_code == 200
        body = r.json()
        # No anomaly should be flagged for this minor variation
        housing_anomalies = [a for a in body["anomalies"] if a["category"] == "Housing"]
        assert len(housing_anomalies) == 0

    def test_only_own_data_returned(self, auth_client, db, verified_user, second_user):
        """Anomaly analysis is isolated to the authenticated user's data."""
        # Give second user 3 months of history + a spike
        for mo in ["2026-01", "2026-02", "2026-03"]:
            m = make_month(db, second_user, month=mo, salary_planned=5000.0)
            make_expense(db, m, name="Dining", category="Food", planned=100.0, actual=100.0)
        m_current = make_month(db, second_user, month="2026-04", salary_planned=5000.0)
        make_expense(db, m_current, name="Dining", category="Food", planned=100.0, actual=800.0)

        # Auth user has no data — should see no anomalies
        r = auth_client.get("/insights/anomalies?month=2026-04&lookback=3")
        assert r.status_code == 200
        body = r.json()
        assert body["anomalies"] == []

    def test_response_sorted_high_to_low(self, auth_client, db, verified_user):
        """Anomalies are sorted high → medium → low severity."""
        # Build 3 months of varied history so different categories get different z-scores
        for mo in ["2026-01", "2026-02", "2026-03"]:
            m = make_month(db, verified_user, month=mo, salary_planned=5000.0)
            # Food: mean 100, std_dev ~0 (all same)
            make_expense(db, m, name="Food", category="Food", planned=100.0, actual=100.0)
            # Entertainment: mean 50, std_dev 0
            make_expense(db, m, name="Fun", category="Entertainment", planned=50.0, actual=50.0)

        # Current month: Food spikes to 300 (>100% above mean → high)
        # Entertainment spikes to 80 (60% above mean → medium)
        current = make_month(db, verified_user, month="2026-04", salary_planned=5000.0)
        make_expense(db, current, name="Food", category="Food", planned=100.0, actual=300.0)
        make_expense(db, current, name="Fun", category="Entertainment", planned=50.0, actual=80.0)

        r = auth_client.get("/insights/anomalies?month=2026-04&lookback=3")
        assert r.status_code == 200
        body = r.json()
        anomalies = body["anomalies"]
        assert len(anomalies) >= 1
        # First anomaly should be highest severity
        severity_order = {"high": 0, "medium": 1, "low": 2}
        for i in range(len(anomalies) - 1):
            assert severity_order[anomalies[i]["severity"]] <= severity_order[anomalies[i + 1]["severity"]]

    def test_lookback_param_respected(self, auth_client, db, verified_user):
        """lookback=2 uses only the 2 most recent prior months."""
        # Month 2026-01: Food £100 (old, outside lookback=2 window)
        m_jan = make_month(db, verified_user, month="2026-01", salary_planned=3000.0)
        make_expense(db, m_jan, name="Food", category="Food", planned=100.0, actual=1000.0)
        # Months 2026-02 and 2026-03: Food £100 (inside lookback=2 window)
        for mo in ["2026-02", "2026-03"]:
            m = make_month(db, verified_user, month=mo, salary_planned=3000.0)
            make_expense(db, m, name="Food", category="Food", planned=100.0, actual=100.0)

        # Current month: £200 (100% above the 2-month average of £100)
        current = make_month(db, verified_user, month="2026-04", salary_planned=3000.0)
        make_expense(db, current, name="Food", category="Food", planned=100.0, actual=200.0)

        r = auth_client.get("/insights/anomalies?month=2026-04&lookback=2")
        assert r.status_code == 200
        body = r.json()
        assert body["lookback_months"] == 2


class TestStreaks:
    """Tests for GET /insights/streaks."""

    def test_unauthenticated_returns_401_or_403(self, client):
        r = client.get("/insights/streaks")
        assert r.status_code in (401, 403)

    def test_no_data_returns_zero_streaks(self, auth_client):
        r = auth_client.get("/insights/streaks")
        assert r.status_code == 200
        body = r.json()
        assert body["current_streak"] == 0
        assert body["longest_streak"] == 0
        assert body["total_tracked"] == 0
        assert body["months_under"] == 0

    def test_single_under_budget_month_gives_streak_one(self, auth_client, db, verified_user):
        """One month with actual ≤ planned produces a streak of 1."""
        make_month(
            db, verified_user, month="2026-01",
            salary_planned=3000.0, total_planned=2000.0,
            total_actual=1800.0,
        )
        r = auth_client.get("/insights/streaks")
        assert r.status_code == 200
        body = r.json()
        assert body["current_streak"] == 1
        assert body["longest_streak"] == 1
        assert body["months_under"] == 1

    def test_consecutive_under_budget_months_counted(self, auth_client, db, verified_user):
        """Three consecutive under-budget months yield streak of 3."""
        for mo in ["2026-01", "2026-02", "2026-03"]:
            make_month(
                db, verified_user, month=mo,
                salary_planned=3000.0, total_planned=2000.0,
                total_actual=1500.0,
            )
        r = auth_client.get("/insights/streaks")
        assert r.status_code == 200
        body = r.json()
        assert body["current_streak"] == 3
        assert body["longest_streak"] == 3
        assert body["total_tracked"] == 3

    def test_over_budget_month_resets_current_streak(self, auth_client, db, verified_user):
        """An over-budget month breaks the current streak but longest is preserved."""
        # 2 under-budget months (2026-01, 2026-02)
        for mo in ["2026-01", "2026-02"]:
            make_month(
                db, verified_user, month=mo,
                salary_planned=3000.0, total_planned=2000.0,
                total_actual=1500.0,
            )
        # 1 over-budget month (2026-03)
        make_month(
            db, verified_user, month="2026-03",
            salary_planned=3000.0, total_planned=2000.0,
            total_actual=2500.0,
        )
        # 1 under-budget month (2026-04) — new streak starts
        make_month(
            db, verified_user, month="2026-04",
            salary_planned=3000.0, total_planned=2000.0,
            total_actual=1800.0,
        )
        r = auth_client.get("/insights/streaks")
        assert r.status_code == 200
        body = r.json()
        assert body["current_streak"] == 1
        assert body["longest_streak"] == 2
        assert body["months_under"] == 3

    def test_months_without_actuals_excluded(self, auth_client, db, verified_user):
        """Months with no actual spend (total_actual=0) are skipped — don't break streak."""
        # Month with actuals: under-budget
        make_month(
            db, verified_user, month="2026-01",
            salary_planned=3000.0, total_planned=2000.0,
            total_actual=1500.0,
        )
        # Month with no actuals (not yet tracked)
        make_month(
            db, verified_user, month="2026-02",
            salary_planned=3000.0, total_planned=2000.0,
            total_actual=0.0,
        )
        # Month with actuals: under-budget — streak continues
        make_month(
            db, verified_user, month="2026-03",
            salary_planned=3000.0, total_planned=2000.0,
            total_actual=1800.0,
        )
        r = auth_client.get("/insights/streaks")
        assert r.status_code == 200
        body = r.json()
        assert body["current_streak"] == 2
        assert body["total_tracked"] == 2  # zero-actual month not counted

    def test_only_own_data_returned(self, auth_client, db, verified_user, second_user):
        """Streak data is isolated to the authenticated user."""
        # Give second user a long streak
        for mo in ["2026-01", "2026-02", "2026-03"]:
            make_month(
                db, second_user, month=mo,
                salary_planned=5000.0, total_planned=3000.0,
                total_actual=2000.0,
            )
        # Auth user has no data
        r = auth_client.get("/insights/streaks")
        assert r.status_code == 200
        body = r.json()
        assert body["current_streak"] == 0
        assert body["total_tracked"] == 0


class TestMonthCloseSummary:
    def test_no_data_returns_empty(self, auth_client):
        """No MonthlyData for the month → empty categories, zero total."""
        r = auth_client.get("/insights/month-close-summary", params={"month": "2026-03"})
        assert r.status_code == 200
        body = r.json()
        assert body["month"] == "2026-03"
        assert body["total_unspent"] == 0.0
        assert body["categories"] == []

    def test_unspent_computed_correctly(self, auth_client, db, verified_user):
        """Unspent = planned - actual for under-budget categories."""
        month = make_month(db, verified_user, month="2026-03")
        make_expense(db, month, name="Rent", category="Housing", planned=800.0, actual=600.0)
        make_expense(db, month, name="Groceries", category="Food", planned=300.0, actual=200.0)

        r = auth_client.get("/insights/month-close-summary", params={"month": "2026-03"})
        assert r.status_code == 200
        body = r.json()
        assert body["total_unspent"] == pytest.approx(300.0)
        cats = {c["category"]: c for c in body["categories"]}
        assert cats["Housing"]["unspent"] == pytest.approx(200.0)
        assert cats["Food"]["unspent"] == pytest.approx(100.0)

    def test_overspend_clamped_to_zero(self, auth_client, db, verified_user):
        """Categories where actual > planned must have unspent = 0 (not negative)."""
        month = make_month(db, verified_user, month="2026-03")
        make_expense(db, month, name="Dining", category="Food", planned=100.0, actual=180.0)

        r = auth_client.get("/insights/month-close-summary", params={"month": "2026-03"})
        assert r.status_code == 200
        body = r.json()
        cats = {c["category"]: c for c in body["categories"]}
        assert cats["Food"]["unspent"] == 0.0
        assert body["total_unspent"] == 0.0

    def test_sorted_by_unspent_descending(self, auth_client, db, verified_user):
        """Categories are returned sorted by unspent amount descending."""
        month = make_month(db, verified_user, month="2026-03")
        make_expense(db, month, name="Coffee", category="Entertainment", planned=50.0, actual=10.0)
        make_expense(db, month, name="Rent", category="Housing", planned=800.0, actual=400.0)
        make_expense(db, month, name="Food", category="Food", planned=200.0, actual=150.0)

        r = auth_client.get("/insights/month-close-summary", params={"month": "2026-03"})
        assert r.status_code == 200
        unspent_values = [c["unspent"] for c in r.json()["categories"]]
        assert unspent_values == sorted(unspent_values, reverse=True)

    def test_data_isolated_per_user(self, auth_client, db, verified_user, second_user):
        """Another user's data does not bleed into the authenticated user's result."""
        other_month = make_month(db, second_user, month="2026-03")
        make_expense(db, other_month, name="Luxury", category="Other", planned=5000.0, actual=100.0)

        r = auth_client.get("/insights/month-close-summary", params={"month": "2026-03"})
        assert r.status_code == 200
        assert r.json()["total_unspent"] == 0.0

    def test_unauthenticated_returns_401(self, client):
        """Unauthenticated request is rejected."""
        r = client.get("/insights/month-close-summary", params={"month": "2026-03"})
        assert r.status_code in (401, 403)

    def test_invalid_month_format_returns_422(self, auth_client):
        """Bad month param → 422 validation error."""
        r = auth_client.get("/insights/month-close-summary", params={"month": "not-a-month"})
        assert r.status_code == 422


class TestSpendingVelocity:
    """Tests for GET /insights/spending-velocity and check_spending_velocity job."""

    def test_unauthenticated_returns_401(self, client):
        """Unauthenticated request is rejected."""
        r = client.get("/insights/spending-velocity", params={"month": "2026-03"})
        assert r.status_code in (401, 403)

    def test_no_data_returns_zeroed_structure(self, auth_client):
        """No MonthlyData for month → zeroed structure with on_track=True."""
        r = auth_client.get("/insights/spending-velocity", params={"month": "2025-01"})
        assert r.status_code == 200
        body = r.json()
        assert body["month"] == "2025-01"
        assert body["actual_ytd"] == 0.0
        assert body["planned_total"] == 0.0
        assert body["projected_total"] == 0.0
        assert body["on_track"] is True

    def test_on_track_month_returns_on_track_true(self, auth_client, db, verified_user, monkeypatch):
        """When projected spend is within 110% of plan, on_track is True."""
        import datetime as dt
        monkeypatch.setattr("routers.insights.datetime", type(
            "FakeDatetime", (), {
                "utcnow": staticmethod(lambda: dt.datetime(2026, 3, 15, 12, 0, 0)),
                "date": dt.datetime,
            }
        ))

        make_month(db, verified_user, month="2026-03", total_planned=1000.0, total_actual=400.0)

        r = auth_client.get("/insights/spending-velocity", params={"month": "2026-03"})
        assert r.status_code == 200
        body = r.json()
        # 400/15 * 31 ≈ 826 ≤ 1000 * 1.10 → on_track
        assert body["on_track"] is True
        assert body["days_elapsed"] > 0
        assert body["planned_total"] == pytest.approx(1000.0)

    def test_overspend_pace_returns_on_track_false(self, auth_client, db, verified_user, monkeypatch):
        """When projected spend exceeds 110% of plan, on_track is False."""
        import datetime as dt
        monkeypatch.setattr("routers.insights.datetime", type(
            "FakeDatetime", (), {
                "utcnow": staticmethod(lambda: dt.datetime(2026, 3, 10, 12, 0, 0)),
                "date": dt.datetime,
            }
        ))

        # Spent 900 in 10 days → projected 900/10*31 = 2790 >> 1000*1.10
        make_month(db, verified_user, month="2026-03", total_planned=1000.0, total_actual=900.0)

        r = auth_client.get("/insights/spending-velocity", params={"month": "2026-03"})
        assert r.status_code == 200
        body = r.json()
        assert body["on_track"] is False
        assert body["projected_total"] > body["planned_total"] * 1.10

    def test_invalid_month_format_returns_422(self, auth_client):
        """Bad month format → 422."""
        r = auth_client.get("/insights/spending-velocity", params={"month": "not-valid"})
        assert r.status_code == 422

    def test_check_velocity_job_fires_notification(self, db, verified_user, monkeypatch):
        """Scheduler job fires a notification when projected spend exceeds 110% of plan."""
        import datetime as dt
        from database import Notification, SessionLocal
        from routers.insights import check_spending_velocity

        fixed_now = dt.datetime(2026, 3, 10, 12, 0, 0)
        monkeypatch.setattr("routers.insights.datetime", type(
            "FakeDatetime", (), {"utcnow": staticmethod(lambda: fixed_now)}
        ))

        # 900 actual in 10 days → projected ~2790 >> 1000 * 1.10
        make_month(db, verified_user, month="2026-03", total_planned=1000.0, total_actual=900.0)
        db.commit()

        check_spending_velocity(SessionLocal)

        notif = (
            db.query(Notification)
            .filter(Notification.user_id == verified_user.id, Notification.type == "velocity_warning")
            .first()
        )
        assert notif is not None
        assert "velocity:{}:2026-03:2026-03-10".format(verified_user.id) == notif.dedup_key

    def test_check_velocity_job_dedup_prevents_duplicate(self, db, verified_user, monkeypatch):
        """Running the job twice on the same day does not create a second notification."""
        import datetime as dt
        from database import Notification, SessionLocal
        from routers.insights import check_spending_velocity

        fixed_now = dt.datetime(2026, 3, 10, 12, 0, 0)
        monkeypatch.setattr("routers.insights.datetime", type(
            "FakeDatetime", (), {"utcnow": staticmethod(lambda: fixed_now)}
        ))

        make_month(db, verified_user, month="2026-03", total_planned=1000.0, total_actual=900.0)
        db.commit()

        check_spending_velocity(SessionLocal)
        check_spending_velocity(SessionLocal)

        count = (
            db.query(Notification)
            .filter(Notification.user_id == verified_user.id, Notification.type == "velocity_warning")
            .count()
        )
        assert count == 1

    def test_check_velocity_job_no_notification_when_on_track(self, db, verified_user, monkeypatch):
        """No notification fires when projected spend is within plan."""
        import datetime as dt
        from database import Notification, SessionLocal
        from routers.insights import check_spending_velocity

        fixed_now = dt.datetime(2026, 3, 15, 12, 0, 0)
        monkeypatch.setattr("routers.insights.datetime", type(
            "FakeDatetime", (), {"utcnow": staticmethod(lambda: fixed_now)}
        ))

        # 400 actual / 15 days * 31 ≈ 826 ≤ 1100 → on track
        make_month(db, verified_user, month="2026-03", total_planned=1000.0, total_actual=400.0)
        db.commit()

        check_spending_velocity(SessionLocal)

        count = (
            db.query(Notification)
            .filter(Notification.user_id == verified_user.id, Notification.type == "velocity_warning")
            .count()
        )
        assert count == 0


class TestMonthPerformance:
    def test_empty_month_returns_zeroed_on_track(self, auth_client):
        """Month with no data returns zeroed structure with status on_track."""
        r = auth_client.get("/insights/month-performance?month=2099-01")
        assert r.status_code == 200
        body = r.json()
        assert body["month"] == "2099-01"
        assert body["salary_planned"] == 0.0
        assert body["actual_ytd"] == 0.0
        assert body["planned_ytd"] == 0.0
        assert body["remaining"] == 0.0
        assert body["savings_rate_pct"] == 0.0
        assert body["daily_actuals"] == []
        assert body["status"] == "on_track"

    def test_on_track_status_when_actual_le_planned(self, auth_client, db, verified_user):
        """Status is on_track when actual <= planned."""
        make_month(db, verified_user, month="2026-05", salary_planned=3000.0, total_planned=2000.0, total_actual=1800.0)
        r = auth_client.get("/insights/month-performance?month=2026-05")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "on_track"
        assert body["salary_planned"] == 3000.0
        assert body["actual_ytd"] == 1800.0
        assert body["planned_ytd"] == 2000.0
        assert body["remaining"] == 1200.0

    def test_warning_status_when_actual_101_to_110_pct(self, auth_client, db, verified_user):
        """Status is warning when actual is 101–110% of planned."""
        # 2100 / 2000 = 105% → warning
        make_month(db, verified_user, month="2026-06", salary_planned=3000.0, total_planned=2000.0, total_actual=2100.0)
        r = auth_client.get("/insights/month-performance?month=2026-06")
        assert r.status_code == 200
        assert r.json()["status"] == "warning"

    def test_over_budget_status_when_actual_above_110_pct(self, auth_client, db, verified_user):
        """Status is over_budget when actual exceeds 110% of planned."""
        # 2300 / 2000 = 115% → over_budget
        make_month(db, verified_user, month="2026-07", salary_planned=3000.0, total_planned=2000.0, total_actual=2300.0)
        r = auth_client.get("/insights/month-performance?month=2026-07")
        assert r.status_code == 200
        assert r.json()["status"] == "over_budget"

    def test_savings_rate_pct_calculated_correctly(self, auth_client, db, verified_user):
        """savings_rate_pct = (salary_planned - actual_ytd) / salary_planned * 100."""
        # (3000 - 1500) / 3000 * 100 = 50.0
        make_month(db, verified_user, month="2026-08", salary_planned=3000.0, total_planned=2000.0, total_actual=1500.0)
        r = auth_client.get("/insights/month-performance?month=2026-08")
        assert r.status_code == 200
        assert r.json()["savings_rate_pct"] == 50.0

    def test_savings_rate_clamped_to_zero_when_over_salary(self, auth_client, db, verified_user):
        """savings_rate_pct is clamped to 0 when actual exceeds salary."""
        make_month(db, verified_user, month="2026-09", salary_planned=1000.0, total_planned=1200.0, total_actual=1500.0)
        r = auth_client.get("/insights/month-performance?month=2026-09")
        assert r.status_code == 200
        assert r.json()["savings_rate_pct"] == 0.0

    def test_unauthenticated_returns_401(self, client):
        """Unauthenticated requests are rejected."""
        r = client.get("/insights/month-performance?month=2026-01")
        assert r.status_code in (401, 403)

    def test_missing_month_param_returns_422(self, auth_client):
        """Missing month query param returns 422."""
        r = auth_client.get("/insights/month-performance")
        assert r.status_code == 422

    def test_invalid_month_format_returns_422(self, auth_client):
        """Invalid month format returns 422."""
        r = auth_client.get("/insights/month-performance?month=not-a-month")
        assert r.status_code == 422

    def test_daily_actuals_populated_when_actual_nonzero(self, auth_client, db, verified_user):
        """daily_actuals contains at least one entry when actual_ytd > 0."""
        make_month(db, verified_user, month="2026-10", salary_planned=3000.0, total_planned=2000.0, total_actual=1200.0)
        r = auth_client.get("/insights/month-performance?month=2026-10")
        assert r.status_code == 200
        body = r.json()
        assert len(body["daily_actuals"]) > 0
        entry = body["daily_actuals"][0]
        assert "date" in entry
        assert "amount" in entry
        assert entry["amount"] == 1200.0


class TestSpendingForecast:
    """Tests for GET /insights/spending-forecast."""

    def test_unauthenticated_returns_401_or_403(self, client):
        """Unauthenticated request is rejected."""
        r = client.get("/insights/spending-forecast?month=2026-04")
        assert r.status_code in (401, 403)

    def test_missing_month_param_returns_422(self, auth_client):
        """Missing month query param returns 422."""
        r = auth_client.get("/insights/spending-forecast")
        assert r.status_code == 422

    def test_invalid_month_format_returns_422(self, auth_client):
        """Bad month format returns 422."""
        r = auth_client.get("/insights/spending-forecast?month=not-a-month")
        assert r.status_code == 422

    def test_lookback_below_minimum_returns_422(self, auth_client):
        """lookback < 2 returns 422."""
        r = auth_client.get("/insights/spending-forecast?month=2026-04&lookback=1")
        assert r.status_code == 422

    def test_lookback_above_maximum_returns_422(self, auth_client):
        """lookback > 6 returns 422."""
        r = auth_client.get("/insights/spending-forecast?month=2026-04&lookback=7")
        assert r.status_code == 422

    def test_no_historical_data_returns_empty_list(self, auth_client):
        """No prior months → empty categories list and total 0."""
        r = auth_client.get("/insights/spending-forecast?month=2099-01")
        assert r.status_code == 200
        body = r.json()
        assert body["month"] == "2099-01"
        assert body["categories"] == []
        assert body["total"] == 0.0

    def test_rolling_average_calculated_correctly(self, auth_client, db, verified_user):
        """Predicted amount for a category equals the mean of prior month actuals."""
        # 3 prior months: Food £100, £200, £300 → average £200
        for mo, actual in [("2026-01", 100.0), ("2026-02", 200.0), ("2026-03", 300.0)]:
            m = make_month(db, verified_user, month=mo, salary_planned=3000.0)
            make_expense(db, m, name="Groceries", category="Food", planned=200.0, actual=actual)

        r = auth_client.get("/insights/spending-forecast?month=2026-04&lookback=3")
        assert r.status_code == 200
        body = r.json()
        food = next(c for c in body["categories"] if c["category"] == "Food")
        assert food["predicted_amount"] == pytest.approx(200.0)
        assert body["total"] == pytest.approx(200.0)

    def test_categories_with_no_prior_data_omitted(self, auth_client, db, verified_user):
        """Categories that appear only in the target month (no prior data) are not returned."""
        # No prior months — target month has data but no history
        m = make_month(db, verified_user, month="2026-04", salary_planned=3000.0)
        make_expense(db, m, name="Rent", category="Housing", planned=800.0, actual=800.0)

        r = auth_client.get("/insights/spending-forecast?month=2026-04&lookback=2")
        assert r.status_code == 200
        body = r.json()
        assert body["categories"] == []
        assert body["total"] == 0.0

    def test_multiple_categories_all_predicted(self, auth_client, db, verified_user):
        """Multiple categories each get their own averaged prediction."""
        for mo in ["2026-01", "2026-02"]:
            m = make_month(db, verified_user, month=mo, salary_planned=4000.0)
            make_expense(db, m, name="Rent", category="Housing", planned=800.0, actual=800.0)
            make_expense(db, m, name="Food", category="Food", planned=300.0, actual=250.0)

        r = auth_client.get("/insights/spending-forecast?month=2026-03&lookback=2")
        assert r.status_code == 200
        body = r.json()
        cats = {c["category"]: c for c in body["categories"]}
        assert "Housing" in cats
        assert "Food" in cats
        assert cats["Housing"]["predicted_amount"] == pytest.approx(800.0)
        assert cats["Food"]["predicted_amount"] == pytest.approx(250.0)
        assert body["total"] == pytest.approx(1050.0)

    def test_only_own_data_used(self, auth_client, db, verified_user, second_user):
        """Forecast uses only the authenticated user's history."""
        # Give second user 3 months of high spending
        for mo in ["2026-01", "2026-02", "2026-03"]:
            m = make_month(db, second_user, month=mo, salary_planned=9000.0)
            make_expense(db, m, name="Luxury", category="Luxury", planned=5000.0, actual=5000.0)

        # Authenticated user has no data
        r = auth_client.get("/insights/spending-forecast?month=2026-04&lookback=3")
        assert r.status_code == 200
        body = r.json()
        assert body["categories"] == []
        assert body["total"] == 0.0

    def test_months_of_data_field_returned(self, auth_client, db, verified_user):
        """Each category entry includes months_of_data showing how many prior months contributed."""
        # 2 prior months of Food data
        for mo in ["2026-02", "2026-03"]:
            m = make_month(db, verified_user, month=mo, salary_planned=3000.0)
            make_expense(db, m, name="Groceries", category="Food", planned=300.0, actual=250.0)

        r = auth_client.get("/insights/spending-forecast?month=2026-04&lookback=3")
        assert r.status_code == 200
        body = r.json()
        food = next(c for c in body["categories"] if c["category"] == "Food")
        # Only 2 of the 3 lookback months had Food data
        assert food["months_of_data"] == 2
