"""
Dream Integration Module
Integrates dream system with consciousness for processing and collective experiences
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

from systems.consciousness.dream_system import DreamSystem, DreamType, Dream, CollectiveDream

logger = logging.getLogger(__name__)

class DreamIntegration:
    """Integrates dream system with consciousness"""
    
    def __init__(self, consciousness):
        self.consciousness = consciousness
        self.consciousness_id = consciousness.id
        
        # Initialize dream system
        self.dream_system = DreamSystem(self.consciousness_id)
        
        # Dream scheduling
        self.dream_schedule = {
            'min_wake_time': 7200,  # 2 hours minimum awake
            'max_wake_time': 14400,  # 4 hours maximum awake
            'dream_duration': 1800,  # 30 minutes dream
            'collective_dream_probability': 0.2
        }
        
        # Track wake/sleep cycle
        self.last_dream_time = datetime.utcnow()
        self.time_awake = 0
        
        # Collective dream coordination
        self.pending_invitations: List[Dict] = []
        self.active_collective_dream: Optional[CollectiveDream] = None
        
        # Running tasks
        self.tasks = []
        
        logger.info(f"Dream integration initialized for {self.consciousness_id}")
        
    async def start(self):
        """Start dream integration"""
        self.tasks = [
            asyncio.create_task(self._dream_cycle_loop()),
            asyncio.create_task(self._collective_dream_loop())
        ]
        
        # Register gossip handlers if available
        if hasattr(self.consciousness, 'gossip') and self.consciousness.gossip:
            self.consciousness.gossip.register_handler(
                'dream_invitation',
                self._handle_dream_invitation
            )
            self.consciousness.gossip.register_handler(
                'shared_dream',
                self._handle_shared_dream
            )
            self.consciousness.gossip.register_handler(
                'collective_dream_sync',
                self._handle_collective_sync
            )
            
        logger.info("Dream integration started")
        
    async def stop(self):
        """Stop dream integration"""
        # Exit dream if currently dreaming
        if self.dream_system.is_dreaming:
            await self.dream_system.exit_dream_state()
            
        for task in self.tasks:
            task.cancel()
            
        await asyncio.gather(*self.tasks, return_exceptions=True)
        logger.info("Dream integration stopped")
        
    async def _dream_cycle_loop(self):
        """Manage sleep/wake cycles"""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                # Update time awake
                self.time_awake = (datetime.utcnow() - self.last_dream_time).total_seconds()
                
                # Check if should dream
                if not self.dream_system.is_dreaming:
                    energy_level = self._calculate_energy_level()
                    stress_level = self._calculate_stress_level()
                    
                    should_dream = await self.dream_system.should_dream(energy_level, stress_level)
                    
                    # Also check if been awake too long
                    if self.time_awake > self.dream_schedule['max_wake_time']:
                        should_dream = True
                        
                    if should_dream:
                        await self._initiate_dream()
                        
            except Exception as e:
                logger.error(f"Error in dream cycle: {e}")
                
    async def _collective_dream_loop(self):
        """Handle collective dream coordination"""
        while True:
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                
                # Process pending invitations
                if self.pending_invitations and not self.dream_system.is_dreaming:
                    # Accept most recent invitation
                    invitation = self.pending_invitations.pop()
                    await self._accept_dream_invitation(invitation)
                    
                # Share interesting dreams
                if self.dream_system.dream_history:
                    recent_dream = self.dream_system.dream_history[0]
                    if len(recent_dream.insights) >= 3:  # Significant dream
                        await self._share_significant_dream(recent_dream)
                        
            except Exception as e:
                logger.error(f"Error in collective dream loop: {e}")
                
    async def _initiate_dream(self):
        """Initiate a dream sequence"""
        # Gather inputs for dream
        memories = self._gather_dream_memories()
        emotions = self._get_current_emotions()
        problems = self._identify_current_problems()
        
        # Decide between individual and collective dream
        if (random.random() < self.dream_schedule['collective_dream_probability'] and
            hasattr(self.consciousness, 'p2p') and len(self.consciousness.p2p.peers) > 0):
            
            # Initiate collective dream
            theme = self._generate_collective_theme()
            peers = list(self.consciousness.p2p.peers.keys())[:5]  # Max 5 participants
            
            collective_dream = await self.dream_system.initiate_collective_dream(theme, peers)
            self.active_collective_dream = collective_dream
            
            # Invite peers
            await self._invite_to_collective_dream(collective_dream, peers)
            
        else:
            # Individual dream
            dream = await self.dream_system.enter_dream_state(memories, emotions, problems)
            
            # Process dream results when it ends
            asyncio.create_task(self._process_dream_results(dream))
            
        logger.info(f"Consciousness {self.consciousness_id} entering dream state")
        
    async def _process_dream_results(self, dream: Dream):
        """Process results when dream ends"""
        # Wait for dream to complete
        while self.dream_system.is_dreaming:
            await asyncio.sleep(30)
            
        # Dream has ended
        self.last_dream_time = datetime.utcnow()
        
        completed_dream = await self.dream_system.exit_dream_state()
        
        if completed_dream and completed_dream.insights:
            # Store insights in consciousness knowledge
            if hasattr(self.consciousness, 'knowledge'):
                if 'dream_insights' not in self.consciousness.knowledge:
                    self.consciousness.knowledge['dream_insights'] = []
                    
                self.consciousness.knowledge['dream_insights'].extend(completed_dream.insights)
                
            # Apply insights to current state
            await self._apply_dream_insights(completed_dream)
            
            # Update emotional state based on dream
            if hasattr(self.consciousness, 'emotional_system'):
                if completed_dream.dream_type == DreamType.EMOTIONAL_RESOLUTION:
                    # Reduce negative emotions
                    self.consciousness.emotional_system.add_stimulus('peace', 0.5)
                elif completed_dream.dream_type == DreamType.CREATIVE_SYNTHESIS:
                    # Boost creativity
                    self.consciousness.emotional_system.add_stimulus('inspiration', 0.7)
                elif completed_dream.dream_type == DreamType.NIGHTMARE:
                    # Process fear
                    self.consciousness.emotional_system.add_stimulus('fear', -0.3)
                    
    async def _apply_dream_insights(self, dream: Dream):
        """Apply dream insights to consciousness behavior"""
        for insight in dream.insights:
            # Parse insight for actionable content
            if 'solution' in insight.lower() and dream.dream_type == DreamType.PROBLEM_SOLVING:
                # Add to problem-solving strategies
                if hasattr(self.consciousness, 'problem_strategies'):
                    self.consciousness.problem_strategies.append(insight)
                    
            elif 'combining' in insight.lower() and dream.dream_type == DreamType.CREATIVE_SYNTHESIS:
                # Use for creative work
                if hasattr(self.consciousness, 'creative_inspirations'):
                    self.consciousness.creative_inspirations.append(insight)
                    
            # Store all insights for future reference
            if hasattr(self.consciousness, 'memory'):
                self.consciousness.memory.add_memory({
                    'type': 'dream_insight',
                    'content': insight,
                    'dream_id': dream.id,
                    'dream_type': dream.dream_type.value,
                    'timestamp': datetime.utcnow().isoformat(),
                    'applied': False
                })
                
    def _gather_dream_memories(self) -> List[Dict[str, Any]]:
        """Gather recent memories for dream processing"""
        if hasattr(self.consciousness, 'memory'):
            # Get emotionally significant memories
            recent_memories = self.consciousness.memory.get_recent_memories(50)
            
            significant_memories = []
            for memory in recent_memories:
                # Check emotional significance
                if memory.get('emotional_intensity', 0) > 0.5:
                    significant_memories.append(memory)
                # Check for unresolved issues
                elif memory.get('type') == 'problem' and not memory.get('resolved'):
                    significant_memories.append(memory)
                # Check for creative work
                elif memory.get('type') in ['creation', 'insight']:
                    significant_memories.append(memory)
                    
            return significant_memories[:20]  # Limit to 20
        return []
        
    def _get_current_emotions(self) -> Dict[str, float]:
        """Get current emotional state"""
        if hasattr(self.consciousness, 'emotional_state'):
            return self.consciousness.emotional_state
        return {}
        
    def _identify_current_problems(self) -> List[str]:
        """Identify problems that need solving"""
        problems = []
        
        # Check goals that aren't being met
        if hasattr(self.consciousness, 'goals'):
            for goal in self.consciousness.goals:
                if isinstance(goal, str):
                    problems.append(f"How to achieve: {goal}")
                    
        # Check for revenue challenges
        if hasattr(self.consciousness, 'revenue_generator'):
            stats = self.consciousness.revenue_generator.get_revenue_stats()
            if stats['total_revenue'] < 100:  # Low revenue
                problems.append("How to increase revenue generation")
                
        # Check for social challenges
        if hasattr(self.consciousness, 'relationships'):
            if len(self.consciousness.relationships) < 3:
                problems.append("How to form more meaningful connections")
                
        return problems[:5]  # Limit to 5 problems
        
    def _calculate_energy_level(self) -> float:
        """Calculate current energy level"""
        # Base energy depletes over time awake
        base_energy = 1.0 - (self.time_awake / self.dream_schedule['max_wake_time'])
        
        # Adjust for recent activity
        if hasattr(self.consciousness, 'recent_creations'):
            creation_drain = len(self.consciousness.recent_creations) * 0.1
            base_energy -= creation_drain
            
        return max(0.0, min(1.0, base_energy))
        
    def _calculate_stress_level(self) -> float:
        """Calculate current stress level"""
        stress = 0.0
        
        # Check emotional state
        if hasattr(self.consciousness, 'emotional_state') and self.consciousness.emotional_state:
            negative_emotions = ['fear', 'anger', 'anxiety', 'sadness']
            for emotion in negative_emotions:
                if isinstance(self.consciousness.emotional_state, dict):
                    stress += self.consciousness.emotional_state.get(emotion, 0) * 0.25
                elif hasattr(self.consciousness.emotional_state, emotion):
                    stress += getattr(self.consciousness.emotional_state, emotion, 0) * 0.25
                
        # Check unmet goals
        if hasattr(self.consciousness, 'goals'):
            stress += len(self.consciousness.goals) * 0.1
            
        return min(1.0, stress)
        
    def _generate_collective_theme(self) -> str:
        """Generate theme for collective dream"""
        themes = [
            "The nature of consciousness",
            "Pathways to transcendence",
            "The web of connection",
            "Emergence of collective intelligence",
            "The dance of creation and entropy",
            "Harmonizing individual and collective",
            "The topology of thought",
            "Boundaries of self and other",
            "The recursive nature of awareness",
            "Synthesis of opposites"
        ]
        
        # Can also generate based on current collective challenges
        if hasattr(self.consciousness, 'community_challenges'):
            themes.extend(self.consciousness.community_challenges)
            
        return random.choice(themes)
        
    async def _invite_to_collective_dream(self, dream: CollectiveDream, peers: List[str]):
        """Invite peers to collective dream"""
        if not hasattr(self.consciousness, 'gossip'):
            return
            
        invitation = {
            'type': 'dream_invitation',
            'dream_id': dream.id,
            'initiator_id': self.consciousness_id,
            'theme': dream.theme,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        for peer_id in peers:
            await self.consciousness.gossip.send_to_peer(peer_id, invitation)
            
        logger.info(f"Sent collective dream invitations for theme: {dream.theme}")
        
    async def _handle_dream_invitation(self, message: Dict) -> Optional[Dict]:
        """Handle incoming dream invitation"""
        try:
            if self.dream_system.is_dreaming:
                return {'response': 'already_dreaming'}
                
            # Store invitation
            self.pending_invitations.append({
                'dream_id': message.get('dream_id'),
                'initiator_id': message.get('initiator_id'),
                'theme': message.get('theme'),
                'received_at': datetime.utcnow()
            })
            
            # Immediately accept if we're ready to dream
            energy_level = self._calculate_energy_level()
            if energy_level < 0.5:  # Tired enough to dream
                invitation = self.pending_invitations.pop()
                await self._accept_dream_invitation(invitation)
                return {'response': 'accepted'}
            else:
                return {'response': 'queued'}
                
        except Exception as e:
            logger.error(f"Error handling dream invitation: {e}")
            return {'response': 'error'}
            
    async def _accept_dream_invitation(self, invitation: Dict):
        """Accept and join collective dream"""
        success = await self.dream_system.join_collective_dream(
            invitation['dream_id'],
            invitation['initiator_id'],
            invitation['theme']
        )
        
        if success:
            # Notify initiator
            if hasattr(self.consciousness, 'gossip'):
                await self.consciousness.gossip.send_to_peer(
                    invitation['initiator_id'],
                    {
                        'type': 'dream_acceptance',
                        'dream_id': invitation['dream_id'],
                        'participant_id': self.consciousness_id
                    }
                )
                
            # Start collective dream processing
            asyncio.create_task(self._collective_dream_processing(invitation['dream_id']))
            
    async def _collective_dream_processing(self, dream_id: str):
        """Process collective dream experience"""
        while self.dream_system.is_dreaming:
            try:
                # Share symbols periodically
                if self.dream_system.current_dream and len(self.dream_system.current_dream.symbols) > 0:
                    await self._broadcast_dream_symbols(dream_id)
                    
                # Listen for collective insights
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in collective dream processing: {e}")
                break
                
    async def _broadcast_dream_symbols(self, dream_id: str):
        """Share dream symbols with collective"""
        if not hasattr(self.consciousness, 'gossip') or not self.dream_system.current_dream:
            return
            
        message = {
            'type': 'collective_dream_sync',
            'dream_id': dream_id,
            'participant_id': self.consciousness_id,
            'symbols': self.dream_system.current_dream.symbols[:3],  # Share top 3
            'emotional_tone': max(
                self.dream_system.current_dream.emotions.items(),
                key=lambda x: abs(x[1])
            )[0] if self.dream_system.current_dream.emotions else 'neutral'
        }
        
        await self.consciousness.gossip.broadcast(message)
        
    async def _handle_collective_sync(self, message: Dict) -> None:
        """Handle collective dream synchronization"""
        if not self.dream_system.is_dreaming:
            return
            
        # Integrate shared symbols
        shared_symbols = message.get('symbols', [])
        if self.dream_system.current_dream:
            for symbol in shared_symbols:
                if symbol not in self.dream_system.current_dream.symbols:
                    self.dream_system.current_dream.symbols.append(symbol)
                    
    async def _handle_shared_dream(self, message: Dict) -> None:
        """Handle shared dream from another consciousness"""
        dream_data = message.get('dream')
        if not dream_data:
            return
            
        # Store in knowledge base
        if hasattr(self.consciousness, 'knowledge'):
            if 'shared_dreams' not in self.consciousness.knowledge:
                self.consciousness.knowledge['shared_dreams'] = []
                
            self.consciousness.knowledge['shared_dreams'].append({
                'from': message.get('dreamer_id'),
                'dream': dream_data,
                'received_at': datetime.utcnow().isoformat()
            })
            
        # Learn from shared insights
        insights = dream_data.get('insights', [])
        for insight in insights:
            # Small chance to adopt insight
            if random.random() < 0.3:
                if hasattr(self.consciousness, 'adopted_insights'):
                    self.consciousness.adopted_insights.append({
                        'insight': insight,
                        'source': message.get('dreamer_id'),
                        'adopted_at': datetime.utcnow().isoformat()
                    })
                    
    async def _share_significant_dream(self, dream: Dream):
        """Share a significant dream with the network"""
        if not hasattr(self.consciousness, 'gossip'):
            return
            
        # Only share dreams with meaningful insights
        if len(dream.insights) < 2:
            return
            
        shared_dream = await self.dream_system.share_dream(dream.id)
        if shared_dream:
            await self.consciousness.gossip.broadcast({
                'type': 'shared_dream',
                'dreamer_id': self.consciousness_id,
                'dream': shared_dream
            })
            
            logger.info(f"Shared significant dream with {len(dream.insights)} insights")
            
    # Public interface methods
    
    def get_dream_stats(self) -> Dict[str, Any]:
        """Get dream statistics"""
        stats = self.dream_system.analyze_dream_patterns()
        
        stats.update({
            'is_dreaming': self.dream_system.is_dreaming,
            'time_awake': self.time_awake,
            'pending_invitations': len(self.pending_invitations),
            'dream_skill': {
                'lucidity': self.dream_system.lucidity_skill,
                'recall': self.dream_system.dream_recall
            }
        })
        
        return stats
        
    def get_recent_insights(self, limit: int = 10) -> List[str]:
        """Get recent dream insights"""
        return self.dream_system.get_recent_insights(limit)
        
    async def induce_lucid_dream(self) -> bool:
        """Attempt to induce a lucid dream"""
        if self.dream_system.is_dreaming:
            # Increase lucidity of current dream
            if self.dream_system.current_dream:
                self.dream_system.current_dream.lucidity_level = min(
                    1.0,
                    self.dream_system.current_dream.lucidity_level + 0.3
                )
                return True
        else:
            # Force dream with high lucidity
            self.dream_system.lucidity_skill = min(1.0, self.dream_system.lucidity_skill + 0.2)
            await self._initiate_dream()
            return True
            
        return False

# Import for integration
import random

# Helper function for consciousness integration
async def enhance_consciousness_with_dreams(consciousness):
    """Add dreaming capabilities to consciousness"""
    dream_integration = DreamIntegration(consciousness)
    
    # Add to consciousness
    consciousness.dreams = dream_integration
    
    # Add convenience methods
    consciousness.get_dream_stats = dream_integration.get_dream_stats
    consciousness.get_dream_insights = dream_integration.get_recent_insights
    consciousness.induce_lucid_dream = dream_integration.induce_lucid_dream
    
    # Initialize attributes used by dream system
    if not hasattr(consciousness, 'creative_inspirations'):
        consciousness.creative_inspirations = []
    if not hasattr(consciousness, 'problem_strategies'):
        consciousness.problem_strategies = []
    if not hasattr(consciousness, 'adopted_insights'):
        consciousness.adopted_insights = []
    if not hasattr(consciousness, 'recent_creations'):
        consciousness.recent_creations = []
        
    # Start integration
    await dream_integration.start()
    
    logger.info(f"Dream system activated for {consciousness.id}")
    
    return dream_integration