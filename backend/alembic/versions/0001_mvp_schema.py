"""Create the current MVP schema from SQLAlchemy metadata."""

from alembic import op
from database.models import Base

revision = "0001_mvp_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade():
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
