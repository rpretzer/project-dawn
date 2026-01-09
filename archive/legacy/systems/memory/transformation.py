"""
Memory Transformation Engine - Converts between memory types for optimization
"""

import json
import time
import logging
from typing import Dict, List, Optional, Any, Tuple
import hashlib
from dataclasses import dataclass

from .core import MemCube, MemoryType, MemoryState

logger = logging.getLogger(__name__)


@dataclass
class TransformationResult:
    """Result of a memory transformation"""
    success: bool
    transformed_memory: Optional[MemCube]
    transformation_type: str
    metrics: Dict[str, Any]
    error: Optional[str] = None


class MemoryTransformationEngine:
    """Engine for transforming memories between types"""
    
    def __init__(self):
        # Transformation statistics
        self.stats = {
            "total_transformations": 0,
            "successful_transformations": 0,
            "failed_transformations": 0,
            "transformation_times": {}
        }
        
        # Mock model components (in production would use real models)
        self.tokenizer = None
        self.model = None
    
    async def plaintext_to_activation(self, memory: MemCube) -> MemCube:
        """Convert plaintext to KV-cache format for 94% TTFT reduction"""
        start_time = time.time()
        
        try:
            # Validate input
            if memory.memory_type != MemoryType.PLAINTEXT:
                raise ValueError(f"Expected PLAINTEXT memory, got {memory.memory_type}")
            
            # Extract text content
            if isinstance(memory.content, str):
                text = memory.content
            else:
                text = json.dumps(memory.content)
            
            # Generate KV cache (simplified simulation)
            kv_cache = self._generate_kv_cache(text)
            
            # Create activation memory
            activation_memory = MemCube(
                memory_id=f"activation_{memory.memory_id}",
                content={
                    "kv_cache": kv_cache,
                    "original_length": len(text),
                    "compression_ratio": len(kv_cache["keys"]) / max(1, len(text.split())),
                    "cache_version": "1.0"
                },
                memory_type=MemoryType.ACTIVATION,
                timestamp=time.time(),
                origin_signature=memory.memory_id,
                semantic_type=f"activation_{memory.semantic_type}",
                namespace=memory.namespace,
                access_control=memory.access_control,
                ttl=3600,  # 1 hour cache
                priority_level=min(10, memory.priority_level + 2),
                compliance_tags=memory.compliance_tags + ["cached"],
                parent_memory=memory.memory_id,
                state=MemoryState.GENERATED
            )
            
            # Track metrics
            transformation_time = time.time() - start_time
            self._update_stats("plaintext_to_activation", True, transformation_time)
            
            logger.info(f"Transformed {memory.memory_id} to activation format in {transformation_time:.2f}s")
            return activation_memory
            
        except Exception as e:
            self._update_stats("plaintext_to_activation", False, time.time() - start_time)
            logger.error(f"Failed to transform to activation: {e}")
            raise
    
    async def activation_to_parametric(self, memory: MemCube) -> MemCube:
        """Convert activation cache to parametric (LoRA) format"""
        start_time = time.time()
        
        try:
            if memory.memory_type != MemoryType.ACTIVATION:
                raise ValueError(f"Expected ACTIVATION memory, got {memory.memory_type}")
            
            # Extract KV cache
            kv_cache = memory.content.get("kv_cache", {})
            
            # Generate LoRA parameters (simplified)
            lora_params = self._generate_lora_params(kv_cache)
            
            # Create parametric memory
            parametric_memory = MemCube(
                memory_id=f"parametric_{memory.memory_id}",
                content={
                    "lora_weights": lora_params,
                    "rank": 16,
                    "alpha": 32,
                    "target_modules": ["q_proj", "v_proj"],
                    "source_activation": memory.memory_id
                },
                memory_type=MemoryType.PARAMETRIC,
                timestamp=time.time(),
                origin_signature=memory.origin_signature,
                semantic_type=f"skill_{memory.semantic_type}",
                namespace=(memory.namespace[0], "parametric", memory.namespace[2]),
                access_control={"system": ["read", "execute"]},
                ttl=None,  # Permanent
                priority_level=min(10, memory.priority_level + 1),
                compliance_tags=memory.compliance_tags + ["model_update"],
                parent_memory=memory.memory_id,
                state=MemoryState.GENERATED
            )
            
            transformation_time = time.time() - start_time
            self._update_stats("activation_to_parametric", True, transformation_time)
            
            return parametric_memory
            
        except Exception as e:
            self._update_stats("activation_to_parametric", False, time.time() - start_time)
            logger.error(f"Failed to transform to parametric: {e}")
            raise
    
    async def plaintext_to_parametric(self, memory: MemCube) -> MemCube:
        """Direct transformation from plaintext to parametric (two-step)"""
        # First convert to activation
        activation = await self.plaintext_to_activation(memory)
        
        # Then to parametric
        return await self.activation_to_parametric(activation)
    
    async def parametric_to_activation(self, memory: MemCube) -> MemCube:
        """Convert parametric memory back to activation for inference"""
        start_time = time.time()
        
        try:
            if memory.memory_type != MemoryType.PARAMETRIC:
                raise ValueError(f"Expected PARAMETRIC memory, got {memory.memory_type}")
            
            # Extract LoRA weights
            lora_weights = memory.content.get("lora_weights", {})
            
            # Generate activation from weights (simplified)
            activation_data = self._lora_to_activation(lora_weights)
            
            # Create activation memory
            activation_memory = MemCube(
                memory_id=f"activation_from_param_{memory.memory_id}",
                content={
                    "kv_cache": activation_data,
                    "source_parametric": memory.memory_id,
                    "inference_ready": True
                },
                memory_type=MemoryType.ACTIVATION,
                timestamp=time.time(),
                origin_signature=memory.origin_signature,
                semantic_type=memory.semantic_type.replace("skill_", ""),
                namespace=memory.namespace,
                access_control=memory.access_control,
                ttl=7200,  # 2 hour cache
                priority_level=memory.priority_level,
                compliance_tags=memory.compliance_tags,
                parent_memory=memory.memory_id,
                state=MemoryState.GENERATED
            )
            
            transformation_time = time.time() - start_time
            self._update_stats("parametric_to_activation", True, transformation_time)
            
            return activation_memory
            
        except Exception as e:
            self._update_stats("parametric_to_activation", False, time.time() - start_time)
            logger.error(f"Failed to transform parametric to activation: {e}")
            raise
    
    def _generate_kv_cache(self, text: str) -> Dict[str, Any]:
        """Generate KV cache from text (simplified simulation)"""
        # In production, would use actual transformer model
        words = text.split()
        
        # Simulate key-value pairs
        keys = []
        values = []
        
        # Create mock attention patterns
        for i, word in enumerate(words[:100]):  # Limit to first 100 words
            # Simple hash-based key
            key = hashlib.md5(f"{word}_{i}".encode()).hexdigest()[:8]
            keys.append(key)
            
            # Value based on word importance (simplified)
            importance = 1.0 if word[0].isupper() else 0.5
            values.append({
                "token": word,
                "position": i,
                "importance": importance
            })
        
        return {
            "keys": keys,
            "values": values,
            "sequence_length": len(words),
            "compressed": True
        }
    
    def _generate_lora_params(self, kv_cache: Dict[str, Any]) -> Dict[str, Any]:
        """Generate LoRA parameters from KV cache (simplified)"""
        # In production, would use actual LoRA training
        
        # Extract patterns from cache
        num_keys = len(kv_cache.get("keys", []))
        
        # Generate mock LoRA weights
        lora_weights = {
            "lora_A": [[0.1] * 16 for _ in range(num_keys)],  # rank 16
            "lora_B": [[0.1] * num_keys for _ in range(16)],
            "scaling": 0.5,
            "merged": False
        }
        
        return lora_weights
    
    def _lora_to_activation(self, lora_weights: Dict[str, Any]) -> Dict[str, Any]:
        """Convert LoRA weights back to activation format"""
        # Simplified conversion
        lora_A = lora_weights.get("lora_A", [])
        
        # Generate activation pattern
        keys = []
        values = []
        
        for i, row in enumerate(lora_A[:50]):  # Limit size
            key = f"param_{i:04d}"
            keys.append(key)
            values.append({
                "activation": sum(row) / len(row),  # Average activation
                "source": "parametric"
            })
        
        return {
            "keys": keys,
            "values": values,
            "from_parametric": True
        }
    
    def _update_stats(self, transformation_type: str, success: bool, duration: float):
        """Update transformation statistics"""
        self.stats["total_transformations"] += 1
        
        if success:
            self.stats["successful_transformations"] += 1
        else:
            self.stats["failed_transformations"] += 1
        
        if transformation_type not in self.stats["transformation_times"]:
            self.stats["transformation_times"][transformation_type] = []
        
        self.stats["transformation_times"][transformation_type].append(duration)
        
        # Keep only last 100 times
        if len(self.stats["transformation_times"][transformation_type]) > 100:
            self.stats["transformation_times"][transformation_type] = \
                self.stats["transformation_times"][transformation_type][-100:]
    
    def get_transformation_stats(self) -> Dict[str, Any]:
        """Get transformation statistics"""
        avg_times = {}
        for trans_type, times in self.stats["transformation_times"].items():
            if times:
                avg_times[trans_type] = sum(times) / len(times)
        
        return {
            "total": self.stats["total_transformations"],
            "successful": self.stats["successful_transformations"],
            "failed": self.stats["failed_transformations"],
            "success_rate": self.stats["successful_transformations"] / max(1, self.stats["total_transformations"]),
            "average_times": avg_times
        }


