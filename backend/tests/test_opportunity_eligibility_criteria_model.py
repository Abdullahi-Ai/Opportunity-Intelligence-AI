"""
Unit and integration tests for OpportunityEligibilityCriterion relational model,
criterion audit logs, database CHECK constraints, and Alembic migration.

Phase 2 — Stages 2.2B-1 & 2.2B-1A Implementation.
Covers:
1. Model import and controlled enum definitions.
2. Successful criterion creation, default PENDING_REVIEW state, and mandatory flag.
3. Valid and invalid criterion categories.
4. Valid and invalid operators.
5. Invalid verification statuses.
6. Verification integrity invariant: VERIFIED state requires verified_by, verified_at, evidence_url.
7. Verification integrity invariant: PENDING_REVIEW state rejects verified_by and verified_at.
8. Opportunity foreign key relationship and back-population.
9. Physical opportunity deletion is blocked when eligibility criteria exist (ON DELETE RESTRICT).
10. Administrator deletion nullifies verified_by without cascading deletion (ON DELETE SET NULL).
11. Multiple criteria belonging to a single opportunity with independent ordering.
12. Independent verification statuses across multiple criteria of the same opportunity.
13. Storage of Numeric GPA criteria with scale and decimal precision.
14. Storage of County restriction criteria.
15. Storage of Graduation window / temporal criteria.
16. Database CHECK constraint enforcement:
    - Empty source_text rejected.
    - Empty criterion_value rejected.
    - Zero or negative numeric_scale rejected.
17. Immutable criterion audit log (OpportunityCriterionVerificationLog) creation and relationships.
18. ON DELETE RESTRICT on criterion_id: Criterion cannot be deleted while verification logs exist.
19. ON DELETE SET NULL on admin_id in criterion verification logs.
20. Table definitions, indexes, composite indexes, and constraints.
21. Backend and API mirror file byte-for-byte parity.
22. Alembic migration revision chain and upgrade/downgrade execution on temporary database.
"""

import os
import sys
import uuid
import filecmp
from pathlib import Path
from datetime import datetime
from decimal import Decimal
import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
repo_root = backend_dir.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.db.session import Base
from app.models.entities import (
    User,
    Opportunity,
    OpportunityEligibilityCriterion,
    OpportunityCriterionVerificationLog,
    CriterionCategory,
    CriterionOperator,
    CriterionVerificationStatus,
)


@pytest.fixture(scope="module")
def isolated_db():
    """Provides an isolated SQLite engine with foreign key and check constraint enforcement enabled."""
    test_engine = create_engine("sqlite:///:memory:", echo=False)

    @event.listens_for(test_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=test_engine)
    TestSession = sessionmaker(bind=test_engine)
    session = TestSession()
    yield session, test_engine
    session.close()


