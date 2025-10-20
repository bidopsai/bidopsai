"""
Database connection pool manager with retry logic and connection health monitoring.

This module provides a robust PostgreSQL connection pool using asyncpg with:
- Automatic retry logic for transient failures
- Connection health checks
- Graceful shutdown
- Connection pooling with configurable limits
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional, Any
from datetime import datetime, timedelta

import asyncpg
from asyncpg.pool import Pool

from core.config import get_config

logger = logging.getLogger(__name__)


class DatabaseConnectionError(Exception):
    """Raised when database connection fails"""
    pass


class DatabasePool:
    """
    Singleton database connection pool manager.
    
    Features:
    - Connection pooling with configurable size
    - Automatic retry with exponential backoff
    - Health monitoring
    - Graceful shutdown
    """
    
    _instance: Optional['DatabasePool'] = None
    _pool: Optional[Pool] = None
    _initialized: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def initialize(
        self,
        min_size: int = 5,
        max_size: int = 20,
        max_queries: int = 50000,
        max_inactive_connection_lifetime: float = 300.0,
        timeout: float = 10.0,
        command_timeout: float = 60.0,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ) -> None:
        """
        Initialize the database connection pool.
        
        Args:
            min_size: Minimum number of connections in pool
            max_size: Maximum number of connections in pool
            max_queries: Max queries per connection before recycling
            max_inactive_connection_lifetime: Max idle time before closing connection
            timeout: Connection timeout in seconds
            command_timeout: Query execution timeout in seconds
            max_retries: Maximum retry attempts for connection
            retry_delay: Initial delay between retries (exponential backoff)
        """
        if self._initialized:
            logger.warning("Database pool already initialized")
            return
        
        config = get_config()
        
        # Parse DATABASE_URL into individual components (like copilot code)
        import re
        # Format: postgresql://user:password@host:port/database
        match = re.match(r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', config.database_url)
        if not match:
            raise DatabaseConnectionError(f"Invalid DATABASE_URL format: {config.database_url}")
        
        db_user, db_password, db_host, db_port, db_name = match.groups()
        
        retry_count = 0
        last_error = None
        
        while retry_count < max_retries:
            try:
                logger.info(f"Initializing database pool (attempt {retry_count + 1}/{max_retries})...")
                logger.info(f"Connecting to {db_host}:{db_port}/{db_name} as {db_user}")
                
                # Use individual parameters instead of DSN (like working copilot code)
                self._pool = await asyncpg.create_pool(
                    host=db_host,
                    port=int(db_port),
                    database=db_name,
                    user=db_user,
                    password=db_password,
                    min_size=min_size,
                    max_size=max_size,
                    max_queries=max_queries,
                    max_inactive_connection_lifetime=max_inactive_connection_lifetime,
                    timeout=timeout,
                    command_timeout=command_timeout,
                    server_settings={
                        'application_name': 'bidopsai_agents',
                        'jit': 'off'  # Disable JIT for faster simple queries
                    }
                )
                
                # Test connection
                async with self._pool.acquire() as conn:
                    version = await conn.fetchval('SELECT version()')
                    logger.info(f"PostgreSQL version: {version[:100]}...")
                    await conn.fetchval('SELECT 1')
                
                self._initialized = True
                logger.info(f"Database pool initialized successfully (min={min_size}, max={max_size})")
                return
                
            except Exception as e:
                last_error = e
                retry_count += 1
                
                if retry_count < max_retries:
                    wait_time = retry_delay * (2 ** (retry_count - 1))  # Exponential backoff
                    logger.warning(
                        f"Database connection failed: {e}. "
                        f"Retrying in {wait_time}s... ({retry_count}/{max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Failed to initialize database pool after {max_retries} attempts: {e}")
                    raise DatabaseConnectionError(
                        f"Could not connect to database after {max_retries} attempts: {last_error}"
                    ) from last_error
    
    async def close(self) -> None:
        """Close the database pool gracefully."""
        if self._pool:
            logger.info("Closing database pool...")
            await self._pool.close()
            self._pool = None
            self._initialized = False
            logger.info("Database pool closed")
    
    @asynccontextmanager
    async def acquire(self):
        """
        Acquire a connection from the pool.
        
        Usage:
            async with db_pool.acquire() as conn:
                result = await conn.fetch('SELECT * FROM users')
        """
        if not self._initialized or not self._pool:
            raise DatabaseConnectionError("Database pool not initialized")
        
        async with self._pool.acquire() as connection:
            yield connection
    
    async def execute(
        self,
        query: str,
        *args,
        timeout: Optional[float] = None
    ) -> str:
        """
        Execute a query that doesn't return rows (INSERT, UPDATE, DELETE).
        
        Args:
            query: SQL query
            *args: Query parameters
            timeout: Optional query timeout override
            
        Returns:
            Status string from the database
        """
        async with self.acquire() as conn:
            return await conn.execute(query, *args, timeout=timeout)
    
    async def fetch(
        self,
        query: str,
        *args,
        timeout: Optional[float] = None
    ) -> list[asyncpg.Record]:
        """
        Execute a query and return all rows.
        
        Args:
            query: SQL query
            *args: Query parameters
            timeout: Optional query timeout override
            
        Returns:
            List of records
        """
        async with self.acquire() as conn:
            return await conn.fetch(query, *args, timeout=timeout)
    
    async def fetchrow(
        self,
        query: str,
        *args,
        timeout: Optional[float] = None
    ) -> Optional[asyncpg.Record]:
        """
        Execute a query and return the first row.
        
        Args:
            query: SQL query
            *args: Query parameters
            timeout: Optional query timeout override
            
        Returns:
            First record or None
        """
        async with self.acquire() as conn:
            return await conn.fetchrow(query, *args, timeout=timeout)
    
    async def fetchval(
        self,
        query: str,
        *args,
        column: int = 0,
        timeout: Optional[float] = None
    ) -> Any:
        """
        Execute a query and return a single value.
        
        Args:
            query: SQL query
            *args: Query parameters
            column: Column index to return (default: 0)
            timeout: Optional query timeout override
            
        Returns:
            Single value or None
        """
        async with self.acquire() as conn:
            return await conn.fetchval(query, *args, column=column, timeout=timeout)
    
    async def health_check(self) -> dict[str, Any]:
        """
        Check database pool health.
        
        Returns:
            Dictionary with health status and metrics
        """
        if not self._initialized or not self._pool:
            return {
                "status": "unhealthy",
                "error": "Pool not initialized",
                "timestamp": datetime.now().isoformat()
            }
        
        try:
            start_time = datetime.now()
            
            async with self.acquire() as conn:
                await conn.fetchval('SELECT 1')
            
            response_time = (datetime.now() - start_time).total_seconds()
            
            return {
                "status": "healthy",
                "pool_size": self._pool.get_size(),
                "pool_free": self._pool.get_idle_size(),
                "response_time_seconds": round(response_time, 3),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    @property
    def is_initialized(self) -> bool:
        """Check if pool is initialized."""
        return self._initialized and self._pool is not None


# Global database pool instance
db_pool = DatabasePool()


def get_database_manager() -> DatabasePool:
    """
    Get the global database pool instance.
    
    Returns:
        Global DatabasePool instance
    """
    return db_pool


async def init_database() -> None:
    """Initialize the global database pool."""
    config = get_config()
    await db_pool.initialize(
        min_size=config.db_pool_min_size,
        max_size=config.db_pool_max_size,
        timeout=config.db_connection_timeout,
        command_timeout=config.db_command_timeout
    )


async def close_database() -> None:
    """Close the global database pool."""
    await db_pool.close()


# Convenience function for transaction management
@asynccontextmanager
async def transaction():
    """
    Context manager for database transactions.
    
    Usage:
        async with transaction() as conn:
            await conn.execute('INSERT INTO ...')
            await conn.execute('UPDATE ...')
            # Automatically commits on success, rolls back on exception
    """
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            yield conn