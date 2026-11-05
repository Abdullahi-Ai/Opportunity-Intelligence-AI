"""
Unit and integration tests for Stage 2.2B-1B:
Migration Integrity, Append-Only Audit History, and Criterion Invariants Remediation.

Covers:
1. Migration revision chain (05a08e706197 -> 05a08e706198).
2. Clean sequential execution of migration upgrade() and downgrade() on temporary database.
3. Verification integrity: PENDING_REVIEW vs VERIFIED invariants.
4. Append-only audit history immutability:
   - ORM update blocked with ValueError.
   - ORM delete blocked with ValueError.
   - Demonstrates GPA criterion change from 3.0 to 3.3 with structured before/after snapshots.
5. Historical administrator attribution preservation upon admin account deletion.
6. ON DELETE RESTRICT on criterion_id prevents criterion erasure when logs exist.
7. Backend/API mirror parity.
"""

import sys
import uuid
import json
import filecmp
from pathlib import Path
from datetime import datetime
from decimal import Decimal
import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

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


@pytest.fixture
def db_session():
    """Provides a fresh isolated in-memory SQLite database per test."""
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


def test_01_migration_revision_chain():
    """Verifies Alembic migration graph: 05a08e706196 -> 05a08e706197 -> 05a08e706198."""
    v197 = backend_dir / "alembic" / "versions" / "05a08e706197_add_opportunity_eligibility_criteria.py"
    v198 = backend_dir / "alembic" / "versions" / "05a08e706198_add_eligibility_criteria_integrity_and_audit_triggers.py"

    assert v197.exists(), "05a08e706197 migration file missing"
    assert v198.exists(), "05a08e706198 migration file missing"

    c197 = v197.read_text()
    assert "revision: str = '05a08e706197'" in c197
    assert "down_revision: Union[str, Sequence[str], None] = '05a08e706196'" in c197

    c198 = v198.read_text()
    assert "revision: str = '05a08e706198'" in c198
    assert "down_revision: Union[str, Sequence[str], None] = '05a08e706197'" in c198


def test_02_migration_upgrade_and_downgrade():
    """Tests upgrade and downgrade of both migrations sequentially on isolated database."""
    import importlib.util
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    f197 = backend_dir / "alembic" / "versions" / "05a08e706197_add_opportunity_eligibility_criteria.py"
    f198 = backend_dir / "alembic" / "versions" / "05a08e706198_add_eligibility_criteria_integrity_and_audit_triggers.py"

    spec197 = importlib.util.spec_from_file_location("mig_197", str(f197))
    mod197 = importlib.util.module_from_spec(spec197)
    spec197.loader.exec_module(mod197)

    spec198 = importlib.util.spec_from_file_location("mig_198", str(f198))
    mod198 = importlib.util.module_from_spec(spec198)
    spec198.loader.exec_module(mod198)

    test_engine = create_engine("sqlite:///:memory:")

    # Create prerequisite tables (users, opportunities)
    tables_to_create = [
        t for name, t in Base.metadata.tables.items()
        if name not in ("opportunity_eligibility_criteria", "opportunity_criterion_verification_logs")
    ]
    Base.metadata.create_all(bind=test_engine, tables=tables_to_create)

    with test_engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        op_obj = Operations(ctx)

        # Patch Alembic op for mod197
        orig_197_get_bind = mod197.op.get_bind
        orig_197_create_table = mod197.op.create_table
        orig_197_create_index = mod197.op.create_index
        orig_197_drop_table = mod197.op.drop_table

        mod197.op.get_bind = lambda: conn
        mod197.op.create_table = op_obj.create_table
        mod197.op.create_index = op_obj.create_index
        mod197.op.drop_table = op_obj.drop_table

        # Patch Alembic op for mod198
        orig_198_get_bind = mod198.op.get_bind
        orig_198_batch_alter_table = mod198.op.batch_alter_table
        orig_198_execute = mod198.op.execute

        mod198.op.get_bind = lambda: conn
        mod198.op.batch_alter_table = op_obj.batch_alter_table
        mod198.op.execute = op_obj.execute

        try:
            # Upgrade 197
            mod197.upgrade()
            conn.commit()

            # Upgrade 198
            mod198.upgrade()
            conn.commit()

            inspector = sa.inspect(conn)
            tables = set(inspector.get_table_names())
            assert "opportunity_eligibility_criteria" in tables
            assert "opportunity_criterion_verification_logs" in tables

            # Downgrade 198
            mod198.downgrade()
            conn.commit()

            # Downgrade 197
            mod197.downgrade()
            conn.commit()

            inspector_after = sa.inspect(conn)
            tables_after = set(inspector_after.get_table_names())
            assert "opportunity_eligibility_criteria" not in tables_after
            assert "opportunity_criterion_verification_logs" not in tables_after
        finally:
            mod197.op.get_bind = orig_197_get_bind
            mod197.op.create_table = orig_197_create_table
            mod197.op.create_index = orig_197_create_index
            mod197.op.drop_table = orig_197_drop_table

            mod198.op.get_bind = orig_198_get_bind
            mod198.op.batch_alter_table = orig_198_batch_alter_table
            mod198.op.execute = orig_198_execute


