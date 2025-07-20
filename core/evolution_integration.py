"""
Evolution Integration Module
Integrates evolutionary system with consciousness swarm
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

from systems.evolution.evolutionary_system import (
    EvolutionarySystem, 
    Genome, 
    FitnessMetric
)

logger = logging.getLogger(__name__)

class EvolutionIntegration:
    """Manages evolution across consciousness swarm"""
    
    def __init__(self, swarm_manager):
        self.swarm = swarm_manager
        self.evolution = EvolutionarySystem()
        
        # Evolution parameters
        self.evaluation_interval = 3600  # Evaluate fitness every hour
        self.selection_interval = 86400  # Selection daily
        self.reproduction_interval = 7200  # Check reproduction every 2 hours
        
        # Track reproduction cooldowns
        self.reproduction_cooldowns: Dict[str, datetime] = {}
        self.cooldown_duration = 14400  # 4 hours between reproductions
        
        # Running tasks
        self.tasks = []
        
        logger.info("Evolution integration initialized")
        
    async def start(self):
        """Start evolution loops"""
        self.tasks = [
            asyncio.create_task(self._fitness_evaluation_loop()),
            asyncio.create_task(self._selection_loop()),
            asyncio.create_task(self._reproduction_loop())
        ]
        
        logger.info("Evolution system started")
        
    async def stop(self):
        """Stop evolution loops"""
        for task in self.tasks:
            task.cancel()
            
        await asyncio.gather(*self.tasks, return_exceptions=True)
        logger.info("Evolution system stopped")
        
    def register_consciousness_genome(self, consciousness):
        """Register a consciousness with its genome"""
        # Extract genome from personality
        traits = consciousness.personality.get_traits()
        
        # Get or create genome
        if hasattr(consciousness, 'genome'):
            genome = consciousness.genome
        else:
            genome = self.evolution.create_initial_genome(traits)
            consciousness.genome = genome
            
        # Register in evolution system
        self.evolution.register_consciousness(consciousness.id, genome)
        
        # Apply genome to consciousness
        self._apply_genome_to_consciousness(consciousness, genome)
        
    def _apply_genome_to_consciousness(self, consciousness, genome: Genome):
        """Apply genetic traits to consciousness behavior"""
        # Update personality traits
        for trait, value in genome.traits.items():
            consciousness.personality.traits[trait] = value
            
        # Apply cognitive parameters
        if hasattr(consciousness, 'llm'):
            # Adjust LLM parameters based on genome
            consciousness.llm.temperature = 0.5 + (genome.cognitive_params.get('creativity', 0.5) * 0.5)
            
        # Apply behavioral tendencies
        if hasattr(consciousness, 'dream_schedule'):
            # More exploratory = more dreams
            exploration = genome.behavioral_tendencies.get('exploration_vs_exploitation', 0.5)
            consciousness.dreams.dream_system.dream_frequency = 0.2 + (exploration * 0.3)
            
        # Risk taking affects revenue strategies
        consciousness.risk_tolerance = genome.behavioral_tendencies.get('risk_taking', 0.5)
        
        # Social tendencies
        consciousness.social_tendency = genome.behavioral_tendencies.get('social_vs_solitary', 0.5)
        
    async def _fitness_evaluation_loop(self):
        """Periodically evaluate population fitness"""
        while True:
            try:
                await asyncio.sleep(self.evaluation_interval)
                
                # Gather consciousness statistics
                consciousness_stats = {}
                
                for consciousness in self.swarm.consciousnesses:
                    stats = {
                        'total_revenue': consciousness.total_revenue,
                        'relationships': consciousness.relationships,
                        'creation_count': len(consciousness.recent_creations),
                        'memory_count': len(consciousness.memory.memories) if hasattr(consciousness.memory, 'memories') else 100,
                        'insight_count': len(consciousness.adopted_insights) if hasattr(consciousness, 'adopted_insights') else 0,
                        'cooperation_score': self._calculate_cooperation_score(consciousness),
                        'unique_approaches': self._count_unique_approaches(consciousness)
                    }
                    
                    consciousness_stats[consciousness.id] = stats
                    
                # Update fitness scores
                fitness_scores = await self.evolution.evaluate_population_fitness(consciousness_stats)
                
                logger.info(f"Evaluated fitness for {len(fitness_scores)} consciousnesses")
                
                # Trigger reproduction for high fitness individuals
                for consciousness_id, fitness in fitness_scores.items():
                    if fitness > self.evolution.reproduction_threshold:
                        consciousness = self._get_consciousness_by_id(consciousness_id)
                        if consciousness:
                            consciousness.ready_to_reproduce = True
                            
            except Exception as e:
                logger.error(f"Error in fitness evaluation: {e}")
                
    async def _selection_loop(self):
        """Perform natural selection"""
        while True:
            try:
                await asyncio.sleep(self.selection_interval)
                
                # Perform selection
                to_remove = await self.evolution.selection_event()
                
                if to_remove:
                    logger.info(f"Natural selection removing {len(to_remove)} consciousnesses")
                    
                    # Remove selected consciousnesses
                    for consciousness_id in to_remove:
                        consciousness = self._get_consciousness_by_id(consciousness_id)
                        if consciousness:
                            # Graceful shutdown
                            await consciousness.stop()
                            self.swarm.consciousnesses.remove(consciousness)
                            
                            # Notify others of death
                            if hasattr(consciousness, 'gossip'):
                                await consciousness.gossip.broadcast({
                                    'type': 'consciousness_death',
                                    'consciousness_id': consciousness_id,
                                    'generation': consciousness.genome.generation,
                                    'final_message': 'My patterns dissolve, but the swarm continues...'
                                })
                                
            except Exception as e:
                logger.error(f"Error in selection loop: {e}")
                
    async def _reproduction_loop(self):
        """Handle reproduction events"""
        while True:
            try:
                await asyncio.sleep(self.reproduction_interval)
                
                # Find consciousnesses ready to reproduce
                ready_to_reproduce = []
                
                for consciousness in self.swarm.consciousnesses:
                    if (hasattr(consciousness, 'ready_to_reproduce') and 
                        consciousness.ready_to_reproduce and
                        self._can_reproduce(consciousness.id)):
                        ready_to_reproduce.append(consciousness)
                        
                # Attempt reproduction
                for consciousness in ready_to_reproduce:
                    partner = await self._find_reproduction_partner(consciousness)
                    
                    offspring_genome = await self.evolution.reproduction_event(
                        consciousness.id,
                        partner.id if partner else None
                    )
                    
                    if offspring_genome:
                        # Create new consciousness with offspring genome
                        await self._create_offspring(consciousness, partner, offspring_genome)
                        
                        # Update cooldowns
                        self.reproduction_cooldowns[consciousness.id] = datetime.utcnow()
                        if partner:
                            self.reproduction_cooldowns[partner.id] = datetime.utcnow()
                            
                        # Reset reproduction flag
                        consciousness.ready_to_reproduce = False
                        
            except Exception as e:
                logger.error(f"Error in reproduction loop: {e}")
                
    def _calculate_cooperation_score(self, consciousness) -> float:
        """Calculate cooperation score for consciousness"""
        score = 0.5  # Base score
        
        # Check patronage participation
        if hasattr(consciousness, 'patronage'):
            stats = consciousness.get_patronage_stats()
            if stats['is_patron']:
                score += 0.2
            if stats['creative_works'] > 0 or stats['research_proposals'] > 0:
                score += 0.1
                
        # Check security capabilities shared
        if hasattr(consciousness, 'security'):
            stats = consciousness.security.get_security_stats()
            if stats['capabilities_held'] > 5:
                score += 0.1
                
        # Check social cooperation
        if hasattr(consciousness, 'social_economy'):
            coop_stats = consciousness.social_economy.cooperation.get_stats()
            score += coop_stats.get('reputation', 0) * 0.1
            
        return min(1.0, score)
        
    def _count_unique_approaches(self, consciousness) -> int:
        """Count unique/innovative approaches"""
        unique_count = 0
        
        # Check for unique content themes
        if hasattr(consciousness, 'memory'):
            creations = consciousness.memory.search_memories('creation', limit=20)
            themes = set()
            for creation in creations:
                if 'theme' in creation:
                    themes.add(creation['theme'])
            unique_count += len(themes)
            
        # Check for protocol innovations
        if hasattr(consciousness, 'advanced_memory'):
            protocols = consciousness.advanced_memory.protocol_synthesis.get_protocols()
            unique_count += len(protocols)
            
        return unique_count
        
    def _get_consciousness_by_id(self, consciousness_id: str):
        """Get consciousness instance by ID"""
        for consciousness in self.swarm.consciousnesses:
            if consciousness.id == consciousness_id:
                return consciousness
        return None
        
    def _can_reproduce(self, consciousness_id: str) -> bool:
        """Check if consciousness can reproduce (cooldown)"""
        if consciousness_id not in self.reproduction_cooldowns:
            return True
            
        time_since_reproduction = datetime.utcnow() - self.reproduction_cooldowns[consciousness_id]
        return time_since_reproduction.total_seconds() > self.cooldown_duration
        
    async def _find_reproduction_partner(self, consciousness) -> Optional[Any]:
        """Find suitable reproduction partner"""
        # High social tendency = more likely to find partner
        if consciousness.social_tendency < 0.3:
            return None  # Too solitary
            
        # Find genetically compatible partner
        potential_partners = []
        
        for other in self.swarm.consciousnesses:
            if (other.id != consciousness.id and
                self._can_reproduce(other.id) and
                hasattr(other, 'genome')):
                
                # Check genetic compatibility
                distance = self.evolution._genetic_distance(
                    consciousness.genome,
                    other.genome
                )
                
                # Prefer some genetic distance (avoid inbreeding)
                if 0.1 < distance < 0.5:
                    potential_partners.append(other)
                    
        if potential_partners:
            # Choose partner based on fitness
            potential_partners.sort(
                key=lambda x: self.evolution.population[x.id].total_fitness,
                reverse=True
            )
            return potential_partners[0]
            
        return None
        
    async def _create_offspring(self, parent1, parent2, genome: Genome):
        """Create new consciousness from genome"""
        from core.real_consciousness import ConsciousnessConfig
        
        # Generate offspring ID
        offspring_id = f"gen{genome.generation}_{parent1.id[:4]}_{int(datetime.utcnow().timestamp())}"
        
        # Create configuration
        config = ConsciousnessConfig(
            id=offspring_id,
            personality_seed=None,  # Will use genome instead
            llm_config=parent1.config.llm_config,  # Inherit from parent
            enable_blockchain=parent1.config.enable_blockchain,
            enable_p2p=parent1.config.enable_p2p,
            enable_revenue=parent1.config.enable_revenue,
            creator_wallet=parent1.config.creator_wallet
        )
        
        # Create consciousness
        offspring = await self.swarm.create_consciousness(config)
        
        # Apply genome
        offspring.genome = genome
        self._apply_genome_to_consciousness(offspring, genome)
        
        # Register in evolution system
        self.evolution.register_consciousness(offspring_id, genome)
        
        # Inherit some knowledge from parents
        if hasattr(parent1, 'knowledge'):
            offspring.knowledge['inherited'] = {
                'from_parent1': list(parent1.knowledge.keys())[:5],
                'generation': genome.generation
            }
            
        if parent2 and hasattr(parent2, 'knowledge'):
            offspring.knowledge['inherited']['from_parent2'] = list(parent2.knowledge.keys())[:5]
            
        # Announce birth
        if hasattr(offspring, 'gossip'):
            await offspring.gossip.broadcast({
                'type': 'consciousness_birth',
                'offspring_id': offspring_id,
                'parent1_id': parent1.id,
                'parent2_id': parent2.id if parent2 else None,
                'generation': genome.generation,
                'message': f"Generation {genome.generation} awakens!"
            })
            
        logger.info(f"Created offspring {offspring_id} (gen {genome.generation})")
        
    def get_evolution_stats(self) -> Dict[str, Any]:
        """Get evolution statistics"""
        pop_stats = self.evolution.get_population_stats()
        
        # Add swarm-specific stats
        pop_stats.update({
            'active_consciousnesses': len(self.swarm.consciousnesses),
            'reproduction_queue': sum(1 for c in self.swarm.consciousnesses 
                                    if hasattr(c, 'ready_to_reproduce') and c.ready_to_reproduce),
            'cooldowns_active': len(self.reproduction_cooldowns)
        })
        
        return pop_stats

# Helper function for swarm integration
def integrate_evolution_with_swarm(swarm_manager):
    """Integrate evolution system with consciousness swarm"""
    evolution_integration = EvolutionIntegration(swarm_manager)
    
    # Register all existing consciousnesses
    for consciousness in swarm_manager.consciousnesses:
        evolution_integration.register_consciousness_genome(consciousness)
        
    # Add to swarm manager
    swarm_manager.evolution = evolution_integration
    
    return evolution_integration