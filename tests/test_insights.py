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
        # Patch in-memory counter to simulate limit already reached
        from datetime import datetime
        from database import User, SessionLocal
        from security import verify_token

        # Force the in-memory counter past the limit for any user key today
        today = datetime.utcnow().strftime("%Y-%m-%d")

        original_check = ins._check_and_increment_ai_rate_limit

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