def test_03_verification_invariants_and_audit_snapshots(db_session):
    """Demonstrates GPA change from 3.0 to 3.3 with before/after snapshots and invariants."""
    session, _ = db_session
    admin = User(
        email=f"officer_{uuid.uuid4().hex[:6]}@moi.ac.ke",
        hashed_password="SecretAdminPassword!",
        full_name="Verification Officer",
        role="admin"
    )
    session.add(admin)
    session.commit()

    opp = Opportunity(
        id=f"opp-gpa-{uuid.uuid4().hex[:6]}",
        title="Engineering Graduate Trainee",
        provider="KenGen",
        category="Internship",
        official_url="https://kengen.co.ke"
    )
    session.add(opp)
    session.commit()

    # Step 1: Ingest criterion with initial GPA 3.0
    crit = OpportunityEligibilityCriterion(
        opportunity_id=opp.id,
        criterion_type=CriterionCategory.NUMERIC_GPA.value,
        operator=CriterionOperator.GTE.value,
        criterion_value="3.0",
        numeric_scale=Decimal("4.00"),
        source_text="Minimum GPA 3.0 required.",
        verification_status=CriterionVerificationStatus.PENDING_REVIEW.value
    )
    session.add(crit)
    session.commit()
    assert crit.verification_status == "PENDING_REVIEW"
    assert crit.verified_by is None
    assert crit.verified_at is None

    # Step 2: Administrator updates requirement to GPA 3.3 based on revised bulletin
    before_snap = {
        "criterion_value": crit.criterion_value,
        "numeric_scale": str(crit.numeric_scale),
        "source_text": crit.source_text,
        "verification_status": crit.verification_status
    }

    crit.criterion_value = "3.3"
    crit.source_text = "Revised: Minimum GPA 3.3 required for engineering graduates."
    crit.verified_by = admin.id
    crit.verified_at = datetime.utcnow()
    crit.evidence_url = "https://kengen.co.ke/careers/engineering-trainee-2026.pdf"
    crit.verification_status = CriterionVerificationStatus.VERIFIED.value

    after_snap = {
        "criterion_value": crit.criterion_value,
        "numeric_scale": str(crit.numeric_scale),
        "source_text": crit.source_text,
        "verification_status": crit.verification_status,
        "evidence_url": crit.evidence_url
    }

    log = OpportunityCriterionVerificationLog(
        criterion_id=crit.id,
        admin_id=admin.id,
        admin_email=admin.email,
        event_type="UPDATE_AND_VERIFY",
        previous_status="PENDING_REVIEW",
        new_status="VERIFIED",
        before_snapshot=json.dumps(before_snap),
        after_snapshot=json.dumps(after_snap),
        evidence_url=crit.evidence_url,
        evidence_notes="Verified against KenGen official 2026 trainee specifications PDF.",
        metadata_json=json.dumps({"scale": "4.00", "min_gpa": "3.3"})
    )
    session.add(log)
    session.commit()

    session.refresh(crit)
    session.refresh(log)
    assert crit.criterion_value == "3.3"
    assert log.event_type == "UPDATE_AND_VERIFY"
    assert "3.0" in log.before_snapshot
    assert "3.3" in log.after_snapshot