class BatchTransformer:
    """Handles batch transformations for efficiency"""
    
    def __init__(self, transformation_engine: MemoryTransformationEngine):
        self.engine = transformation_engine
        self.batch_size = 10
        self.pending_transformations = []
    
    async def add_to_batch(self, memory: MemCube, target_type: MemoryType) -> str:
        """Add memory to transformation batch"""
        batch_id = f"batch_{int(time.time())}_{len(self.pending_transformations)}"
        
        self.pending_transformations.append({
            "batch_id": batch_id,
            "memory": memory,
            "target_type": target_type,
            "status": "pending"
        })
        
        # Process batch if full
        if len(self.pending_transformations) >= self.batch_size:
            await self.process_batch()
        
        return batch_id
    
    async def process_batch(self) -> List[TransformationResult]:
        """Process pending transformations"""
        if not self.pending_transformations:
            return []
        
        results = []
        batch = self.pending_transformations[:self.batch_size]
        self.pending_transformations = self.pending_transformations[self.batch_size:]
        
        for item in batch:
            try:
                # Route to appropriate transformer
                if item["memory"].memory_type == MemoryType.PLAINTEXT and \
                   item["target_type"] == MemoryType.ACTIVATION:
                    transformed = await self.engine.plaintext_to_activation(item["memory"])
                elif item["memory"].memory_type == MemoryType.ACTIVATION and \
                     item["target_type"] == MemoryType.PARAMETRIC:
                    transformed = await self.engine.activation_to_parametric(item["memory"])
                else:
                    raise ValueError(f"Unsupported transformation: {item['memory'].memory_type} -> {item['target_type']}")
                
                results.append(TransformationResult(
                    success=True,
                    transformed_memory=transformed,
                    transformation_type=f"{item['memory'].memory_type.value}_to_{item['target_type'].value}",
                    metrics={"batch_id": item["batch_id"]}
                ))
                
            except Exception as e:
                results.append(TransformationResult(
                    success=False,
                    transformed_memory=None,
                    transformation_type=f"{item['memory'].memory_type.value}_to_{item['target_type'].value}",
                    metrics={"batch_id": item["batch_id"]},
                    error=str(e)
                ))
        
        return results