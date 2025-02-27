"""
Resource management utilities for Sabrina's Presence System

Manages resources to optimize memory usage and improve performance through
efficient tracking, caching, and cleanup of resources like animations and images
"""
# Standard imports
import os
import gc
import time
import psutil

# Third-party imports
from PyQt5.QtGui import QMovie

# Local imports
from .error_handling import logger, ErrorHandler

class ResourceManager:
    """Manages resources for the Presence System to optimize memory usage"""
    
    def __init__(self, cleanup_threshold=10, max_inactive_time=60):
        """Initialize the resource manager
        
        Args:
            cleanup_threshold: Number of resources before auto-cleanup (default: 10)
            max_inactive_time: Seconds before resource is considered inactive (default: 60)
        """
        # Resource tracking
        self.active_resources = {}  # Track active resources by ID
        self.last_used = {}  # Track when resources were last used
        self.resource_sizes = {}  # Track approximate size of resources
        self.resource_types = {}  # Track types of resources
        
        # Resource statistics
        self.total_registered = 0
        self.total_unregistered = 0
        self.last_cleanup_time = 0
        
        # Configuration
        self.cleanup_threshold = cleanup_threshold
        self.max_inactive_time = max_inactive_time
        
        # Performance monitoring
        self.process = psutil.Process(os.getpid())  # Current process for memory monitoring
        
        logger.info(f"ResourceManager initialized (cleanup_threshold={cleanup_threshold}, " +
                   f"max_inactive_time={max_inactive_time}s)")
        
    def register_resource(self, resource_id, resource_obj, estimated_size=0, resource_type=None):
        """Register a resource for tracking
        
        Args:
            resource_id: Unique identifier for the resource
            resource_obj: The resource object (QMovie, QPixmap, etc.)
            estimated_size: Estimated size in bytes (default: 0)
            resource_type: Type of resource for categorization (default: None)
            
        Returns:
            bool: True if newly registered, False if just updated
        """
        # Check if already registered - just update timestamp if so
        if resource_id in self.active_resources:
            self.last_used[resource_id] = time.time()
            return False
            
        # Register new resource
        self.active_resources[resource_id] = resource_obj
        self.last_used[resource_id] = time.time()
        self.resource_sizes[resource_id] = estimated_size
        
        # Track resource type if provided
        if resource_type:
            self.resource_types[resource_id] = resource_type
        
        # Update statistics
        self.total_registered += 1
        logger.debug(f"Registered resource: {resource_id}" + 
                    (f" ({resource_type})" if resource_type else ""))
        
        # Perform cleanup if we have too many resources
        if len(self.active_resources) > self.cleanup_threshold:
            self.cleanup_inactive()
            
        return True
    
    def use_resource(self, resource_id):
        """Mark a resource as recently used
        
        Args:
            resource_id: ID of the resource being used
            
        Returns:
            bool: True if resource exists and was marked, False otherwise
        """
        if resource_id in self.last_used:
            self.last_used[resource_id] = time.time()
            return True
        return False
    
    def unregister_resource(self, resource_id):
        """Unregister and clean up a resource
        
        Args:
            resource_id: ID of the resource to unregister
            
        Returns:
            bool: True if resource was unregistered, False if it didn't exist
        """
        if resource_id in self.active_resources:
            try:
                # Properly clean up different resource types
                resource = self.active_resources[resource_id]
                
                # Special handling for QMovie - must stop to prevent memory leaks
                if isinstance(resource, QMovie):
                    resource.stop()
                
                # Remove from tracking dictionaries
                del self.active_resources[resource_id]
                
                # Also clean up from other dictionaries
                if resource_id in self.last_used:
                    del self.last_used[resource_id]
                if resource_id in self.resource_sizes:
                    del self.resource_sizes[resource_id]
                if resource_id in self.resource_types:
                    del self.resource_types[resource_id]
                    
                # Update statistics
                self.total_unregistered += 1
                logger.debug(f"Unregistered resource: {resource_id}")
                return True
                
            except Exception as e:
                ErrorHandler.log_error(e, f"ResourceManager.unregister_resource({resource_id})")
                return False
        
        return False
    
    def cleanup_inactive(self, max_age=None):
        """Clean up resources that haven't been used recently
        
        Args:
            max_age: Override the default max_inactive_time (default: None)
            
        Returns:
            int: Number of resources cleaned up
        """
        current_time = time.time()
        inactive_resources = []
        max_age = max_age or self.max_inactive_time
        
        # Find inactive resources
        for resource_id, last_time in self.last_used.items():
            if current_time - last_time > max_age:
                inactive_resources.append(resource_id)
        
        # Clean up inactive resources
        cleaned_count = 0
        for resource_id in inactive_resources:
            if self.unregister_resource(resource_id):
                cleaned_count += 1
        
        # Track cleanup time
        self.last_cleanup_time = current_time
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} inactive resources")
            # Suggest garbage collection
            gc.collect()
            
        return cleaned_count
    
    def force_cleanup(self):
        """Force cleanup of all resources
        
        Returns:
            int: Number of resources cleaned up
        """
        resource_ids = list(self.active_resources.keys())
        cleaned_count = 0
        
        for resource_id in resource_ids:
            if self.unregister_resource(resource_id):
                cleaned_count += 1
        
        logger.info(f"Forced cleanup of {cleaned_count} resources")
        
        # Force garbage collection
        gc.collect()
        return cleaned_count
    
    def get_memory_usage(self):
        """Get current memory usage of the process
        
        Returns:
            float: Memory usage in MB
        """
        try:
            memory_info = self.process.memory_info()
            return memory_info.rss / (1024 * 1024)  # Convert to MB
        except Exception as e:
            ErrorHandler.log_error(e, "ResourceManager.get_memory_usage")
            return 0
    
    def get_resource_stats(self):
        """Get statistics about tracked resources
        
        Returns:
            dict: Dictionary with resource statistics
        """
        # Count resources by type
        type_counts = {}
        for resource_id, resource_type in self.resource_types.items():
            if resource_type not in type_counts:
                type_counts[resource_type] = 0
            type_counts[resource_type] += 1
            
        # Calculate oldest resource age
        current_time = time.time()
        oldest_age = max([current_time - t for t in self.last_used.values()]) if self.last_used else 0
        
        return {
            "active_count": len(self.active_resources),
            "total_registered": self.total_registered,
            "total_unregistered": self.total_unregistered,
            "total_estimated_size_kb": sum(self.resource_sizes.values()) / 1024,
            "memory_usage_mb": self.get_memory_usage(),
            "oldest_resource_age_seconds": oldest_age,
            "time_since_cleanup": current_time - self.last_cleanup_time if self.last_cleanup_time else None,
            "resource_types": type_counts
        }
    
    def get_resource(self, resource_id):
        """Get a registered resource by ID
        
        Args:
            resource_id: ID of the resource to retrieve
            
        Returns:
            The resource object, or None if not found
        """
        if resource_id in self.active_resources:
            # Mark as recently used
            self.use_resource(resource_id)
            return self.active_resources[resource_id]
        return None
        
    def resource_exists(self, resource_id):
        """Check if a resource exists
        
        Args:
            resource_id: ID of the resource to check
            
        Returns:
            bool: True if resource exists, False otherwise
        """
        return resource_id in self.active_resources
    
    def clear_resource_type(self, resource_type):
        """Clear all resources of a specific type
        
        Args:
            resource_type: Type of resources to clear
            
        Returns:
            int: Number of resources cleared
        """
        if not resource_type:
            return 0
            
        # Find resources of the specified type
        resources_to_clear = [
            resource_id for resource_id, r_type in self.resource_types.items()
            if r_type == resource_type
        ]
        
        # Unregister each resource
        cleared_count = 0
        for resource_id in resources_to_clear:
            if self.unregister_resource(resource_id):
                cleared_count += 1
                
        if cleared_count > 0:
            logger.info(f"Cleared {cleared_count} resources of type '{resource_type}'")
            gc.collect()
            
        return cleared_count