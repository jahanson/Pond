"""Pond CLI main entry point."""

import asyncio
import sys

import click
import structlog

from pond.infrastructure.auth import APIKeyManager
from pond.infrastructure.database import DatabasePool
from pond.infrastructure.schema import ensure_tenant_schema, list_tenants, tenant_exists

# Configure logging for CLI
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.dev.ConsoleRenderer(colors=True),
    ],
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@click.group()
@click.pass_context
def cli(ctx):
    """Pond - Semantic memory system for AI assistants.
    
    System administration tool for managing tenants, API keys, and data.
    """
    # Store shared resources in context
    ctx.ensure_object(dict)


@cli.group()
@click.pass_context
def tenant(ctx):
    """Manage tenants."""
    pass


@tenant.command(name="list")
@click.pass_context
def tenant_list(ctx):
    """List all tenants."""
    async def _list():
        pool = DatabasePool()
        try:
            await pool.initialize()
            async with pool.acquire() as conn:
                tenants = await list_tenants(conn)
                if not tenants:
                    click.echo("No tenants found.")
                else:
                    click.echo(f"Found {len(tenants)} tenant(s):")
                    for t in tenants:
                        click.echo(f"  - {t}")
        finally:
            await pool.close()

    asyncio.run(_list())


@tenant.command(name="create")
@click.argument("name")
@click.option("--with-key", is_flag=True, help="Generate an API key for the new tenant")
@click.pass_context
def tenant_create(ctx, name: str, with_key: bool):
    """Create a new tenant."""
    async def _create():
        pool = DatabasePool()
        try:
            await pool.initialize()

            # Check if tenant already exists
            async with pool.acquire() as conn:
                if await tenant_exists(conn, name):
                    click.echo(f"Error: Tenant '{name}' already exists.", err=True)
                    sys.exit(1)

                # Create the tenant schema
                await ensure_tenant_schema(conn, name)
                click.echo(f"✓ Created tenant: {name}")

            # Generate API key if requested
            if with_key:
                api_key_manager = APIKeyManager(pool)
                key = await api_key_manager.create_key(
                    name,
                    description=f"Initial key for {name}"
                )
                click.echo(f"✓ Generated API key: {key}")
                click.echo("\n⚠️  Save this key now! It cannot be retrieved later.")

        finally:
            await pool.close()

    asyncio.run(_create())


@cli.group()
@click.pass_context
def key(ctx):
    """Manage API keys."""
    pass


@key.command(name="generate")
@click.argument("tenant")
@click.option("--description", "-d", help="Description for the key")
@click.pass_context
def key_generate(ctx, tenant: str, description: str | None):
    """Generate a new API key for a tenant."""
    async def _generate():
        pool = DatabasePool()
        try:
            await pool.initialize()

            # Check tenant exists
            async with pool.acquire() as conn:
                if not await tenant_exists(conn, tenant):
                    click.echo(f"Error: Tenant '{tenant}' does not exist.", err=True)
                    sys.exit(1)

            # Generate key
            api_key_manager = APIKeyManager(pool)
            key = await api_key_manager.create_key(tenant, description)

            click.echo(f"Generated API key for tenant '{tenant}':")
            click.echo(f"  {key}")
            click.echo("\n⚠️  Save this key now! It cannot be retrieved later.")

        finally:
            await pool.close()

    asyncio.run(_generate())


@key.command(name="list")
@click.argument("tenant")
@click.pass_context
def key_list(ctx, tenant: str):
    """List API keys for a tenant."""
    async def _list():
        pool = DatabasePool()
        try:
            await pool.initialize()

            # Check tenant exists
            async with pool.acquire() as conn:
                if not await tenant_exists(conn, tenant):
                    click.echo(f"Error: Tenant '{tenant}' does not exist.", err=True)
                    sys.exit(1)

            # List keys
            api_key_manager = APIKeyManager(pool)
            keys = await api_key_manager.list_keys(tenant)

            if not keys:
                click.echo(f"No API keys found for tenant '{tenant}'.")
            else:
                click.echo(f"API keys for tenant '{tenant}':")
                for k in keys:
                    status = "active" if k["active"] else "inactive"
                    last_used = k["last_used"] or "never"
                    click.echo(f"  ID: {k['id']} | {status} | Last used: {last_used}")
                    if k["description"]:
                        click.echo(f"      {k['description']}")

        finally:
            await pool.close()

    asyncio.run(_list())


@key.command(name="rotate")
@click.argument("tenant")
@click.option("--old-key", help="Specific key to rotate (deactivates all if not specified)")
@click.pass_context
def key_rotate(ctx, tenant: str, old_key: str | None):
    """Rotate API keys for a tenant."""
    async def _rotate():
        pool = DatabasePool()
        try:
            await pool.initialize()

            # Check tenant exists
            async with pool.acquire() as conn:
                if not await tenant_exists(conn, tenant):
                    click.echo(f"Error: Tenant '{tenant}' does not exist.", err=True)
                    sys.exit(1)

            # Rotate key(s)
            api_key_manager = APIKeyManager(pool)
            new_key = await api_key_manager.rotate_key(tenant, old_key)

            if old_key:
                click.echo("✓ Deactivated old key")
            else:
                click.echo(f"✓ Deactivated all existing keys for tenant '{tenant}'")

            click.echo("✓ Generated new API key:")
            click.echo(f"  {new_key}")
            click.echo("\n⚠️  Save this key now! It cannot be retrieved later.")

        finally:
            await pool.close()

    asyncio.run(_rotate())


@key.command(name="deactivate")
@click.argument("tenant")
@click.argument("key_id", type=int)
@click.pass_context
def key_deactivate(ctx, tenant: str, key_id: int):
    """Deactivate a specific API key."""
    async def _deactivate():
        pool = DatabasePool()
        try:
            await pool.initialize()

            # Check tenant exists
            async with pool.acquire() as conn:
                if not await tenant_exists(conn, tenant):
                    click.echo(f"Error: Tenant '{tenant}' does not exist.", err=True)
                    sys.exit(1)

            # Deactivate key
            api_key_manager = APIKeyManager(pool)
            if await api_key_manager.deactivate_key(tenant, key_id):
                click.echo(f"✓ Deactivated key {key_id} for tenant '{tenant}'")
            else:
                click.echo(f"Error: Key {key_id} not found or already inactive.", err=True)
                sys.exit(1)

        finally:
            await pool.close()

    asyncio.run(_deactivate())


if __name__ == "__main__":
    cli()
