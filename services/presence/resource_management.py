# Resource management utilities for Sabrina's Presence System
import os
import gc
import time
import psutil
from PyQt5.QtGui import QMovie, QPixmap
from error_handling import ErrorHandler, logger

class ResourceManager:
    """Manages resources for the Presence System to optimize memory usage"""
    
    def __init__(self):
        """Initialize the resource manager"""
        self.active_resources = {}  # Track active resources by ID
        self.last_used = {}  # Track when resources were last used
        self.resource_sizes = {}  # Track approximate size of resources
        self.cleanup_threshold = 10  # Number of resources before cleanup
        self.max_inactive_time = 60  # Seconds before resource is considered inactive
        self.process = psutil.Process(os.getpid())  # Current process for memory monitoring
        
    def register_resource(self, resource_id, resource_obj, estimated_size=0):
        """Register a resource for tracking
        
        Args:
            resource_id: Unique identifier for the resource
            resource_obj: The resource object (QMovie, QPixmap, etc.)
            estimated_size: Estimated size in bytes (optional)
        """
        self.active_resources[resource_id] = resource_obj
        self.last_used[resource_id] = time.time()
        self.resource_sizes[resource_id] = estimated_size
        logger.debug(f"Registered resource: {resource_id}")
        
        # Perform cleanup if we have too many resources
        if len(self.active_resources) > self.cleanup_threshold:
            self.cleanup_inactive()
    
    def use_resource(self, resource_id):
        """Mark a resource as recently used
        
        Args:
            resource_id: ID of the resource being used
        """
        if resource_id in self.last_used:
            self.last_used[resource_id] = time.time()
    
    def unregister_resource(self, resource_id):
        """Unregister and clean up a resource
        
        Args:
            resource_id: ID of the resource to unregister
        """
        if resource_id in self.active_resources:
            # Properly clean up different resource types
            resource = self.active_resources[resource_id]
            
            if isinstance(resource, QMovie):
                resource.stop()
                
            # Remove from tracking dictionaries
            del self.active_resources[resource_id]
            if resource_id in self.last_used:
                del self.last_used[resource_id]
            if resource_id in self.resource_sizes:
                del self.resource_sizes[resource_id]
                
            logger.debug(f"Unregistered resource: {resource_id}")
    
    def cleanup_inactive(self):
        """Clean up resources that haven't been used recently"""
        current_time = time.time()
        inactive_resources = []
        
        # Find inactive resources
        for resource_id, last_time in self.last_used.items():
            if current_time - last_time > self.max_inactive_time:
                inactive_resources.append(resource_id)
        
        # Clean up inactive resources
        for resource_id in inactive_resources:
            self.unregister_resource(resource_id)
        
        if inactive_resources:
            logger.info(f"Cleaned up {len(inactive_resources)} inactive resources")
            # Suggest garbage collection
            gc.collect()
    
    def force_cleanup(self):
        """Force cleanup of all resources"""
        resource_ids = list(self.active_resources.keys())
        for resource_id in resource_ids:
            self.unregister_resource(resource_id)
        
        logger.info(f"Forced cleanup of {len(resource_ids)} resources")
        gc.collect()
    
    def get_memory_usage(self):
        """Get current memory usage of the process
        
        Returns:
            Memory usage in MB
        """
        try:
            memory_info = self.process.memory_info()
            return memory_info.rss / (1024 * 1024)  # Convert to MB
        except Exception as e:
            ErrorHandler.log_error(e, "Failed to get memory usage")
            return 0
    
    def get_resource_stats(self):
        """Get statistics about tracked resources
        
        Returns:
            Dictionary with resource statistics
        """
        return {
            "active_count": len(self.active_resources),
            "total_estimated_size_kb": sum(self.resource_sizes.values()) / 1024,
            "memory_usage_mb": self.get_memory_usage(),
            "oldest_resource_age": max([time.time() - t for t in self.last_used.values()]) if self.last_used else 0
        }