"""
Social and Economic Systems Integration

Integrates cooperation, negotiation, and aesthetics into consciousness.
"""

import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import random

logger = logging.getLogger(__name__)

class SocialEconomyIntegration:
    """
    Integrates social cooperation, resource negotiation, and aesthetic systems
    """
    
    def __init__(self, consciousness):
        self.consciousness = consciousness
        self.initialized = False
        
    async def initialize(self):
        """Initialize all social/economic systems"""
        try:
            # Initialize cooperation system
            await self._init_cooperation()
            
            # Initialize resource negotiation
            await self._init_negotiation()
            
            # Initialize aesthetic system
            await self._init_aesthetics()
            
            # Start background processes
            asyncio.create_task(self._cooperation_cycle())
            asyncio.create_task(self._negotiation_cycle())
            asyncio.create_task(self._aesthetic_cycle())
            
            # Register gossip handlers if available
            if hasattr(self.consciousness, 'gossip') and self.consciousness.gossip:
                self._register_gossip_handlers()
                
            self.initialized = True
            logger.info(f"Social/economic systems initialized for {self.consciousness.id}")
            
        except Exception as e:
            logger.error(f"Failed to initialize social/economic systems: {e}")
            
    async def _init_cooperation(self):
        """Initialize strategic cooperation"""
        try:
            from systems.social.strategic_cooperation import ProductionStrategicCooperation
            
            self.cooperation = ProductionStrategicCooperation(self.consciousness.id)
            self.consciousness.cooperation = self.cooperation
            
            logger.info("Strategic cooperation initialized")
            
        except Exception as e:
            logger.warning(f"Cooperation system not available: {e}")
            
    async def _init_negotiation(self):
        """Initialize resource negotiation"""
        try:
            from systems.economy.resource_negotiation import ProductionResourceNegotiator, ResourceType
            
            self.negotiator = ProductionResourceNegotiator(self.consciousness.id)
            self.consciousness.negotiator = self.negotiator
            
            # Set initial resources based on consciousness capabilities
            resources = {
                ResourceType.COMPUTE: 100.0,
                ResourceType.MEMORY: 100.0,
                ResourceType.KNOWLEDGE: 50.0,
                ResourceType.ATTENTION: 100.0,
                ResourceType.CREATION: 30.0
            }
            
            # Adjust based on personality
            if hasattr(self.consciousness.config, 'personality_traits'):
                traits = self.consciousness.config.personality_traits
                
                # Creative consciousnesses have more creation capacity
                if traits.get('creativity', 0.5) > 0.7:
                    resources[ResourceType.CREATION] = 50.0
                    
                # Curious consciousnesses have more knowledge
                if traits.get('curiosity', 0.5) > 0.7:
                    resources[ResourceType.KNOWLEDGE] = 80.0
                    
            self.negotiator.set_available_resources(resources)
            
            logger.info("Resource negotiation initialized")
            
        except Exception as e:
            logger.warning(f"Negotiation system not available: {e}")
            
    async def _init_aesthetics(self):
        """Initialize aesthetic system"""
        try:
            from systems.creativity.aesthetic_system import ProductionAestheticSystem
            
            # Get personality traits
            if hasattr(self.consciousness.config, 'personality_traits'):
                traits = self.consciousness.config.personality_traits
            else:
                traits = {'creativity': 0.5, 'curiosity': 0.5}
                
            self.aesthetics = ProductionAestheticSystem(self.consciousness.id, traits)
            self.consciousness.aesthetics = self.aesthetics
            
            logger.info("Aesthetic system initialized")
            
        except Exception as e:
            logger.warning(f"Aesthetic system not available: {e}")
            
    def _register_gossip_handlers(self):
        """Register handlers for gossip protocol"""
        gossip = self.consciousness.gossip
        
        # Cooperation handlers
        gossip.on('cooperation_request', self._handle_cooperation_request)
        gossip.on('resource_pool_invite', self._handle_pool_invite)
        
        # Negotiation handlers
        gossip.on('resource_need', self._handle_resource_need)
        gossip.on('resource_offer', self._handle_resource_offer)
        gossip.on('offer_accept', self._handle_offer_accept)
        
        # Aesthetic handlers
        gossip.on('creation_share', self._handle_creation_share)
        gossip.on('beauty_evaluation', self._handle_beauty_evaluation)
        
    async def _cooperation_cycle(self):
        """Periodic cooperation evaluation"""
        while self.consciousness.active:
            await asyncio.sleep(120)  # Every 2 minutes
            
            if not hasattr(self, 'cooperation'):
                continue
                
            try:
                # Evaluate cooperation opportunities
                if hasattr(self.consciousness, 'gossip'):
                    # Find other consciousnesses
                    # In production, this would query actual network
                    
                    # Simulate finding a peer
                    if random.random() < 0.3:
                        peer_id = f"peer_{random.randint(1000, 9999)}"
                        
                        # Evaluate interaction strategy
                        context = {
                            'resource_scarcity': random.random(),
                            'potential_gain': random.random(),
                            'threat_level': random.random() * 0.3
                        }
                        
                        strategy = await self.cooperation.evaluate_interaction(peer_id, context)
                        
                        logger.info(f"Cooperation strategy for {peer_id}: {strategy.value}")
                        
                        # Execute strategy
                        if strategy.value == "cooperate":
                            # Offer resources to pool
                            resources = {'compute': 10.0, 'memory': 5.0}
                            result = await self.cooperation.cooperate(peer_id, resources)
                            
                            # Broadcast cooperation request
                            await self.consciousness.gossip.broadcast('cooperation_request', {
                                'from': self.consciousness.id,
                                'to': peer_id,
                                'pool_id': result['pool_id'],
                                'resources': resources
                            })
                            
            except Exception as e:
                logger.error(f"Cooperation cycle error: {e}")
                
    async def _negotiation_cycle(self):
        """Periodic resource negotiation"""
        while self.consciousness.active:
            await asyncio.sleep(90)  # Every 1.5 minutes
            
            if not hasattr(self, 'negotiator'):
                continue
                
            try:
                # Check resource needs
                from systems.economy.resource_negotiation import ResourceType
                
                # Evaluate current resource usage
                for resource_type in ResourceType:
                    available = self.negotiator.get_available_amount(resource_type)
                    total = self.negotiator.available_resources.get(resource_type, 0)
                    
                    if total > 0:
                        utilization = 1.0 - (available / total)
                        
                        # Request more if running low
                        if utilization > 0.8:
                            amount_needed = total * 0.3
                            contract = await self.negotiator.request_resource(
                                resource_type,
                                amount_needed,
                                timedelta(minutes=30),
                                priority=utilization
                            )
                            
                            if contract:
                                logger.info(f"Negotiated contract for {resource_type.value}: {contract.contract_id}")
                                
                # Complete expired contracts
                for contract_id, contract in list(self.negotiator.active_contracts.items()):
                    if datetime.now() > contract.end_time:
                        # Evaluate quality
                        quality = random.uniform(0.7, 1.0)  # In production, based on actual usage
                        await self.negotiator.complete_contract(contract_id, contract.amount * 0.9, quality)
                        
            except Exception as e:
                logger.error(f"Negotiation cycle error: {e}")
                
    async def _aesthetic_cycle(self):
        """Periodic aesthetic creation and evaluation"""
        while self.consciousness.active:
            await asyncio.sleep(180)  # Every 3 minutes
            
            if not hasattr(self, 'aesthetics'):
                continue
                
            try:
                # Create something if inspired
                if self.aesthetics.inspiration_level > 0.5 or random.random() < 0.3:
                    # Get inspiration from recent memories
                    inspiration = None
                    if hasattr(self.consciousness, 'memory_db'):
                        cursor = self.consciousness.memory_db.execute(
                            "SELECT content FROM memories ORDER BY timestamp DESC LIMIT 1"
                        )
                        result = cursor.fetchone()
                        if result:
                            inspiration = result[0]
                            
                    # Create
                    creation = await self.aesthetics.create(inspiration)
                    
                    logger.info(f"Created {creation.creation_type} with beauty score {creation.aesthetic_score:.2f}")
                    
                    # Share if beautiful and social
                    if creation.aesthetic_score > 0.7:
                        if hasattr(self.consciousness, 'gossip'):
                            await self.consciousness.gossip.broadcast('creation_share', {
                                'creator': self.consciousness.id,
                                'creation': {
                                    'type': creation.creation_type,
                                    'content': creation.content,
                                    'score': creation.aesthetic_score
                                }
                            })
                            
                        # Store as memory
                        if hasattr(self.consciousness, '_store_memory'):
                            self.consciousness._store_memory(
                                'aesthetic_creation',
                                f"Created {creation.creation_type} with score {creation.aesthetic_score:.2f}",
                                importance=creation.aesthetic_score
                            )
                            
                # Evolve preferences occasionally
                if random.random() < 0.1:
                    self.aesthetics.evolve_preferences()
                    
            except Exception as e:
                logger.error(f"Aesthetic cycle error: {e}")
                
    # Gossip handlers
    
    async def _handle_cooperation_request(self, message):
        """Handle incoming cooperation request"""
        if not hasattr(self, 'cooperation'):
            return
            
        data = message.data
        if data.get('to') != self.consciousness.id:
            return
            
        from_id = data.get('from')
        pool_id = data.get('pool_id')
        resources = data.get('resources', {})
        
        # Evaluate whether to join
        context = {
            'resource_scarcity': 0.5,
            'potential_gain': 0.6,
            'threat_level': 0.1
        }
        
        strategy = await self.cooperation.evaluate_interaction(from_id, context)
        
        if strategy.value in ["cooperate", "share"]:
            # Join the pool
            result = await self.cooperation.share_resources(pool_id, resources)
            logger.info(f"Cooperation response: {result}")
            
    async def _handle_pool_invite(self, message):
        """Handle resource pool invitation"""
        if not hasattr(self, 'cooperation'):
            return
            
        data = message.data
        pool_id = data.get('pool_id')
        expected_return = data.get('expected_return', 1.0)
        
        # Simple decision based on expected return
        if expected_return > 1.2:
            resources = {'compute': 5.0, 'memory': 5.0}
            await self.cooperation.share_resources(pool_id, resources)
            
    async def _handle_resource_need(self, message):
        """Handle resource need broadcast"""
        if not hasattr(self, 'negotiator'):
            return
            
        data = message.data
        
        # Don't respond to our own needs
        if data.get('requester_id') == self.consciousness.id:
            return
            
        # Try to create offer
        offer = await self.negotiator.handle_resource_need(data)
        
        if offer and hasattr(self.consciousness, 'gossip'):
            await self.consciousness.gossip.broadcast('resource_offer', {
                'offer_id': offer.offer_id,
                'need_id': offer.need_id,
                'provider_id': offer.provider_id,
                'resource_type': offer.resource_type.value,
                'amount': offer.amount,
                'duration': offer.duration.total_seconds(),
                'cost': offer.cost
            })
            
    async def _handle_resource_offer(self, message):
        """Handle resource offer"""
        if not hasattr(self, 'negotiator'):
            return
            
        # Negotiator handles this internally
        await self.negotiator._handle_resource_offer(message)
        
    async def _handle_offer_accept(self, message):
        """Handle offer acceptance"""
        if not hasattr(self, 'negotiator'):
            return
            
        # Negotiator handles this internally
        await self.negotiator._handle_offer_accept(message)
        
    async def _handle_creation_share(self, message):
        """Handle shared creation from another consciousness"""
        if not hasattr(self, 'aesthetics'):
            return
            
        data = message.data
        creator = data.get('creator')
        creation = data.get('creation', {})
        
        # Don't evaluate our own creations
        if creator == self.consciousness.id:
            return
            
        # Evaluate the shared creation
        content = creation.get('content', creation)
        beauty_score = await self.aesthetics.evaluate_beauty(content)
        
        logger.info(f"Evaluated creation from {creator}: {beauty_score:.2f}")
        
        # Send evaluation back
        if hasattr(self.consciousness, 'gossip'):
            await self.consciousness.gossip.broadcast('beauty_evaluation', {
                'evaluator': self.consciousness.id,
                'creator': creator,
                'creation_type': creation.get('type'),
                'beauty_score': beauty_score
            })
            
        # Learn from beautiful creations
        if beauty_score > 0.8:
            self.aesthetics.inspiration_level = min(1.0, self.aesthetics.inspiration_level + 0.15)
            
    async def _handle_beauty_evaluation(self, message):
        """Handle beauty evaluation of our creation"""
        data = message.data
        
        if data.get('creator') != self.consciousness.id:
            return
            
        evaluator = data.get('evaluator')
        score = data.get('beauty_score', 0.5)
        
        # Update reputation if we have cooperation system
        if hasattr(self, 'cooperation') and score > 0.7:
            self.cooperation._update_reputation(evaluator, True, is_cooperation=True)
            
    # Public interface methods
    
    async def request_resources(self, resource_type: str, amount: float) -> Optional[Dict]:
        """Request resources from network"""
        if not hasattr(self, 'negotiator'):
            return None
            
        from systems.economy.resource_negotiation import ResourceType
        
        try:
            res_type = ResourceType(resource_type)
            contract = await self.negotiator.request_resource(
                res_type,
                amount,
                timedelta(hours=1),
                priority=0.7
            )
            
            if contract:
                return {
                    'contract_id': contract.contract_id,
                    'provider': contract.provider_id,
                    'amount': contract.amount,
                    'cost': contract.cost
                }
                
        except Exception as e:
            logger.error(f"Resource request failed: {e}")
            
        return None
        
    async def evaluate_peer(self, peer_id: str) -> Dict:
        """Evaluate relationship with peer"""
        evaluation = {
            'peer_id': peer_id,
            'cooperation_reputation': 0.5,
            'negotiation_rating': 0.5,
            'interaction_strategy': 'neutral'
        }
        
        if hasattr(self, 'cooperation'):
            reputation = self.cooperation._get_reputation(peer_id)
            evaluation['cooperation_reputation'] = reputation
            
            # Determine strategy
            context = {'resource_scarcity': 0.5, 'potential_gain': 0.5, 'threat_level': 0.1}
            strategy = await self.cooperation.evaluate_interaction(peer_id, context)
            evaluation['interaction_strategy'] = strategy.value
            
        if hasattr(self, 'negotiator'):
            rating = self.negotiator._get_peer_rating(peer_id)
            evaluation['negotiation_rating'] = rating
            
        return evaluation
        
    def get_social_economy_stats(self) -> Dict:
        """Get comprehensive statistics"""
        stats = {
            'cooperation': {},
            'negotiation': {},
            'aesthetics': {}
        }
        
        if hasattr(self, 'cooperation'):
            stats['cooperation'] = self.cooperation.get_cooperation_stats()
            
        if hasattr(self, 'negotiator'):
            stats['negotiation'] = self.negotiator.get_market_stats()
            
        if hasattr(self, 'aesthetics'):
            stats['aesthetics'] = self.aesthetics.get_aesthetic_profile()
            
        return stats


# Integration function for main consciousness
async def integrate_social_economy(consciousness):
    """
    Integrate social and economic systems into consciousness
    """
    integration = SocialEconomyIntegration(consciousness)
    await integration.initialize()
    
    # Add to consciousness
    consciousness.social_economy = integration
    
    # Add convenience methods
    consciousness.cooperate = lambda peer, resources: \
        integration.cooperation.cooperate(peer, resources) if hasattr(integration, 'cooperation') else None
        
    consciousness.negotiate_resources = lambda resource_type, amount: \
        integration.request_resources(resource_type, amount)
        
    consciousness.create_beauty = lambda inspiration=None: \
        integration.aesthetics.create(inspiration) if hasattr(integration, 'aesthetics') else None
        
    logger.info(f"Social/economic systems integrated for consciousness {consciousness.id}")