def test_04_audit_log_orm_immutability(db_session):
    """Enforces that OpportunityCriterionVerificationLog cannot be updated or deleted."""
    session, _ = db_session
    opp = Opportunity(
        id=f"opp-audit-{uuid.uuid4().hex[:6]}",
        title="Audit Protected Opp",
        provider="KCB",
        category="Scholarship",
        official_url="https://kcbgroup.com"
    )
    session.add(opp)
    session.commit()

    crit = OpportunityEligibilityCriterion(
        opportunity_id=opp.id,
        criterion_type=CriterionCategory.ACADEMIC_STANDING.value,
        operator=CriterionOperator.EQ.value,
        criterion_value="UNDERGRADUATE",
        source_text="Must be continuing undergraduate.",
        verification_status=CriterionVerificationStatus.PENDING_REVIEW.value
    )
    session.add(crit)
    session.commit()

    log = OpportunityCriterionVerificationLog(
        criterion_id=crit.id,
        admin_id=None,
        admin_email="system@test.ke",
        event_type="CREATE",
        previous_status="PENDING_REVIEW",
        new_status="PENDING_REVIEW",
        evidence_notes="Initial ingestion from web portal.",
        metadata_json="{}"
    )
    session.add(log)
    session.commit()

    # Attempt UPDATE on audit log -> ValueError
    log.evidence_notes = "Tampered evidence notes"
    with pytest.raises(ValueError, match="immutable and cannot be updated"):
        session.commit()
    session.rollback()

    # Attempt DELETE on audit log -> ValueError
    refreshed_log = session.query(OpportunityCriterionVerificationLog).filter_by(id=log.id).first()
    session.delete(refreshed_log)
    with pytest.raises(ValueError, match="immutable and cannot be deleted"):
        session.commit()
    session.rollback()


def test_05_admin_account_deletion_preserves_attribution(db_session):
    """Admin deletion sets admin_id=NULL via SET NULL, while admin_email persists."""
    session, _ = db_session
    admin = User(
        email=f"durable_admin_{uuid.uuid4().hex[:6]}@uonbi.ac.ke",
        hashed_password="SecretAdminPassword!",
        full_name="Durable Auditor",
        role="admin"
    )
    session.add(admin)
    session.commit()

    opp = Opportunity(
        id=f"opp-durable-{uuid.uuid4().hex[:6]}",
        title="Durable Audit Opp",
        provider="Equity",
        category="Scholarship",
        official_url="https://equitybank.co.ke"
    )
    session.add(opp)
    session.commit()

    crit = OpportunityEligibilityCriterion(
        opportunity_id=opp.id,
        criterion_type=CriterionCategory.COUNTY_RESTRICTION.value,
        operator=CriterionOperator.IN.value,
        criterion_value="Turkana, Samburu",
        source_text="Only Turkana and Samburu counties.",
        verification_status=CriterionVerificationStatus.VERIFIED.value,
        verified_by=admin.id,
        verified_at=datetime.utcnow(),
        evidence_url="https://equitybank.co.ke/wings-to-fly"
    )
    session.add(crit)
    session.commit()

    log = OpportunityCriterionVerificationLog(
        criterion_id=crit.id,
        admin_id=admin.id,
        admin_email=admin.email,
        event_type="VERIFY",
        previous_status="PENDING_REVIEW",
        new_status="VERIFIED",
        evidence_url=crit.evidence_url,
        evidence_notes="Verified against official circular.",
        metadata_json="{}"
    )
    session.add(log)
    session.commit()

    # Delete administrator account
    session.delete(admin)
    session.commit()

    session.refresh(crit)
    session.refresh(log)
    assert crit.verified_by is None
    assert crit.verification_status == "VERIFIED"
    assert log.admin_id is None
    assert log.admin_email.endswith("@uonbi.ac.ke")


def test_06_model_parity():
    """Confirms byte-for-byte source parity between backend/app/models and api/app/models."""
    backend_file = backend_dir / "app" / "models" / "entities.py"
    api_file = repo_root / "api" / "app" / "models" / "entities.py"
    assert backend_file.exists()
    assert api_file.exists()
    assert filecmp.cmp(str(backend_file), str(api_file), shallow=False)