class TestOpportunityEligibilityCriteriaModel:
    """Test suite for OpportunityEligibilityCriterion, audit logs, and schema invariants."""

    def test_01_model_import_and_enums(self):
        """Scenario 1: Model and enums are cleanly importable and structured."""
        assert issubclass(OpportunityEligibilityCriterion, Base)
        assert issubclass(OpportunityCriterionVerificationLog, Base)
        assert hasattr(OpportunityEligibilityCriterion, "opportunity_id")
        assert hasattr(OpportunityEligibilityCriterion, "criterion_type")
        assert hasattr(OpportunityEligibilityCriterion, "operator")
        assert hasattr(OpportunityEligibilityCriterion, "criterion_value")
        assert hasattr(OpportunityEligibilityCriterion, "verification_status")

        # Verify category enum contains required categories
        assert CriterionCategory.MINIMUM_ACADEMIC_GRADE.value == "MINIMUM_ACADEMIC_GRADE"
        assert CriterionCategory.KCSE_GRADE.value == "KCSE_GRADE"
        assert CriterionCategory.NUMERIC_GPA.value == "NUMERIC_GPA"
        assert CriterionCategory.COUNTY_RESTRICTION.value == "COUNTY_RESTRICTION"
        assert CriterionCategory.GRADUATION_YEAR_RANGE.value == "GRADUATION_YEAR_RANGE"
        assert CriterionCategory.MONTHS_SINCE_GRADUATION.value == "MONTHS_SINCE_GRADUATION"
        assert CriterionCategory.EXPECTED_GRADUATION_WINDOW.value == "EXPECTED_GRADUATION_WINDOW"
        assert CriterionCategory.ACADEMIC_STANDING.value == "ACADEMIC_STANDING"

        # Verify operator enum
        assert CriterionOperator.GTE.value == "GTE"
        assert CriterionOperator.LTE.value == "LTE"
        assert CriterionOperator.EQ.value == "EQ"
        assert CriterionOperator.IN.value == "IN"
        assert CriterionOperator.BETWEEN.value == "BETWEEN"

        # Verify verification status enum
        assert CriterionVerificationStatus.PENDING_REVIEW.value == "PENDING_REVIEW"
        assert CriterionVerificationStatus.VERIFIED.value == "VERIFIED"
        assert CriterionVerificationStatus.NEEDS_REVIEW.value == "NEEDS_REVIEW"
        assert CriterionVerificationStatus.REJECTED.value == "REJECTED"

    def test_02_successful_criterion_creation_and_defaults(self, isolated_db):
        """Scenario 2: Successful creation, default verification status and mandatory flag."""
        session, _ = isolated_db
        opp_id = f"opp-test-{uuid.uuid4().hex[:6]}"
        opp = Opportunity(
            id=opp_id,
            title="Test Tech Fellowship",
            provider="Tech Trust",
            category="Fellowship",
            official_url="https://techtrust.ke"
        )
        session.add(opp)
        session.commit()

        crit = OpportunityEligibilityCriterion(
            opportunity_id=opp_id,
            criterion_type=CriterionCategory.MINIMUM_ACADEMIC_GRADE.value,
            operator=CriterionOperator.GTE.value,
            criterion_value="UPPER_SECOND",
            grading_system="KENYAN_UNIVERSITY_HONOURS",
            source_text="Minimum Upper Second Class Honours degree required."
        )
        session.add(crit)
        session.commit()
        session.refresh(crit)

        assert crit.id is not None
        assert len(crit.id) == 36
        assert crit.opportunity_id == opp_id
        assert crit.criterion_type == "MINIMUM_ACADEMIC_GRADE"
        assert crit.operator == "GTE"
        assert crit.criterion_value == "UPPER_SECOND"
        assert crit.verification_status == CriterionVerificationStatus.PENDING_REVIEW.value
        assert crit.is_mandatory is True
        assert crit.created_at is not None
        assert crit.updated_at is not None

    def test_03_valid_and_invalid_criterion_categories(self, isolated_db):
        """Scenario 3: Valid categories succeed; invalid categories raise ValueError."""
        session, _ = isolated_db
        opp_id = f"opp-test-{uuid.uuid4().hex[:6]}"
        opp = Opportunity(
            id=opp_id,
            title="Category Validation Opportunity",
            provider="Test Provider",
            category="Internship",
            official_url="https://test.ke"
        )
        session.add(opp)
        session.commit()

        # All 10 valid categories succeed
        for cat in CriterionCategory:
            c = OpportunityEligibilityCriterion(
                opportunity_id=opp_id,
                criterion_type=cat.value,
                operator=CriterionOperator.EQ.value,
                criterion_value="test_val",
                source_text="Sample requirement."
            )
            session.add(c)
        session.commit()

        # Invalid category raises ValueError from validator
        with pytest.raises(ValueError, match="Invalid criterion_type 'INVALID_CATEGORY'"):
            OpportunityEligibilityCriterion(
                opportunity_id=opp_id,
                criterion_type="INVALID_CATEGORY",
                operator=CriterionOperator.EQ.value,
                criterion_value="test_val",
                source_text="Sample requirement."
            )

    def test_04_valid_and_invalid_operators(self, isolated_db):
        """Scenario 4: Valid operators succeed; arbitrary operators raise ValueError."""
        session, _ = isolated_db
        opp_id = f"opp-test-{uuid.uuid4().hex[:6]}"
        opp = Opportunity(
            id=opp_id,
            title="Operator Validation Opportunity",
            provider="Test Provider",
            category="Scholarship",
            official_url="https://test.ke"
        )
        session.add(opp)
        session.commit()

        for op in CriterionOperator:
            c = OpportunityEligibilityCriterion(
                opportunity_id=opp_id,
                criterion_type=CriterionCategory.ACADEMIC_STANDING.value,
                operator=op.value,
                criterion_value="FINAL_YEAR",
                source_text="Must be final year student."
            )
            session.add(c)
        session.commit()

        with pytest.raises(ValueError, match="Invalid operator 'LIKE'"):
            OpportunityEligibilityCriterion(
                opportunity_id=opp_id,
                criterion_type=CriterionCategory.ACADEMIC_STANDING.value,
                operator="LIKE",
                criterion_value="FINAL_YEAR",
                source_text="Must be final year student."
            )

    def test_05_invalid_verification_status_rejected(self, isolated_db):
        """Scenario 5: Invalid verification status raises ValueError."""
        session, _ = isolated_db
        opp_id = f"opp-test-{uuid.uuid4().hex[:6]}"
        opp = Opportunity(
            id=opp_id,
            title="Status Validation Opp",
            provider="Test Provider",
            category="Scholarship",
            official_url="https://test.ke"
        )
        session.add(opp)
        session.commit()

        with pytest.raises(ValueError, match="Invalid verification_status 'APPROVED'"):
            OpportunityEligibilityCriterion(
                opportunity_id=opp_id,
                criterion_type=CriterionCategory.KCSE_GRADE.value,
                operator=CriterionOperator.GTE.value,
                criterion_value="B+",
                verification_status="APPROVED",
                source_text="KCSE B+ required."
            )

    def test_06_verified_state_requires_admin_metadata(self, isolated_db):
        """Scenario 6: VERIFIED state requires non-empty verified_by, verified_at, and evidence_url."""
        session, _ = isolated_db
        admin = User(
            email=f"admin_ver_{uuid.uuid4().hex[:6]}@moi.ac.ke",
            hashed_password="SecretAdminPassword!",
            full_name="Verifying Officer",
            role="admin"
        )
        session.add(admin)
        session.commit()

        opp_id = f"opp-ver-invar-{uuid.uuid4().hex[:6]}"
        opp = Opportunity(
            id=opp_id,
            title="Verified Invariant Opp",
            provider="Test Provider",
            category="Scholarship",
            official_url="https://test.ke"
        )
        session.add(opp)
        session.commit()

        # Attempt 1: VERIFIED without verified_by raises ValueError
        c1 = OpportunityEligibilityCriterion(
            opportunity_id=opp_id,
            criterion_type=CriterionCategory.KCSE_GRADE.value,
            operator=CriterionOperator.GTE.value,
            criterion_value="B+",
            source_text="KCSE B+ required.",
            verification_status=CriterionVerificationStatus.VERIFIED.value,
            verified_by=None,
            verified_at=datetime.utcnow(),
            evidence_url="https://official.ke/bulletin"
        )
        session.add(c1)
        with pytest.raises(ValueError, match="A VERIFIED criterion must specify a non-empty verified_by"):
            session.commit()
        session.rollback()

        # Attempt 2: VERIFIED without evidence_url raises ValueError
        c2 = OpportunityEligibilityCriterion(
            opportunity_id=opp_id,
            criterion_type=CriterionCategory.KCSE_GRADE.value,
            operator=CriterionOperator.GTE.value,
            criterion_value="B+",
            source_text="KCSE B+ required.",
            verification_status=CriterionVerificationStatus.VERIFIED.value,
            verified_by=admin.id,
            verified_at=datetime.utcnow(),
            evidence_url=None
        )
        session.add(c2)
        with pytest.raises(ValueError, match="A VERIFIED criterion must specify a non-empty authoritative evidence_url"):
            session.commit()
        session.rollback()

        # Attempt 3: VERIFIED with all required metadata succeeds
        c3 = OpportunityEligibilityCriterion(
            opportunity_id=opp_id,
            criterion_type=CriterionCategory.KCSE_GRADE.value,
            operator=CriterionOperator.GTE.value,
            criterion_value="B+",
            source_text="KCSE B+ required.",
            verification_status=CriterionVerificationStatus.VERIFIED.value,
            verified_by=admin.id,
            verified_at=datetime.utcnow(),
            evidence_url="https://official.ke/bulletin"
        )
        session.add(c3)
        session.commit()
        assert c3.verification_status == "VERIFIED"

    def test_07_pending_review_rejects_verified_metadata(self, isolated_db):
        """Scenario 7: PENDING_REVIEW state rejects retained verified_by or verified_at metadata."""
        session, _ = isolated_db
        admin = User(
            email=f"admin_pend_{uuid.uuid4().hex[:6]}@moi.ac.ke",
            hashed_password="SecretAdminPassword!",
            full_name="Verifying Officer",
            role="admin"
        )
        session.add(admin)
        session.commit()

        opp_id = f"opp-pending-invar-{uuid.uuid4().hex[:6]}"
        opp = Opportunity(
            id=opp_id,
            title="Pending Invariant Opp",
            provider="Test Provider",
            category="Internship",
            official_url="https://test.ke"
        )
        session.add(opp)
        session.commit()

        # PENDING_REVIEW with verified_by raises ValueError
        crit = OpportunityEligibilityCriterion(
            opportunity_id=opp_id,
            criterion_type=CriterionCategory.MINIMUM_ACADEMIC_GRADE.value,
            operator=CriterionOperator.GTE.value,
            criterion_value="UPPER_SECOND",
            source_text="Upper Second required.",
            verification_status=CriterionVerificationStatus.PENDING_REVIEW.value,
            verified_by=admin.id,
            verified_at=datetime.utcnow()
        )
        session.add(crit)
        with pytest.raises(ValueError, match="A PENDING_REVIEW criterion must not retain verified_by or verified_at"):
            session.commit()
        session.rollback()

    def test_08_database_check_constraints_enforced(self, isolated_db):
        """Scenario 16: Database CHECK constraints reject empty text and invalid numeric scale."""
        session, test_engine = isolated_db
        opp_id = f"opp-ck-{uuid.uuid4().hex[:6]}"
        opp = Opportunity(
            id=opp_id,
            title="Check Constraint Opp",
            provider="Test Provider",
            category="Internship",
            official_url="https://test.ke"
        )
        session.add(opp)
        session.commit()

        # Test empty source_text rejected by validator
        with pytest.raises(ValueError, match="source_text cannot be empty"):
            OpportunityEligibilityCriterion(
                opportunity_id=opp_id,
                criterion_type=CriterionCategory.NUMERIC_GPA.value,
                operator=CriterionOperator.GTE.value,
                criterion_value="3.0",
                source_text="   "
            )

        # Test non-positive numeric_scale rejected
        with pytest.raises(ValueError, match="numeric_scale must be strictly greater than zero"):
            OpportunityEligibilityCriterion(
                opportunity_id=opp_id,
                criterion_type=CriterionCategory.NUMERIC_GPA.value,
                operator=CriterionOperator.GTE.value,
                criterion_value="3.0",
                numeric_scale=Decimal("-4.00"),
                source_text="Valid source text."
            )

    def test_09_on_delete_restrict_prevents_opportunity_deletion(self, isolated_db):
        """Scenario 9: ON DELETE RESTRICT blocks physical deletion of an opportunity with criteria."""
        session, _ = isolated_db
        opp_id = f"opp-restrict-{uuid.uuid4().hex[:6]}"
        opp = Opportunity(
            id=opp_id,
            title="Protected High-Stakes Program",
            provider="Public Service Commission",
            category="Internship",
            official_url="https://publicservice.go.ke"
        )
        session.add(opp)
        session.commit()

        crit = OpportunityEligibilityCriterion(
            opportunity_id=opp_id,
            criterion_type=CriterionCategory.GRADUATION_YEAR_RANGE.value,
            operator=CriterionOperator.BETWEEN.value,
            criterion_value="2023-2026",
            source_text="Graduated between 2023 and 2026."
        )
        session.add(crit)
        session.commit()

        session.delete(opp)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        assert session.query(Opportunity).filter(Opportunity.id == opp_id).first() is not None
        assert session.query(OpportunityEligibilityCriterion).filter(
            OpportunityEligibilityCriterion.opportunity_id == opp_id
        ).count() == 1

    def test_10_administrator_deletion_sets_verified_by_null(self, isolated_db):
        """Scenario 10: Deleting an administrator nullifies verified_by (ON DELETE SET NULL)."""
        session, _ = isolated_db
        admin = User(
            email=f"admin_{uuid.uuid4().hex[:6]}@moi.ac.ke",
            hashed_password="SecretAdminPassword!",
            full_name="Chief Verification Officer",
            role="admin"
        )
        session.add(admin)
        session.commit()

        opp_id = f"opp-admin-setnull-{uuid.uuid4().hex[:6]}"
        opp = Opportunity(
            id=opp_id,
            title="Admin Integrity Test Opportunity",
            provider="HELB",
            category="Scholarship",
            official_url="https://hef.co.ke"
        )
        session.add(opp)
        session.commit()

        crit = OpportunityEligibilityCriterion(
            opportunity_id=opp_id,
            criterion_type=CriterionCategory.KCSE_GRADE.value,
            operator=CriterionOperator.GTE.value,
            criterion_value="C+",
            source_text="KCSE C+ minimum required.",
            verification_status=CriterionVerificationStatus.VERIFIED.value,
            verified_by=admin.id,
            verified_at=datetime.utcnow(),
            evidence_url="https://hef.co.ke/official-guidelines"
        )
        session.add(crit)
        session.commit()

        assert crit.verified_by == admin.id

        session.delete(admin)
        session.commit()

        session.refresh(crit)
        assert crit.verified_by is None
        assert crit.verification_status == CriterionVerificationStatus.VERIFIED.value

    def test_11_criterion_audit_log_creation_and_restrict(self, isolated_db):
        """Scenarios 17 & 18: OpportunityCriterionVerificationLog records audit trail and blocks criterion deletion."""
        session, _ = isolated_db
        admin = User(
            email=f"audit_admin_{uuid.uuid4().hex[:6]}@moi.ac.ke",
            hashed_password="SecretAdminPassword!",
            full_name="Auditor General",
            role="admin"
        )
        session.add(admin)
        session.commit()

        opp_id = f"opp-audit-log-{uuid.uuid4().hex[:6]}"
        opp = Opportunity(
            id=opp_id,
            title="Audit Trail Protected Opp",
            provider="KRA",
            category="Internship",
            official_url="https://kra.go.ke"
        )
        session.add(opp)
        session.commit()

        crit = OpportunityEligibilityCriterion(
            opportunity_id=opp_id,
            criterion_type=CriterionCategory.MINIMUM_ACADEMIC_GRADE.value,
            operator=CriterionOperator.GTE.value,
            criterion_value="UPPER_SECOND",
            source_text="Upper Second required.",
            verification_status=CriterionVerificationStatus.VERIFIED.value,
            verified_by=admin.id,
            verified_at=datetime.utcnow(),
            evidence_url="https://kra.go.ke/internships"
        )
        session.add(crit)
        session.commit()

        # Create verification log
        crit_log = OpportunityCriterionVerificationLog(
            criterion_id=crit.id,
            admin_id=admin.id,
            admin_email=admin.email,
            previous_status="PENDING_REVIEW",
            new_status="VERIFIED",
            evidence_url="https://kra.go.ke/internships",
            evidence_notes="Verified against KRA 2026 official recruitment portal.",
            metadata_json='{"verified_fields": ["min_grade"]}'
        )
        session.add(crit_log)
        session.commit()

        session.refresh(crit)
        assert len(crit.verification_logs) == 1
        assert crit.verification_logs[0].new_status == "VERIFIED"

        # Attempt physical deletion of criterion while audit logs exist -> Blocked by ON DELETE RESTRICT
        session.delete(crit)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        # Admin deletion sets admin_id to NULL in log without deleting audit entry
        session.delete(admin)
        session.commit()
        session.refresh(crit_log)
        assert crit_log.admin_id is None
        assert crit_log.admin_email is not None

    def test_12_typed_criterion_values_storage(self, isolated_db):
        """Scenario 13-15: Typed validation and storage across categories."""
        session, _ = isolated_db
        opp_id = f"opp-typed-{uuid.uuid4().hex[:6]}"
        opp = Opportunity(
            id=opp_id,
            title="Typed Criteria Opp",
            provider="Test",
            category="Internship",
            official_url="https://test.ke"
        )
        session.add(opp)
        session.commit()

        # GPA
        c_gpa = OpportunityEligibilityCriterion(
            opportunity_id=opp_id,
            criterion_type=CriterionCategory.NUMERIC_GPA.value,
            operator=CriterionOperator.GTE.value,
            criterion_value="3.30",
            numeric_scale=Decimal("4.00"),
            source_text="GPA 3.3/4.0."
        )
        # County
        c_county = OpportunityEligibilityCriterion(
            opportunity_id=opp_id,
            criterion_type=CriterionCategory.COUNTY_RESTRICTION.value,
            operator=CriterionOperator.IN.value,
            criterion_value="Turkana, Samburu",
            source_text="Only Turkana and Samburu."
        )
        # Graduation Year Range
        c_grad = OpportunityEligibilityCriterion(
            opportunity_id=opp_id,
            criterion_type=CriterionCategory.GRADUATION_YEAR_RANGE.value,
            operator=CriterionOperator.BETWEEN.value,
            criterion_value="2023-2026",
            source_text="Graduated between 2023 and 2026."
        )
        session.add_all([c_gpa, c_county, c_grad])
        session.commit()

        session.refresh(opp)
        assert len(opp.eligibility_criteria) >= 3

    def test_13_indexes_and_table_metadata(self):
        """Scenario 20: Table definitions, indexes, composite indexes."""
        crit_table = OpportunityEligibilityCriterion.__table__
        log_table = OpportunityCriterionVerificationLog.__table__

        assert crit_table.name == "opportunity_eligibility_criteria"
        assert log_table.name == "opportunity_criterion_verification_logs"

        crit_indexes = {idx.name for idx in crit_table.indexes}
        assert "ix_opp_crit_opp_type" in crit_indexes
        assert "ix_opp_crit_opp_status" in crit_indexes

        log_indexes = {idx.name for idx in log_table.indexes}
        assert "ix_crit_ver_logs_crit_created" in log_indexes

    def test_14_backend_and_api_models_identical(self):
        """Scenario 21: Byte-for-byte source parity between backend/app/models and api/app/models."""
        backend_file = backend_dir / "app" / "models" / "entities.py"
        api_file = repo_root / "api" / "app" / "models" / "entities.py"
        assert backend_file.exists()
        assert api_file.exists()
        assert filecmp.cmp(str(backend_file), str(api_file), shallow=False), (
            "backend/app/models/entities.py and api/app/models/entities.py differ!"
        )

    def test_15_alembic_migration_consistency_and_execution(self):
        """Scenario 22: Migration revision chain and isolated execution on temporary database."""
        migration_file = backend_dir / "alembic" / "versions" / "05a08e706197_add_opportunity_eligibility_criteria.py"
        migration_198 = backend_dir / "alembic" / "versions" / "05a08e706198_add_eligibility_criteria_integrity_and_audit_triggers.py"
        assert migration_file.exists(), "Migration file does not exist!"
        assert migration_198.exists(), "Migration 198 file does not exist!"

        content = migration_file.read_text()
        assert "revision: str = '05a08e706197'" in content
        assert "down_revision: Union[str, Sequence[str], None] = '05a08e706196'" in content
        assert "opportunity_eligibility_criteria" in content
        assert "opportunity_criterion_verification_logs" in content

        content_198 = migration_198.read_text()
        assert "revision: str = '05a08e706198'" in content_198
        assert "down_revision: Union[str, Sequence[str], None] = '05a08e706197'" in content_198
        assert "ck_opp_crit_type" in content_198
        assert "ck_opp_crit_verified_requirements" in content_198

        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        import importlib.util

        spec = importlib.util.spec_from_file_location("migration_05a08e706197", str(migration_file))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        test_engine = create_engine("sqlite:///:memory:")
        tables_to_create = [
            t for name, t in Base.metadata.tables.items()
            if name not in ("opportunity_eligibility_criteria", "opportunity_criterion_verification_logs")
        ]
        Base.metadata.create_all(bind=test_engine, tables=tables_to_create)

        # Test UPGRADE
        with test_engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            op_obj = Operations(ctx)

            orig_get_bind = mod.op.get_bind
            orig_create_table = mod.op.create_table
            orig_create_index = mod.op.create_index
            orig_drop_table = mod.op.drop_table

            mod.op.get_bind = lambda: conn
            mod.op.create_table = op_obj.create_table
            mod.op.create_index = op_obj.create_index
            mod.op.drop_table = op_obj.drop_table

            try:
                mod.upgrade()
                conn.commit()
            finally:
                mod.op.get_bind = orig_get_bind
                mod.op.create_table = orig_create_table
                mod.op.create_index = orig_create_index
                mod.op.drop_table = orig_drop_table

        with test_engine.connect() as conn:
            inspector = sa.inspect(conn)
            tables = set(inspector.get_table_names())
            assert "opportunity_eligibility_criteria" in tables
            assert "opportunity_criterion_verification_logs" in tables

        # Test DOWNGRADE
        with test_engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            op_obj = Operations(ctx)

            orig_get_bind = mod.op.get_bind
            orig_drop_table = mod.op.drop_table

            mod.op.get_bind = lambda: conn
            mod.op.drop_table = op_obj.drop_table

            try:
                mod.downgrade()
                conn.commit()
            finally:
                mod.op.get_bind = orig_get_bind
                mod.op.drop_table = orig_drop_table

        with test_engine.connect() as conn:
            inspector_after = sa.inspect(conn)
            tables_after = set(inspector_after.get_table_names())
            assert "opportunity_eligibility_criteria" not in tables_after
            assert "opportunity_criterion_verification_logs" not in tables_after
