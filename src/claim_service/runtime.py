"""Process-wide service instance shared by the REST API and MCP tools."""

from claim_service.config import get_settings
from claim_service.db.engine import create_db_engine, init_schema
from claim_service.db.repository import PolicyRepository
from claim_service.db.seed import seed_all
from claim_service.service import PolicyService

_service: PolicyService | None = None


def init_runtime(database_url: str | None = None, seed: bool | None = None) -> PolicyService:
    """Create the engine, schema and service once. Later calls replace the instance."""
    global _service
    settings = get_settings()
    engine = create_db_engine(database_url or settings.database_url)
    init_schema(engine)
    repo = PolicyRepository(engine)
    service = PolicyService(repo)
    should_seed = settings.seed_sample_data if seed is None else seed
    if should_seed:
        seed_all(repo, service)
    _service = service
    return service


def get_service() -> PolicyService:
    if _service is None:
        raise RuntimeError("service is not initialised; call init_runtime() first")
    return _service
