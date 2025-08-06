"""Startup configuration checks and logging."""

import sys

import asyncpg
import httpx
import spacy
import structlog

logger = structlog.get_logger()


async def check_database() -> bool:
    """Check PostgreSQL connectivity and permissions."""
    from pond.config import settings

    print("  Checking PostgreSQL...", flush=True)

    try:
        # Test basic connection
        conn = await asyncpg.connect(settings.database_url)

        # Check if we can create schemas (permission test)
        test_schema = "_pond_startup_test_"
        quoted_schema = await conn.fetchval("SELECT quote_ident($1)", test_schema)

        try:
            await conn.execute(f"CREATE SCHEMA IF NOT EXISTS {quoted_schema}")
            await conn.execute(f"DROP SCHEMA IF EXISTS {quoted_schema}")
            print("    ✓ Database connection established", flush=True)
            print("    ✓ Schema creation permissions verified", flush=True)
        except Exception as e:
            print(f"    ✗ Insufficient database permissions: {e}", flush=True)
            print("      User needs CREATE SCHEMA privilege", flush=True)
            return False
        finally:
            await conn.close()

        return True

    except asyncpg.InvalidCatalogNameError:
        print("    ✗ Database does not exist", flush=True)
        print(f"      Create it with: createdb {settings.database_url.split('/')[-1]}", flush=True)
        return False
    except Exception as e:
        print(f"    ✗ Cannot connect to PostgreSQL: {e}", flush=True)
        print("      Check DATABASE_URL environment variable", flush=True)
        return False


async def check_pgvector() -> bool:
    """Check if pgvector extension is available."""
    from pond.config import settings

    print("  Checking pgvector extension...", flush=True)

    conn = await asyncpg.connect(settings.database_url)
    try:
        # Check if extension exists
        result = await conn.fetchval(
            "SELECT COUNT(*) FROM pg_available_extensions WHERE name = 'vector'"
        )
        if result == 0:
            print("    ✗ pgvector extension not available", flush=True)
            print("      Use the pgvector-enabled Postgres image", flush=True)
            print("      e.g., pgvector/pgvector:pg17", flush=True)
            return False

        # Try to create it (idempotent)
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        print("    ✓ pgvector extension available", flush=True)

    except Exception as e:
        print(f"    ✗ Error checking pgvector: {e}", flush=True)
        return False
    finally:
        await conn.close()

    return True


def check_spacy_model() -> bool:
    """Check if required SpaCy model is installed."""
    print("  Checking NLP model...", flush=True)

    try:
        # Try to load the model
        spacy.load("en_core_web_lg")
        print("    ✓ SpaCy model 'en_core_web_lg' loaded", flush=True)
        return True
    except OSError:
        print("    ✗ SpaCy model 'en_core_web_lg' not found", flush=True)
        print("      Install it with: python -m spacy download en_core_web_lg", flush=True)
        return False
    except Exception as e:
        print(f"    ✗ Error loading SpaCy model: {e}", flush=True)
        return False


async def check_embedding_provider() -> bool:
    """Check if embedding provider is healthy (modular!)."""
    from pond.config import settings

    print(f"  Checking embedding provider ({settings.embedding_provider})...", flush=True)

    if settings.embedding_provider == "mock":
        print("    ✓ Mock provider always ready", flush=True)
        return True

    if settings.embedding_provider == "ollama":
        # Check Ollama service
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{settings.ollama_url}/api/tags",
                    timeout=5.0
                )
                response.raise_for_status()
                print(f"    ✓ Ollama service reachable at {settings.ollama_url}", flush=True)

                # Check if model is available
                data = response.json()
                models = [m.get("name", "").split(":")[0] for m in data.get("models", [])]

                if settings.ollama_embedding_model and settings.ollama_embedding_model.split(":")[0] not in models:
                    print(f"    ✗ Model '{settings.ollama_embedding_model}' not found", flush=True)
                    print(f"      Pull it with: ollama pull {settings.ollama_embedding_model}", flush=True)
                    return False
                elif settings.ollama_embedding_model:
                    print(f"    ✓ Model '{settings.ollama_embedding_model}' available", flush=True)
                else:
                    print("    ✓ Using default model 'nomic-embed-text'", flush=True)
                return True

        except httpx.ConnectError:
            print(f"    ✗ Cannot connect to Ollama at {settings.ollama_url}", flush=True)
            print("      Is Ollama running? Start it with: ollama serve", flush=True)
            return False
        except Exception as e:
            print(f"    ✗ Error checking Ollama: {e}", flush=True)
            return False


async def run_startup_checks() -> bool:
    """Run all vital sign checks and return success status."""

    # Force flush to ensure output is visible
    print("\nStarting Pond - Checking vital signs...\n", flush=True)
    sys.stdout.flush()

    # Check in order of dependency
    if not await check_database():
        return False
    if not await check_pgvector():
        return False
    if not check_spacy_model():
        return False
    if not await check_embedding_provider():
        return False

    print("\n✓ All vital signs normal - Pond is ready!\n", flush=True)
    sys.stdout.flush()
    return True


def check_configuration():
    """Legacy function for backward compatibility."""
    from pond.config import settings

    if settings.embedding_provider is None:
        logger.critical(
            "EMBEDDING_PROVIDER not configured",
            help="Set EMBEDDING_PROVIDER=ollama or EMBEDDING_PROVIDER=mock",
        )
        return False

    return True


def get_health_status() -> dict:
    """Get health status for the embedding service configuration."""
    from pond.config import settings

    if settings.embedding_provider is None:
        return {
            "healthy": False,
            "service": "embeddings",
            "error": "EMBEDDING_PROVIDER not configured",
            "help": "Set EMBEDDING_PROVIDER=ollama or EMBEDDING_PROVIDER=mock",
        }

    return {
        "healthy": True,
        "service": "embeddings",
        "provider": settings.embedding_provider,
        "configured": True,
    }
