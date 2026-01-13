"""Utilities for order processing, including Redis-based concurrency control."""

import uuid
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)


def get_stock_lock_key(variant_id):
    """Generate Redis lock key for a service variant."""
    return f"stock_lock:{variant_id}"


def try_reserve_stock(variant_id, timeout=30):
    """
    Attempt to reserve stock for a service variant using Redis lock.
    
    This is a concurrency-safe mechanism that:
    1. Acquires a lock on the variant's stock
    2. Decrements the stock count
    3. Releases the lock
    
    Args:
        variant_id: UUID of the ServiceVariant
        timeout: Lock timeout in seconds
    
    Returns:
        bool: True if stock was successfully reserved, False if not available
    
    Implementation details:
    - Uses Redis SETNX (SET if Not eXists) for atomic lock acquisition
    - Lock key: stock_lock:{variant_id}
    - Lock prevents race conditions between stock check and decrement
    - If lock acquisition fails, another customer is booking simultaneously
    """
    from services.models import ServiceVariant
    from django.db import transaction
    
    lock_key = get_stock_lock_key(variant_id)
    lock_id = str(uuid.uuid4())
    
    try:
        # Try to acquire lock
        if not cache.add(lock_key, lock_id, timeout):
            # Lock already held by another process
            logger.info(f"Failed to acquire stock lock for variant {variant_id}")
            return False
        
        try:
            # Lock acquired, now perform atomic stock decrement
            with transaction.atomic():
                variant = ServiceVariant.objects.select_for_update().get(id=variant_id)
                if variant.stock > 0:
                    variant.stock -= 1
                    variant.save(update_fields=['stock', 'updated_at'])
                    logger.info(f"Stock reserved for variant {variant_id}. Remaining: {variant.stock}")
                    return True
                else:
                    logger.warning(f"Stock exhausted for variant {variant_id}")
                    return False
        finally:
            # Always release the lock
            lock_value = cache.get(lock_key)
            if lock_value == lock_id:
                cache.delete(lock_key)
    except Exception as e:
        logger.error(f"Error reserving stock for variant {variant_id}: {str(e)}")
        # Release lock on error
        cache.delete(lock_key)
        return False


def release_stock(variant_id):
    """
    Release reserved stock (refund operation).
    
    Args:
        variant_id: UUID of the ServiceVariant
    """
    from services.models import ServiceVariant
    from django.db import transaction
    
    try:
        with transaction.atomic():
            variant = ServiceVariant.objects.select_for_update().get(id=variant_id)
            variant.stock += 1
            variant.save(update_fields=['stock', 'updated_at'])
            logger.info(f"Stock released for variant {variant_id}. Available: {variant.stock}")
    except Exception as e:
        logger.error(f"Error releasing stock for variant {variant_id}: {str(e)}")
